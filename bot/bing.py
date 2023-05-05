import asyncio

from EdgeGPT import Chatbot, ConversationStyle

from configs import config


async def main():
    bot = Chatbot(cookiePath='./cookies.json', proxy=config.PROXY)
    while True:
        send_msg = input('You:')
        print('')
        wrote = 0
        async for final, response in bot.ask_stream(prompt=send_msg, conversation_style=ConversationStyle.creative,
                                                    wss_link="wss://sydney.bing.com/sydney/ChatHub"):
            if not final:
                print(response[wrote:], end="", flush=True)
                wrote = len(response)
        print('')


if __name__ == '__main__':
    asyncio.run(main())
