import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..models import NewsItem
from .base_storage import BaseStorage

logger = logging.getLogger(__name__)


class SQLiteStorage(BaseStorage):
    def __init__(self, config: Dict):
        self.config = config
        self.database_path = config.get("database_path", "news_data.db")
        self._connection = None
        self._cursor = None

    def connect(self) -> bool:
        try:
            import sqlite3
            self._connection = sqlite3.connect(self.database_path)
            self._connection.row_factory = sqlite3.Row
            self._cursor = self._connection.cursor()
            logger.info(f"Connected to SQLite at {self.database_path}")
            return True
        except Exception as e:
            logger.error(f"SQLite connection failed: {e}")
            return False

    def disconnect(self) -> None:
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._connection:
            self._connection.close()
            self._connection = None
        logger.info("Disconnected from SQLite")

    def is_connected(self) -> bool:
        return self._connection is not None

    def init_schema(self) -> None:
        if not self.is_connected():
            if not self.connect():
                return

        schema = """
        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            url VARCHAR(1000) UNIQUE NOT NULL,
            source VARCHAR(100) NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            author VARCHAR(200),
            published_at TIMESTAMP,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sentiment VARCHAR(20) DEFAULT 'neutral',
            relevance_score FLOAT DEFAULT 0.0,
            categories TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_news_source_type ON news_articles(source_type);
        CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_articles(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news_articles(sentiment);
        CREATE INDEX IF NOT EXISTS idx_news_relevance ON news_articles(relevance_score DESC);
        CREATE INDEX IF NOT EXISTS idx_news_url ON news_articles(url);
        """

        try:
            self._cursor.executescript(schema)
            self._connection.commit()
            logger.info("SQLite schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            self._connection.rollback()

    def save_news(self, news_item: NewsItem) -> bool:
        if not self.is_connected():
            if not self.connect():
                return False

        query = """
        INSERT INTO news_articles 
        (title, description, url, source, source_type, author, published_at, 
         fetched_at, sentiment, relevance_score, categories, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            sentiment = excluded.sentiment,
            relevance_score = excluded.relevance_score,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            categories_json = json.dumps(news_item.categories)
            self._cursor.execute(query, (
                news_item.title,
                news_item.description,
                news_item.url,
                news_item.source,
                news_item.source_type,
                news_item.author,
                news_item.published_at,
                news_item.fetched_at,
                news_item.sentiment,
                news_item.relevance_score,
                categories_json,
            ))
            self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save news: {e}")
            self._connection.rollback()
            return False

    def save_batch(self, news_items: List[NewsItem]) -> int:
        if not news_items:
            return 0

        if not self.is_connected():
            if not self.connect():
                return 0

        saved_count = 0
        for item in news_items:
            if self.save_news(item):
                saved_count += 1

        logger.info(f"Saved {saved_count}/{len(news_items)} news items to SQLite")
        return saved_count

    def get_news(self, keywords: List[str], limit: int,
                 since: Optional[datetime] = None) -> List[NewsItem]:
        if not self.is_connected():
            if not self.connect():
                return []

        if since is None:
            since = datetime.now() - timedelta(hours=24)

        query = """
        SELECT id, title, description, url, source, source_type, author,
               published_at, fetched_at, sentiment, relevance_score, categories
        FROM news_articles
        WHERE fetched_at >= ?
        """

        params = [since.isoformat()]

        if keywords:
            keyword_conditions = " OR ".join(["(title LIKE ? OR description LIKE ?)" 
                                              for _ in keywords])
            query += f" AND ({keyword_conditions})"
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])

        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)

        try:
            self._cursor.execute(query, params)
            rows = self._cursor.fetchall()

            news_items = []
            for row in rows:
                categories = json.loads(row[11]) if row[11] else []
                if isinstance(categories, str):
                    categories = json.loads(categories)

                published_at = row[7]
                if isinstance(published_at, str):
                    try:
                        published_at = datetime.fromisoformat(published_at)
                    except ValueError:
                        published_at = None

                fetched_at = row[8]
                if isinstance(fetched_at, str):
                    try:
                        fetched_at = datetime.fromisoformat(fetched_at)
                    except ValueError:
                        fetched_at = datetime.now()

                news_items.append(NewsItem(
                    title=row[1],
                    description=row[2],
                    url=row[3],
                    source=row[4],
                    source_type=row[5],
                    author=row[6],
                    published_at=published_at,
                    fetched_at=fetched_at,
                    sentiment=row[9],
                    relevance_score=row[10],
                    categories=categories,
                ))

            return news_items

        except Exception as e:
            logger.error(f"Failed to get news: {e}")
            return []

    def update_sentiment(self, news_id: int, sentiment: str) -> bool:
        if not self.is_connected():
            if not self.connect():
                return False

        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"

        query = """
        UPDATE news_articles 
        SET sentiment = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """

        try:
            self._cursor.execute(query, (sentiment, news_id))
            self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update sentiment: {e}")
            self._connection.rollback()
            return False

    def delete_old_news(self, days: int) -> int:
        if not self.is_connected():
            if not self.connect():
                return 0

        query = """
        DELETE FROM news_articles 
        WHERE fetched_at < ?
        """

        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            self._cursor.execute(query, (cutoff_date.isoformat(),))
            deleted_count = self._cursor.rowcount
            self._connection.commit()
            logger.info(f"Deleted {deleted_count} old news items from SQLite")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete old news: {e}")
            self._connection.rollback()
            return 0
