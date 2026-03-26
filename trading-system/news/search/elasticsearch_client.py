import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.hosts = self.config.get("hosts", ["localhost:9200"])
        self.index = self.config.get("index", "news_articles")
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from elasticsearch import Elasticsearch
            self._client = Elasticsearch(hosts=self.hosts)
            if self._client.ping():
                self._connected = True
                logger.info(f"Connected to Elasticsearch at {self.hosts}")
                self._ensure_index()
                return True
            else:
                logger.error("Elasticsearch ping failed")
                return False
        except ImportError:
            logger.warning("elasticsearch package not installed")
            return False
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            return False

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._connected = False
            logger.info("Disconnected from Elasticsearch")

    def is_connected(self) -> bool:
        return self._connected

    def _ensure_index(self) -> None:
        if not self._client:
            return

        try:
            if not self._client.indices.exists(index=self.index):
                mapping = {
                    "mappings": {
                        "properties": {
                            "title": {"type": "text", "analyzer": "english"},
                            "description": {"type": "text", "analyzer": "english"},
                            "url": {"type": "keyword"},
                            "source": {"type": "keyword"},
                            "source_type": {"type": "keyword"},
                            "author": {"type": "keyword"},
                            "published_at": {"type": "date"},
                            "fetched_at": {"type": "date"},
                            "sentiment": {"type": "keyword"},
                            "relevance_score": {"type": "float"},
                            "categories": {"type": "keyword"},
                        }
                    }
                }
                self._client.indices.create(index=self.index, body=mapping)
                logger.info(f"Created Elasticsearch index: {self.index}")

        except Exception as e:
            logger.error(f"Failed to create index: {e}")

    def index_news(self, news_item: Any) -> bool:
        if not self._connected:
            if not self.connect():
                return False

        try:
            doc = {
                "title": news_item.title,
                "description": news_item.description,
                "url": news_item.url,
                "source": news_item.source,
                "source_type": news_item.source_type,
                "author": news_item.author,
                "published_at": news_item.published_at.isoformat() if news_item.published_at else None,
                "fetched_at": news_item.fetched_at.isoformat() if news_item.fetched_at else datetime.now().isoformat(),
                "sentiment": news_item.sentiment,
                "relevance_score": news_item.relevance_score,
                "categories": news_item.categories,
            }

            self._client.index(index=self.index, document=doc)
            return True

        except Exception as e:
            logger.error(f"Failed to index news: {e}")
            return False

    def bulk_index(self, news_items: List[Any]) -> int:
        if not news_items:
            return 0

        if not self._connected:
            if not self.connect():
                return 0

        try:
            from elasticsearch.helpers import bulk

            actions = []
            for item in news_items:
                doc = {
                    "_index": self.index,
                    "_source": {
                        "title": item.title,
                        "description": item.description,
                        "url": item.url,
                        "source": item.source,
                        "source_type": item.source_type,
                        "author": item.author,
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                        "fetched_at": item.fetched_at.isoformat() if item.fetched_at else datetime.now().isoformat(),
                        "sentiment": item.sentiment,
                        "relevance_score": item.relevance_score,
                        "categories": item.categories,
                    }
                }
                actions.append(doc)

            success, _ = bulk(self._client, actions)
            logger.info(f"Indexed {success} news items to Elasticsearch")
            return success

        except Exception as e:
            logger.error(f"Bulk index failed: {e}")
            return 0

    def search(self, query: str, limit: int = 10,
               filters: Optional[Dict] = None) -> List[Dict]:
        if not self._connected:
            if not self.connect():
                return []

        try:
            body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^2", "description", "source"],
                                    "fuzziness": "AUTO",
                                }
                            }
                        ]
                    }
                },
                "highlight": {
                    "fields": {
                        "title": {},
                        "description": {}
                    }
                },
                "size": limit
            }

            if filters:
                filter_clauses = []
                if "source_type" in filters:
                    filter_clauses.append({"term": {"source_type": filters["source_type"]}})
                if "sentiment" in filters:
                    filter_clauses.append({"term": {"sentiment": filters["sentiment"]}})
                if "source" in filters:
                    filter_clauses.append({"term": {"source": filters["source"]}})

                if filter_clauses:
                    body["query"]["bool"]["filter"] = filter_clauses

            response = self._client.search(index=self.index, body=body)
            results = []

            for hit in response["hits"]["hits"]:
                result = hit["_source"]
                if "highlight" in hit:
                    result["highlight"] = hit["highlight"]
                result["score"] = hit["_score"]
                results.append(result)

            logger.info(f"Search '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def aggregate_by_source(self) -> Dict:
        if not self._connected:
            if not self.connect():
                return {}

        try:
            body = {
                "size": 0,
                "aggs": {
                    "by_source": {
                        "terms": {"field": "source", "size": 20}
                    },
                    "by_sentiment": {
                        "terms": {"field": "sentiment", "size": 3}
                    },
                    "by_source_type": {
                        "terms": {"field": "source_type", "size": 10}
                    }
                }
            }

            response = self._client.search(index=self.index, body=body)

            return {
                "by_source": [
                    {"source": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in response["aggregations"]["by_source"]["buckets"]
                ],
                "by_sentiment": [
                    {"sentiment": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in response["aggregations"]["by_sentiment"]["buckets"]
                ],
                "by_source_type": [
                    {"source_type": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in response["aggregations"]["by_source_type"]["buckets"]
                ],
            }

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            return {}

    def delete_old_news(self, days: int) -> int:
        if not self._connected:
            if not self.connect():
                return 0

        try:
            cutoff = datetime.now()
            cutoff_iso = cutoff.isoformat()

            response = self._client.delete_by_query(
                index=self.index,
                body={
                    "query": {
                        "range": {
                            "fetched_at": {"lt": cutoff_iso}
                        }
                    }
                }
            )

            deleted = response.get("deleted", 0)
            logger.info(f"Deleted {deleted} old news items from Elasticsearch")
            return deleted

        except Exception as e:
            logger.error(f"Delete old news failed: {e}")
            return 0
