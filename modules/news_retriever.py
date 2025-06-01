import requests
import yaml
import os
from modules.utils import load_yaml_config
from typing import List, Dict, Any, Optional
import logging

logging.basicConfig(level=logging.ERROR)


class NewsRetriever:
    def __init__(
        self,
        config_path: str = "configs/configs.yml",
        topics_path: str = "configs/topics.yml",
        secrets_path: str = "configs/secrets.yml",
    ):
        self.topic_configs = load_yaml_config(topics_path, "topics")
        self.secrets = load_yaml_config(secrets_path, "newsapi")
        self.news_api_key = self.secrets.get("api_key", "")

    def fetch_all(self, topic: str) -> List[Dict[str, Any]]:
        """
        Fetches news articles for a given topic using configured sources.
        Args:
            topic (str): Name of the topic to fetch articles for.
        Returns:
            List[Dict[str, Any]]: List of articles matching the topic and keywords.
        """
        self.topic_conf = self.topic_configs.get(topic, {})
        keyword_list = self.topic_conf.get("keywords", None)
        limit = self.topic_conf.get("limit", 5)

        articles = self._fetch_newsapi(topic=topic, limit=limit, keyword_list=keyword_list)
        return articles[:limit]

    def _filter(self, entries, topic):
        results = []
        excluded_keywords = self.topic_conf.get("excluded_keywords", [])
        for entry in entries:
            text = entry.get("title", "") + " " + entry.get("description", "")
            if not any(bad.lower() in text.lower() for bad in excluded_keywords):
                results.append(entry)
        return results

    def _fetch_newsapi(
        self, topic: str, limit: int = 5, keyword_list: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if keyword_list:
            url = f"https://newsapi.org/v2/everything?q={' OR '.join(keyword_list)}&language=en&pageSize={limit}"
        else:
            url = f"https://newsapi.org/v2/everything?q={topic}&language=en&pageSize={limit}"

        headers = {"Authorization": self.news_api_key}
        try:
            r = requests.get(url, headers=headers)
            data = r.json()
            articles = data.get("articles", [])
            return self._filter(articles, topic)

        except Exception as e:
            logging.error("NewsAPI error:", e)
            return []
