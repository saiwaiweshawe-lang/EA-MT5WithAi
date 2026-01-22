# 免费新闻API集成模块
# 集成多个免费新闻源，获取市场相关信息

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    description: str
    url: str
    source: str
    published_at: str
    sentiment: str = "neutral"
    relevance_score: float = 0.0
    categories: List[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = []


class BaseNewsAPI:
    """新闻API基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.rate_limit = config.get("rate_limit", 10)  # 每分钟请求数
        self.request_count = 0
        self.last_request_time = None

    def _check_rate_limit(self):
        """检查速率限制"""
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < 60 and self.request_count >= self.rate_limit:
                wait_time = 60 - elapsed
                logger.warning(f"达到速率限制，等待 {wait_time:.1f} 秒")
                return False

        return True

    def _record_request(self):
        """记录请求"""
        now = datetime.now()
        if self.last_request_time and (now - self.last_request_time).total_seconds() >= 60:
            self.request_count = 0

        self.request_count += 1
        self.last_request_time = now

    @abstractmethod
    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        """获取新闻"""
        pass


class CryptoCompareAPI(BaseNewsAPI):
    """CryptoCompare 新闻API（免费）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = "https://min-api.cryptocompare.com/data/v2"

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        """获取加密货币新闻"""
        if not self.enabled:
            return []

        if not self._check_rate_limit():
            return []

        try:
            url = f"{self.base_url}/news/"
            params = {
                "lang": "EN",
                "sortOrder": "latest"
            }

            if self.api_key:
                params["api_key"] = self.api_key

            response = requests.get(url, params=params, timeout=10)
            self._record_request()

            data = response.json()

            if data.get("Response") != "Success":
                logger.error(f"CryptoCompare API错误: {data.get('Message', '未知错误')}")
                return []

            news_items = []
            for item in data.get("Data", [])[:limit]:
                news_items.append(NewsItem(
                    title=item.get("title", ""),
                    description=item.get("body", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "CryptoCompare"),
                    published_at=datetime.fromtimestamp(item.get("published_on", 0)).isoformat(),
                    categories=item.get("categories", "").split("|") if item.get("categories") else []
                ))

            logger.info(f"CryptoCompare: 获取 {len(news_items)} 条新闻")
            return news_items

        except Exception as e:
            logger.error(f"CryptoCompare请求失败: {e}")
            return []


class NewsAPI(BaseNewsAPI):
    """NewsAPI.org（免费计划）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = "https://newsapi.org/v2"

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        """获取新闻"""
        if not self.enabled or not self.api_key:
            return []

        if not self._check_rate_limit():
            return []

        try:
            # 构建查询
            query = " OR ".join(keywords)

            url = f"{self.base_url}/everything"
            params = {
                "q": query,
                "apiKey": self.api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "from": (datetime.now() - timedelta(hours=24)).isoformat()
            }

            response = requests.get(url, params=params, timeout=10)
            self._record_request()

            data = response.json()

            if data.get("status") != "ok":
                logger.error(f"NewsAPI错误: {data.get('message', '未知错误')}")
                return []

            news_items = []
            for item in data.get("articles", []):
                news_items.append(NewsItem(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "NewsAPI"),
                    published_at=item.get("publishedAt", "")
                ))

            logger.info(f"NewsAPI: 获取 {len(news_items)} 条新闻")
            return news_items

        except Exception as e:
            logger.error(f"NewsAPI请求失败: {e}")
            return []


class RSSNewsSource(BaseNewsAPI):
    """RSS新闻源（完全免费）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.feeds = config.get("feeds", [
            "https://feeds.feedburner.com/coindesk",
            "https://cointelegraph.com/rss",
            "https://finance.yahoo.com/rss/2.0/headline",
            "https://www.forexfactory.com/news.php?do=rss"
        ])

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        """获取RSS新闻"""
        if not self.enabled:
            return []

        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser未安装，RSS功能不可用")
            return []

        all_news = []

        for feed_url in self.feeds:
            try:
                if not self._check_rate_limit():
                    break

                feed = feedparser.parse(feed_url)
                self._record_request()

                source_name = feed.feed.get("title", "RSS")

                for entry in feed.entries:
                    # 检查是否匹配关键词
                    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
                    if not any(kw.lower() in text for kw in keywords):
                        continue

                    news_items.append(NewsItem(
                        title=entry.get("title", ""),
                        description=entry.get("description", "")[:500],
                        url=entry.get("link", ""),
                        source=source_name,
                        published_at=entry.get("published", "")
                    ))

                logger.info(f"RSS {source_name}: 解析 {len(feed.entries)} 条新闻")

            except Exception as e:
                logger.error(f"RSS解析失败 {feed_url}: {e}")

        # 按时间排序并限制数量
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        return all_news[:limit]


class FinnhubAPI(BaseNewsAPI):
    """Finnhub 新闻API（免费计划）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = "https://finnhub.io/api/v1"

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        """获取外汇/股市新闻"""
        if not self.enabled or not self.api_key:
            return []

        if not self._check_rate_limit():
            return []

        try:
            url = f"{self.base_url}/news"
            params = {
                "category": "forex",
                "token": self.api_key,
                "minId": 0
            }

            response = requests.get(url, params=params, timeout=10)
            self._record_request()

            data = response.json()

            if not isinstance(data, list):
                logger.error(f"Finnhub API错误")
                return []

            news_items = []
            for item in data[:limit]:
                # 检查关键词匹配
                text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
                if not any(kw.lower() in text for kw in keywords):
                    continue

                news_items.append(NewsItem(
                    title=item.get("headline", ""),
                    description=item.get("summary", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "Finnhub"),
                    published_at=datetime.fromtimestamp(item.get("datetime", 0)).isoformat()
                ))

            logger.info(f"Finnhub: 获取 {len(news_items)} 条新闻")
            return news_items

        except Exception as e:
            logger.error(f"Finnhub请求失败: {e}")
            return []


class TwitterNewsSource(BaseNewsAPI):
    """Twitter/X 新闻源（需要Nitter或Twitter API）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.nitter_instances = config.get("nitter_instances", [
            "https://nitter.net",
            "https://nitter.poast.org",
            "https://nitter.fdn.fr"
        ])
        self.accounts = config.get("accounts", [
            "CryptoCom",
            "binance",
            "coindesk",
            "forexcom",
            "ReutersFinance"
        ])

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        """从Twitter获取新闻推文"""
        if not self.enabled:
            return []

        all_news = []

        for account in self.accounts[:3]:  # 限制账户数量
            for instance in self.nitter_instances:
                try:
                    if not self._check_rate_limit():
                        break

                    url = f"{instance}/{account}"
                    response = requests.get(url, timeout=10)

                    if response.status_code != 200:
                        continue

                    self._record_request()

                    # 简单解析（实际需要更复杂的HTML解析）
                    import re

                    tweet_pattern = r'<div class="tweet-content[^>]*>(.*?)</div>'
                    tweets = re.findall(tweet_pattern, response.text, re.DOTALL)

                    for tweet in tweets[:limit]:
                        # 清理HTML标签
                        text = re.sub(r'<[^>]+>', '', tweet)
                        text = ' '.join(text.split())

                        if len(text) < 20:
                            continue

                        # 检查关键词
                        if not any(kw.lower() in text.lower() for kw in keywords):
                            continue

                        all_news.append(NewsItem(
                            title=text[:100],
                            description=text,
                            url=url,
                            source=f"Twitter @{account}",
                            published_at=datetime.now().isoformat()
                        ))

                    if all_news:
                        break

                except Exception as e:
                    logger.debug(f"Twitter获取失败 {instance}/{account}: {e}")

        return all_news[:limit]


class NewsAggregator:
    """新闻聚合器 - 整合多个新闻源"""

    def __init__(self, config: Dict):
        self.config = config
        self.sources = []
        self.sentiment_analyzer = SentimentAnalyzer(config.get("sentiment", {}))

        self._init_sources()

    def _init_sources(self):
        """初始化新闻源"""
        sources_config = self.config.get("sources", {})

        if sources_config.get("cryptocompare", {}).get("enabled", False):
            self.sources.append(CryptoCompareAPI(sources_config["cryptocompare"]))

        if sources_config.get("newsapi", {}).get("enabled", False):
            self.sources.append(NewsAPI(sources_config["newsapi"]))

        if sources_config.get("rss", {}).get("enabled", True):
            self.sources.append(RSSNewsSource(sources_config["rss"]))

        if sources_config.get("finnhub", {}).get("enabled", False):
            self.sources.append(FinnhubAPI(sources_config["finnhub"]))

        if sources_config.get("twitter", {}).get("enabled", False):
            self.sources.append(TwitterNewsSource(sources_config["twitter"]))

        logger.info(f"已初始化 {len(self.sources)} 个新闻源")

    def fetch_all_news(self,
                     keywords: List[str],
                     limit_per_source: int = 10,
                     total_limit: int = 50) -> List[NewsItem]:
        """从所有源获取新闻"""
        all_news = []

        for source in self.sources:
            if not source.enabled:
                continue

            try:
                news = source.fetch_news(keywords, limit_per_source)
                all_news.extend(news)
            except Exception as e:
                logger.error(f"从 {source.__class__.__name__} 获取新闻失败: {e}")

        # 去重
        seen_urls = set()
        unique_news = []
        for item in all_news:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_news.append(item)

        # 按时间排序
        unique_news.sort(key=lambda x: x.published_at, reverse=True)

        # 分析情绪
        unique_news = self._analyze_sentiments(unique_news)

        return unique_news[:total_limit]

    def _analyze_sentiments(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """分析新闻情绪"""
        for item in news_items:
            text = item.title + " " + item.description
            item.sentiment = self.sentiment_analyzer.analyze(text)
            item.relevance_score = self._calculate_relevance(text)

        return news_items

    def _calculate_relevance(self, text: str) -> float:
        """计算相关性得分"""
        # 简化实现：根据标题长度和关键词数量
        score = min(len(text.split()) / 20, 1.0)
        return score

    def get_sentiment_summary(self, news_items: List[NewsItem]) -> Dict:
        """获取情绪摘要"""
        if not news_items:
            return {
                "overall": "neutral",
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0
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
        """过滤相关性低的新闻"""
        return [item for item in news_items if item.relevance_score >= min_score]

    def group_by_category(self,
                        news_items: List[NewsItem]) -> Dict[str, List[NewsItem]]:
        """按类别分组新闻"""
        groups = {}

        for item in news_items:
            for category in item.categories:
                if category not in groups:
                    groups[category] = []
                groups[category].append(item)

        return groups


class SentimentAnalyzer:
    """简单的情绪分析器"""

    def __init__(self, config: Dict):
        self.positive_words = set(config.get("positive_words", [
            "bull", "bullish", "rise", "gain", "surge", "rally", "growth",
            "positive", "upgrade", "strong", "突破", "上涨", "利好", "增长"
        ]))
        self.negative_words = set(config.get("negative_words", [
            "bear", "bearish", "fall", "drop", "plunge", "crash", "decline",
            "negative", "downgrade", "weak", "crisis", "下跌", "暴跌", "利空", "衰退"
        ]))

    def analyze(self, text: str) -> str:
        """分析文本情绪"""
        text_lower = text.lower()

        positive_count = sum(1 for word in self.positive_words if word in text_lower)
        negative_count = sum(1 for word in self.negative_words if word in text_lower)

        if positive_count > negative_count * 1.5:
            return "positive"
        elif negative_count > positive_count * 1.5:
            return "negative"
        else:
            return "neutral"


def create_news_aggregator(config_path: str) -> NewsAggregator:
    """创建新闻聚合器"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return NewsAggregator(config.get("news", {}))


if __name__ == "__main__":
    # 测试代码
    config = {
        "sources": {
            "rss": {
                "enabled": True,
                "feeds": [
                    "https://feeds.feedburner.com/coindesk"
                ]
            },
            "cryptocompare": {
                "enabled": False,
                "api_key": ""
            }
        }
    }

    aggregator = NewsAggregator(config)

    # 获取比特币相关新闻
    news = aggregator.fetch_all_news(["bitcoin", "btc", "crypto"], limit_per_source=5)

    print(f"\n获取到 {len(news)} 条新闻:\n")

    for item in news:
        print(f"\n[{item.source}] {item.published_at}")
        print(f"  {item.title}")
        print(f"  情绪: {item.sentiment}, 相关性: {item.relevance_score:.2f}")

    # 情绪摘要
    summary = aggregator.get_sentiment_summary(news)
    print(f"\n情绪摘要: {summary}")
