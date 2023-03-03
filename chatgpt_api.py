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
            timeout=30,
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
    def __init__(self, bot, user_id, create_time, ask_message, conversation_id):
        super(Conversation, self).__init__()
        self.daemon = True
        self.status = 'pending'
        self.ask_message = ask_message
        self.create_time = create_time
        self.bot = bot
        self.user_id = user_id
        self.reply = '抱歉，请求超时，请重试'
        self.id = conversation_id
        self.get_reply_times = 0
        self.already_send = False

    def run(self) -> None:
        reply = self.bot.ask(self.ask_message)
        self.reply = reply
        self.status = 'finish'

    async def get_reply(self):
        must_return = False
        self.get_reply_times += 1
        if self.get_reply_times == 3:
            # 微信服务器第三次请求 必须返回
            must_return = True
        for i in range(10):
            # 必须返回
            if must_return and i >= 4:
                self.status = 'finish'
            # 最多等待4秒， 不然就微信接口超时后返回
            if self.status == 'finish' and i < 4:
                reply = self.reply
                self.already_send = True
                logger.info(f'User Ask: {self.ask_message}')
                logger.info(f'chatGPT Reply:{self.reply}')
                return reply
            await asyncio.sleep(1)
        logger.info('超过4秒，不响应请求')
        return self.reply


# def ask_task(conversation: Conversation):
#     reply = conversation.bot.ask(conversation.ask_message)
#     conversation.reply = reply
#     conversation.status = 'finish'


class ConversationManager:
    def __init__(self):
        self.bot_manager = BotManager()
        self.user_map = {}

    def get_conversation(self, user_id) -> Optional[Conversation]:
        conversation = self.user_map.get(user_id)
        if conversation.already_send:
            del self.user_map[user_id]
            return None
        else:
            return conversation

    def create_conversation(self, user_id, ask_message, create_time, conversation_id):
        bot = self.bot_manager.get_bot(user_id)
        conversation = Conversation(bot, user_id, create_time, ask_message, conversation_id)
        conversation.start()
        self.user_map[user_id] = conversation


# class MessageControl:
#     def __init__(self):
#         self.bot_manager = BotManager()
#         self.pending_conversation = {}
#         self.pending_user = []
#         self.request_times = {}
#
#     async def get_reply(self, user_id, ask_message, create_time):
#         reply_id = user_id + create_time
#         conversation: Conversation = self.pending_conversation.get(reply_id)
#         if not conversation:  # 有不同的消息进来
#             if user_id in self.pending_user:
#                 return '我正在处理上一条消息，请等我回复你以后重新发送。'
#
#             self.pending_user.append(user_id)
#             logger.info('等待处理...')
#             # 第一次请求
#             # print('第 1 次请求')
#             bot = self.bot_manager.get_bot(user_id)
#             conversation = Conversation(bot, user_id, ask_message)
#             self.pending_conversation[reply_id] = conversation
#             self.request_times[reply_id] = 0
#             conversation.start_generate()
#
#         self.request_times[reply_id] += 1  # 记录请求数
#         if self.request_times[reply_id] <= 2:
#             wait_time = 6
#         else:
#             wait_time = 3
#         for i in range(wait_time):
#             if conversation.status == 'finish':
#                 return self.return_and_clear(reply_id)
#             else:
#                 await asyncio.sleep(1)
#             # 超过5秒  微信服务器不会接受  变相实现不响应请求
#         if wait_time == 6:
#             return None
#
#         return self.return_and_clear(reply_id)
#
#     def return_and_clear(self, reply_id):
#         # print('处理完成 返回消息')
#         try:
#             conversation = self.pending_conversation[reply_id]
#             reply = conversation.reply
#             user_id = conversation.user_id
#             self.pending_user.remove(user_id)
#             del self.pending_conversation[reply_id]
#             del self.request_times[reply_id]
#             return reply
#         except Exception as e:
#             logger.warning('消息已处理')
#             return '消息已处理'


if __name__ == '__main__':
    test_bot = Chatbot(api_key=chatGPT_KEY, proxy='socks5h://192.168.1.104:10801')
    test_bot.session = requests.Session()
    test_bot.session.proxies = {'http': config.PROXY, 'https': config.PROXY}

    data = test_bot.ask('你好')
    print(data)
