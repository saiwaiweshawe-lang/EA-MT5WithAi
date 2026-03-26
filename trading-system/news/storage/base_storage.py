from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from ..models import NewsItem


class BaseStorage(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def save_news(self, news_item: NewsItem) -> bool:
        pass

    @abstractmethod
    def save_batch(self, news_items: List[NewsItem]) -> int:
        pass

    @abstractmethod
    def get_news(self, keywords: List[str], limit: int,
                 since: Optional[datetime] = None) -> List[NewsItem]:
        pass

    @abstractmethod
    def update_sentiment(self, news_id: int, sentiment: str) -> bool:
        pass

    @abstractmethod
    def delete_old_news(self, days: int) -> int:
        pass

    @abstractmethod
    def init_schema(self) -> None:
        pass

    def is_connected(self) -> bool:
        return False
