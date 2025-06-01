import logging
import asyncio
import psutil
import datetime
from typing import Dict, Optional, Callable
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from modules.utils import load_yaml_config


class TelegramBot:
    """
    A class to communicate with Telegram Bot API using python-telegram-bot library.
    Handles sending messages and receiving updates from users.
    """

    def __init__(
        self, config_path: str = "configs/configs.yml", secrets_path: str = "configs/secrets.yml"
    ):
        """
        Initialize the Telegram bot with configuration from YAML file.

        Args:
            config_path (str): Path to the configuration file
            secrets_path (str): Path to the secrets file
        """
        self.configs = load_yaml_config(config_path, "telegram")
        self.secrets = load_yaml_config(secrets_path, "telegram")
        bot_token = self.secrets.get("bot_token", None)
        self.chat_id = self.secrets.get("chat_ids", {}).get("default", None)
        if not bot_token:
            raise ValueError("Telegram bot token not found in secrets file")

        self.bot = Bot(token=bot_token)
        self.application = Application.builder().token(bot_token).build()

        # Set up logging
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

        # Register default handlers
        self._setup_default_handlers()

    async def send_message(
        self, text: str, chat_id: Optional[int] = None, parse_mode: str = "", reply_markup=None
    ) -> bool:
        """
        Send a message to a specific chat.

        Args:
            chat_id (int): Optional chat ID to send the message to. The bot has a default chat ID from secrets.
            text (str): The message text to send
            parse_mode (str, optional): Parse mode (HTML, Markdown, MarkdownV2)
            reply_markup (optional): Additional interface options

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        chat_id = chat_id or self.chat_id
        try:
            await self.bot.send_message(
                chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup
            )
            return True
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False

    def add_command_handler(self, command: str, callback: Callable):
        """
        Add a command handler.

        Args:
            command (str): Command name (without /)
            callback (Callable): Async function to handle the command
        """
        handler = CommandHandler(command, callback)
        self.application.add_handler(handler)
        self.logger.info(f"Added command handler for /{command}")

    def add_message_handler(self, callback: Callable, message_filter=None):
        """
        Add a message handler.

        Args:
            callback (Callable): Async function to handle messages
            message_filter: Filter for specific message types (default: text messages)
        """
        if message_filter is None:
            message_filter = filters.TEXT & ~filters.COMMAND

        handler = MessageHandler(message_filter, callback)
        self.application.add_handler(handler)
        self.logger.info("Added message handler")

    def _setup_default_handlers(self):
        """Set up default command handlers."""
        self.add_command_handler("start", self._start_command)
        self.add_command_handler("help", self._help_command)
        self.add_command_handler("info", self._info_command)
        self.add_command_handler("status", self._status_command)
        self.add_command_handler("ping", self._ping_command)
        # self.add_message_handler(self._default_message)

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Default start command handler."""
        chat = update.effective_chat

        if not self.chat_id:
            self.chat_id = chat.id

        await update.message.reply_text(
            "Hello! I'm your Telegram bot. Use /help to see available commands."
        )

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Default help command handler."""
        help_text = """
    Available commands:
    /start - Start the bot
    /help - Show this help message
    /info - Show your user and chat information
    /ping - Check if the bot is responsive
    /status - Show bot status and system information

    You can also send me any text message and I'll echo it back!
        """
        await update.message.reply_text(help_text)

    async def _info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Custom command to show user info."""
        user = update.effective_user
        chat = update.effective_chat

        info_text = f"""
    User Information:
    - Name: {user.first_name} {user.last_name or ''}
    - Username: @{user.username or 'Not set'}
    - User ID: {user.id}
    - Chat ID: {chat.id}
    - Chat Type: {chat.type}
        """
        await update.message.reply_text(info_text)

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # Get system info
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        status_text = f"""
🟢 Bot Status: Online

⏱️ Uptime: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
💻 CPU Usage: {cpu_percent}%
🧠 Memory Usage: {memory.percent}%
🔄 Status: Running normally

Bot is healthy and ready to serve!
        """
        await update.message.reply_text(status_text.strip())

    async def _ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ping command"""
        await update.message.reply_text("🏓 Pong! Bot is responsive.")

    async def _echo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Default message handler that echoes messages."""
        user_message = update.message.text
        await update.message.reply_text(f"Echo: {user_message}")

    async def _default_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Process incoming messages - customize this method for your specific logic
        """
        message_lower = update.message.text.lower()
        user = update.effective_user

        if any(greeting in message_lower for greeting in ["hello", "hi", "hey"]):
            await update.message.reply_text(
                f"Hello {user.first_name}! 👋 How can I help you today?"
            )

        elif any(word in message_lower for word in ["bye", "goodbye", "see you"]):
            await update.message.reply_text("Goodbye! Feel free to message me anytime. 👋")

        elif "thank" in message_lower:
            await update.message.reply_text("You're welcome! Happy to help! 😊")

        else:
            # Default response - customize this for your specific use case
            await update.message.reply_text(
                f"I received your message: '{update.message.text}'\n\nI'm processing it... 🤔"
            )

    def remove_default_handlers(self):
        """Remove default handlers if you want to add custom ones only."""
        self.application.handlers.clear()

    async def get_bot_info(self) -> Dict:
        """
        Get basic information about the bot.

        Returns:
            Dict: Bot information
        """
        try:
            bot_info = await self.bot.get_me()
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries,
            }
        except Exception as e:
            self.logger.error(f"Error getting bot info: {e}")
            return {}

    def run(self):
        """Start the bot and begin polling for updates."""
        self.logger.info("Starting bot...")
        self.application.run_polling()

    def stop(self):
        """Stop the bot."""
        self.logger.info("Stopping bot...")
        self.application.stop()


class NotificationService:
    def __init__(self, bot: Optional[TelegramBot] = None):
        """
        Initialize the notification service with a Telegram bot instance.
        Args:
            bot (TelegramBot): Optional instance of TelegramBot to use for sending notifications.
        """
        if bot is None:
            self.bot = TelegramBot()
        else:
            self.bot = bot

        self.chat_ids = []  # Store chat IDs of users who want notifications

        # append the default chat ID if it exists
        if self.bot.chat_id:
            self.chat_ids.append(self.bot.chat_id)

    def add_chat_id(self, chat_id: int):
        """Add a chat ID for notifications"""
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    async def send_to_chat(self, message: str, chat_id: Optional[int] = None):
        """Send message to specific chat"""
        if not chat_id:
            chat_id = self.chat_ids[0]
        return await self.bot.send_message(message, chat_id)

    async def broadcast_notification(self, message: str):
        """Send message to all registered chat IDs"""
        results = []
        for chat_id in self.chat_ids:
            success = await self.bot.send_message(message, chat_id)
            results.append((chat_id, success))
        return results

    def send_notification_sync(self, message: str, chat_id: Optional[int] = None):
        """Synchronous method to send notification"""
        if not chat_id:
            chat_id = self.chat_ids[0]

        async def _send():
            return await self.send_to_chat(message, chat_id)

        try:
            return asyncio.run(_send())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_send())
            finally:
                loop.close()


##################################################################
# Example usage with custom handlers
async def custom_hello_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Custom command handler example."""
    user = update.effective_user
    await update.message.reply_text(f"Hello {user.first_name}! Nice to meet you.")


