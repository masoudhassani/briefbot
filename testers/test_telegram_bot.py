import asyncio
from modules.telegram_bot import TelegramBot, NotificationService

bot = TelegramBot()
notifier = NotificationService(bot)

# Fix for the async bot info call
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If there's already a running loop, we can't use asyncio.run()
        print("Event loop already running, skipping bot info display")
    else:
        info = loop.run_until_complete(bot.get_bot_info())
        if info:
            print(f"Bot started: {info['first_name']} (@{info['username']})")
except RuntimeError:
    # No event loop, create one
    async def get_info():
        return await bot.get_bot_info()

    info = asyncio.run(get_info())
    if info:
        print(f"Bot started: {info['first_name']} (@{info['username']})")

# UNCOMMENT THIS TO SEND A START MESSAGE
# This part is commented out to avoid sending a message on every run
# try:
#     loop = asyncio.get_event_loop()
#     if loop.is_running():
#         print("Event loop already running, skipping server start message")
#     else:
#         loop.run_until_complete(notifier.send_to_chat("✅ Server is starting..."))
# except RuntimeError:

#     async def send_start_msg():
#         await notifier.send_to_chat("✅ Server is starting...")

#     asyncio.run(send_start_msg())

# Start the bot
print("Bot is running... Press Ctrl+C to stop.")
bot.run()
