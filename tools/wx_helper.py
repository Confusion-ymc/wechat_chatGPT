import asyncio

import config
from tools.my_requests import aio_request


async def get_mini_app_user_opendid(code):
    res = {}
    try:
        url = f"https://api.weixin.qq.com/sns/jscode2session?appid={config.MINI_APP_ID}&secret={config.MINI_SECRET}&js_code={code}&grant_type=authorization_code"
        res = await aio_request(url, method="POST")
        return res['openid']
    except Exception as e:
        raise Exception(f'获取微信用户信息失败 {e} {res}')


if __name__ == '__main__':
    asyncio.run(get_mini_app_user_opendid('083UMqFa135S5D0wppJa1n5giw1UMqFL'))
