import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from ..models import NewsItem
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class FXStreetSpider(BaseSpider):
    FXSTREET_SOURCES = {
        "fxstreet": {
            "name": "FXStreet",
            "rss_url": "https://www.fxstreet.com/rss/news",
            "html_url": "https://www.fxstreet.com/news/forex-news",
        },
    }

    def __init__(self, config: dict):
        super().__init__(config)

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        if not self.enabled:
            return []

        search_keywords = keywords or self.keywords
        return self._fetch_source("fxstreet", self.FXSTREET_SOURCES["fxstreet"],
                                  search_keywords, limit)

    def _fetch_source(self, source_id: str, source: Dict,
                      keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            import feedparser

            rss_url = source.get("rss_url")
            response = self._fetch_url(rss_url)
            if not response:
                return []

            feed = feedparser.parse(response.text)
            news_items = []

            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                description = self._clean_html(entry.get("description", ""))
                link = entry.get("link", "")

                if not title or not link:
                    continue

                text = title + " " + description
                if keywords and not any(kw.lower() in text.lower() for kw in keywords):
                    continue

                published_at = self._parse_rss_date(entry.get("published"))

                news_items.append(NewsItem(
                    title=title,
                    description=description[:500],
                    url=link,
                    source=source.get("name", source_id),
                    source_type="finance",
                    published_at=published_at,
                    fetched_at=datetime.now(),
                    relevance_score=self._calculate_relevance(text),
                ))

            logger.info(f"FXStreet: fetched {len(news_items)} items")
            return news_items

        except ImportError:
            logger.warning("feedparser not installed")
            return []
        except Exception as e:
            logger.warning(f"FXStreet fetch failed: {e}")
            return []

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        return ' '.join(text.split())

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
