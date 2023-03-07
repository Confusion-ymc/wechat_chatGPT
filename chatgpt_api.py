import datetime
import json
import threading

import asyncio
import time
import uuid
from typing import Dict, Optional

import requests
from loguru import logger
from revChatGPT.V3 import Chatbot

import config
from config import chatGPT_KEY


class MyBot(Chatbot):
    def __init__(self, *args, **kwargs):
        super(MyBot, self).__init__(*args, **kwargs)

    def ask_stream(self, prompt: str, role: str = "user", **kwargs) -> str:
        """
        Ask a question
        """
        api_key = kwargs.get("api_key")
        self.__add_to_conversation(prompt, role)
        # Get response
        response = self.session.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + (api_key or self.api_key)},
            timeout=120,
            json={
                "model": self.engine,
                "messages": self.conversation,
                "stream": True,
                # kwargs
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1),
                "n": kwargs.get("n", 1),
                "user": kwargs.get("user", "user"),
            },
            stream=True,
        )
        if response.status_code != 200:
            raise Exception(
                f"Error: {response.status_code} {response.reason} {response.text}",
            )
        response_role: Optional[str] = None
        full_response: str = ""
        for line in response.iter_lines():
            if not line:
                continue
            # Remove "data: "
            line = line.decode("utf-8")[6:]
            if line == "[DONE]":
                break
            resp: dict = json.loads(line)
            choices = resp.get("choices")
            if not choices:
                continue
            delta = choices[0].get("delta")
            if not delta:
                continue
            if "role" in delta:
                response_role = delta["role"]
            if "content" in delta:
                content = delta["content"]
                full_response += content
                yield content
        self.__add_to_conversation(full_response, response_role)

    def __add_to_conversation(self, message: str, role: str):
        """
        Add a message to the conversation
        """
        self.conversation.append({"role": role, "content": message})


class BotManager:
    def __init__(self):
        self.bot_pool: Dict[str, MyBot] = {}
        self.bot_last_use_time = {}

    def get_bot(self, user_id) -> MyBot:
        self.clear_bot()
        bot = self.bot_pool.get(user_id)
        if not bot:
            bot = MyBot(api_key=chatGPT_KEY)
            # 配置代理
            if config.PROXY:
                bot.session = requests.Session()
                bot.session.proxies = {'http': config.PROXY, 'https': config.PROXY}
            self.bot_pool[user_id] = bot
        self.bot_last_use_time[user_id] = datetime.datetime.now()
        return bot

    def clear_bot(self):
        copy_last_use_time = self.bot_last_use_time.copy()
        for user_id, use_time in copy_last_use_time.items():
            if (datetime.datetime.now() - use_time) > datetime.timedelta(hours=1):
                del self.bot_last_use_time[user_id]
                del self.bot_pool[user_id]


class Conversation(threading.Thread):
    def __init__(self, bot, user_id, ask_message, conversation_id):
        super(Conversation, self).__init__()
        self.daemon = True
        self.ask_message = ask_message
        self.bot = bot
        self.user_id = user_id
        self.reply = ''
        self.id = conversation_id
        self.timeout_send = False
        self.process_finish = False

    def run(self) -> None:
        try:
            reply = self.bot.ask(self.ask_message)
            logger.info(f'task finish {self.ask_message} :: {reply}')
            self.reply = reply
        except Exception as e:
            self.reply = '抱歉，chatGPT繁忙，请尝试重新发送你的问题'
            logger.error(f'请求API失败 {self.ask_message} :: {e}')
        print(f'内容长度 {len(self.reply)}')
        self.process_finish = True


class TimeoutReply(threading.Thread):
    def __init__(self):
        super().__init__()
        self.reply_task: Dict[str, Conversation] = {}
        self.add_time = {}

    def add_task(self, task: Conversation):
        task.timeout_send = True
        task_id = uuid.uuid1().__str__()
        self.reply_task[task_id] = task
        self.add_time[task_id] = time.time()
        return task_id

    def get_reply(self, task_id):
        task = self.reply_task.get(task_id)
        if task:
            if task.process_finish:
                return task.ask_message, task.reply
            else:
                return task.ask_message, '处理中...'
        else:
            return None, None

    def run(self):
        while True:
            task_list = list(self.reply_task)
            for task_id in task_list:
                if time.time() - self.add_time[task_id] > 60 * 60:
                    del self.add_time[task_id]
                    del self.reply_task[task_id]
            time.sleep(60)


class User:
    def __init__(self, user_id, bot_manager, timeout_reply: TimeoutReply):
        self.bot_manager = bot_manager
        self.timeout_reply = timeout_reply
        self.id = user_id
        self.task: Optional[Conversation] = None
        self.msg_request_times = {}

    async def get_reply(self, ask_message, msg_id):
        self.msg_request_times.setdefault(msg_id, 0)
        self.msg_request_times[msg_id] += 1
        msg_request_times = self.msg_request_times[msg_id]

        if not self.task:
            self.create_task(ask_message, msg_id)
        else:
            if self.task.timeout_send and self.task.process_finish:
                self.create_task(ask_message, msg_id)
        if msg_id != self.task.id:
            logger.info(f'跳过处理 {ask_message}')
            del self.msg_request_times[msg_id]
            return '我正在处理上一条消息，请等我回复你以后重新发送。'

        wait_time = 0
        while True:
            if wait_time >= 3 and msg_request_times == 3:
                timeout_msg_id = self.timeout_reply.add_task(self.task)
                del self.msg_request_times[msg_id]
                logger.info(f'处理时间过长，通过网页查看 \n https://64g8573f7.zicp.fun/reply?msg_id={timeout_msg_id}')
                return f'处理时间过长，请点击下方连接查看\nhttps://64g8573f7.zicp.fun/reply?msg_id={timeout_msg_id}'
            if not self.task:
                logger.info(f'【消息已处理】{ask_message}')
                return
            if self.task.process_finish or wait_time >= 10:
                reply = self.task.reply
                if wait_time <= 4:
                    if len(reply) >= 800:
                        timeout_msg_id = self.timeout_reply.add_task(self.task)
                        del self.msg_request_times[msg_id]
                        return f'内容长度超过限制，请点击下方连接查看\nhttps://64g8573f7.zicp.fun/reply?msg_id={timeout_msg_id}'
                    # 成功处理
                    logger.info(f'【清理任务】{ask_message}')
                    del self.msg_request_times[msg_id]
                    self.task = None
                else:
                    logger.info(f'【处理超时，不响应】{msg_request_times} {ask_message}')
                return reply
            else:
                await asyncio.sleep(1)
            wait_time += 1

    def create_task(self, ask_message, msg_id):
        bot = self.bot_manager.get_bot(self.id)
        conversation = Conversation(bot, self.id, ask_message, msg_id)
        conversation.start()
        self.task = conversation
        return True


if __name__ == '__main__':
    test_bot = Chatbot(api_key=chatGPT_KEY, proxy='socks5h://192.168.1.104:10801')
    test_bot.session = requests.Session()
    test_bot.session.proxies = {'http': config.PROXY, 'https': config.PROXY}

    data = test_bot.ask('你好')
    print(data)
