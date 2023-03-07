import datetime
import json
import threading

import asyncio
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
        # self.create_time = create_time
        self.bot = bot
        self.user_id = user_id
        self.reply = ''
        self.id = conversation_id
        # self.get_reply_times = 0
        self.already_send = False
        self.process_finish = False
        self.failed_send = False

    def run(self) -> None:
        try:
            reply = self.bot.ask(self.ask_message)
            logger.info(f'task finish {self.ask_message} :: {reply}')
            self.reply = reply
        except Exception as e:
            self.reply = '抱歉，chatGPT繁忙，请尝试重新发送你的问题'
            logger.error(f'请求API失败 {self.ask_message} :: {e}')
        self.process_finish = True

    # async def get_reply(self):
    #     self.get_reply_times += 1
    #     if self.get_reply_times == 3:
    #         # 微信服务器第三次请求 必须返回
    #         for i in range(3):
    #             if self.process_finish:
    #                 self.already_send = True
    #                 logger.info(f'User Ask: {self.ask_message}')
    #                 logger.info(f'chatGPT Reply:{self.reply}')
    #                 break
    #             await asyncio.sleep(1)
    #         self.get_reply_times = 0
    #         return '抱歉，处理时间过长,请发送【重试】尝试获取回复'
    #     else:
    #         wait_time = 0
    #         while not self.process_finish:
    #             if wait_time >= 10:
    #                 logger.info('超过4秒，不响应请求')
    #                 break
    #             await asyncio.sleep(1)
    #             wait_time += 1
    #         if wait_time <= 4:
    #             self.already_send = True
    #             logger.info(f'User Ask: {self.ask_message}')
    #             logger.info(f'chatGPT Reply:{self.reply}')
    #         reply = self.reply
    #         return reply

    #
    #     must_return = True
    # for i in range(10):
    #     # 必须返回
    #     if must_return and i >= wait_time:
    #         self.status = 'finish'
    #         logger.info('第三次请求必须返回')
    #     # 最多等待4秒， 不然就微信接口超时后返回
    #     if self.status == 'finish' and i <= wait_time:
    #         reply = self.reply
    #         # todo
    #         logger.info(f'User Ask: {self.ask_message}')
    #         logger.info(f'chatGPT Reply:{self.reply}')
    #         return reply
    #     await asyncio.sleep(1)
    # logger.info('超过4秒，不响应请求')
    # return self.reply


class User:
    def __init__(self, user_id, bot_manager):
        self.bot_manager = bot_manager
        self.id = user_id
        self.task: Optional[Conversation] = None
        self.msg_request_times = {}

    async def get_reply(self, ask_message, msg_id):
        if ask_message == '重试':
            if self.task and self.task.failed_send:
                msg_id = self.task.id

        self.msg_request_times.setdefault(msg_id, 0)
        self.msg_request_times[msg_id] += 1
        msg_request_times = self.msg_request_times[msg_id]

        self.create_task(ask_message, msg_id)
        if msg_id != self.task.id:
            logger.info(f'跳过处理 {ask_message}')
            del self.msg_request_times[msg_id]
            return '我正在处理上一条消息，请等我回复你以后重新发送。\n如果长时间未返回消息请发送【重试】尝试获取回复'

        wait_time = 0
        while True:
            if wait_time >= 4 and msg_request_times == 3:
                self.msg_request_times[msg_id] = 0
                self.task.failed_send = True
                logger.info(f'处理时间过长 {ask_message}')
                return '处理时间过长，发送【重试】尝试重新获取回复'
            if self.task.process_finish or wait_time >= 10:
                reply = self.task.reply
                if wait_time <= 4:
                    # 成功处理
                    logger.info(f'【清理任务】{ask_message}')
                    del self.msg_request_times[msg_id]
                    self.task = None
                else:
                    logger.info(f'【处理超时，不响应】{ask_message}')
                return reply
            else:
                await asyncio.sleep(1)
            wait_time += 1

    def create_task(self, ask_message, msg_id):
        if self.task and self.task.id == msg_id:
            return False
        bot = self.bot_manager.get_bot(self.id)
        conversation = Conversation(bot, self.id, ask_message, msg_id)
        conversation.start()
        self.task = conversation
        return True


# class ConversationManager:
#     def __init__(self):
#         self.bot_manager = BotManager()
#         self.user_map = {}
#         self.pending_task = {}
#         self.finish_task = {}
#
#     def get_conversation(self, user_id) -> Optional[Conversation]:
#         conversation = self.user_map.get(user_id)
#         if conversation and conversation.already_send:
#             logger.warning('删除对话')
#             del self.user_map[user_id]
#             return None
#         else:
#             return conversation
#
#     def create_conversation(self, user_id, ask_message, create_time, conversation_id):
#         bot = self.bot_manager.get_bot(user_id)
#         conversation = Conversation(bot, user_id, create_time, ask_message, conversation_id)
#         conversation.start()
#         self.user_map[user_id] = conversation
#         return conversation


if __name__ == '__main__':
    test_bot = Chatbot(api_key=chatGPT_KEY, proxy='socks5h://192.168.1.104:10801')
    test_bot.session = requests.Session()
    test_bot.session.proxies = {'http': config.PROXY, 'https': config.PROXY}

    data = test_bot.ask('你好')
    print(data)
