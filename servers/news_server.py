from mcp.server.fastmcp import FastMCP

from modules.news_retriever import NewsRetriever
from modules.data_structure import BooleanMessage
from typing import List, Dict
import logging


# Setup
mcp = FastMCP("News Server")
fetcher = NewsRetriever()
logging.basicConfig(level=logging.ERROR)


@mcp.tool()
def fetch_news(topic: str) -> List[Dict] | str:
    """Returns a list of latest news for a topic"""
    if not topic:
        logging.error("Topic name must be provided")
        return BooleanMessage.failure

    articles = fetcher.fetch_all(topic)
    return [
        {
            "title": a["title"],
            "summary": a.get("description", ""),
            "publisher": a.get("source", {}).get("name", ""),
            "url": a.get("url", ""),
        }
        for a in articles
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
