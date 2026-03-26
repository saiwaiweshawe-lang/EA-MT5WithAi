from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class NewsItem:
    title: str
    description: str
    url: str
    source: str
    source_type: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=datetime.now)
    sentiment: str = "neutral"
    relevance_score: float = 0.0
    categories: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.sentiment not in ("positive", "negative", "neutral"):
            self.sentiment = "neutral"
        if not 0.0 <= self.relevance_score <= 1.0:
            self.relevance_score = max(0.0, min(1.0, self.relevance_score))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "source_type": self.source_type,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "sentiment": self.sentiment,
            "relevance_score": self.relevance_score,
            "categories": self.categories,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        published_at = data.get("published_at")
        if published_at and isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at)
            except ValueError:
                published_at = None

        fetched_at = data.get("fetched_at")
        if fetched_at and isinstance(fetched_at, str):
            try:
                fetched_at = datetime.fromisoformat(fetched_at)
            except ValueError:
                fetched_at = datetime.now()
        elif not fetched_at:
            fetched_at = datetime.now()

        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            url=data.get("url", ""),
            source=data.get("source", ""),
            source_type=data.get("source_type", ""),
            author=data.get("author"),
            published_at=published_at,
            fetched_at=fetched_at,
            sentiment=data.get("sentiment", "neutral"),
            relevance_score=data.get("relevance_score", 0.0),
            categories=data.get("categories", []),
        )


@dataclass
class SentimentConfig:
    positive_words: List[str] = field(default_factory=lambda: [
        "bull", "bullish", "rise", "gain", "surge", "rally", "growth",
        "positive", "upgrade", "strong", "breakout", "high", "up"
    ])
    negative_words: List[str] = field(default_factory=lambda: [
        "bear", "bearish", "fall", "drop", "plunge", "crash", "decline",
        "negative", "downgrade", "weak", "crisis", "low", "down", "sell"
    ])


@dataclass
class StorageConfig:
    type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    database: str = "trading_news"
    username: str = "user"
    password: str = "password"


@dataclass
class CacheConfig:
    type: str = "memory"
    ttl: int = 300
    redis_url: Optional[str] = None


@dataclass
class SchedulerConfig:
    enabled: bool = True
    interval_seconds: int = 300
    cron_expression: Optional[str] = None


@dataclass
class ElasticsearchConfig:
    enabled: bool = False
    hosts: List[str] = field(default_factory=lambda: ["localhost:9200"])
    index: str = "news_articles"
