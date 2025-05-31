import asyncio
import subprocess
import sys
from pathlib import Path


class MCPDebugHelper:
    """Helper class to debug MCP server connection issues"""

    @staticmethod
    async def test_server_executable(command: str, args: list = None):
        """Test if the server executable can be started"""
        args = args or []
        full_command = [command] + args

        print(f"Testing command: {' '.join(full_command)}")

        try:
            # Test if command exists
            result = subprocess.run(
                ["which", command] if sys.platform != "win32" else ["where", command],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"❌ Command '{command}' not found in PATH")
                return False

            print(f"✅ Command '{command}' found at: {result.stdout.strip()}")

            # Try to run the command with --help or --version
            for flag in ["--help", "--version", "-h", "-v"]:
                try:
                    result = subprocess.run(
                        full_command + [flag], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        print(f"✅ Command responds to {flag}")
                        return True
                except subprocess.TimeoutExpired:
                    print(f"⚠️  Command timed out with {flag}")
                except Exception as e:
                    print(f"⚠️  Error testing {flag}: {e}")

            return True

        except Exception as e:
            print(f"❌ Error testing command: {e}")
            return False

    @staticmethod
    async def test_simple_connection(command: str, args: list = None):
        """Test a simple MCP connection without full session"""
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        args = args or []
        print(f"\n🔍 Testing simple connection to: {command} {' '.join(args)}")

        try:
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=None,
            )

            # Start the process and see if it responds
            async with asyncio.timeout(10):
                async with stdio_client(server_params) as (read, write):
                    print("✅ Process started successfully")

                    # Try to read some initial output
                    try:
                        # Give the server a moment to start
                        await asyncio.sleep(1)
                        print("✅ Connection established")
                        return True
                    except Exception as e:
                        print(f"⚠️  Warning during connection test: {e}")
                        return True  # Process started, that's good enough

        except asyncio.TimeoutError:
            print("❌ Connection timed out")
            return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False


# Comprehensive debug function
async def debug_mcp_config(config_path: str = "configs/server_configs.json"):
    """Debug all servers in your MCP configuration"""
    import json

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        servers = config.get("mcpServers", {})
    except Exception as e:
        print(f"❌ Could not load config: {e}")
        return

    print("🔍 DEBUGGING MCP SERVER CONFIGURATION")
    print("=" * 50)

    for server_name, server_config in servers.items():
        print(f"\n📋 Testing {server_name.upper()} server:")
        command = server_config["command"]
        args = server_config.get("args", [])

        # Test 1: Check if executable exists
        exe_ok = await MCPDebugHelper.test_server_executable(command, args)

        if exe_ok:
            # Test 2: Try simple connection
            conn_ok = await MCPDebugHelper.test_simple_connection(command, args)

            if conn_ok:
                print(f"✅ {server_name} appears to be working")
            else:
                print(f"❌ {server_name} executable exists but connection failed")
        else:
            print(f"❌ {server_name} executable not found or not working")

    print("\n" + "=" * 50)
    print("🔍 DEBUGGING TIPS:")
    print("1. Make sure all commands are installed and in your PATH")
    print("2. Try running each command manually first")
    print("3. Check if you need to activate virtual environments")
    print("4. For npm packages, ensure they're globally installed or use npx")
    print("5. For uv/uvx commands, make sure uv is installed and working")


# Simple test for your original single-server approach
async def debug_single_server():
    """Debug a single server connection step by step"""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Test with a simple server first
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "servers.test_server"],
        env=None,
    )

    print("🔍 Testing single server connection step by step...")

    try:
        print("Step 1: Creating stdio client...")
        async with stdio_client(server_params) as (read, write):
            print("✅ Step 1 passed - stdio client created")

            print("Step 2: Creating client session...")
            async with ClientSession(read, write) as session:
                print("✅ Step 2 passed - client session created")

                print("Step 3: Initializing session...")
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                print("✅ Step 3 passed - session initialized")

                print("Step 4: Listing tools...")
                response = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                print(f"✅ Step 4 passed - found {len(response.tools)} tools")

                for tool in response.tools:
                    print(f"  - {tool.name}: {tool.description}")

    except asyncio.TimeoutError as e:
        print(f"❌ Timeout during connection: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run debugging
    print("Choose debug option:")
    print("1. Debug config file servers")
    print("2. Debug single server")

    choice = input("Enter 1 or 2: ")

    if choice == "1":
        asyncio.run(debug_mcp_config())
    else:
        asyncio.run(debug_single_server())
