import asyncio
import time

from fastapi import Request, APIRouter, Depends
from fastapi import BackgroundTasks
from starlette.templating import Jinja2Templates

from bot import chatGPT

from loguru import logger
from starlette.responses import HTMLResponse
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException, InvalidAppIdException
from wechatpy.replies import create_reply
from wechatpy.utils import check_signature
from wechatpy import parse_message

import config
from bot.chatGPT import TimeoutReply, timeout_reply_mgr, retry_request_count
from depends import AppState

router = APIRouter(tags=['公众号接口'])

get_user_map = AppState('user_map')
get_bot_manager = AppState('bot_manager')
templates = Jinja2Templates(directory="templates")


@router.get("/wechat/reply")
async def get_pending_reply(msg_id, request: Request):
    """
    超时回复 查询接口
    :param request:
    :param msg_id:
    :return:
    """
    timeout_reply: TimeoutReply = timeout_reply_mgr.reply.get(msg_id)
    if not timeout_reply:
        return templates.TemplateResponse("timeoutReply.html", {"request": request,
                                                                "ask_message": '没有找到数据 或 已过期',
                                                                "reply": ''})
    return templates.TemplateResponse("timeoutReply.html", {"request": request,
                                                            "ask_message": timeout_reply.ask_message,
                                                            "reply": timeout_reply.text})


@router.get("/wechat")
async def verify_wechat_server(signature: str, echostr: str, timestamp: str, nonce: str):
    """
    微信服务器验证接口
    :param signature:
    :param echostr:
    :param timestamp:
    :param nonce:
    :return:
    """
    try:
        check_signature(config.Token, signature, timestamp, nonce)
        return HTMLResponse(content=echostr)
    except InvalidSignatureException:
        return "Invalid request"


def make_response(reply_text, msg, crypto, nonce, timestamp):
    return HTMLResponse(content=crypto.encrypt_message(
        create_reply(reply_text, msg).render(),
        nonce,
        timestamp
    ))


@router.post('/wechat')
async def reply_wechat_message(
        request: Request,
        background_task: BackgroundTasks,
        bot_manager: chatGPT.BotManager = Depends(get_bot_manager),
):
    data = await request.body()
    xml_data = data.decode("utf-8")
    nonce = request.query_params.get('nonce')
    timestamp = request.query_params.get('timestamp')
    crypto = WeChatCrypto(config.Token, config.EncodingAESKey, config.AppID)

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
        bot = bot_manager.get_bot(user_id + '_acc')
        msg_id = user_id + create_time

        if bot.reply and msg_id not in retry_request_count:
            # 如果存在处理的任务  且不是微信重试的消息则直接回复
            return make_response('我正在处理上一条消息，请等我回复你以后重新发送。', msg, crypto, nonce, timestamp)
        else:
            # 统计微信服务器重试次数
            retry_request_count.setdefault(msg_id, 0)
            retry_request_count[msg_id] += 1

            if retry_request_count[msg_id] == 1:
                # 创建任务
                asyncio.create_task(bot.make_reply(ask_message))
            # 如果最后一次请求  必须回复  否则会显示公众号故障  所以提供查询结果的连接
            if retry_request_count[msg_id] >= 3:
                timeout_reply = TimeoutReply(bot, ask_message)
                background_task.add_task(timeout_reply.wait_finish)

                timeout_reply_mgr.reply[timeout_reply.id] = timeout_reply
                timeout_reply_mgr.add_time_map[timeout_reply.id] = time.time()
                timeout_reply_mgr.clear_task()

                logger.info(f'处理时间过长，通过网页查看\n{config.URL or "[未配置] "}/reply?msg_id={timeout_reply.id}')
                reply_text = f'处理时间过长，请点击下方连接查看\n{config.URL or "[未配置] "}/reply?msg_id={timeout_reply.id}'
                del retry_request_count[msg_id]
                return make_response(reply_text, msg, crypto, nonce, timestamp)
            else:
                reply_text = await bot.get_reply_text(timeout=3)
                del retry_request_count[msg_id]
        return make_response(reply_text, msg, crypto, nonce, timestamp)

    elif msg.type == 'event' and msg.event == 'subscribe':
        reply_text = '感谢你的关注，我将为你提供chatGPT的体验服务'
        return make_response(reply_text, msg, crypto, nonce, timestamp)
    else:
        reply_text = '对不起，我现在只能处理文字消息'
    return make_response(reply_text, msg, crypto, nonce, timestamp)
