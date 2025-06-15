import requests
from mcp.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("Test Server")


@mcp.tool()
def get_weather(city: str) -> str:
    """Get the current weather and weather focast for a given city"""

    endpoint = "https://wttr.in"
    response = requests.get(f"{endpoint}/{city}")
    return response.text


if __name__ == "__main__":
    mcp.run(transport="stdio")
