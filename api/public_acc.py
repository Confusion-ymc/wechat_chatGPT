from fastapi import Request, APIRouter, Depends
import chatgpt_api

from loguru import logger
from starlette.responses import HTMLResponse
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException, InvalidAppIdException
from wechatpy.replies import create_reply
from wechatpy.utils import check_signature
from wechatpy import parse_message

from config import TOKEN, EncodingAESKey, APP_ID
from depends import AppState

router = APIRouter()

get_timeout_reply = AppState('timeout_reply')
get_user_map = AppState('user_map')
get_bot_manager = AppState('bot_manager')


@router.get("/wechat")
async def verify_wechat_server(signature: str, echostr: str, timestamp: str, nonce: str):
    try:
        check_signature(TOKEN, signature, timestamp, nonce)
        return HTMLResponse(content=echostr)
    except InvalidSignatureException:
        return "Invalid request"


@router.get("/reply")
async def get_pending_reply(msg_id, timeout_reply: chatgpt_api.TimeoutReply = Depends(get_timeout_reply)):
    ask_message, reply = timeout_reply.get_reply(msg_id)
    if ask_message is None:
        return HTMLResponse(
            content=f'<html><head><title>Hello橙同学</title></head><pre>没有找到数据 或 已过期</pre></html>')
    return HTMLResponse(
        content=f'<html><head><title>Hello橙同学</title></head><pre>你:\n{ask_message}\nchatGPT:\n{reply}</pre></html>')


@router.post('/wechat')
async def reply_wechat_message(request: Request,
                               timeout_reply: chatgpt_api.TimeoutReply = Depends(get_timeout_reply),
                               user_map: dict = Depends(get_user_map),
                               bot_manager: chatgpt_api.BotManager = Depends(get_bot_manager)
                               ):
    data = await request.body()
    xml_data = data.decode("utf-8")
    nonce = request.query_params.get('nonce')
    timestamp = request.query_params.get('timestamp')
    crypto = WeChatCrypto(TOKEN, EncodingAESKey, APP_ID)

    try:
        msg = crypto.decrypt_message(
            xml_data,
            request.query_params.get('msg_signature'),
            timestamp,
            nonce
        )
    except (InvalidAppIdException, InvalidSignatureException):
        # 处理异常或忽略
        return
    msg = parse_message(msg)
    if msg.type == 'text':
        logger.info(f'收到消息：[{msg.type}] {msg.content}')
        user_id, ask_message, create_time = msg.source, msg.content, str(msg.create_time.timestamp())
        conversation_id = user_id + create_time
        user = user_map.get(user_id)
        if not user:
            user = chatgpt_api.User(user_id, bot_manager, timeout_reply)
            user_map[user_id] = user
        reply_text = await user.get_reply(ask_message, conversation_id)

        reply = create_reply(reply_text, msg)
    elif msg.type == 'event' and msg.event == 'subscribe':
        reply = create_reply('感谢你的关注，我将为你提供chatGPT的体验服务', msg)
    else:
        reply = create_reply('对不起，我现在只能处理文字消息', msg)
    return HTMLResponse(content=crypto.encrypt_message(
        reply.render(),
        nonce,
        timestamp
    ))
