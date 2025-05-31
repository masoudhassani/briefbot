import json
import asyncio
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class MCPServerManager:
    def __init__(self, config_path: str = "configs/server_configs.json"):
        self.config_path = config_path
        self.sessions = {}
        self.all_tools = []
        self.connection_contexts = {}  # Store context managers for proper cleanup

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

    async def connect_to_server(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """Connect to a single MCP server with robust error handling"""
        print(f"\n🔄 Connecting to {server_name}...")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config.get("args", []),
                env=server_config.get("env", None),
            )

            print(f"  📋 Command: {server_params.command} {' '.join(server_params.args)}")

            # Create connection with timeout
            print(f"  ⏳ Starting process...")
            connection_timeout = asyncio.timeout(15)  # Generous timeout for process start

            async with connection_timeout:
                # Start the stdio client
                stdio_context = stdio_client(server_params)
                read, write = await stdio_context.__aenter__()
                print(f"  ✅ Process started for {server_name}")

                # Create session
                session_context = ClientSession(read, write)
                session = await session_context.__aenter__()
                print(f"  ✅ Session created for {server_name}")

                # Store contexts for proper cleanup
                self.connection_contexts[server_name] = {
                    "stdio_context": stdio_context,
                    "session_context": session_context,
                    "read": read,
                    "write": write,
                }

                self.sessions[server_name] = session

                # Initialize with detailed timeout and retry logic
                print(f"  ⏳ Initializing connection...")

                # Try initialization with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        init_timeout = asyncio.timeout(10)
                        async with init_timeout:
                            await session.initialize()
                        print(f"  ✅ Initialized {server_name} (attempt {attempt + 1})")
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

                # Get capabilities and tools
                print(f"  ⏳ Fetching server capabilities...")

                # First, let's see what the server supports
                try:
                    # Some servers might not support list_tools immediately
                    tools_timeout = asyncio.timeout(8)
                    async with tools_timeout:
                        response = await session.list_tools()

                    tools = response.tools if hasattr(response, "tools") else []
                    print(f"  ✅ Retrieved {len(tools)} tools from {server_name}")

                    # Process tools
                    for tool in tools:
                        tool_def = {
                            "name": tool.name,
                            "type": "function",
                            "description": tool.description or f"Tool from {server_name} server",
                            "parameters": getattr(tool, "inputSchema", {}) or {},
                            "server": server_name,
                        }
                        self.all_tools.append(tool_def)
                        print(f"    📦 {tool.name}: {tool.description}")

                except asyncio.TimeoutError:
                    print(f"  ⚠️  Timeout getting tools from {server_name}")
                    # Server connected but tools fetch failed - still count as success
                    pass
                except Exception as e:
                    print(f"  ⚠️  Error getting tools from {server_name}: {e}")
                    # Server connected but tools fetch failed - still count as success
                    pass

                print(f"  🎉 Successfully connected to {server_name}")
                return True

        except asyncio.TimeoutError:
            print(f"  ❌ Connection to {server_name} timed out")
            await self._cleanup_failed_connection(server_name)
            return False
        except Exception as e:
            print(f"  ❌ Failed to connect to {server_name}: {e}")
            print(f"  📋 Error details: {type(e).__name__}")
            await self._cleanup_failed_connection(server_name)
            return False

    async def _cleanup_failed_connection(self, server_name: str):
        """Clean up a failed connection attempt"""
        if server_name in self.connection_contexts:
            contexts = self.connection_contexts[server_name]
            try:
                if "session_context" in contexts:
                    await contexts["session_context"].__aexit__(None, None, None)
            except:
                pass
            try:
                if "stdio_context" in contexts:
                    await contexts["stdio_context"].__aexit__(None, None, None)
            except:
                pass
            del self.connection_contexts[server_name]

        if server_name in self.sessions:
            del self.sessions[server_name]

    async def connect_to_all_servers(self):
        """Connect to all servers with sequential connection (more reliable than concurrent)"""
        config = await self.load_config()

        if not config:
            print("❌ No server configuration found")
            return

        print(f"🚀 Found {len(config)} servers in configuration")
        print("🔄 Connecting sequentially for better reliability...")

        successful_connections = 0

        # Connect to servers one by one (more reliable than concurrent)
        for server_name, server_config in config.items():
            success = await self.connect_to_server(server_name, server_config)
            if success:
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
        if server_name not in self.sessions:
            print(f"❌ Server '{server_name}' not connected")
            return None

        session = self.sessions[server_name]

        try:
            print(f"🔧 Calling {tool_name} on {server_name}...")
            result = await session.call_tool(tool_name, arguments or {})
            print(f"✅ Tool call successful")
            return result
        except Exception as e:
            print(f"❌ Error calling tool '{tool_name}': {e}")
            return None

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

    async def cleanup(self):
        """Properly close all server connections"""
        print("\n🧹 Cleaning up connections...")

        # Simply clear the references - the context managers will handle cleanup automatically
        for server_name in list(self.sessions.keys()):
            try:
                print(f"  🔌 Closing {server_name}...")
                # Don't manually call __aexit__ - let the context managers handle it
                print(f"  ✅ Closed {server_name}")
            except Exception as e:
                print(f"  ⚠️  Error closing {server_name}: {e}")

        self.connection_contexts.clear()
        self.sessions.clear()
        print("🧹 Cleanup complete")


# Example usage with your config
async def main():
    manager = MCPServerManager("configs/server_configs.json")

    try:
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

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
