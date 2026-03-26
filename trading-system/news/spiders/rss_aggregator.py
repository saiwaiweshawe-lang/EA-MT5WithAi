import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from ..models import NewsItem
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class RSSAggregator(BaseSpider):
    DEFAULT_FEEDS = [
        "https://feeds.feedburner.com/coindesk",
        "https://cointelegraph.com/rss",
        "https://cryptoslate.com/feed/",
        "https://www.theblock.co/rss",
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self.feeds = config.get("feeds", self.DEFAULT_FEEDS)

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        if not self.enabled:
            return []

        all_news = []
        search_keywords = keywords or self.keywords

        for feed_url in self.feeds:
            if len(all_news) >= limit:
                break

            news = self._fetch_feed(feed_url, search_keywords, limit)
            all_news.extend(news)

        all_news.sort(key=lambda x: x.published_at or datetime.now(), reverse=True)
        return all_news[:limit]

    def _fetch_feed(self, feed_url: str, keywords: List[str],
                    limit: int) -> List[NewsItem]:
        try:
            import feedparser

            response = self._fetch_url(feed_url)
            if not response:
                return []

            feed = feedparser.parse(response.text)
            news_items = []

            source_name = self._extract_source_name(feed, feed_url)

            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                description = self._clean_html(self._extract_description(entry))
                link = entry.get("link", "")

                if not title or not link:
                    continue

                text = title + " " + description
                if keywords and not any(kw.lower() in text.lower() for kw in keywords):
                    continue

                author = ""
                if hasattr(entry, 'author_detail') and entry.author_detail:
                    author = entry.author_detail.get("name", "")
                elif hasattr(entry, 'author'):
                    author = entry.author

                published_at = self._parse_rss_date(entry.get("published"))
                categories = self._extract_categories(entry)

                news_items.append(NewsItem(
                    title=title,
                    description=description[:500],
                    url=link,
                    source=source_name,
                    source_type="rss",
                    author=author,
                    published_at=published_at,
                    fetched_at=datetime.now(),
                    relevance_score=self._calculate_relevance(text),
                    categories=categories,
                ))

            logger.info(f"RSS {source_name}: fetched {len(news_items)} items")
            return news_items

        except ImportError:
            logger.warning("feedparser not installed, RSS aggregation unavailable")
            return []
        except Exception as e:
            logger.warning(f"RSS fetch failed for {feed_url}: {e}")
            return []

    def _extract_source_name(self, feed, feed_url: str) -> str:
        if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
            return feed.feed.title

        feed_name = feed_url.split('/')[2].replace('www.', '')
        return feed_name

    def _extract_description(self, entry) -> str:
        if hasattr(entry, 'content') and entry.content:
            for content in entry.content:
                if hasattr(content, 'value'):
                    return content.value

        if hasattr(entry, 'summary'):
            return entry.summary

        if hasattr(entry, 'description'):
            return entry.description

        return ""

    def _extract_categories(self, entry) -> List[str]:
        categories = []

        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if hasattr(tag, 'term'):
                    categories.append(tag.term)

        if hasattr(entry, 'category'):
            cat = entry.category
            if isinstance(cat, str):
                categories.append(cat)
            elif hasattr(cat, 'term'):
                categories.append(cat.term)

        return categories

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

    def add_feed(self, feed_url: str) -> None:
        if feed_url not in self.feeds:
            self.feeds.append(feed_url)
            logger.info(f"Added RSS feed: {feed_url}")

    def remove_feed(self, feed_url: str) -> bool:
        if feed_url in self.feeds:
            self.feeds.remove(feed_url)
            logger.info(f"Removed RSS feed: {feed_url}")
            return True
        return False

    def get_feeds(self) -> List[str]:
        return self.feeds.copy()
