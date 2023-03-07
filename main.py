import uvicorn as uvicorn
from fastapi import FastAPI, Request

from loguru import logger
from starlette.responses import HTMLResponse
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException, InvalidAppIdException
from wechatpy.replies import create_reply
from wechatpy.utils import check_signature
from wechatpy import parse_message

import chatgpt_api
from config import TOKEN, EncodingAESKey, APP_ID

app = FastAPI()


@app.get("/wechat")
async def verify_wechat_server(signature: str, echostr: str, timestamp: str, nonce: str, request: Request):
    try:
        check_signature(TOKEN, signature, timestamp, nonce)
        return HTMLResponse(content=echostr)
    except InvalidSignatureException:
        return "Invalid request"


conversation_manager = chatgpt_api.ConversationManager()


@app.post('/wechat')
async def reply_wechat_message(request: Request):
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
        conversation = conversation_manager.get_conversation(user_id)
        if not conversation:
            conversation = conversation_manager.create_conversation(user_id, ask_message, create_time, conversation_id)
        else:
            if ask_message == '重试' and conversation:
                conversation_id = conversation.id

        if conversation.id != conversation_id:
            reply_text = '我正在处理上一条消息，请等我回复你以后重新发送。\n如果长时间未返回消息请发送【重试】尝试获取回复'
            logger.info(f'跳过处理 {ask_message}')
        else:
            reply_text = await conversation.get_reply()

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


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)
