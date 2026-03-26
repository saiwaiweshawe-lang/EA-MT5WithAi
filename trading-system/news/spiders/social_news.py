import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from ..models import NewsItem
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class SocialNewsSpider(BaseSpider):
    REDDIT_SUBREDDITS = {
        "cryptocurrency": {
            "name": "r/Cryptocurrency",
            "rss_url": "https://www.reddit.com/r/Cryptocurrency/.rss",
        },
        "bitcoin": {
            "name": "r/Bitcoin",
            "rss_url": "https://www.reddit.com/r/Bitcoin/.rss",
        },
        "ethereum": {
            "name": "r/Ethereum",
            "rss_url": "https://www.reddit.com/r/ethereum/.rss",
        },
        "bitcoincash": {
            "name": "r/Bitcoincash",
            "rss_url": "https://www.reddit.com/r/Bitcoincash/.rss",
        },
        "solana": {
            "name": "r/Solana",
            "rss_url": "https://www.reddit.com/r/Solana/.rss",
        },
    }

    TELEGRAM_CHANNELS = {
        "crypto": {
            "name": "Telegram Crypto",
            "rss_url": "https://rsshub.app/telegram/channel/cryptocurrency",
        },
        "bitcoin": {
            "name": "Telegram Bitcoin",
            "rss_url": "https://rsshub.app/telegram/channel/bitcoinschema",
        },
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.reddit_enabled = config.get("reddit_enabled", True)
        self.telegram_enabled = config.get("telegram_enabled", True)
        self.reddit_subreddits = config.get("reddit", list(self.REDDIT_SUBREDDITS.keys()))
        self.telegram_channels = config.get("telegram", list(self.TELEGRAM_CHANNELS.keys()))

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        if not self.enabled:
            return []

        all_news = []
        search_keywords = keywords or self.keywords

        if self.reddit_enabled:
            reddit_news = self._fetch_reddit(search_keywords, limit)
            all_news.extend(reddit_news)

        if self.telegram_enabled:
            telegram_news = self._fetch_telegram(search_keywords, limit)
            all_news.extend(telegram_news)

        return all_news[:limit]

    def _fetch_reddit(self, keywords: List[str], limit: int) -> List[NewsItem]:
        all_news = []

        for subreddit_id in self.reddit_subreddits:
            if len(all_news) >= limit:
                break

            subreddit = self.REDDIT_SUBREDDITS.get(subreddit_id)
            if not subreddit:
                continue

            news = self._fetch_subreddit(subreddit_id, subreddit, keywords, limit)
            all_news.extend(news)

        return all_news

    def _fetch_subreddit(self, subreddit_id: str, subreddit: Dict,
                        keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            import feedparser

            rss_url = subreddit.get("rss_url")
            if not rss_url:
                return []

            response = self._fetch_url(rss_url)
            if not response:
                return []

            feed = feedparser.parse(response.text)
            news_items = []

            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                description = self._extract_reddit_description(entry)

                if not title:
                    continue

                text = title + " " + description
                if keywords and not any(kw.lower() in text.lower() for kw in keywords):
                    continue

                author = ""
                if hasattr(entry, 'author_detail') and entry.author_detail:
                    author = entry.author_detail.get("name", "")

                published_at = self._parse_rss_date(entry.get("published"))

                news_items.append(NewsItem(
                    title=title,
                    description=description[:500],
                    url=link,
                    source=subreddit.get("name", subreddit_id),
                    source_type="social",
                    author=author,
                    published_at=published_at,
                    fetched_at=datetime.now(),
                    relevance_score=self._calculate_relevance(text),
                ))

            logger.info(f"Reddit {subreddit.get('name')}: fetched {len(news_items)} items")
            return news_items

        except ImportError:
            logger.warning("feedparser not installed, Reddit RSS unavailable")
            return []
        except Exception as e:
            logger.warning(f"Reddit fetch failed for {subreddit_id}: {e}")
            return []

    def _extract_reddit_description(self, entry) -> str:
        description = ""

        if hasattr(entry, 'content') and entry.content:
            for content in entry.content:
                if hasattr(content, 'value'):
                    description = self._clean_html(content.value)
                    break

        if not description and hasattr(entry, 'summary'):
            description = self._clean_html(entry.summary)

        if not description and hasattr(entry, 'description'):
            description = self._clean_html(entry.description)

        return description

    def _fetch_telegram(self, keywords: List[str], limit: int) -> List[NewsItem]:
        all_news = []

        for channel_id in self.telegram_channels:
            if len(all_news) >= limit:
                break

            channel = self.TELEGRAM_CHANNELS.get(channel_id)
            if not channel:
                continue

            news = self._fetch_telegram_channel(channel_id, channel, keywords, limit)
            all_news.extend(news)

        return all_news

    def _fetch_telegram_channel(self, channel_id: str, channel: Dict,
                                 keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            import feedparser

            rss_url = channel.get("rss_url")
            if not rss_url:
                return []

            response = self._fetch_url(rss_url)
            if not response:
                return []

            feed = feedparser.parse(response.text)
            news_items = []

            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                description = self._clean_html(entry.get("description", ""))

                if not title:
                    continue

                text = title + " " + description
                if keywords and not any(kw.lower() in text.lower() for kw in keywords):
                    continue

                published_at = self._parse_rss_date(entry.get("published"))

                news_items.append(NewsItem(
                    title=title[:200],
                    description=description[:500],
                    url=link,
                    source=channel.get("name", channel_id),
                    source_type="social",
                    published_at=published_at,
                    fetched_at=datetime.now(),
                    relevance_score=self._calculate_relevance(text),
                ))

            logger.info(f"Telegram {channel.get('name')}: fetched {len(news_items)} items")
            return news_items

        except ImportError:
            logger.warning("feedparser not installed, Telegram RSS unavailable")
            return []
        except Exception as e:
            logger.warning(f"Telegram fetch failed for {channel_id}: {e}")
            return []

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = ' '.join(text.split())
        return text

    def _parse_rss_date(self, date_str: Optional[str]) -> datetime:
        if not date_str:
            return datetime.now()
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                return datetime.now()
