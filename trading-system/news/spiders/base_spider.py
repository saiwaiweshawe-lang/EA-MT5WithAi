import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import requests

from ..models import NewsItem

logger = logging.getLogger(__name__)


class BaseSpider(ABC):
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.rate_limit = config.get("rate_limit", 10)
        self.timeout = config.get("timeout", 10)
        self.request_count = 0
        self.last_request_time: Optional[datetime] = None
        self.keywords = config.get("keywords", [])

    def _check_rate_limit(self) -> bool:
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < 1 and self.request_count >= self.rate_limit:
                wait_time = (1 - elapsed) + 0.1
                logger.warning(f"Rate limit reached for {self.__class__.__name__}, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                return False
        return True

    def _record_request(self) -> None:
        now = datetime.now()
        if self.last_request_time:
            elapsed = (now - self.last_request_time).total_seconds()
            if elapsed >= 1:
                self.request_count = 0
        self.request_count += 1
        self.last_request_time = now

    def _fetch_url(self, url: str, retry: int = 3) -> Optional[requests.Response]:
        for attempt in range(retry):
            try:
                if not self._check_rate_limit():
                    return None

                response = requests.get(url, timeout=self.timeout)
                self._record_request()

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    logger.warning(f"Rate limited by {url}, attempt {attempt + 1}/{retry}")
                    time.sleep(2 ** attempt)
                else:
                    logger.debug(f"HTTP {response.status_code} from {url}")
            except requests.Timeout:
                logger.warning(f"Timeout fetching {url}, attempt {attempt + 1}/{retry}")
                time.sleep(1)
            except requests.RequestException as e:
                logger.warning(f"Request failed for {url}: {e}, attempt {attempt + 1}/{retry}")
                time.sleep(1)
        return None

    def _match_keywords(self, text: str) -> bool:
        if not self.keywords:
            return True
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.keywords)

    def _calculate_relevance(self, text: str) -> float:
        if not self.keywords:
            return 0.5
        text_lower = text.lower()
        match_count = sum(1 for kw in self.keywords if kw.lower() in text_lower)
        return min(match_count / len(self.keywords), 1.0)

    @abstractmethod
    def fetch_news(self, keywords: List[str], limit: int = 10) -> List[NewsItem]:
        pass

    def get_source_type(self) -> str:
        return self.__class__.__name__.replace("Spider", "").lower()
