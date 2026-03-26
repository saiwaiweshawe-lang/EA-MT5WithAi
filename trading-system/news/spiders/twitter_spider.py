import re
import logging
from datetime import datetime
from typing import List, Optional

from ..models import NewsItem
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class TwitterSpider(BaseSpider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.nitter_instances = config.get("nitter_instances", [
            "https://nitter.net",
            "https://nitter.poast.org",
            "https://nitter.fdn.fr",
            "https://nitter.privacydev.net",
            "https://nitter.kavin.rocks",
        ])
        self.accounts = config.get("accounts", [
            "CryptoCom", "binance", "coindesk", "forexcom", "ReutersFinance"
        ])
        self.use_twitter_api = config.get("use_twitter_api", False)
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.bearer_token = config.get("bearer_token", "")

    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        if not self.enabled:
            return []

        all_news = []
        search_keywords = keywords or self.keywords

        if self.use_twitter_api and self.bearer_token:
            return self._fetch_via_twitter_api(search_keywords, limit)

        for account in self.accounts[:5]:
            if len(all_news) >= limit:
                break

            for instance in self.nitter_instances:
                if len(all_news) >= limit:
                    break

                tweets = self._fetch_from_nitter(instance, account, search_keywords, limit)
                all_news.extend(tweets)

                if tweets:
                    break

        return all_news[:limit]

    def _fetch_from_nitter(self, instance: str, account: str, 
                           keywords: List[str], limit: int) -> List[NewsItem]:
        try:
            url = f"{instance}/{account}"
            response = self._fetch_url(url)

            if not response or response.status_code != 200:
                return []

            return self._parse_tweets(response.text, account, keywords, limit)

        except Exception as e:
            logger.warning(f"Nitter fetch failed for {instance}/{account}: {e}")
            return []

    def _parse_tweets(self, html: str, account: str, 
                      keywords: List[str], limit: int) -> List[NewsItem]:
        news_items = []

        tweet_pattern = r'<div class="tweet-content[^>]*>(.*?)</div>'
        date_pattern = r'<span class="tweet-date[^>]*>.*?title="([^"]+)"'
        link_pattern = r'<a href="([^"]+)"[^>]*class="tweet-link"'

        tweets = re.findall(tweet_pattern, html, re.DOTALL)
        dates = re.findall(date_pattern, html, re.DOTALL)
        links = re.findall(link_pattern, html)

        for i, tweet in enumerate(tweets[:limit]):
            text = re.sub(r'<[^>]+>', '', tweet)
            text = ' '.join(text.split())

            if len(text) < 10:
                continue

            if keywords and not any(kw.lower() in text.lower() for kw in keywords):
                continue

            published_at = dates[i] if i < len(dates) else datetime.now().isoformat()
            link = links[i] if i < len(links) else f"https://nitter.net/{account}"

            if link and not link.startswith('http'):
                link = f"https://nitter.net{link}"

            news_items.append(NewsItem(
                title=text[:100] + ("..." if len(text) > 100 else ""),
                description=text,
                url=link,
                source=f"@{account}",
                source_type="twitter",
                author=account,
                published_at=self._parse_date(published_at),
                fetched_at=datetime.now(),
                relevance_score=self._calculate_relevance(text),
            ))

        return news_items

    def _parse_date(self, date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str.replace('"', ''))
        except (ValueError, AttributeError):
            try:
                return datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
            except ValueError:
                return datetime.now()

    def _fetch_via_twitter_api(self, keywords: List[str], 
                                limit: int) -> List[NewsItem]:
        if not self.bearer_token:
            logger.warning("Twitter API bearer token not configured")
            return []

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json"
            }

            query = " OR ".join(keywords) if keywords else "crypto OR bitcoin"
            url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                "query": query,
                "max_results": min(limit, 100),
                "tweet.fields": "created_at,author_id,source"
            }

            response = requests.get(url, headers=headers, params=params, 
                                   timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(f"Twitter API error: {response.status_code}")
                return []

            data = response.json()
            news_items = []

            for tweet in data.get("data", []):
                text = tweet.get("text", "")
                created_at = tweet.get("created_at", "")

                news_items.append(NewsItem(
                    title=text[:100],
                    description=text,
                    url=f"https://twitter.com/i/web/status/{tweet.get('id')}",
                    source="Twitter API",
                    source_type="twitter",
                    author=tweet.get("author_id"),
                    published_at=self._parse_twitter_date(created_at),
                    fetched_at=datetime.now(),
                    relevance_score=self._calculate_relevance(text),
                ))

            return news_items

        except Exception as e:
            logger.error(f"Twitter API fetch failed: {e}")
            return []

    def _parse_twitter_date(self, date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return datetime.now()

    def search_by_keyword(self, keyword: str, limit: int = 10) -> List[NewsItem]:
        if not self.enabled:
            return []

        all_news = []

        for instance in self.nitter_instances:
            if len(all_news) >= limit:
                break

            tweets = self._search_nitter(instance, keyword, limit)
            all_news.extend(tweets)

        return all_news[:limit]

    def _search_nitter(self, instance: str, keyword: str, 
                       limit: int) -> List[NewsItem]:
        try:
            url = f"{instance}/search?f=tweets&q={keyword}"
            response = self._fetch_url(url)

            if not response or response.status_code != 200:
                return []

            return self._parse_tweets(response.text, f"search:{keyword}", 
                                     [keyword], limit)

        except Exception as e:
            logger.warning(f"Nitter search failed for {instance}: {e}")
            return []
