import asyncio
import threading
import time

from fastapi import APIRouter, Depends, Body
from starlette.websockets import WebSocket, WebSocketDisconnect

import chatgpt_api

from loguru import logger
from depends import AppState
from tools.wx_helper import wx_tools

router = APIRouter(prefix='/app', tags=['小程序接口'])

get_timeout_reply = AppState('timeout_reply')
get_user_map = AppState('user_map')
get_bot_manager = AppState('bot_manager')

ws_user_manager = {}


@router.post('/ask')
async def ask_chatgpt(
        user_id=Body(..., embed=True),
        ask_message=Body(..., embed=True),
        timeout_reply: chatgpt_api.TimeoutReply = Depends(get_timeout_reply),
        user_map: dict = Depends(get_user_map),
        bot_manager: chatgpt_api.BotManager = Depends(get_bot_manager)
):
    """
    接口请求
    :param user_id:
    :param ask_message:
    :param timeout_reply:
    :param user_map:
    :param bot_manager:
    :return:
    """
    # data = await request.json()
    # user_id, ask_message = recv_msg.user_id, recv_msg.ask_message
    # ask_message = data.get('ask_message')
    logger.info(f'收到消息：[{user_id}] [{ask_message}]')
    assert user_id and ask_message
    create_time = str(time.time())
    conversation_id = user_id + create_time
    user = user_map.get(user_id)
    if not user:
        user = chatgpt_api.User(user_id, bot_manager, timeout_reply)
        user_map[user_id] = user
    task = user.create_task(ask_message, conversation_id)
    while not task.process_finish:
        await asyncio.sleep(0.1)
    return {'data': task.reply}


@router.post('/login')
async def app_login(code=Body(..., embed=True)):
    """
    登录换取code
    :param code:
    :return:
    """
    # data = await request.json()
    # code = data.get('code')
    open_id = await wx_tools.get_we_user_opendid(code)
    return {'data': open_id}


class WsUser:
    def __init__(self, user_id,  bot_manager):
        self.pending = False
        self.bot_manager = bot_manager
        self.user_id = user_id
        self.ask_message = ''
        self.reply_queue = []

    def ask(self, bot, ask_message):
        if self.pending or self.reply_queue:
            logger.info('已存在运行中的任务, 不创建任务')
            return False
        else:
            self.ask_message = ask_message
            threading.Thread(target=self.stream_reply, args=(bot, ask_message)).start()
            return True

    async def send_reply(self, ws: WebSocket):
        backup = []
        if not self.pending and not self.reply_queue:
            return
        try:
            start_send = False
            reply_message = ''
            while True:
                if self.reply_queue:
                    send_data = self.reply_queue.pop(0)
                    backup.append(send_data)
                    if not start_send:
                        logger.info(f'开始回复消息 [{self.user_id}] [{self.ask_message}]')
                        start_send = True
                    await ws.send_json(send_data)
                    reply_message += send_data['data']
                    if send_data['finish']:
                        self.reply_queue = []
                        break
                else:
                    await asyncio.sleep(0.1)
            logger.info(f'全部消息成功发送 [{self.user_id}] [{self.ask_message}] [{reply_message}]')

        except Exception as e:
            logger.error(f'[发送失败] {e}')
            if len(backup):
                logger.warning(f"[回滚所有消息] [{self.ask_message}] [{''.join([item['data'] for item in backup])}]")
                for i in range(len(backup)):
                    self.reply_queue.insert(0, backup[-(1 + i)])
            raise e

    def stream_reply(self, ask_message):
        bot = self.bot_manager.get_bot(self.user_id)
        self.pending = True
        logger.info(f'[线程启动] [{self.user_id}] {ask_message}')
        error = ''
        try:
            for item in bot.ask_stream(ask_message):
                self.reply_queue.append({'data': item, 'finish': False})
        except chatgpt_api.ContextLengthError as e:
            error = str(e)
            self.bot_manager.clear_bot(self.user_id)
            self.reply_queue.append({'data': '[抱歉，对话超过模型支持长度，已重置上下文]', 'finish': False})
        except Exception as e:
            error = str(e)
            self.reply_queue.append({'data': '[抱歉，连接超时，请重新尝试]', 'finish': False})
        self.reply_queue.append({'data': '', 'finish': True})
        logger.warning(f'[线程退出] [{self.user_id}] {ask_message} {error}')
        self.pending = False


@router.websocket('/ws/{user_id}/')
async def websocket_endpoint(user_id: str, websocket: WebSocket):
    await websocket.accept()
    assert user_id
    bot_manager = websocket.app.state.bot_manager
    logger.info(f'[WS连接成功] [{user_id}]')
    user = ws_user_manager.get(user_id)
    if not user:
        user = WsUser(user_id, bot_manager)
        ws_user_manager[user_id] = user
    try:
        asyncio.create_task(user.send_reply(websocket))
        while True:
            ask_message = await websocket.receive_text()
            if not user.ask(ask_message):
                await websocket.send_json({'data': '请等待上一条消息处理完毕后发送', 'finish': False})
                await websocket.send_json({'data': '', 'finish': True})
            await user.send_reply(websocket)
    except WebSocketDisconnect:
        logger.warning(f'[WS断开连接] [{user_id}]')
