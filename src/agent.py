import asyncio
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from modules.mcp_server_manager import MCPServerManager
from modules.config_manager import ConfigManager

# Load environment variables
load_dotenv()

# Initialize OpenAI client
config_manager = ConfigManager()
openai_api_key = config_manager.get_api_key("openai")
model = "gpt-4o-mini"
client = OpenAI(api_key=openai_api_key)


async def main():
    server_manager = MCPServerManager("configs/server_configs.json")
    await server_manager.connect_to_all_servers()

    try:
        # Run chatbot loop
        query = input("Enter a query: ")
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
                result = await server_manager.call_tool(tool_name, arguments=parsed_args)

                messages.append(
                    {
                        "role": "system",
                        "content": result.content[0].text,
                    }
                )
                response = client.responses.create(
                    model="gpt-4o-mini",
                    input=messages,
                )

                if len(response.output) == 1:
                    print(response.output[0].content[0].text)

    finally:
        await server_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
