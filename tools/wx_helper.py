import asyncio
import hashlib
import time

import config
from tools.my_requests import aio_request


class WXHelper:
    def __init__(self, pub_app_id=None, pub_app_secret=None, we_app_id=None, we_secret=None, app_token=''):
        self.pub_app_id = pub_app_id
        self.pub_app_secret = pub_app_secret
        self.we_app_id = we_app_id
        self.we_secret = we_secret
        self.app_token = app_token
        self.access_token = {}
        self._pub_admin_access_token = None

    async def get_user_access_token(self, code):
        url = f'https://api.weixin.qq.com/sns/oauth2/access_token?appid={self.pub_app_id}&secret={self.pub_app_secret}&code={code}&grant_type=authorization_code'
        res = await aio_request(url, method='POST')
        return res

    async def get_we_user_opendid(self, code):
        try:
            url = f"https://api.weixin.qq.com/sns/jscode2session?appid={self.we_app_id}&secret={self.we_secret}&js_code={code}&grant_type=authorization_code"
            res = await aio_request(url, method="POST")
            return res['openid']
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

    async def get_admin_pub_access_token(self):
        if not self._pub_admin_access_token or self._pub_admin_access_token['expires_in'] < time.time():
            url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.pub_app_id}&secret={self.pub_app_secret}'
            json_res = await aio_request(url, method="GET")
            json_res['expires_in'] += time.time()
            self._pub_admin_access_token = json_res
        return self._pub_admin_access_token['access_token']


wx_tools = WXHelper(
    pub_app_id=config.pub_app_id,
    pub_app_secret=config.pub_app_secret,
    we_app_id=config.we_app_id,
    we_secret=config.we_secret,
    app_token=config.app_token
)

if __name__ == '__main__':
    asyncio.run(wx_tools.get_we_user_opendid('083UMqFa135S5D0wppJa1n5giw1UMqFL'))
