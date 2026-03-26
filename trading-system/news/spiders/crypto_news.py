import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from ..models import NewsItem
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class CryptoNewsSpider(BaseSpider):
    CRYPTO_SOURCES = {
        "coindesk": {
            "name": "CoinDesk",
            "rss_url": "https://feeds.feedburner.com/coindesk",
            "html_url": "https://www.coindesk.com/",
            "priority": 1,
        },
        "cointelegraph": {
            "name": "Cointelegraph",
            "rss_url": "https://cointelegraph.com/rss",
            "html_url": "https://cointelegraph.com/",
            "priority": 2,
        },
        "cryptoslate": {
            "name": "CryptoSlate",
            "rss_url": "https://cryptoslate.com/feed/",
            "html_url": "https://cryptoslate.com/",
            "priority": 3,
        },
        "theblock": {
            "name": "The Block",
            "rss_url": "https://www.theblock.co/rss",
            "html_url": "https://www.theblock.co/",
            "priority": 4,
        },
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.sources = config.get("sources", list(self.CRYPTO_SOURCES.keys()))
        self.rss_fallback_to_html = config.get("rss_fallback_to_html", True)

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        if not self.enabled:
            return []

        all_news = []
        search_keywords = keywords or self.keywords

        sorted_sources = sorted(
            [(s, self.CRYPTO_SOURCES.get(s, {}).get("priority", 99)) 
             for s in self.sources if s in self.CRYPTO_SOURCES],
            key=lambda x: x[1]
        )

        for source_id, _ in sorted_sources:
            if len(all_news) >= limit:
                break

            source = self.CRYPTO_SOURCES[source_id]
            news = self._fetch_source(source_id, source, search_keywords, limit)
            all_news.extend(news)

        return all_news[:limit]

    def _fetch_source(self, source_id: str, source: Dict,
                      keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            news = self._fetch_via_rss(source_id, source, keywords, limit)
            if news:
                return news

            if self.rss_fallback_to_html:
                return self._fetch_via_html(source_id, source, keywords, limit)

            return []
        except Exception as e:
            logger.warning(f"Failed to fetch from {source_id}: {e}")
            return []

    def _fetch_via_rss(self, source_id: str, source: Dict,
                       keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            import feedparser

            rss_url = source.get("rss_url")
            if not rss_url:
                return []

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
                    source_type="crypto",
                    author=entry.get("author", ""),
                    published_at=published_at,
                    fetched_at=datetime.now(),
                    relevance_score=self._calculate_relevance(text),
                    categories=self._extract_categories(entry),
                ))

            logger.info(f"{source.get('name')}: fetched {len(news_items)} items via RSS")
            return news_items

        except ImportError:
            logger.warning("feedparser not installed, RSS unavailable")
            return []
        except Exception as e:
            logger.warning(f"RSS fetch failed for {source_id}: {e}")
            return []

    def _fetch_via_html(self, source_id: str, source: Dict,
                        keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            html_url = source.get("html_url")
            if not html_url:
                return []

            response = self._fetch_url(html_url)
            if not response:
                return []

            return self._parse_html(response.text, source, keywords, limit)

        except Exception as e:
            logger.warning(f"HTML fetch failed for {source_id}: {e}")
            return []

    def _parse_html(self, html: str, source: Dict,
                    keywords: List[str], limit: int) -> List[NewsItem]:
        news_items = []
        source_name = source.get("name", "Unknown")

        if source_id == "coindesk":
            news_items = self._parse_coindesk(html, source_name, keywords, limit)
        elif source_id == "cointelegraph":
            news_items = self._parse_cointelegraph(html, source_name, keywords, limit)
        elif source_id == "cryptoslate":
            news_items = self._parse_cryptoslate(html, source_name, keywords, limit)
        elif source_id == "theblock":
            news_items = self._parse_theblock(html, source_name, keywords, limit)

        logger.info(f"{source_name}: parsed {len(news_items)} items from HTML")
        return news_items

    def _parse_coindesk(self, html: str, source_name: str,
                        keywords: List[str], limit: int) -> List[NewsItem]:
        return self._generic_parse_articles(
            html, source_name, keywords, limit,
            title_pattern=r'<h3[^>]*class="typography__Styled.*?"[^>]*>(.*?)</h3>',
            link_pattern=r'<a href="([^"]+)"[^>]*class="article-card-link"',
            desc_pattern=r'<p[^>]*class="excerpt.*?"[^>]*>(.*?)</p>',
        )

    def _parse_cointelegraph(self, html: str, source_name: str,
                             keywords: List[str], limit: int) -> List[NewsItem]:
        return self._generic_parse_articles(
            html, source_name, keywords, limit,
            title_pattern=r'<span[^>]*class="post-title.*?"[^>]*>(.*?)</span>',
            link_pattern=r'<a href="([^"]+)"[^>]*class="post-url"',
            desc_pattern=r'<span[^>]*class="post-meta.*?"[^>]*>(.*?)</span>',
        )

    def _parse_cryptoslate(self, html: str, source_name: str,
                           keywords: List[str], limit: int) -> List[NewsItem]:
        return self._generic_parse_articles(
            html, source_name, keywords, limit,
            title_pattern=r'<h2[^>]*class="cs-article.*?"[^>]*>(.*?)</h2>',
            link_pattern=r'<a href="([^"]+)"[^>]*class="cs-article-card"',
            desc_pattern=r'<p[^>]*class="cs-excerpt.*?"[^>]*>(.*?)</p>',
        )

    def _parse_theblock(self, html: str, source_name: str,
                        keywords: List[str], limit: int) -> List[NewsItem]:
        return self._generic_parse_articles(
            html, source_name, keywords, limit,
            title_pattern=r'<h3[^>]*class=".*?summary.*?"[^>]*>(.*?)</h3>',
            link_pattern=r'<a href="([^"]+)"[^>]*class=".*?card.*?"',
            desc_pattern=r'<p[^>]*class=".*?deck.*?"[^>]*>(.*?)</p>',
        )

    def _generic_parse_articles(self, html: str, source_name: str,
                                 keywords: List[str], limit: int,
                                 title_pattern: str,
                                 link_pattern: str,
                                 desc_pattern: str) -> List[NewsItem]:
        news_items = []

        titles = re.findall(title_pattern, html, re.DOTALL)
        links = re.findall(link_pattern, html, re.DOTALL)
        descs = re.findall(desc_pattern, html, re.DOTALL)

        for i in range(min(len(titles), len(links), limit)):
            title = self._clean_html(titles[i])
            link = links[i]
            desc = self._clean_html(descs[i]) if i < len(descs) else ""

            if not title or not link:
                continue

            if keywords and not any(kw.lower() in (title + desc).lower() for kw in keywords):
                continue

            if link and not link.startswith('http'):
                link = f"https://{source_name.lower().replace(' ', '')}.com{link}"

            news_items.append(NewsItem(
                title=title[:200],
                description=desc[:500],
                url=link,
                source=source_name,
                source_type="crypto",
                published_at=datetime.now(),
                fetched_at=datetime.now(),
                relevance_score=self._calculate_relevance(title + desc),
            ))

        return news_items

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

    def _extract_categories(self, entry) -> List[str]:
        categories = []
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if hasattr(tag, 'term'):
                    categories.append(tag.term)
        return categories
