import unittest
from datetime import datetime
from news.models import NewsItem, SentimentConfig


class TestNewsItem(unittest.TestCase):
    def test_news_item_creation(self):
        news = NewsItem(
            title="Bitcoin surges past $100k",
            description="Bitcoin price Surges",
            url="https://example.com/news/1",
            source="TestSource",
            source_type="test",
        )
        self.assertEqual(news.title, "Bitcoin surges past $100k")
        self.assertEqual(news.sentiment, "neutral")
        self.assertEqual(news.relevance_score, 0.0)

    def test_news_item_sentiment_validation(self):
        news = NewsItem(
            title="Test",
            description="Test",
            url="https://example.com/1",
            source="Test",
            source_type="test",
            sentiment="invalid"
        )
        self.assertEqual(news.sentiment, "neutral")

    def test_news_item_relevance_bounds(self):
        news = NewsItem(
            title="Test",
            description="Test",
            url="https://example.com/1",
            source="Test",
            source_type="test",
            relevance_score=1.5
        )
        self.assertEqual(news.relevance_score, 1.0)
        self.assertEqual(news.relevance_score, 1.0)

    def test_news_item_to_dict(self):
        news = NewsItem(
            title="Test",
            description="Test desc",
            url="https://example.com/1",
            source="Test",
            source_type="test",
            published_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        data = news.to_dict()
        self.assertEqual(data["title"], "Test")
        self.assertEqual(data["url"], "https://example.com/1")

    def test_news_item_from_dict(self):
        data = {
            "title": "Test",
            "description": "Test desc",
            "url": "https://example.com/1",
            "source": "Test",
            "source_type": "test",
            "published_at": "2024-01-01T12:00:00"
        }
        news = NewsItem.from_dict(data)
        self.assertEqual(news.title, "Test")
        self.assertIsNotNone(news.published_at)


class TestSentimentConfig(unittest.TestCase):
    def test_default_positive_words(self):
        config = SentimentConfig()
        self.assertIn("bull", config.positive_words)
        self.assertIn("rise", config.positive_words)

    def test_default_negative_words(self):
        config = SentimentConfig()
        self.assertIn("bear", config.negative_words)
        self.assertIn("crash", config.negative_words)

    def test_custom_words(self):
        config = SentimentConfig(
            positive_words=["good", "great"],
            negative_words=["bad", "terrible"]
        )
        self.assertIn("good", config.positive_words)
        self.assertIn("terrible", config.negative_words)


if __name__ == "__main__":
    unittest.main()
