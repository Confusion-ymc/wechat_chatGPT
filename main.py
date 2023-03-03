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


message_control = chatgpt_api.MessageControl()


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
    logger.info(f'收到消息：{msg.type}')
    if msg.type == 'text':
        user_id, ask_message, create_time = msg.source, msg.content, str(msg.create_time.timestamp())
        reply_text = await message_control.get_reply(user_id, ask_message, create_time)
        if reply_text:
            logger.info(f'User Ask: {msg.content}')
            logger.info(f'chatGPT Reply:{reply_text}')
        reply = create_reply(reply_text, msg)
    else:
        reply = create_reply('对不起，我现在只能处理文字消息', msg)
    return HTMLResponse(content=crypto.encrypt_message(
        reply.render(),
        nonce,
        timestamp
    ))


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)
