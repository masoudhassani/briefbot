from mcp.server.fastmcp import FastMCP

from modules.telegram_bot import NotificationService
from modules.data_structure import BooleanMessage
from typing import List, Dict
import logging


# Setup
mcp = FastMCP("News Server")
notifier = NotificationService()
logging.basicConfig(level=logging.ERROR)


@mcp.tool()
async def send_telegram_message(message: str) -> str:
    """Sends a message to the Telegram bot"""
    if not message:
        logging.error("Message must be provided")
        return BooleanMessage.failure

    try:
        await notifier.send_to_chat(message)
        logging.info(f"Message sent: {message}")
        return BooleanMessage.success
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        return BooleanMessage.failure


if __name__ == "__main__":
    mcp.run(transport="stdio")
