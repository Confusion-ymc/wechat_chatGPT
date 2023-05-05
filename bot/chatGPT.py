import asyncio
import datetime
import time
import traceback
import uuid

from typing import Dict

from loguru import logger
from revChatGPT.V3 import Chatbot

from configs import config


class TimeoutReplyManger:
    def __init__(self):
        self.reply = {}
        self.add_time_map = {}

    def clear_task(self):
        delete_k = []
        for k, add_time in self.add_time_map.items():
            if time.time() - add_time > 60 * 60:
                delete_k.append(k)
        for k in delete_k:
            del self.reply[k]
            del self.add_time_map[k]


class TimeoutReply:
    def __init__(self, bot, ask_message):
        self.id = uuid.uuid1().__str__()
        self.bot = bot
        self.ask_message = ask_message
        self.text = '处理中...'

    def wait_finish(self):
        for i in range(100):
            self.text = self.bot.reply.text
            if self.bot.reply.finish:
                break
            else:
                time.sleep(1)
        self.text = self.bot.reply.text
        self.bot.reply = None


class Reply:
    def __init__(self, ask_message):
        self.ask_message = ask_message
        self.text = ''
        self.finish = False

    @property
    def text_len(self):
        return len(self.text)


class MyBot(Chatbot):
    def __init__(self, *args, **kwargs):
        self.conversation_id = kwargs.pop('conversation_id', None)
        super(MyBot, self).__init__(*args, **kwargs)
        self.timeout = 120
        self.reply = None

    async def send_reply(self, websocket):
        send_index = 0
        while True:
            try:
                await websocket.send_json({'data': self.reply.text[send_index], 'finish': False})
                send_index += 1
            except IndexError:
                if self.reply.finish and send_index >= self.reply.text_len:
                    await websocket.send_json({'data': '', 'finish': True})
                    self.reply = None
                    return
            await asyncio.sleep(0.05)  # 控制速度

    async def get_reply_text(self, timeout):
        for i in range(timeout):
            if self.reply and self.reply.finish:
                text = self.reply.text
                self.reply = None
                return text
            await asyncio.sleep(1)
        raise Exception(f'reply timeout, {timeout}')

    async def make_reply(self, ask_message):
        logger.info(f'[线程启动] [{self.conversation_id}] {ask_message}')
        error = ''
        self.reply = Reply(ask_message)
        try:
            async for content in self.ask_stream_async(ask_message):
                self.reply.text += content
        except Exception as e:
            error = str(e)
            logger.error(traceback.format_exc())
            self.reply.text += '\n[抱歉, 接口异常, 请重试]'
        finally:
            self.reply.finish = True
        logger.warning(f'[线程退出] {ask_message} {error}')


class BotManager:
    def __init__(self):
        self.bot_pool: Dict[str, MyBot] = {}
        self.bot_last_use_time = {}

    def get_bot(self, conversation_id) -> MyBot:
        self.clear_bot()
        bot = self.bot_pool.get(conversation_id)
        if not bot:
            bot = MyBot(api_key=config.CHATGPT_KEY, proxy=config.PROXY, conversation_id=conversation_id)
            self.bot_pool[conversation_id] = bot
        self.bot_last_use_time[conversation_id] = datetime.datetime.now()
        return bot

    def clear_bot(self, conversation_id=None):
        if conversation_id:
            del self.bot_last_use_time[conversation_id]
            del self.bot_pool[conversation_id]
            return
        copy_last_use_time = self.bot_last_use_time.copy()
        for conversation_id, use_time in copy_last_use_time.items():
            if (datetime.datetime.now() - use_time) > datetime.timedelta(hours=1):
                del self.bot_last_use_time[conversation_id]
                del self.bot_pool[conversation_id]


retry_request_count = {}
timeout_reply_mgr = TimeoutReplyManger()
