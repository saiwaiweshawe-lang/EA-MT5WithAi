# News Spiders Module
# Contains web crawlers for various news sources

from .base_spider import BaseSpider
from .twitter_spider import TwitterSpider
from .crypto_news import CryptoNewsSpider
from .finance_news import FinanceNewsSpider
from .social_news import SocialNewsSpider
from .rss_aggregator import RSSAggregator

__all__ = [
    "BaseSpider",
    "TwitterSpider",
    "CryptoNewsSpider",
    "FinanceNewsSpider",
    "SocialNewsSpider",
    "RSSAggregator",
]
