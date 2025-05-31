from dotenv import load_dotenv

# from anthropic import Anthropic
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import List
import asyncio
import json
import nest_asyncio
from modules.config_manager import ConfigManager

nest_asyncio.apply()

load_dotenv()


class Agent:

    def __init__(self):
        config_manager = ConfigManager()
        openai_api_key = config_manager.get_api_key("openai")

        # Initialize session and client objects
        self.session: ClientSession = None
        # self.anthropic = Anthropic()
        self.openai = OpenAI(api_key=openai_api_key)
        self.available_tools: List[dict] = []

    async def process_query(self, query):
        messages = [{"role": "user", "content": query}]
        response = self.openai.responses.create(
            model="gpt-4o-mini",
            tools=self.available_tools,  # tools exposed to the LLM
            input=messages,
        )

        process_query = True
        while process_query:
            assistant_content = []
            for content in response.output:
                if content.type == "message":
                    assistant_content.append(content)
                    if len(content.content) == 1:
                        process_query = False

                elif content.type == "function_call":
                    tool_id = content.call_id
                    tool_args = content.arguments
                    tool_name = content.name

                    print(f"Calling tool {tool_name} with args {tool_args}")

                    # Call a tool
                    parsed_args = json.loads(tool_args)
                    result = await self.session.call_tool(tool_name, arguments=parsed_args)

                    messages.append(
                        {
                            "role": "system",
                            "content": result.content[0].text,
                        }
                    )
                    response = self.openai.responses.create(
                        model="gpt-4o-mini",
                        input=messages,
                    )

                    if len(response.output) == 1:
                        print(response.output[0].content[0].text)
                        process_query = False

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                await self.process_query(query)
                print("\n")

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def connect_to_server_and_run(self):
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="python",  # Executable
            args=["-m", "servers.test_server"],  # Optional command line arguments
            env=None,  # Optional environment variables
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                # Initialize the connection
                await session.initialize()

                # List available tools
                response = await session.list_tools()

                tools = response.tools
                print("\nConnected to server with tools:", [tool.name for tool in tools])

                self.available_tools = [
                    {
                        "name": tool.name,
                        "type": "function",
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                    for tool in response.tools
                ]
                # print("\nAvailable tools:", self.available_tools)

                await self.chat_loop()


async def main():
    chatbot = Agent()
    await chatbot.connect_to_server_and_run()


if __name__ == "__main__":
    asyncio.run(main())
