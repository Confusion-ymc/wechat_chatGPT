import asyncio
import hashlib

import config
from tools.my_requests import aio_request


class WXHelper:
    def __init__(self, h5_app_id=None, h5_secret=None, we_app_id=None, we_secret=None, app_token=''):
        self.h5_app_id = h5_app_id
        self.h5_secret = h5_secret
        self.we_app_id = we_app_id
        self.we_secret = we_secret
        self.app_token = app_token
        self.access_token = {}

    async def get_user_access_token(self, code):
        url = f'https://api.weixin.qq.com/sns/oauth2/access_token?appid={self.h5_app_id}&secret={self.h5_secret}&code={code}&grant_type=authorization_code'
        res = await aio_request(url, method='POST')
        return res

    async def get_we_user_opendid(self, code):
        url = f"https://api.weixin.qq.com/sns/jscode2session?appid={self.we_app_id}&secret={self.we_secret}&js_code={code}&grant_type=authorization_code"
        res = await aio_request(url, method="POST")
        return res['openid']

    async def get_we_user_info(self, code):
        try:
            openid = await self.get_we_user_opendid(code)
            return openid
        except Exception as e:
            raise Exception(f'获取微信用户信息失败 {e}')

    async def get_user_info(self, code: str):
        res = None
        auth_info = None
        try:
            auth_info = await self.get_user_access_token(code)
            url = f'https://api.weixin.qq.com/sns/userinfo?access_token={auth_info["access_token"]}&openid={auth_info["openid"]}&lang=zh_CN'
            res = await aio_request(url)
            return res
        except Exception as e:
            raise Exception(f'获取微信用户信息失败 {e} auth_info:{auth_info} res:{res}')

    def check_signature(self, signature, timestamp, nonce):
        if not signature or not timestamp or not nonce:
            return False
        tmp_str = "".join(sorted([self.app_token, timestamp, nonce]))
        tmp_str = hashlib.sha1(tmp_str.encode('UTF-8')).hexdigest()
        if tmp_str == signature:
            return True
        else:
            return False


wx_tools = WXHelper(
    we_app_id=config.we_app_id,
    we_secret=config.we_secret,
    app_token=config.app_token
)

# wx_tools = WXHelper(appid='wx79041d8625ec9aa8', secret='c0021e35348e6b177ecaccda8b816ed4', token='ymc4399')

if __name__ == '__main__':
    # auth_url = f'https://open.weixin.qq.com/connect/oauth2/authorize?appid={wx_tools.appid}&redirect_uri={settings.redirect_url}&response_type=code&scope=snsapi_userinfo#wechat_redirect'
    # image_data = make_code(auth_url, 300, 300)  # 二维码大小
    # image_data.save('123.png')
    asyncio.run(wx_tools.get_we_user_opendid('083UMqFa135S5D0wppJa1n5giw1UMqFL'))
