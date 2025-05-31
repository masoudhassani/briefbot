import json
import asyncio
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logging

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
        self._connection_task = None

    async def _connection_task_runner(self):
        """Long-running task that maintains the connection"""
        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command=self.server_config["command"],
                args=self.server_config.get("args", []),
                env=self.server_config.get("env", None),
            )

            print(f"  📋 Command: {server_params.command} {' '.join(server_params.args)}")
            print(f"  ⏳ Starting process...")

            async with asyncio.timeout(15):
                async with stdio_client(server_params) as (read, write):
                    print(f"  ✅ Process started for {self.server_name}")

                    async with ClientSession(read, write) as session:
                        self.session = session
                        print(f"  ✅ Session created for {self.server_name}")

                        # Initialize with retries
                        print(f"  ⏳ Initializing connection...")
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                async with asyncio.timeout(10):
                                    await self.session.initialize()
                                print(
                                    f"  ✅ Initialized {self.server_name} (attempt {attempt + 1})"
                                )
                                break
                            except asyncio.TimeoutError:
                                if attempt < max_retries - 1:
                                    print(
                                        f"  ⚠️  Initialization timeout, retrying... (attempt {attempt + 1})"
                                    )
                                    await asyncio.sleep(1)
                                else:
                                    raise
                            except Exception as e:
                                if attempt < max_retries - 1:
                                    print(
                                        f"  ⚠️  Initialization error: {e}, retrying... (attempt {attempt + 1})"
                                    )
                                    await asyncio.sleep(1)
                                else:
                                    raise

                        # Get tools
                        print(f"  ⏳ Fetching server capabilities...")
                        try:
                            async with asyncio.timeout(8):
                                response = await self.session.list_tools()

                            tools = response.tools if hasattr(response, "tools") else []
                            print(f"  ✅ Retrieved {len(tools)} tools from {self.server_name}")

                            # Process tools
                            for tool in tools:
                                tool_def = {
                                    "name": tool.name,
                                    "type": "function",
                                    "description": tool.description
                                    or f"Tool from {self.server_name} server",
                                    "parameters": getattr(tool, "inputSchema", {}) or {},
                                    "server": self.server_name,
                                }
                                self.tools.append(tool_def)
                                print(f"    📦 {tool.name}: {tool.description}")

                        except Exception as e:
                            print(f"  ⚠️  Error getting tools from {self.server_name}: {e}")

                        self._connected = True
                        print(f"  🎉 Successfully connected to {self.server_name}")

                        # Keep connection alive until cancelled
                        try:
                            while self._connected:
                                await asyncio.sleep(1)
                        except asyncio.CancelledError:
                            print(f"  🔌 Connection task cancelled for {self.server_name}")
                            raise

        except asyncio.CancelledError:
            print(f"  🔌 Connection cancelled for {self.server_name}")
            raise
        except Exception as e:
            print(f"  ❌ Connection error for {self.server_name}: {e}")
        finally:
            self._connected = False
            self.session = None
            print(f"  ✅ Connection cleanup complete for {self.server_name}")

    async def connect(self) -> bool:
        """Connect to the MCP server"""
        print(f"\n🔄 Connecting to {self.server_name}...")

        try:
            # Start the connection task
            self._connection_task = asyncio.create_task(self._connection_task_runner())

            # Wait for connection to be established
            max_wait = 20  # seconds
            start_time = asyncio.get_event_loop().time()

            while not self._connected and not self._connection_task.done():
                if asyncio.get_event_loop().time() - start_time > max_wait:
                    print(f"  ⏰ Connection timeout for {self.server_name}")
                    await self.disconnect()
                    return False

                await asyncio.sleep(0.1)

            if self._connection_task.done() and not self._connected:
                # Task finished but not connected - there was an error
                try:
                    await self._connection_task  # This will raise the exception
                except Exception as e:
                    print(f"  ❌ Connection task failed for {self.server_name}: {e}")
                return False

            return self._connected

        except Exception as e:
            print(f"  ❌ Failed to connect to {self.server_name}: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """Disconnect from the server"""
        if not self._connected and not self._connection_task:
            return

        print(f"  🔌 Disconnecting {self.server_name}...")
        self._connected = False

        if self._connection_task and not self._connection_task.done():
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"  ⚠️  Error during disconnect: {e}")

        self.session = None
        self._connection_task = None
        print(f"  ✅ Disconnected {self.server_name}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = {}) -> Optional[Any]:
        """Call a tool on this server"""
        if not self._connected or not self.session:
            raise RuntimeError(f"Server {self.server_name} is not connected")

        try:
            result = await self.session.call_tool(tool_name, arguments or {})
            return result
        except Exception as e:
            print(f"❌ Error calling tool '{tool_name}' on {self.server_name}: {e}")
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected


class MCPServerManager:
    def __init__(self, config_path: str = "configs/server_configs.json"):
        self.config_path = config_path
        self.connections: Dict[str, MCPServerConnection] = {}
        self.all_tools = []

    async def load_config(self) -> Dict[str, Any]:
        """Load MCP server configuration from JSON file"""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            return config.get("mcpServers", {})
        except FileNotFoundError:
            print(f"Configuration file {self.config_path} not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing configuration file: {e}")
            return {}

    async def connect_to_all_servers(self):
        """Connect to all servers"""
        config = await self.load_config()

        if not config:
            print("❌ No server configuration found")
            return False

        print(f"🚀 Found {len(config)} servers in configuration")
        print("🔄 Connecting sequentially for better reliability...")

        successful_connections = 0

        # Create connections for each server
        for server_name, server_config in config.items():
            connection = MCPServerConnection(server_name, server_config)
            success = await connection.connect()

            if success:
                self.connections[server_name] = connection
                self.all_tools.extend(connection.tools)
                successful_connections += 1

            # Small delay between connections
            await asyncio.sleep(0.5)

        print(f"\n🎉 CONNECTION SUMMARY:")
        print(f"   ✅ Successful: {successful_connections}/{len(config)} servers")
        print(f"   📦 Total tools: {len(self.all_tools)}")

        if successful_connections > 0:
            self.print_tools_summary()

        return successful_connections > 0

    def print_tools_summary(self):
        """Print a summary of all available tools grouped by server"""
        print(f"\n{'='*60}")
        print("🛠️  AVAILABLE TOOLS SUMMARY")
        print(f"{'='*60}")

        # Group tools by server
        tools_by_server = {}
        for tool in self.all_tools:
            server = tool["server"]
            if server not in tools_by_server:
                tools_by_server[server] = []
            tools_by_server[server].append(tool)

        for server_name, tools in tools_by_server.items():
            print(f"\n📋 {server_name.upper()} ({len(tools)} tools):")
            for tool in tools:
                print(f"   • {tool['name']}: {tool['description']}")

        print(f"\n{'='*60}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = {}) -> Optional[Any]:
        """Call a specific tool by name"""
        # Find which server has this tool
        tool_info = None
        for tool in self.all_tools:
            if tool["name"] == tool_name:
                tool_info = tool
                break

        if not tool_info:
            print(f"❌ Tool '{tool_name}' not found")
            return None

        server_name = tool_info["server"]
        if server_name not in self.connections:
            print(f"❌ Server '{server_name}' not connected")
            return None

        connection = self.connections[server_name]
        if not connection.is_connected:
            print(f"❌ Server '{server_name}' is not connected")
            return None

        print(f"🔧 Calling {tool_name} on {server_name}...")
        result = await connection.call_tool(tool_name, arguments)
        if result:
            print(f"✅ Tool call successful")
        return result

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
        print("\n🧹 Cleaning up connections...")

        # Disconnect all connections
        disconnect_tasks = []
        for server_name, connection in self.connections.items():
            if connection.is_connected:
                disconnect_tasks.append(connection.disconnect())

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        self.connections.clear()
        self.all_tools.clear()
        print("🧹 Cleanup complete")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.cleanup()


# Example usage
async def main():
    async with MCPServerManager("configs/server_configs.json") as manager:
        # Connect to all servers
        success = await manager.connect_to_all_servers()

        if success:
            # Get tools for OpenAI API
            openai_tools = await manager.get_available_tools_for_openai()
            print(f"\n🤖 Ready for OpenAI integration with {len(openai_tools)} tools")

            # Example tool call (uncomment to test)
            # if openai_tools:
            #     result = await manager.call_tool(openai_tools[0]["name"])
            #     print(f"Test result: {result}")
        else:
            print("❌ No servers connected successfully")


if __name__ == "__main__":
    asyncio.run(main())
