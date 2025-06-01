import asyncio
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from modules.mcp_server_manager import MCPServerManager
from modules.utils import load_yaml_config

# Load environment variables
load_dotenv()

# Initialize OpenAI client
secrets = load_yaml_config("configs/secrets.yml", "openai")
openai_api_key = secrets.get("api_key")

model = "gpt-4o-mini"
client = OpenAI(api_key=openai_api_key)


async def process_query(query: str, server_manager: MCPServerManager):
    messages = [{"role": "user", "content": query}]
    response = client.responses.create(
        model="gpt-4o-mini",
        tools=server_manager.all_tools,
        input=messages,
        tool_choice="auto",
        temperature=0.0,
    )

    for response_output in response.output:
        if response_output.type == "message":
            print(response_output.content[0].text)

        elif response_output.type == "function_call":
            tool_id = response_output.call_id
            tool_args = response_output.arguments
            tool_name = response_output.name

            print(f"Calling tool {tool_name} with args {tool_args}")
            parsed_args = json.loads(tool_args)

            try:
                result = await server_manager.call_tool(tool_name, arguments=parsed_args)

            except RuntimeError as e:
                print(f"❌ Connection error: {e}")
                print("🔄 Try reconnecting or restart the application")
                return

            messages.append(
                {
                    "role": "system",
                    "content": result,
                }
            )
            response = client.responses.create(
                model="gpt-4o-mini",
                input=messages,
            )

            if len(response.output) == 1:
                print(response.output[0].content[0].text)


async def main():
    # Use the context manager for proper cleanup
    async with MCPServerManager("configs/server_configs.json") as server_manager:
        await server_manager.connect_to_all_servers()
        print("Type 'quit' to exit the chatbot session")

        while True:
            try:
                query = input("Query: ").strip()

                if query.lower() == "quit":
                    break

                await process_query(query, server_manager)

            except Exception as e:
                print(f"Error: {str(e)}")

    # Cleanup happens automatically when exiting the context manager
    print("🎉 Chatbot session ended cleanly")


if __name__ == "__main__":
    asyncio.run(main())
