from mcp.server.fastmcp import FastMCP

from modules.telegram_bot import NotificationService
from typing import List, Dict
import logging


# Setup
mcp = FastMCP("News Server")
notifier = NotificationService()
logging.basicConfig(level=logging.ERROR)


@mcp.tool()
async def send_telegram_message(message: str) -> None:
    """Sends a message to the Telegram bot"""
    if not message:
        logging.error("Message must be provided")
        return None

    try:
        await notifier.send_to_chat(message)
        logging.info(f"Message sent: {message}")
        return None
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        return None


if __name__ == "__main__":
    mcp.run(transport="stdio")
