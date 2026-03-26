import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import NewsItem, SentimentConfig
from .spiders.base_spider import BaseSpider
from .spiders.twitter_spider import TwitterSpider
from .spiders.crypto_news import CryptoNewsSpider
from .spiders.finance_news import FinanceNewsSpider
from .spiders.social_news import SocialNewsSpider
from .spiders.rss_aggregator import RSSAggregator
from .spiders.decrypt_spider import DecryptSpider
from .spiders.bitcoinist_spider import BitcoinistSpider
from .spiders.ccn_spider import CCNSpider
from .spiders.fxstreet_spider import FXStreetSpider
from .spiders.investing_spider import InvestingSpider
from .storage.base_storage import BaseStorage
from .storage.postgres_storage import PostgreSQLStorage
from .storage.mysql_storage import MySQLStorage
from .storage.sqlite_storage import SQLiteStorage
from .cache.memory_cache import MemoryCache
from .cache.redis_cache import RedisCache
from .search.elasticsearch_client import ElasticsearchClient
from .scheduler.crawler_scheduler import CrawlerScheduler

logger = logging.getLogger(__name__)


class EnhancedNewsAggregator:
    def __init__(self, config: Dict):
        self.config = config
        self.spiders: List[BaseSpider] = []
        self.sentiment_config = SentimentConfig(
            positive_words=config.get("sentiment", {}).get("positive_words", [
                "bull", "bullish", "rise", "gain", "surge", "rally", "growth",
                "positive", "upgrade", "strong", "突破", "上涨", "利好", "增长"
            ]),
            negative_words=config.get("sentiment", {}).get("negative_words", [
                "bear", "bearish", "fall", "drop", "plunge", "crash", "decline",
                "negative", "downgrade", "weak", "crisis", "下跌", "暴跌", "利空", "衰退"
            ])
        )
        self.keywords = config.get("keywords", [])
        self.cache = self._init_cache()
        self.storage = self._init_storage()
        self.search = self._init_search()
        self.scheduler = self._init_scheduler()
        self._init_spiders()

    def _init_spiders(self) -> None:
        sources_config = self.config.get("sources", {})

        twitter_config = sources_config.get("twitter", {})
        if twitter_config.get("enabled", True):
            self.spiders.append(TwitterSpider(twitter_config))

        crypto_config = sources_config.get("crypto", {})
        if crypto_config.get("enabled", True):
            self.spiders.append(CryptoNewsSpider(crypto_config))

        finance_config = sources_config.get("finance", {})
        if finance_config.get("enabled", True):
            self.spiders.append(FinanceNewsSpider(finance_config))

        social_config = sources_config.get("social", {})
        if social_config.get("enabled", True):
            self.spiders.append(SocialNewsSpider(social_config))

        rss_config = sources_config.get("rss", {})
        if rss_config.get("enabled", True):
            self.spiders.append(RSSAggregator(rss_config))

        decrypt_config = sources_config.get("decrypt", {})
        if decrypt_config.get("enabled", False):
            self.spiders.append(DecryptSpider(decrypt_config))

        bitcoinist_config = sources_config.get("bitcoinist", {})
        if bitcoinist_config.get("enabled", False):
            self.spiders.append(BitcoinistSpider(bitcoinist_config))

        ccn_config = sources_config.get("ccn", {})
        if ccn_config.get("enabled", False):
            self.spiders.append(CCNSpider(ccn_config))

        fxstreet_config = sources_config.get("fxstreet", {})
        if fxstreet_config.get("enabled", False):
            self.spiders.append(FXStreetSpider(fxstreet_config))

        investing_config = sources_config.get("investing", {})
        if investing_config.get("enabled", False):
            self.spiders.append(InvestingSpider(investing_config))

        logger.info(f"Initialized {len(self.spiders)} spiders")

    def _init_cache(self):
        cache_config = self.config.get("cache", {})
        cache_type = cache_config.get("type", "memory")

        if cache_type == "redis":
            return RedisCache(cache_config)
        return MemoryCache(cache_config)

    def _init_storage(self) -> Optional[BaseStorage]:
        storage_config = self.config.get("storage", {})
        storage_type = storage_config.get("type", "postgresql")

        storage: BaseStorage
        if storage_type == "postgresql":
            storage = PostgreSQLStorage(storage_config)
        elif storage_type == "mysql":
            storage = MySQLStorage(storage_config)
        elif storage_type == "sqlite":
            storage = SQLiteStorage(storage_config)
        else:
            logger.warning(f"Unknown storage type: {storage_type}")
            return None

        storage.connect()
        storage.init_schema()
        return storage

    def _init_search(self) -> Optional[ElasticsearchClient]:
        es_config = self.config.get("elasticsearch", {})
        if not es_config.get("enabled", False):
            return None

        client = ElasticsearchClient(es_config)
        if client.connect():
            return client
        return None

    def _init_scheduler(self) -> Optional[CrawlerScheduler]:
        scheduler_config = self.config.get("scheduler", {})
        if not scheduler_config.get("enabled", True):
            return None

        scheduler = CrawlerScheduler(scheduler_config)
        scheduler.add_job(self.fetch_and_store_news)
        return scheduler

    def start_scheduler(self) -> None:
        if self.scheduler:
            self.scheduler.start()
            logger.info("News scheduler started")

    def stop_scheduler(self) -> None:
        if self.scheduler:
            self.scheduler.stop()
            logger.info("News scheduler stopped")

    def fetch_all_news(self,
                       keywords: Optional[List[str]] = None,
                       limit_per_source: int = 10,
                       total_limit: int = 50,
                       use_cache: bool = True) -> List[NewsItem]:
        keywords = keywords or self.keywords
        cache_key = f"news:{','.join(keywords)}:{total_limit}"

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.info("Returning cached news")
                return [NewsItem.from_dict(c) for c in cached]

        all_news = []
        for spider in self.spiders:
            if not spider.enabled:
                continue
            try:
                news = spider.fetch_news(keywords, limit_per_source)
                all_news.extend(news)
            except Exception as e:
                logger.error(f"Failed to fetch from {spider.__class__.__name__}: {e}")

        all_news = self._deduplicate_news(all_news)
        all_news = self._analyze_sentiments(all_news)
        all_news.sort(key=lambda x: x.published_at or datetime.now(), reverse=True)
        result = all_news[:total_limit]

        if use_cache:
            cache_ttl = self.config.get("cache", {}).get("ttl", 300)
            self.cache.set(cache_key, [n.to_dict() for n in result], cache_ttl)

        return result

    def fetch_and_store_news(self,
                            keywords: Optional[List[str]] = None,
                            limit_per_source: int = 10,
                            total_limit: int = 50) -> int:
        news = self.fetch_all_news(keywords, limit_per_source, total_limit, use_cache=False)

        if self.storage and self.storage.is_connected():
            saved = self.storage.save_batch(news)
            logger.info(f"Saved {saved} news items to storage")
            return saved

        return 0

    def _deduplicate_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        seen_urls = set()
        unique_news = []
        for item in news_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_news.append(item)
        return unique_news

    def _analyze_sentiments(self, news_items: List[NewsItem]) -> List[NewsItem]:
        positive_words = set(self.sentiment_config.positive_words)
        negative_words = set(self.sentiment_config.negative_words)

        for item in news_items:
            text = (item.title + " " + item.description).lower()

            positive_count = sum(1 for word in positive_words if word in text)
            negative_count = sum(1 for word in negative_words if word in text)

            if positive_count > negative_count * 1.5:
                item.sentiment = "positive"
            elif negative_count > positive_count * 1.5:
                item.sentiment = "negative"
            else:
                item.sentiment = "neutral"

            item.relevance_score = self._calculate_relevance(text, positive_count + negative_count)

        return news_items

    def _calculate_relevance(self, text: str, match_count: int) -> float:
        base_score = min(len(text.split()) / 20, 1.0)
        match_bonus = min(match_count / 10, 0.3)
        return min(base_score + match_bonus, 1.0)

    def get_sentiment_summary(self, news_items: List[NewsItem]) -> Dict:
        if not news_items:
            return {
                "overall": "neutral",
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "total_news": 0
            }

        positive = sum(1 for item in news_items if item.sentiment == "positive")
        negative = sum(1 for item in news_items if item.sentiment == "negative")
        neutral = len(news_items) - positive - negative
        total = len(news_items)

        if positive / total > 0.6:
            overall = "positive"
        elif negative / total > 0.6:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "overall": overall,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "positive_ratio": positive / total,
            "negative_ratio": negative / total,
            "total_news": total
        }

    def filter_by_relevance(self,
                           news_items: List[NewsItem],
                           min_score: float = 0.3) -> List[NewsItem]:
        return [item for item in news_items if item.relevance_score >= min_score]

    def group_by_source(self, news_items: List[NewsItem]) -> Dict[str, List[NewsItem]]:
        groups = {}
        for item in news_items:
            if item.source not in groups:
                groups[item.source] = []
            groups[item.source].append(item)
        return groups

    def group_by_sentiment(self, news_items: List[NewsItem]) -> Dict[str, List[NewsItem]]:
        groups = {"positive": [], "negative": [], "neutral": []}
        for item in news_items:
            groups[item.sentiment].append(item)
        return groups

    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        if self.search and self.search.is_connected():
            return self.search.search(query, limit)
        return []

    def get_news_from_storage(self,
                             keywords: Optional[List[str]] = None,
                             limit: int = 50,
                             since_hours: int = 24) -> List[NewsItem]:
        if not self.storage or not self.storage.is_connected():
            return []

        since = datetime.now() - timedelta(hours=since_hours)
        return self.storage.get_news(keywords or self.keywords, limit, since)

    def get_status(self) -> Dict:
        return {
            "spiders_count": len(self.spiders),
            "spiders": [s.__class__.__name__ for s in self.spiders if s.enabled],
            "storage_connected": self.storage.is_connected() if self.storage else False,
            "cache_size": self.cache.size(),
            "search_connected": self.search.is_connected() if self.search else False,
            "scheduler_running": self.scheduler.is_running() if self.scheduler else False,
        }

    def cleanup(self, days: int = 7) -> int:
        deleted = 0
        if self.storage and self.storage.is_connected():
            deleted += self.storage.delete_old_news(days)

        if self.search and self.search.is_connected():
            deleted += self.search.delete_old_news(days)

        if self.cache.size() > 1000:
            self.cache.cleanup()

        return deleted
