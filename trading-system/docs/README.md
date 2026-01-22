# 交易系统完整文档

## 目录

1. [系统概述](#系统概述)
2. [系统架构](#系统架构)
3. [核心模块](#核心模块)
4. [部署指南](#部署指南)
5. [运维手册](#运维手册)
6. [故障排查](#故障排查)
7. [性能优化](#性能优化)
8. [安全最佳实践](#安全最佳实践)

---

## 系统概述

### 简介

本系统是一个企业级量化交易平台,支持多种交易策略、实盘数据获取、回测分析和风险管理。系统采用模块化设计,具有高可用性、高性能和高安全性。

### 主要特性

- **多平台支持**: MT5、币安等主流交易平台
- **策略引擎**: 支持自定义交易策略,内置多种技术指标
- **回测框架**: 完整的历史数据回测和性能评估
- **风险管理**: 实时风险监控和自动止损
- **高可用性**: 双服务器同步和自动故障转移
- **安全防护**: API 限流、IP 黑名单、数据加密
- **监控告警**: 实时系统监控和多渠道告警
- **备份恢复**: 自动备份和灾难恢复机制

### 技术栈

- **语言**: Python 3.8+
- **Web 框架**: Flask
- **数据存储**: SQLite/PostgreSQL, Redis
- **消息队列**: RabbitMQ
- **监控**: Prometheus + Grafana
- **日志**: ELK Stack (Elasticsearch, Logstash, Kibana)

---

## 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          客户端应用                              │
│                   (Web UI / Mobile App / API)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         负载均衡器                                │
│                      (Nginx / HAProxy)                          │
└────────────┬───────────────────────────────────┬────────────────┘
             │                                   │
             ▼                                   ▼
┌────────────────────────┐        ┌────────────────────────┐
│     主服务器 (Primary)  │◄──────►│   备份服务器 (Backup)   │
│                        │  同步   │                        │
│  - API 网关            │        │  - 待命状态             │
│  - 策略引擎            │        │  - 数据同步             │
│  - 风险管理            │        │  - 健康监测             │
└────────┬───────────────┘        └────────────────────────┘
         │
         ├──────────┬──────────┬──────────┬──────────┐
         ▼          ▼          ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │ MT5    │ │ 币安   │ │数据库  │ │ Redis  │ │ MQ    │
    │ 连接器 │ │ 连接器 │ │        │ │ 缓存   │ │       │
    └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

### 核心组件

1. **API 网关层**
   - 请求路由和负载均衡
   - API 限流和防护
   - 身份认证和授权

2. **业务逻辑层**
   - 策略引擎
   - 交易执行器
   - 风险管理器
   - 数据分析器

3. **数据访问层**
   - 数据库连接池
   - 缓存管理
   - 消息队列

4. **基础设施层**
   - 日志聚合
   - 监控告警
   - 配置管理
   - 备份恢复

---

## 核心模块

### 1. 备份与灾难恢复系统

**位置**: `utilities/backup_manager.py`

**功能**:
- 自动定期备份数据库和配置文件
- 支持全量备份和增量备份
- 备份压缩和加密
- 灾难恢复和数据回滚

**配置**: `config/backup_config.json`

**使用示例**:
```python
from utilities.backup_manager import BackupManager

manager = BackupManager()
manager.start()  # 启动自动备份

# 手动备份
backup_file = manager.create_backup(include_db=True, include_config=True)

# 恢复备份
manager.restore_backup(backup_file)
```

**详细文档**: [backup_recovery.md](backup_recovery.md)

### 2. 敏感信息加密存储

**位置**: `utilities/encryption_manager.py`

**功能**:
- AES-256 数据加密
- 密钥管理和轮换
- 敏感字段自动加密
- 加密配置文件

**配置**: `config/encryption_config.json`

**使用示例**:
```python
from utilities.encryption_manager import EncryptionManager

manager = EncryptionManager()

# 加密数据
encrypted = manager.encrypt_data("sensitive_data")

# 解密数据
decrypted = manager.decrypt_data(encrypted)

# 加密文件
manager.encrypt_file("config.json", "config.json.enc")
```

**详细文档**: [encryption.md](encryption.md)

### 3. 统一进程管理系统

**位置**: `utilities/process_manager.py`

**功能**:
- 进程生命周期管理
- 自动重启失败进程
- 进程健康检查
- 资源使用监控

**配置**: `config/process_config.json`

**使用示例**:
```python
from utilities.process_manager import ProcessManager

manager = ProcessManager()

# 注册进程
manager.register_process("strategy_engine", "python", ["strategy_engine.py"])

# 启动所有进程
manager.start_all()

# 停止特定进程
manager.stop_process("strategy_engine")
```

**详细文档**: [process_management.md](process_management.md)

### 4. 监控和告警系统

**位置**: `utilities/monitoring.py`

**功能**:
- 系统资源监控 (CPU、内存、磁盘、网络)
- 应用性能监控 (响应时间、错误率)
- 多渠道告警 (邮件、Webhook、企业微信)
- 告警规则管理

**配置**: `config/monitoring_config.json`

**使用示例**:
```python
from utilities.monitoring import MonitoringSystem

monitor = MonitoringSystem()
monitor.start()

# 添加自定义指标
monitor.record_metric("trade_count", 100)

# 手动触发告警
monitor.trigger_alert("critical", "系统异常", "CPU使用率超过90%")
```

**详细文档**: [monitoring.md](monitoring.md)

### 5. 配置管理中心

**位置**: `utilities/config_manager.py`

**功能**:
- 集中配置管理
- 配置版本控制
- 配置热更新
- 配置加密存储

**配置**: 所有 `config/*.json` 文件

**使用示例**:
```python
from utilities.config_manager import ConfigManager

manager = ConfigManager()

# 加载配置
config = manager.load_config("trading_config.json")

# 获取配置值
api_key = manager.get_config_value("trading_config.json", "api.key")

# 设置配置值
manager.set_config_value("trading_config.json", "api.timeout", 30)
```

**详细文档**: [config_management.md](config_management.md)

### 6. 日志聚合和分析

**位置**: `utilities/log_aggregator.py`

**功能**:
- 多源日志收集
- 日志解析和结构化
- 日志搜索和过滤
- 日志统计和报表

**配置**: `config/logging_config.json`

**使用示例**:
```python
from utilities.log_aggregator import LogAggregator

aggregator = LogAggregator()
aggregator.start()

# 查询日志
logs = aggregator.query_logs(
    level="ERROR",
    start_time="2024-01-01",
    end_time="2024-01-31",
    source="strategy_engine"
)

# 生成报表
report = aggregator.generate_report(period="daily")
```

**详细文档**: [log_aggregation.md](log_aggregation.md)

### 7. 测试和回测框架

**位置**: `utilities/backtesting_engine.py`, `tests/test_runner.py`

**功能**:
- 历史数据回测
- 策略性能评估
- 多策略对比
- 单元测试框架

**配置**: `config/testing_config.json`

**使用示例**:
```python
from utilities.backtesting_engine import BacktestingEngine

engine = BacktestingEngine(initial_capital=100000)

# 运行回测
result = engine.run_backtest(
    strategy_func=my_strategy,
    symbol="BTCUSD",
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# 查看结果
print(f"总收益: {result.total_return:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2f}%")
```

**详细文档**: [tests/README.md](../tests/README.md)

### 8. API 限流和防护

**位置**: `utilities/api_security.py`

**功能**:
- 滑动窗口速率限制
- IP 黑名单管理
- 请求验证 (SQL 注入、XSS 防护)
- 安全事件日志

**配置**: `config/api_security_config.json`

**使用示例**:
```python
from utilities.api_security import APISecurityManager

security = APISecurityManager()

# Flask 装饰器使用
from utilities.api_security import require_api_security

@app.route('/api/trade')
@require_api_security(security)
def trade():
    return {"status": "ok"}

# 手动检查
allowed, error = security.check_request(
    client_id="client-123",
    endpoint="/api/trade",
    ip_address="192.168.1.100"
)
```

**详细文档**: [api_security.md](api_security.md)

### 9. 双服务器同步和故障转移

**位置**: `utilities/server_sync.py`

**功能**:
- 主备服务器心跳监测
- 自动故障转移
- 数据同步复制
- 自动回切

**配置**: `config/server_sync_config.json`

**使用示例**:
```python
from utilities.server_sync import ServerSyncManager, DataReplicator

sync_manager = ServerSyncManager()
sync_manager.start()

# 数据复制
replicator = DataReplicator(sync_manager)
replicator.replicate("trade:12345", trade_data)

# 注册回调
def on_failover(old_role, new_role):
    print(f"故障转移: {old_role} -> {new_role}")

sync_manager.register_failover_callback(on_failover)
```

**详细文档**: [server_sync.md](server_sync.md)

---

## 部署指南

### 系统要求

**硬件要求**:
- CPU: 4 核及以上
- 内存: 8GB 及以上
- 硬盘: 100GB 及以上 SSD
- 网络: 稳定的网络连接

**软件要求**:
- 操作系统: Linux (Ubuntu 20.04+ / CentOS 8+)
- Python: 3.8 或更高版本
- 数据库: PostgreSQL 12+ / SQLite 3+
- Redis: 6.0+
- Nginx: 1.18+

### 安装步骤

#### 1. 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.8 python3-pip postgresql redis-server nginx

# CentOS/RHEL
sudo yum install -y python38 python38-pip postgresql-server redis nginx
```

#### 2. 克隆项目

```bash
git clone https://github.com/your-org/trading-system.git
cd trading-system
```

#### 3. 安装 Python 依赖

```bash
pip3 install -r requirements.txt
```

#### 4. 配置数据库

```bash
# PostgreSQL
sudo -u postgres psql
CREATE DATABASE trading_db;
CREATE USER trading_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trading_db TO trading_user;
\q

# 初始化数据库
python3 scripts/init_database.py
```

#### 5. 配置系统

```bash
# 复制配置模板
cp config/example_config.json config/trading_config.json

# 编辑配置文件
nano config/trading_config.json
```

#### 6. 启动服务

```bash
# 启动主服务
python3 main.py --role primary

# 启动备份服务器(在另一台机器上)
python3 main.py --role backup
```

### Docker 部署

```bash
# 构建镜像
docker build -t trading-system:latest .

# 运行容器
docker run -d \
  --name trading-primary \
  -p 5000:5000 \
  -v /data/trading:/app/data \
  -e ROLE=primary \
  trading-system:latest
```

### Kubernetes 部署

```bash
# 应用配置
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 检查状态
kubectl get pods -l app=trading-system
```

---

## 运维手册

### 日常运维

#### 系统监控

```bash
# 查看系统状态
python3 utilities/monitoring.py --status

# 查看进程状态
python3 utilities/process_manager.py --list

# 查看同步状态
curl http://localhost:5000/api/status
```

#### 日志查看

```bash
# 查看实时日志
tail -f logs/system.log

# 查看错误日志
grep ERROR logs/system.log | tail -50

# 日志统计
python3 utilities/log_aggregator.py --stats --period daily
```

#### 备份管理

```bash
# 创建备份
python3 utilities/backup_manager.py --backup --type full

# 查看备份列表
python3 utilities/backup_manager.py --list

# 恢复备份
python3 utilities/backup_manager.py --restore backup_20240101_120000.tar.gz
```

### 配置更新

```bash
# 更新配置
python3 utilities/config_manager.py set trading_config.json api.timeout 60

# 重载配置(热更新)
curl -X POST http://localhost:5000/api/config/reload
```

### 性能调优

#### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);

-- 清理旧数据
DELETE FROM logs WHERE timestamp < NOW() - INTERVAL '30 days';

-- 真空优化
VACUUM ANALYZE;
```

#### Redis 优化

```bash
# 内存使用分析
redis-cli --bigkeys

# 清理过期键
redis-cli FLUSHDB
```

### 安全加固

```bash
# 更新依赖
pip3 install --upgrade -r requirements.txt

# 检查安全漏洞
pip3 install safety
safety check

# 更新系统补丁
sudo apt update && sudo apt upgrade
```

---

## 故障排查

### 常见问题

#### 1. 服务无法启动

**症状**: 执行启动命令后服务立即退出

**排查步骤**:
```bash
# 检查日志
tail -50 logs/system.log

# 检查端口占用
netstat -tunlp | grep 5000

# 检查配置文件
python3 -m json.tool config/trading_config.json

# 检查依赖
pip3 check
```

**常见原因**:
- 端口被占用
- 配置文件格式错误
- 缺少依赖包
- 数据库连接失败

#### 2. 故障转移未触发

**症状**: 主服务器宕机后备份服务器未接管

**排查步骤**:
```bash
# 检查同步状态
curl http://backup-server:5001/api/status

# 查看心跳日志
grep "heartbeat" logs/system.log | tail -20

# 检查网络连通性
ping primary-server
telnet primary-server 5000
```

**常见原因**:
- 心跳配置错误
- 网络不通
- 防火墙阻止
- 认证令牌不匹配

#### 3. API 请求被限流

**症状**: 返回 429 错误

**排查步骤**:
```bash
# 查看限流日志
grep "rate limit" logs/security.log

# 检查客户端 IP
python3 utilities/api_security.py --status --client CLIENT_ID

# 清除限流记录
python3 utilities/api_security.py --reset CLIENT_ID
```

#### 4. 数据同步延迟

**症状**: 主备服务器数据不一致

**排查步骤**:
```bash
# 查看同步队列
curl http://localhost:5000/api/status | jq .sync_queue_size

# 检查网络延迟
ping -c 100 backup-server

# 查看同步日志
grep "sync" logs/system.log | tail -50
```

### 日志分析

#### 关键日志级别

- **CRITICAL**: 系统崩溃、数据丢失
- **ERROR**: 功能错误、请求失败
- **WARNING**: 潜在问题、性能降级
- **INFO**: 正常操作、状态变更
- **DEBUG**: 详细调试信息

#### 常用日志查询

```bash
# 查找错误
grep -E "ERROR|CRITICAL" logs/system.log

# 统计错误类型
grep ERROR logs/system.log | cut -d: -f4 | sort | uniq -c

# 查看特定时间段
sed -n '/2024-01-01 10:00/,/2024-01-01 11:00/p' logs/system.log

# 实时监控错误
tail -f logs/system.log | grep --line-buffered ERROR
```

---

## 性能优化

### 应用层优化

#### 1. 缓存策略

```python
# Redis 缓存
from redis import Redis
redis_client = Redis(host='localhost', port=6379)

# 缓存交易数据
def get_trade_data(symbol):
    cache_key = f"trade:{symbol}"
    data = redis_client.get(cache_key)

    if data is None:
        data = fetch_from_db(symbol)
        redis_client.setex(cache_key, 300, json.dumps(data))

    return json.loads(data)
```

#### 2. 连接池

```python
# 数据库连接池
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://user:pass@localhost/db',
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10
)
```

#### 3. 异步处理

```python
# 使用消息队列异步处理
from utilities.message_queue import MessageQueue

mq = MessageQueue()

# 发送异步任务
mq.publish('analysis_queue', {'symbol': 'BTCUSD'})

# 消费任务
@mq.subscribe('analysis_queue')
def process_analysis(data):
    # 执行耗时分析
    pass
```

### 数据库优化

#### 1. 查询优化

```sql
-- 避免 SELECT *
SELECT id, symbol, price FROM trades WHERE symbol = 'BTCUSD';

-- 使用索引
CREATE INDEX idx_trades_symbol_time ON trades(symbol, timestamp);

-- 分页查询
SELECT * FROM trades ORDER BY timestamp DESC LIMIT 100 OFFSET 0;
```

#### 2. 分区表

```sql
-- 按时间分区
CREATE TABLE trades (
    id SERIAL,
    symbol VARCHAR(20),
    timestamp TIMESTAMP
) PARTITION BY RANGE (timestamp);

CREATE TABLE trades_2024_q1 PARTITION OF trades
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
```

### 网络优化

#### 1. HTTP/2 支持

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    # SSL 配置
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;
}
```

#### 2. 压缩

```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css application/json;
```

---

## 安全最佳实践

### 1. 密码和密钥管理

- 使用环境变量存储敏感信息
- 定期轮换 API 密钥
- 使用强密码策略

```bash
# 环境变量
export DB_PASSWORD='strong_password'
export API_KEY='secure_api_key'

# 密钥轮换
python3 utilities/encryption_manager.py --rotate-keys
```

### 2. 网络安全

- 启用防火墙
- 使用 HTTPS
- 限制 IP 访问

```bash
# UFW 防火墙
sudo ufw allow 22/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# IP 白名单
python3 utilities/api_security.py --whitelist-add 192.168.1.100
```

### 3. 数据加密

- 传输加密 (TLS)
- 存储加密 (AES-256)
- 备份加密

```python
# 加密敏感配置
from utilities.encryption_manager import EncryptionManager

manager = EncryptionManager()
manager.encrypt_config_file('config/credentials.json')
```

### 4. 审计日志

- 记录所有敏感操作
- 定期审查日志
- 保留足够长的日志周期

```python
# 审计日志
import logging
audit_logger = logging.getLogger('audit')

audit_logger.info(f"用户 {user_id} 执行交易 {trade_id}")
```

### 5. 定期安全检查

```bash
# 依赖漏洞检查
pip3 install safety
safety check

# 代码安全扫描
pip3 install bandit
bandit -r . -f json -o security_report.json

# 渗透测试
# 定期进行渗透测试
```

---

## 附录

### A. 配置文件清单

| 文件 | 说明 |
|------|------|
| `config/backup_config.json` | 备份配置 |
| `config/encryption_config.json` | 加密配置 |
| `config/process_config.json` | 进程配置 |
| `config/monitoring_config.json` | 监控配置 |
| `config/logging_config.json` | 日志配置 |
| `config/testing_config.json` | 测试配置 |
| `config/api_security_config.json` | API 安全配置 |
| `config/server_sync_config.json` | 服务器同步配置 |

### B. API 接口清单

详见各模块文档

### C. 错误代码

| 代码 | 说明 |
|------|------|
| 1000 | 系统错误 |
| 2000 | 配置错误 |
| 3000 | 数据库错误 |
| 4000 | 网络错误 |
| 5000 | 业务逻辑错误 |

### D. 性能基准

- API 响应时间: < 100ms (P95)
- 数据库查询: < 50ms (P95)
- 内存使用: < 4GB
- CPU 使用: < 70%

---

## 联系方式

- 技术支持: support@example.com
- 文档反馈: docs@example.com
- 紧急联系: +86-xxx-xxxx-xxxx

---

**最后更新**: 2024-01-22
**版本**: v2.6
