# 新闻爬虫系统实施计划

- [ ] 1. 设置项目结构
   - 创建 news/spiders/ 目录结构
   - 创建 news/storage/ 目录结构
   - 创建 news/config/ 目录结构
   - 创建 news/cache/ 目录结构
   - 创建 news/scheduler/ 目录结构
   - 创建 news/search/ 目录结构
   - 创建 news/__init__.py, spiders/__init__.py, storage/__init__.py, cache/__init__.py, scheduler/__init__.py, search/__init__.py

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

- [ ] 9. 增加更多新闻源
   - [ ] 9.1 添加 Decrypt (decrypt.co) 爬虫
   - [ ] 9.2 添加 Bitcoinist 爬虫
   - [ ] 9.3 添加 CCN (cryptonews.com) 爬虫
   - [ ] 9.4 添加 FXStreet (fxstreet.com) 爬虫
   - [ ] 9.5 添加 Investing.com RSS 支持

- [ ] 10. 实现多数据库支持
   - [ ] 10.1 创建 news/storage/base_storage.py 存储接口基类
   - [ ] 10.2 创建 news/storage/mysql_storage.py MySQL 存储实现
   - [ ] 10.3 创建 news/storage/sqlite_storage.py SQLite 存储实现
   - [ ] 10.4 更新 NewsAggregator 支持动态切换存储后端

- [ ] 11. 实现缓存机制
   - [ ] 11.1 创建 news/cache/memory_cache.py 内存缓存
   - [ ] 11.2 创建 news/cache/redis_cache.py Redis 缓存
   - [ ] 11.3 实现缓存键策略和过期时间
   - [ ] 11.4 集成缓存到爬虫获取流程

- [ ] 12. 实现定时抓取功能
   - [ ] 12.1 创建 news/scheduler/crawler_scheduler.py 调度器
   - [ ] 12.2 支持按时间间隔抓取配置
   - [ ] 12.3 支持 cron 表达式配置
   - [ ] 12.4 实现任务队列管理

- [ ] 13. 支持 Elasticsearch 搜索
   - [ ] 13.1 创建 news/search/elasticsearch_client.py ES 客户端
   - [ ] 13.2 实现新闻索引和搜索功能
   - [ ] 13.3 支持关键词高亮搜索
   - [ ] 13.4 实现聚合统计功能

- [ ] 14. 实现 PostgreSQL 存储
   - [ ] 14.1 创建 news/storage/postgres_storage.py
   - [ ] 14.2 实现数据库连接管理
   - [ ] 14.3 实现 save_news, save_batch, get_news 方法
   - [ ] 14.4 实现数据库 schema 初始化
   - 参考：design.md 第 115-127 行，149-173 行

- [ ] 15. 扩展 NewsAggregator
   - [ ] 15.1 扩展 news/news_aggregator.py，整合所有爬虫
   - [ ] 15.2 实现新闻去重逻辑
   - [ ] 15.3 实现情绪分析和相关性评分
   - [ ] 15.4 集成缓存和定时任务功能
   - 参考：design.md 第 1-35 行

- [ ] 16. 创建配置文件
   - [ ] 16.1 创建 news/config/news_config.json
   - [ ] 16.2 配置所有新闻源、存储、缓存、调度参数
   - 参考：design.md 第 200-256 行

- [ ] 17. 检查点
   - 确保所有模块导入正常
   - 确保配置文件格式正确
   - 运行基本功能测试

- [ ] 18. 编写单元测试
   - [ ] 18.1 为 Spider 解析逻辑编写测试
   - [ ] 18.2 为 Storage 操作编写测试
   - [ ] 18.3 为情绪分析编写测试
   - [ ] 18.4 为缓存机制编写测试
   - [ ] 18.5 为调度器编写测试
   - 参考：design.md 第 259-275 行

- [ ] 19. 更新 README 文档
   - [ ] 19.1 添加新闻爬虫系统使用说明
   - [ ] 19.2 添加配置说明文档
   - [ ] 19.3 添加 API 接口文档
