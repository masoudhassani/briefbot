from servers.news_server import fetch_news
import asyncio

news = fetch_news("Nvidia")
print("Latest news on Python programming:")
for article in news:
    print(f"Title: {article['title']}")
    print(f"Summary: {article['summary']}")
    print(f"URL: {article['url']}")
    print(f"Publisher: {article['publisher']}\n")
