#!/usr/bin/env python3
"""
Configuration Management for BriefBot
"""

import os
import json
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import logging


# @dataclass
# class SourceConfig:
#     """Configuration for a news source"""

#     name: str
#     enabled: bool = True
#     rate_limit: int = 100  # requests per hour
#     timeout: int = 30
#     retry_count: int = 3
#     custom_headers: Dict[str, str] = {}


# @dataclass
# class TopicConfig:
#     """Configuration for a topic subscription"""

#     name: str
#     keywords: List[str]
#     sources: List[str]
#     exclude_keywords: List[str]
#     priority: str = "medium"
#     max_articles_per_source: int = 10
#     freshness_hours: int = 24


class ConfigManager:
    """Simple configuration manager using YAML"""

    def __init__(
        self,
        configs_path: str = "configs/config.yaml",
        topics_path: str = "configs/topics.yml",
        secrets_path: str = "configs/secrets.yml",
    ):
        # self.configs = self._load_config(path=configs_path)
        # self.topics = self._load_config(path=topics_path)
        self.secrets = self._load_config(path=secrets_path)

    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(path, "r") as file:
                config = yaml.safe_load(file)

            return config
        except FileNotFoundError:
            logging.warning(f"Config file {path} not found")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            "sources": {
                "newsapi": {"enabled": True, "rate_limit": 1000},
                "reddit": {"enabled": True, "rate_limit": 60},
                "rss": {"enabled": True, "rate_limit": 100},
            },
            "notification": {
                "telegram_enabled": True,
                "summary_max_length": 500,
                "include_links": True,
            },
            "topics": [],
            "api_keys": {},
        }

    # def get_source_configs(self, source_name: str) -> SourceConfig:
    #     """Get configuration for a specific source"""
    #     source_data = self.configs.get("sources", {}).get(source_name, {})
    #     return SourceConfig(name=source_name, **source_data)

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service"""
        return self.secrets.get("api_keys", {}).get(service)

    # def get_notification_configs(self, notifier: str) -> Dict[str, Any]:
    #     """Get notification configuration"""
    #     return self.configs.get("notifications", {}).get(notifier, {})

    # def get_topics(self) -> TopicConfig:
    #     """Get notification configuration"""
    #     return self.topics.get("topics", {})
