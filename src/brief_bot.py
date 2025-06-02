import logging
import asyncio
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from openai import OpenAI
from modules.mcp_server_manager import MCPServerManager
from modules.telegram_bot import TelegramBot
from modules.utils import load_yaml_config
from functools import partial

# Load environment variables
load_dotenv()

telegram_secrets = load_yaml_config("configs/secrets.yml", "telegram")
openai_secrets = load_yaml_config("configs/secrets.yml", "openai")

TELEGRAM_BOT_TOKEN = telegram_secrets.get("bot_token")
OPENAI_API_KEY = openai_secrets.get("api_key")
OPENAI_MODEL = "gpt-4o-mini"

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")


async def openai_query_handler(query: str, server_manager: MCPServerManager):
    messages = [{"role": "user", "content": query}]
    response = client.responses.create(
        model=OPENAI_MODEL,
        tools=server_manager.all_tools,
        input=messages,
        tool_choice="auto",
        temperature=0.5,
    )
    output_text = ""
    for response_output in response.output:
        if response_output.type == "message":
            output_text += response_output.content[0].text
        elif response_output.type == "function_call":
            tool_name = response_output.name
            tool_args = json.loads(response_output.arguments)
            try:
                result = await server_manager.call_tool(tool_name, arguments=tool_args)
            except RuntimeError as e:
                return f"Connection error: {e}\nTry reconnecting or restart the application."
            if result.get("success") and result.get("content"):
                content = result["content"]
                messages.append({"role": "system", "content": content})
                followup_response = client.responses.create(
                    model=OPENAI_MODEL,
                    input=messages,
                )
                if followup_response.output and followup_response.output[0].content:
                    output_text += "\n" + followup_response.output[0].content[0].text
    return output_text.strip() if output_text else "Sorry, I could not get a response."


async def telegram_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, server_manager: MCPServerManager
):
    user_query = update.message.text
    logger.info(f"User query: {user_query}")
    # await update.message.reply_text("Thinking...")

    # Call OpenAI logic
    response_text = await openai_query_handler(user_query, server_manager)
    await update.message.reply_text(response_text)


async def main():
    async with MCPServerManager("configs/server_configs.json") as server_manager:
        await server_manager.connect_to_all_servers()
        print("Servers connected, starting Telegram bot...")

        # Init your TelegramBot class (do NOT call run() inside)
        telegram_bot = TelegramBot()
        # Remove default handlers if you want (optional)
        # telegram_bot.remove_default_handlers()

        # Add your custom handlers, e.g.:
        # telegram_bot.add_command_handler("custom", custom_func)
        # Now inject server_manager into the message handler as before

        # Remove the default message handler and add yours, or override
        telegram_bot.add_message_handler(
            partial(telegram_message_handler, server_manager=server_manager)
        )

        app = telegram_bot.application

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            print("Received interrupt, shutting down...")

        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    print("Bot stopped and server manager cleaned up.")


# Your telegram_message_handler must accept server_manager as param, as before

if __name__ == "__main__":
    asyncio.run(main())
