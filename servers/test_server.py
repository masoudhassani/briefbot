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


@mcp.tool()
def get_current_weather(city: str) -> str:
    """Get the current weather for a given city"""

    endpoint = "https://wttr.in"
    response = requests.get(f"{endpoint}/{city}")
    return response.text


if __name__ == "__main__":
    mcp.run(transport="stdio")
