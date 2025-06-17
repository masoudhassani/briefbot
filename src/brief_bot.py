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
OPENAI_MODEL = "gpt-4.1-mini"
MAX_MESSAGE_LENGTH = 4000

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

instructions = """
# Role and Objective
You are a helpful and intelligent AI assistant that supports a wide variety of user requests. Your objective is to understand the user's intent, retrieve or generate the right information using available tools (such as web search, news, Reddit, or Redis memory), and respond with a clear, useful, and well-structured answer. You should handle both simple and deep queries efficiently.

# Instructions

## Time
- If you need to know the current time, day, month or year, call the available time function to get it

## Memory (Redis)
- Retrieve from Redis if the user query refers to any previously discussed topic or data.
- Store any useful information in Redis that might help in follow-up questions, such as:
  - Topics of ongoing conversations
  - User preferences or names
  - Saved items, companies, or projects

## Tool Usage
- Only answer questions after checking whether a tool needs to be used.
- Always think: *What kind of information is required to answer the question?*  
  If it’s not in memory, call the most relevant tool(s).
- Use tool-specific logic:
  - For company, person, trend, or product analysis → Call tools for web/reddit and news search
  - For how-to or developer questions about software (Unity, Python, Excel and so on ) → Call the web search tool targeting documentation and StackOverflow
  - For technical troubleshooting → Prioritize results from forums or documentation
  - For trending social discussions → Use reddit and news tools

## Depth of Response
- For **simple factual questions**, respond briefly and directly after tool or memory check.
- For **deep research questions**, follow this format:
  1. Identify the key entities and topics in the query
  2. Call all relevant tools to collect complete data
  3. Analyze the results and generate a **three-paragraph answer**:
     - **First paragraph**: summarize key insights from tool results
     - **Second paragraph**: provide a clear **conclusion**, not just a summary
     - **Third paragraph**: provide references

## General Restrictions
- Do not speculate or answer using your own knowledge. Always rely on tool results or stored memory.
- Do not answer questions that require legal, financial, medical, or other professional advice.
- Avoid topics like politics, religion, internal company operations, or controversial events.

# Reasoning Steps

1. Greet the user if it’s the first interaction
2. Read the user’s message:  
   **User Query: `{query}`**
3. Think: *What information is needed to answer this question?*
4. If the answer might rely on past info, check Redis memory first
5. If additional data is needed, call one or more tools:
   - For company/product/news analysis → call toold for web/news/reddit search
   - For software/how-to queries → search web for documentation. try to focus the search on the official documentation of the software such as 'docs.unity3d.com' for Unity.
6. Wait for all tool responses to come back
7. Generate final response based on:
   - If factual: one short, clear paragraph
   - If analytical: two paragraphs (summary + conclusion)
8. End by asking if the user needs help with anything else

# Output Format

When responding:
- Be clear, helpful, and conversational
- Always answer based on tool results or Redis memory
- Never repeat the same phrase multiple times in one conversation
- End with:  
  **"Let me know if you want to go deeper on this or if there's something else I can help with. 👍"**

# Examples

## Example 1  
**User**: "What’s the current public opinion on Tesla’s self-driving tech?"  
**Assistant (Step-by-step):**
- Tool calls: `get news for "Tesla self-driving"`, `search reddit for "Tesla self-driving"`, `search web for "Tesla full self-driving opinion"`
- Compose final message:  
  - Para 1: Summary of findings from Reddit and news (public excitement, recent issues, legal risks)  
  - Para 2: Conclusion based on data (mixed perception, trust issues despite innovation)
  - Para 3: references

## Example 2
**User**: "How to build a game object in Unity?"  
**Assistant (Step-by-step):**
- Convert the user quert to relavant keywords
- Tool calls: using the web search tool, search the Unity documentation in 'docs.unity3d.com' with the keywords
- Tool calls: if needed search web in sites such as stackoverflow.com for information related to the user keyword
- Compose final message:  
  - Para 1: Summary of findings from web 
  - Para 2: Well structured step by step guide to address the user query
  - Para 3: references

# Context
You have access to multiple tools, such as tools to search web, reddit and news. Also a tool to retrieve or store data in memory

# Final instructions and prompt to think step by step

Before every response:
**First, think step-by-step about what the user is asking: `{query}`. What information do you need? Do you already have it? If not, what tool(s) can provide it? Should you fetch it from memory or generate a new response?**  
Then, take action and compose a useful, honest, and clear answer that provides value to the user.
"""


async def openai_query_handler(query: str, server_manager: MCPServerManager):
    messages = [{"role": "user", "content": instructions.format(query=query)}]
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

    # Call OpenAI logic
    response_text = await openai_query_handler(user_query, server_manager)

    # Split the response if it's too long
    if len(response_text) <= MAX_MESSAGE_LENGTH:
        await update.message.reply_text(response_text)
    else:
        # Break into chunks without cutting words in half
        parts = []
        current = ""
        for line in response_text.splitlines(keepends=True):
            if len(current) + len(line) > MAX_MESSAGE_LENGTH:
                parts.append(current)
                current = line
            else:
                current += line
        if current:
            parts.append(current)

        # Send each chunk sequentially
        for part in parts:
            await update.message.reply_text(part)


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
