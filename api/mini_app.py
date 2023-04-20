import asyncio
import json
from typing import List

from fastapi import APIRouter, Body
from starlette.requests import Request
from starlette.websockets import WebSocket, WebSocketDisconnect

from loguru import logger

from bot.chatGPT import BotManager
from depends import AppState
from tools.wx_helper import wx_tools

router = APIRouter(prefix='/app', tags=['小程序接口'])

get_timeout_reply = AppState('timeout_reply')
get_user_map = AppState('user_map')
get_bot_manager = AppState('bot_manager')

ws_user_manager = {}


@router.post('/login')
async def app_login(code=Body(..., embed=True)):
    """
    登录换取code
    :param code:
    :return:
    """
    open_id = await wx_tools.get_mini_app_user_opendid(code)
    return {'data': open_id}


@router.post('/release_version')
async def set_version(version: List[str], request: Request):
    """
    设置线上版本
    """
    request.app.state.ban_version = version
    return {'data': request.app.state.ban_version}


@router.websocket('/ws/{user_id}/')
async def websocket_endpoint(user_id: str, websocket: WebSocket):
    await websocket.accept()
    assert user_id
    bot_manager: BotManager = websocket.app.state.bot_manager
    logger.info(f'[WS连接成功] [{user_id}]')
    bot = bot_manager.get_bot(user_id)
    # 如果上次有为发送完的内容 先发送完
    if bot.reply:
        asyncio.create_task(bot.send_reply(websocket))
    try:
        while True:
            ask_message = await websocket.receive_text()
            try:
                json_message = json.loads(ask_message)
                if json_message['op'] == 'ask':
                    ask_message = json_message['data']
                    if json_message['version'] in websocket.app.state.ban_version:
                        await websocket.send_json({'data': ask_message, 'finish': True})
                        continue
            except Exception as e:
                pass
            if bot.reply:
                await websocket.send_json({'data': '请等待上一条消息处理完毕后发送', 'finish': True})
                continue
            else:
                asyncio.create_task(bot.make_reply(ask_message))
                asyncio.create_task(bot.send_reply(websocket))

    except WebSocketDisconnect:
        logger.warning(f'[WS断开连接] [{user_id}]')
