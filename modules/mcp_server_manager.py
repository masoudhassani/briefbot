import os
import json
import asyncio
import logging
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from modules.utils import load_json_config
from modules.data_structure import BooleanMessage, ToolResponse

# Load environment variables
load_dotenv()

# Set up logging to see what's happening
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class MCPServerConnection:
    """Wrapper for a single MCP server connection that manages its own lifecycle"""

    def __init__(self, server_name: str, server_config: Dict[str, Any]):
        self.server_name = server_name
        self.server_config = server_config
        self.session = None
        self.tools = []
        self._connected = False
        self._stdio_context = None
        self._session_context = None
        self._read_stream = None
        self._write_stream = None

    async def connect(self) -> bool:
        """Connect to the MCP server and store connection resources"""
        print(f"\nConnecting to {self.server_name}...")

        try:
            # update the environment variables if provided
            raw_env = self.server_config.get("env", {})
            resolved_env = {
                key: (
                    os.getenv(value[2:-1])
                    if value.startswith("${") and value.endswith("}")
                    else value
                )
                for key, value in raw_env.items()
            }
            server_params = StdioServerParameters(
                command=self.server_config["command"],
                args=self.server_config.get("args", []),
                env=resolved_env,
            )

            print(f"  Command: {server_params.command} {' '.join(server_params.args)}")
            print(f"  Starting process...")

            # Create stdio context
            self._stdio_context = stdio_client(server_params)

            # Enter stdio context
            self._read_stream, self._write_stream = await self._stdio_context.__aenter__()

            # Create and enter session context
            self._session_context = ClientSession(self._read_stream, self._write_stream)
            self.session = await self._session_context.__aenter__()

            print(f"  Session created for {self.server_name}")

            # Initialize session with retries
            print(f"  Initializing connection...")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with asyncio.timeout(10):
                        await self.session.initialize()
                    print(f"  Initialized {self.server_name} (attempt {attempt + 1})")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"  Retry {attempt + 1} after error: {e}")
                        await asyncio.sleep(1)
                    else:
                        raise

            # Fetch tools
            print(f"  Fetching server capabilities...")
            try:
                async with asyncio.timeout(8):
                    response = await self.session.list_tools()

                tools = response.tools if hasattr(response, "tools") else []
                print(f"  Retrieved {len(tools)} tools from {self.server_name}")

                self.tools.clear()
                for tool in tools:
                    self.tools.append(
                        {
                            "name": tool.name,
                            "type": "function",
                            "description": tool.description
                            or f"Tool from {self.server_name} server",
                            "parameters": getattr(tool, "inputSchema", {}) or {},
                            "server": self.server_name,
                        }
                    )
                    # print(f"    {tool.name}: {tool.description}")

            except Exception as e:
                print(f"  Error getting tools from {self.server_name}: {e}")

            self._connected = True
            print(f"  Successfully connected to {self.server_name}")
            return True

        except Exception as e:
            print(f"  Failed to connect to {self.server_name}: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """Disconnect from the server with proper cleanup"""
        if not self._connected and not self._session_context and not self._stdio_context:
            return

        print(f"  Disconnecting {self.server_name}...")

        # Mark as disconnected first to prevent new operations
        self._connected = False

        try:
            # Close session context first
            if self._session_context:
                try:
                    await self._session_context.__aexit__(None, None, None)
                    print(f"  Session context closed for {self.server_name}")
                except asyncio.CancelledError:
                    print(f"  Session cleanup cancelled for {self.server_name}")
                except Exception as e:
                    print(f"  Warning: Error closing session context for {self.server_name}: {e}")
                finally:
                    self._session_context = None
                    self.session = None

            # Close stdio context
            if self._stdio_context:
                try:
                    await self._stdio_context.__aexit__(None, None, None)
                    print(f"  Stdio context closed for {self.server_name}")
                except asyncio.CancelledError:
                    print(f"  Stdio cleanup cancelled for {self.server_name}")
                except Exception as e:
                    print(f"  Warning: Error closing stdio context for {self.server_name}: {e}")
                finally:
                    self._stdio_context = None
                    self._read_stream = None
                    self._write_stream = None

        except asyncio.CancelledError:
            print(f"  Disconnect cancelled for {self.server_name}, cleaning up references...")
            # Clean up references even if cancelled
            self._session_context = None
            self.session = None
            self._stdio_context = None
            self._read_stream = None
            self._write_stream = None

        # Clear tools
        self.tools.clear()

        print(f"  Disconnected {self.server_name}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = {}) -> Optional[Any]:
        """Call a tool on this server"""
        if not self._connected or not self.session:
            raise RuntimeError(f"Server {self.server_name} is not connected")

        if arguments is None:
            arguments = {}

        try:
            result = await self.session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            print(f"Error calling tool '{tool_name}' on {self.server_name}: {e}")
            # Check if connection is still alive
            if not self._connected:
                print(f"Connection to {self.server_name} appears to be lost")
            raise

    @property
    def is_connected(self) -> bool:
        return self._connected and self.session is not None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.disconnect()


class MCPServerManager:
    def __init__(self, config_path: str = "configs/server_configs.json"):
        self.config_path = config_path
        self.connections: Dict[str, MCPServerConnection] = {}
        self.all_tools = []
        self._cleanup_done = False

    async def connect_to_all_servers(self):
        """Connect to all servers"""
        config = load_json_config(self.config_path, "mcpServers")

        if not config:
            print("No server configuration found")
            return False

        print(f"Found {len(config)} servers in configuration")
        print("Connecting sequentially for better reliability...")

        successful_connections = 0

        # Create connections for each server
        for server_name, server_config in config.items():

            connection = MCPServerConnection(server_name, server_config)

            try:
                success = await connection.connect()

                if success:
                    self.connections[server_name] = connection
                    self.all_tools.extend(connection.tools)
                    successful_connections += 1
                else:
                    print(f"Failed to connect to {server_name}")
                    # Ensure failed connection is cleaned up
                    await connection.disconnect()

            except Exception as e:
                print(f"Error connecting to {server_name}: {e}")
                # Ensure failed connection is cleaned up
                await connection.disconnect()

            # Small delay between connections
            await asyncio.sleep(0.5)

        print(f"\nCONNECTION SUMMARY:")
        print(f"   Successful: {successful_connections}/{len(config)} servers")
        print(f"   Total tools: {len(self.all_tools)}")

        if successful_connections > 0:
            self.print_tools_summary()

        return successful_connections > 0

    def print_tools_summary(self):
        """Print a summary of all available tools grouped by server"""
        print(f"\n{'='*60}")
        print("AVAILABLE TOOLS SUMMARY")
        print(f"{'='*60}")

        # Group tools by server
        tools_by_server = {}
        for tool in self.all_tools:
            server = tool["server"]
            if server not in tools_by_server:
                tools_by_server[server] = []
            tools_by_server[server].append(tool)

        for server_name, tools in tools_by_server.items():
            print(f"\n{server_name.upper()} ({len(tools)} tools):")
            for tool in tools:
                print(f"   • {tool['name']}: {tool['description']}")

        print(f"\n{'='*60}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Optional[Any]:
        """Call a specific tool by name"""
        if arguments is None:
            arguments = {}

        # Find which server has this tool
        tool_info = None
        for tool in self.all_tools:
            if tool["name"] == tool_name:
                tool_info = tool
                break

        if not tool_info:
            print(f"Tool '{tool_name}' not found")
            return None

        server_name = tool_info["server"]
        if server_name not in self.connections:
            print(f"Server '{server_name}' not connected")
            return None

        connection = self.connections[server_name]

        if not connection.is_connected:
            print(f"Server '{server_name}' is not connected")
            return None

        print(f"Calling {tool_name} on server '{server_name}' with arguments {arguments}...")
        try:
            result = await connection.call_tool(tool_name, arguments)
            return self.parse_tool_message(result)

        except Exception as e:
            print(f"Tool call error: {e}")
            return ToolResponse.failure(None)

    async def get_available_tools_for_openai(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI-compatible format"""
        return [
            {
                "name": tool["name"],
                "type": tool["type"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for tool in self.all_tools
        ]

    @property
    def sessions(self):
        """Compatibility property for existing code"""
        return {name: conn.session for name, conn in self.connections.items() if conn.is_connected}

    async def cleanup(self):
        """Clean up all connections"""
        if self._cleanup_done:
            return

        print("\nCleaning up connections...")
        self._cleanup_done = True

        # Disconnect connections one by one to avoid cancellation issues
        for server_name, connection in list(self.connections.items()):
            if connection.is_connected or connection._session_context or connection._stdio_context:
                try:
                    await connection.disconnect()
                except asyncio.CancelledError:
                    print(f"Cleanup cancelled for {server_name}, forcing cleanup...")
                    # Force immediate cleanup without waiting
                    connection._connected = False
                    connection._session_context = None
                    connection._stdio_context = None
                    connection.session = None
                    connection.tools.clear()
                except Exception as e:
                    print(f"Warning: Exception during cleanup of {server_name}: {e}")

        # Clear all references
        self.connections.clear()
        self.all_tools.clear()
        print("Cleanup complete")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.cleanup()

    def __del__(self):
        """Destructor to ensure cleanup if context manager wasn't used"""
        if hasattr(self, "_cleanup_done") and not self._cleanup_done:
            print("Warning: MCPServerManager was not properly closed. Use async context manager.")

    def parse_tool_message(self, result: Any) -> Dict[str, Any]:
        """Parse a tool message from a string"""
        if result is None or len(result.content) == 0:
            print("❌ Tool call returned no result")
            return ToolResponse.failure(None)

        if result.content[0].text == BooleanMessage.failure:
            print("❌ Tool call failed")
            return ToolResponse.failure(None)

        if result.content[0].text == BooleanMessage.success:
            print("✅ Tool call succeeded")
            return ToolResponse.success(None)

        contents = ""
        for content in result.content:
            if hasattr(content, "text"):
                contents += "\n" + content.text
            else:
                contents += "\n" + str(content)

        print("✅ Tool call succeeded")
        return ToolResponse.success(contents)


# Example usage
async def main():
    try:
        async with MCPServerManager("configs/server_configs.json") as manager:
            # Connect to all servers
            success = await manager.connect_to_all_servers()

            if success:
                # Get tools for OpenAI API
                openai_tools = await manager.get_available_tools_for_openai()
                print(f"\nReady for OpenAI integration with {len(openai_tools)} tools")

                # Example tool call (uncomment to test)
                # if openai_tools:
                #     result = await manager.call_tool(openai_tools[0]["name"])
                #     print(f"Test result: {result}")
            else:
                print("No servers connected successfully")

    except Exception as e:
        print(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
