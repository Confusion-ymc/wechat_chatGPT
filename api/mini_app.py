import asyncio
import threading
import time

from fastapi import Request, APIRouter, Depends
from starlette.websockets import WebSocket, WebSocketDisconnect

import chatgpt_api

from loguru import logger
from depends import AppState
from tools.wx_helper import wx_tools

router = APIRouter(prefix='/app')

get_timeout_reply = AppState('timeout_reply')
get_user_map = AppState('user_map')
get_bot_manager = AppState('bot_manager')


@router.post('/ask')
async def ask_chatgpt(
        request: Request,
        timeout_reply: chatgpt_api.TimeoutReply = Depends(get_timeout_reply),
        user_map: dict = Depends(get_user_map),
        bot_manager: chatgpt_api.BotManager = Depends(get_bot_manager)
):
    data = await request.json()
    user_id = data.get('user_id')
    ask_message = data.get('ask_message')
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
async def app_login(request: Request):
    data = await request.json()
    code = data.get('code')
    open_id = await wx_tools.get_we_user_opendid(code)
    return {'data': open_id}


def stream_reply(reply_queue, bot, ask_message):
    logger.info(f'[线程启动] {ask_message}')
    error = ''
    try:
        for item in bot.ask_stream(ask_message):
            reply_queue.put_nowait({'data': item, 'finish': False})
    except Exception as e:
        error = str(e)
        reply_queue.put_nowait({'data': '[抱歉，连接超时，请重新尝试]', 'finish': False})
    reply_queue.put_nowait({'data': {}, 'finish': True})
    logger.info(f'[线程退出] {ask_message} {error}')


@router.websocket('/ws/{user_id}/')
async def websocket_endpoint(user_id: str, websocket: WebSocket):
    await websocket.accept()
    assert user_id
    user_map = websocket.app.state.user_map
    timeout_reply = websocket.app.state.timeout_reply
    bot_manager = websocket.app.state.bot_manager
    logger.info(f'WS连接成功 [{user_id}]')
    user = user_map.get(user_id)
    if not user:
        user = chatgpt_api.User(user_id, bot_manager, timeout_reply)
        user_map[user_id] = user
    bot = user.get_bot()
    try:
        while True:
            ask_message = await websocket.receive_text()
            reply_message = ''
            reply_queue = asyncio.Queue()
            t = threading.Thread(target=stream_reply, args=(reply_queue, bot, ask_message), daemon=True)
            t.start()
            while True:
                send_data = await reply_queue.get()
                await websocket.send_json(send_data)
                if send_data['finish']:
                    break
                reply_message += send_data['data']
            logger.info(f'[回复完毕] [{ask_message}] [{reply_message}]')
    except WebSocketDisconnect:
        logger.info(f'WS断开连接 [{user_id}]')

