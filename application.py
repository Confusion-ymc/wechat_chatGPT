from fastapi import FastAPI
from api.mini_app import router as app_router
from bot.chatGPT import BotManager


def app_factory():
    app = FastAPI()

    bot_manager = BotManager()
    app.state.bot_manager = bot_manager

    app.include_router(app_router)
    app.state.ban_version = []
    return app


app = app_factory()
