import datetime
import threading

import asyncio
from typing import Dict

import requests
from loguru import logger
from revChatGPT.V3 import Chatbot

import config
from config import chatGPT_KEY


class BotManager:
    def __init__(self):
        self.bot_pool: Dict[str, Chatbot] = {}
        self.bot_last_use_time = {}

    def get_bot(self, user_id) -> Chatbot:
        self.clear_bot()
        bot = self.bot_pool.get(user_id)
        if not bot:
            bot = Chatbot(api_key=chatGPT_KEY)
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


class Conversation:
    def __init__(self, bot, user_id, ask_message):
        self.status = 'pending'
        self.ask_message = ask_message
        self.bot = bot
        self.user_id = user_id
        self.reply = '抱歉，请求超时，请重试'

    def start_generate(self):
        threading.Thread(target=ask_task, args=(self,)).start()


def ask_task(conversation: Conversation):
    reply = conversation.bot.ask(conversation.ask_message)
    conversation.reply = reply
    conversation.status = 'finish'


class MessageControl:
    def __init__(self):
        self.bot_manager = BotManager()
        self.wait_conversation = {}
        self.request_times = {}
        self.pending_user = []

    async def get_reply(self, user_id, ask_message, create_time):
        reply_id = user_id + create_time
        conversation: Conversation = self.wait_conversation.get(reply_id)
        if user_id not in self.pending_user:
            self.pending_user.append(user_id)
        else:
            return '我正在处理上一条消息，请等我回复你以重新发送。'

        if not conversation:
            logger.info('等待处理...')
            # 第一次请求
            # print('第 1 次请求')
            bot = self.bot_manager.get_bot(user_id)
            conversation = Conversation(bot, user_id, ask_message)
            self.wait_conversation[reply_id] = conversation
            self.request_times[reply_id] = 0
            conversation.start_generate()

        self.request_times[reply_id] += 1  # 记录请求数
        if self.request_times[reply_id] <= 2:
            wait_time = 6
        else:
            wait_time = 3
        for i in range(wait_time):
            if conversation.status == 'finish':
                return self.return_and_clear(reply_id)
            else:
                await asyncio.sleep(1)
            # 超过5秒  微信服务器不会接受  变相实现不响应请求
        if wait_time == 6:
            return None

        return self.return_and_clear(reply_id)

    def return_and_clear(self, reply_id):
        # print('处理完成 返回消息')
        conversation = self.wait_conversation[reply_id]
        reply = conversation.reply
        user_id = conversation.user_id
        self.pending_user.remove(user_id)
        del self.wait_conversation[reply_id]
        del self.request_times[reply_id]
        return reply


if __name__ == '__main__':
    test_bot = Chatbot(api_key=chatGPT_KEY, proxy='socks5h://192.168.1.104:10801')
    test_bot.session = requests.Session()
    test_bot.session.proxies = {'http': config.PROXY, 'https': config.PROXY}

    data = test_bot.ask('你好')
    print(data)
