from typing import Dict

import uvicorn as uvicorn
from fastapi import FastAPI
from bot import chatgpt_api
from api.public_acc import router as pub_acc_router
from api.mini_app import router as app_router


app = FastAPI()

user_map: Dict[str, chatgpt_api.User] = {}
bot_manager = chatgpt_api.BotManager()
timeout_reply = chatgpt_api.TimeoutReply()

timeout_reply.start()

app.state.timeout_reply = timeout_reply
app.state.user_map = user_map
app.state.bot_manager = bot_manager

app.include_router(pub_acc_router)
app.include_router(app_router)
app.state.block_version = ['']

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)
