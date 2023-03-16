import json

import aiohttp as aiohttp
from aiohttp import ClientTimeout
from loguru import logger


async def aio_request(url, method='GET', **kwargs) -> dict:
    base_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    try:
        base_headers.update(kwargs.pop('headers'))
    except KeyError:
        pass
    method = method.upper()
    logger.info(f'{method} {url}')
    try:
        async with aiohttp.ClientSession(headers=base_headers, timeout=ClientTimeout(total=60)) as session:
            async with session.request(url=url, method=method, ssl=False, **kwargs) as r:
                json_body = await r.json()
                return json_body
    except Exception as e:
        raise Exception(f'请求失败 url: {url} :: {e}')
