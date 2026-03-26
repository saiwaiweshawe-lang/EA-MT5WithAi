# 新闻爬虫系统实施计划

- [ ] 1. 设置项目结构
   - 创建 news/spiders/ 目录结构
   - 创建 news/storage/ 目录结构
   - 创建 news/config/ 目录结构
   - 创建 news/__init__.py, spiders/__init__.py, storage/__init__.py

- [ ] 2. 实现数据模型
   - [ ] 2.1 创建 news/models.py，包含 NewsItem 数据类
   - [ ] 2.2 实现数据验证函数
   - 参考：design.md 第 131-147 行

- [ ] 3. 实现爬虫基类
   - [ ] 3.1 创建 news/spiders/base_spider.py
   - [ ] 3.2 实现 BaseSpider 抽象基类，包含速率限制功能
   - 参考：design.md 第 61-72 行

- [ ] 4. 实现 TwitterSpider
   - [ ] 4.1 创建 news/spiders/twitter_spider.py
   - [ ] 4.2 实现 Nitter 实例轮询和自动切换
   - [ ] 4.3 实现 Twitter API v2 降级方案
   - [ ] 4.4 实现关键词搜索功能
   - 参考：design.md 第 74-80 行

- [ ] 5. 实现 CryptoNewsSpider
   - [ ] 5.1 创建 news/spiders/crypto_news.py
   - [ ] 5.2 实现 CoinDesk, Cointelegraph, CryptoSlate, The Block 爬虫
   - [ ] 5.3 实现 RSS 优先，HTML 降级方案
   - 参考：design.md 第 82-91 行

- [ ] 6. 实现 FinanceNewsSpider
   - [ ] 6.1 创建 news/spiders/finance_news.py
   - [ ] 6.2 实现 Yahoo Finance, Reuters, Bloomberg, CNBC 爬虫
   - [ ] 6.3 实现 RSS 优先，HTML 降级方案
   - 参考：design.md 第 93-102 行

- [ ] 7. 实现 SocialNewsSpider
   - [ ] 7.1 创建 news/spiders/social_news.py
   - [ ] 7.2 实现 Reddit RSS 爬虫 (r/cryptocurrency, r/Bitcoin, r/ethereum)
   - [ ] 7.3 实现 Telegram RSS 爬虫
   - 参考：design.md 第 104-109 行

- [ ] 8. 实现 RSSAggregator
   - [ ] 8.1 创建 news/spiders/rss_aggregator.py
   - [ ] 8.2 实现通用 RSS 解析功能
   - 参考：design.md 第 111-113 行

- [ ] 9. 实现 PostgreSQL 存储
   - [ ] 9.1 创建 news/storage/postgres_storage.py
   - [ ] 9.2 实现数据库连接管理
   - [ ] 9.3 实现 save_news, save_batch, get_news 方法
   - [ ] 9.4 实现数据库 schema 初始化
   - 参考：design.md 第 115-127 行，149-173 行

- [ ] 10. 扩展 NewsAggregator
   - [ ] 10.1 扩展 news/news_aggregator.py，整合所有爬虫
   - [ ] 10.2 实现新闻去重逻辑
   - [ ] 10.3 实现情绪分析和相关性评分
   - 参考：design.md 第 1-35 行

- [ ] 11. 创建配置文件
   - [ ] 11.1 创建 news/config/news_config.json
   - [ ] 11.2 配置所有新闻源参数
   - 参考：design.md 第 200-256 行

- [ ] 12. 检查点
   - 确保所有模块导入正常
   - 确保配置文件格式正确

- [ ]* 13. 编写单元测试
   - [ ]* 13.1 为 Spider 解析逻辑编写测试
   - [ ]* 13.2 为 Storage 操作编写测试
   - [ ]* 13.3 为情绪分析编写测试
   - 参考：design.md 第 259-275 行

- [ ]* 14. 更新 README 文档
   - [ ]* 14.1 添加新闻爬虫系统使用说明
