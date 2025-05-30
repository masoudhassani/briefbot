from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MathServer", stateless_http=True)


@mcp.tool(description="A simple coversion tool")
def convert(n: float) -> float:
    """
    Converts speed in km/h to m/s.
    Args:
        n: Speed in km/h.
    Returns:
        The result converted to m/s.
    """

    return n / 3.6


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
