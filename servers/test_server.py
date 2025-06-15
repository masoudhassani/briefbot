import random

import requests
from mcp.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("Test Server")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.tool()
def get_secret_word() -> str:
    """Get a secret word"""
    return random.choice(["apple", "banana", "cherry"])


if __name__ == "__main__":
    mcp.run(transport="stdio")