async def custom_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Custom command to show user info."""
    user = update.effective_user
    chat = update.effective_chat

    info_text = f"""
User Information:
- Name: {user.first_name} {user.last_name or ''}
- Username: @{user.username or 'Not set'}
- User ID: {user.id}
- Chat ID: {chat.id}
- Chat Type: {chat.type}
    """
    await update.message.reply_text(info_text)


async def custom_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Custom message handler that processes text differently."""
    text = update.message.text.lower()

    if "hello" in text or "hi" in text:
        await update.message.reply_text("Hello there! 👋")
    elif "bye" in text or "goodbye" in text:
        await update.message.reply_text("Goodbye! See you later! 👋")
    elif "help" in text:
        await update.message.reply_text("You can use /help to see available commands!")
    else:
        await update.message.reply_text(f"You said: {update.message.text}")


##################################################################

if __name__ == "__main__":
    # Initialize the bot
    bot = TelegramBot()

    # Remove default handlers if you want custom ones only
    # bot.remove_default_handlers()

    # Add custom command handlers
    bot.add_command_handler("hello", custom_hello_command)
    bot.add_command_handler("info", custom_info_command)

    # Add custom message handler (this will replace the default echo handler)
    bot.add_message_handler(custom_message_handler)

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

    # Start the bot
    print("Bot is running... Press Ctrl+C to stop.")
    bot.run()
