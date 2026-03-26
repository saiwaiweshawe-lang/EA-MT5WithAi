import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..models import NewsItem
from .base_storage import BaseStorage

logger = logging.getLogger(__name__)


class MySQLStorage(BaseStorage):
    def __init__(self, config: Dict):
        self.config = config
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 3306)
        self.database = config.get("database", "trading_news")
        self.username = config.get("username", "user")
        self.password = config.get("password", "password")
        self._connection = None
        self._cursor = None

    def connect(self) -> bool:
        try:
            import pymysql
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                charset='utf8mb4'
            )
            self._cursor = self._connection.cursor()
            logger.info(f"Connected to MySQL at {self.host}:{self.port}")
            return True
        except ImportError:
            logger.warning("pymysql not installed, MySQL unavailable")
            return False
        except Exception as e:
            logger.error(f"MySQL connection failed: {e}")
            return False

    def disconnect(self) -> None:
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._connection:
            self._connection.close()
            self._connection = None
        logger.info("Disconnected from MySQL")

    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.open

    def init_schema(self) -> None:
        if not self.is_connected():
            if not self.connect():
                return

        schema = """
        CREATE TABLE IF NOT EXISTS news_articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            url VARCHAR(1000) UNIQUE NOT NULL,
            source VARCHAR(100) NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            author VARCHAR(200),
            published_at TIMESTAMP NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sentiment VARCHAR(20) DEFAULT 'neutral',
            relevance_score FLOAT DEFAULT 0.0,
            categories JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_source_type (source_type),
            INDEX idx_published_at (published_at DESC),
            INDEX idx_sentiment (sentiment),
            INDEX idx_relevance (relevance_score DESC),
            INDEX idx_url (url)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        try:
            self._cursor.execute(schema)
            self._connection.commit()
            logger.info("MySQL schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            self._connection.rollback()

    def save_news(self, news_item: NewsItem) -> bool:
        if not self.is_connected():
            if not self.connect():
                return False

        import json
        query = """
        INSERT INTO news_articles 
        (title, description, url, source, source_type, author, published_at, 
         fetched_at, sentiment, relevance_score, categories)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            description = VALUES(description),
            sentiment = VALUES(sentiment),
            relevance_score = VALUES(relevance_score),
            updated_at = CURRENT_TIMESTAMP
        """

        try:
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
                json.dumps(news_item.categories),
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

        logger.info(f"Saved {saved_count}/{len(news_items)} news items to MySQL")
        return saved_count

    def get_news(self, keywords: List[str], limit: int,
                 since: Optional[datetime] = None) -> List[NewsItem]:
        if not self.is_connected():
            if not self.connect():
                return []

        import json

        if since is None:
            since = datetime.now() - timedelta(hours=24)

        query = """
        SELECT id, title, description, url, source, source_type, author,
               published_at, fetched_at, sentiment, relevance_score, categories
        FROM news_articles
        WHERE fetched_at >= %s
        """

        params = [since]

        if keywords:
            keyword_conditions = " OR ".join(["(title LIKE %s OR description LIKE %s)" 
                                              for _ in keywords])
            query += f" AND ({keyword_conditions})"
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])

        query += " ORDER BY published_at DESC LIMIT %s"
        params.append(limit)

        try:
            self._cursor.execute(query, params)
            rows = self._cursor.fetchall()

            news_items = []
            for row in rows:
                cats = json.loads(row[11]) if row[11] else []
                if isinstance(cats, str):
                    cats = json.loads(cats)

                news_items.append(NewsItem(
                    title=row[1],
                    description=row[2],
                    url=row[3],
                    source=row[4],
                    source_type=row[5],
                    author=row[6],
                    published_at=row[7],
                    fetched_at=row[8],
                    sentiment=row[9],
                    relevance_score=row[10],
                    categories=cats,
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
        SET sentiment = %s
        WHERE id = %s
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
        WHERE fetched_at < %s
        """

        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            self._cursor.execute(query, (cutoff_date,))
            deleted_count = self._cursor.rowcount
            self._connection.commit()
            logger.info(f"Deleted {deleted_count} old news items from MySQL")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete old news: {e}")
            self._connection.rollback()
            return 0
