# News Crawler Requirements Document

## Introduction

本需求文档描述新闻爬虫系统的功能需求，包括 Twitter/X 爬虫、加密货币新闻爬虫、金融新闻爬虫、社群新闻爬虫和 RSS 聚合订阅源。系统将整合多个新闻源，实现统一的数据获取、存储和分析。

## Glossary

- **Nitter**: Twitter/X 的开源前端镜像服务，提供 RSS 风格的接口
- **RSS**: Really Simple Syndication，用于新闻订阅的 XML 格式
- **PostgreSQL**: 关系型数据库，用于存储新闻数据
- **Sentiment Analysis**: 情绪分析，判断新闻的情感倾向（正面/负面/中性）

## Requirements

### Requirement 1: Twitter/X 新闻爬虫

**User Story:** 作为交易系统，我需要获取 Twitter/X 上的加密货币和金融相关推文，以便及时了解市场动态和社区情绪。

#### Acceptance Criteria

1. WHEN 系统启动，新闻爬虫 SHALL 从配置的 Nitter 实例获取指定账号的推文
2. IF Nitter 实例不可用，系统 SHALL 自动切换到下一个可用的 Nitter 实例
3. IF 所有 Nitter 实例都不可用且配置了 Twitter API，系统 SHALL 使用 Twitter API v2 获取数据
4. WHEN 获取推文时，系统 SHALL 支持关键词搜索（如 `$BTC`, `$ETH`, `bitcoin`）
5. WHEN 获取推文时，系统 SHALL 支持自定义账号列表配置
6. IF 推文内容匹配配置的关键词，系统 SHALL 将该推文添加到新闻列表

### Requirement 2: 加密货币新闻爬虫

**User Story:** 作为交易系统，我需要获取主流加密货币新闻平台的最新资讯，以便做出基于信息的交易决策。

#### Acceptance Criteria

1. WHEN 系统启动，新闻爬虫 SHALL 从以下加密货币新闻源获取内容：
   - CoinDesk (coindesk.com)
   - Cointelegraph (cointelegraph.com)
   - CryptoSlate (cryptoslate.com)
   - The Block (theblock.co)
2. WHEN 获取新闻时，系统 SHALL 优先使用 RSS 订阅源
3. IF RSS 不可用，系统 SHALL 使用 HTML 页面解析作为降级方案
4. IF 获取新闻时，系统 SHALL 过滤并只保留匹配关键词的新闻

### Requirement 3: 金融新闻爬虫

**User Story:** 作为交易系统，我需要获取传统金融市场的最新资讯，以便了解宏观经济环境对加密货币市场的影响。

#### Acceptance Criteria

1. WHEN 系统启动，新闻爬虫 SHALL 从以下金融新闻源获取内容：
   - Yahoo Finance (finance.yahoo.com)
   - Bloomberg (bloomberg.com)
   - Reuters (reuters.com)
   - CNBC (cnbc.com)
2. WHEN 获取新闻时，系统 SHALL 优先使用 RSS 订阅源
3. IF RSS 不可用，系统 SHALL 使用 HTML 页面解析作为降级方案
4. IF 获取新闻时，系统 SHALL 过滤并只保留匹配关键词的新闻

### Requirement 4: 社群新闻爬虫

**User Story:** 作为交易系统，我需要获取 Reddit 和 Telegram 等社群平台上的热门讨论，以便了解社区情绪和舆论动向。

#### Acceptance Criteria

1. WHEN 系统启动，新闻爬虫 SHALL 从以下社群平台获取内容：
   - Reddit (r/cryptocurrency, r/Bitcoin, r/ethereum)
   - Telegram 公开频道
2. WHEN 获取 Reddit 内容时，系统 SHALL 使用 Reddit 的公共 API 或 RSS
3. WHEN 获取 Telegram 内容时，系统 SHALL 使用 Telegram 的 RSS 镜像服务
4. IF 获取内容时，系统 SHALL 只获取匹配的关键词内容

### Requirement 5: RSS 聚合订阅源

**User Story:** 作为交易系统，我需要支持自定义 RSS 订阅源，以便用户添加自己关注的特定新闻来源。

#### Acceptance Criteria

1. WHEN 系统启动，新闻爬虫 SHALL 从配置的 RSS 订阅源获取内容
2. IF RSS 解析失败，系统 SHALL 记录错误日志并继续处理其他订阅源
3. WHEN 获取 RSS 内容时，系统 SHALL 支持自定义订阅源列表配置
4. IF RSS 内容超过限制，系统 SHALL 按时间排序并返回最新的 N 条

### Requirement 6: PostgreSQL 数据存储

**User Story:** 作为交易系统，我需要将获取的新闻数据持久化存储到 PostgreSQL 数据库，以便后续分析和查询。

#### Acceptance Criteria

1. WHEN 获取新闻时，系统 SHALL 将新闻数据存储到 PostgreSQL 数据库
2. IF 新闻 URL 已存在，系统 SHALL 更新现有记录而非创建重复
3. WHEN 存储新闻时，系统 SHALL 包含以下字段：
   - 标题 (title)
   - 描述 (description)
   - URL (url)
   - 来源 (source)
   - 来源类型 (source_type)
   - 作者 (author)
   - 发布时间 (published_at)
   - 获取时间 (fetched_at)
   - 情绪分析 (sentiment)
   - 相关性评分 (relevance_score)
4. IF 存储失败，系统 SHALL 记录错误日志并继续处理其他新闻

### Requirement 7: 新闻情绪分析

**User Story:** 作为交易系统，我需要分析新闻的情绪倾向（正面/负面/中性），以便评估市场情绪。

#### Acceptance Criteria

1. WHEN 处理新闻时，系统 SHALL 使用基于关键词的情绪分析器
2. IF 新闻标题和描述包含预定义的正面词汇（如 bull, rise, surge），系统 SHALL 将情绪标记为 positive
3. IF 新闻标题和描述包含预定义的负面词汇（如 bear, fall, crash），系统 SHALL 将情绪标记为 negative
4. IF 正面词汇和负面词汇数量相当，系统 SHALL 将情绪标记为 neutral
5. WHEN 计算相关性时，系统 SHALL 根据关键词匹配数量计算相关性评分 (0.0-1.0)

### Requirement 8: 新闻聚合与去重

**User Story:** 作为交易系统，我需要整合所有新闻源的新闻并进行去重，以便提供统一的新闻流。

#### Acceptance Criteria

1. WHEN 获取新闻时，系统 SHALL 从所有启用的新闻源获取新闻
2. IF 存在重复的新闻（相同 URL），系统 SHALL 只保留一条记录
3. WHEN 返回新闻时，系统 SHALL 按发布时间倒序排序
4. IF 请求获取新闻时，系统 SHALL 支持总数量限制参数
5. IF 请求获取新闻时，系统 SHALL 支持每个新闻源的数量限制参数

### Requirement 9: 配置管理

**User Story:** 作为系统管理员，我需要通过配置文件管理所有新闻源和爬虫设置，以便灵活配置系统行为。

#### Acceptance Criteria

1. WHEN 系统启动时，系统 SHALL 从 `config/news_config.json` 读取配置
2. IF 配置文件不存在，系统 SHALL 使用默认配置
3. IF 配置中新闻源 enabled 为 true，系统 SHALL 启用该新闻源
4. IF 配置中新闻源 enabled 为 false，系统 SHALL 禁用该新闻源
