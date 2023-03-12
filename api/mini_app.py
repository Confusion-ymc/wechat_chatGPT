import asyncio
import time

from fastapi import Request, APIRouter, Depends, Body, Query
import chatgpt_api

from loguru import logger
from starlette.responses import HTMLResponse
from wechatpy.exceptions import InvalidSignatureException
from wechatpy.utils import check_signature

from config import TOKEN, EncodingAESKey, APP_ID
from depends import AppState
from tools.wx_helper import wx_tools

router = APIRouter(prefix='/app')

get_timeout_reply = AppState('timeout_reply')
get_user_map = AppState('user_map')
get_bot_manager = AppState('bot_manager')


@router.get("/wechat")
async def verify_wechat_server2(signature: str, echostr: str, timestamp: str, nonce: str):
    try:
        check_signature(TOKEN, signature, timestamp, nonce)
        return HTMLResponse(content=echostr)
    except InvalidSignatureException:
        return "Invalid request"


@router.get("/reply")
async def get_timeout_reply2(msg_id, timeout_reply: chatgpt_api.TimeoutReply = Depends(get_timeout_reply)):
    ask_message, reply = timeout_reply.get_reply(msg_id)
    if ask_message is None:
        return HTMLResponse(
            content=f'<html><head><title>Hello橙同学</title></head><pre>没有找到数据 或 已过期</pre></html>')
    return HTMLResponse(
        content=f'<html><head><title>Hello橙同学</title></head><pre>你:\n{ask_message}\nchatGPT:\n{reply}</pre></html>')


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
    logger.info(f'收到消息：[{ask_message}]')
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
async def ask_chatgpt(request: Request):
    data = await request.json()
    code = data.get('code')
    open_id = await wx_tools.get_we_user_opendid(code)
    return {'data': open_id}
