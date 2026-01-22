# 双服务器同步和故障转移系统

## 概述

本系统实现了主备服务器之间的状态同步、健康监测和自动故障转移功能,确保交易系统的高可用性。

## 主要特性

### 1. 心跳监测
- 定期发送心跳包检测服务器健康状态
- 可配置的心跳间隔和超时时间
- 连续失败阈值触发故障转移

### 2. 自动故障转移
- 主服务器故障时,备份服务器自动升级为主服务器
- 最小化服务中断时间
- 支持自定义故障转移回调

### 3. 自动回切
- 原主服务器恢复后,可自动回切
- 健康状态验证机制
- 支持手动控制回切时机

### 4. 数据同步
- 优先级队列管理同步任务
- 批量同步提高效率
- 自动重试机制

### 5. 数据复制
- 关键数据实时复制到备份服务器
- 支持多种数据类型(状态、配置、业务数据)
- 优先级控制

## 架构

```
┌─────────────────────┐         心跳/同步         ┌─────────────────────┐
│   主服务器           │◄────────────────────────►│   备份服务器          │
│   (Primary)         │                          │   (Backup)          │
│                     │                          │                     │
│  - 处理业务请求      │                          │  - 待命状态          │
│  - 发送心跳         │                          │  - 接收同步数据       │
│  - 同步数据         │                          │  - 监测主服务器       │
└─────────────────────┘                          └─────────────────────┘
         │                                                   │
         │                                                   │
         │        主服务器故障                                │
         ▼                                                   ▼
         ✗                                          ┌─────────────────────┐
                                                    │   备份服务器          │
                                                    │   (升级为 Primary)   │
                                                    │                     │
                                                    │  - 接管业务请求       │
                                                    │  - 发送心跳          │
                                                    └─────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
pip install flask requests psutil
```

### 2. 配置主服务器

编辑 `config/server_sync_config.json`:

```json
{
  "server_id": "server-primary",
  "role": "primary",
  "peer_server": {
    "url": "http://backup-server-ip:5001",
    "auth_token": "your-secure-token"
  },
  "heartbeat_interval": 5,
  "heartbeat_timeout": 15,
  "failover_threshold": 3
}
```

### 3. 配置备份服务器

创建备份服务器配置文件:

```json
{
  "server_id": "server-backup",
  "role": "backup",
  "peer_server": {
    "url": "http://primary-server-ip:5000",
    "auth_token": "your-secure-token"
  },
  "heartbeat_interval": 5,
  "heartbeat_timeout": 15,
  "failover_threshold": 3
}
```

### 4. 启动服务器

主服务器:
```bash
python examples/flask_sync_example.py --host 0.0.0.0 --port 5000
```

备份服务器:
```bash
python examples/flask_sync_example.py --host 0.0.0.0 --port 5001
```

## API 接口

### 健康检查

```bash
GET /api/health
```

响应:
```json
{
  "status": "healthy",
  "server_id": "server-primary",
  "role": "primary"
}
```

### 获取同步状态

```bash
GET /api/status
```

响应:
```json
{
  "server_id": "server-primary",
  "role": "primary",
  "status": "healthy",
  "peer_status": "healthy",
  "sync_queue_size": 0,
  "consecutive_failures": 0,
  "last_heartbeat": 1234567890.123,
  "time_since_last_heartbeat": 3.5
}
```

### 手动故障转移

```bash
POST /api/failover
```

响应:
```json
{
  "success": true,
  "message": "故障转移已触发"
}
```

### 手动回切

```bash
POST /api/failback
```

响应:
```json
{
  "success": true,
  "message": "回切已触发"
}
```

## 集成到现有应用

### 1. 基本集成

```python
from utilities.server_sync import ServerSyncManager, DataReplicator, ServerRole

# 创建同步管理器
sync_manager = ServerSyncManager(config_path='config/server_sync_config.json')

# 创建数据复制器
data_replicator = DataReplicator(sync_manager)

# 启动同步管理器
sync_manager.start()
```

### 2. 注册回调函数

```python
def on_failover(old_role, new_role):
    print(f"故障转移: {old_role.value} -> {new_role.value}")
    # 执行故障转移逻辑
    # - 更新负载均衡配置
    # - 发送通知
    # - 激活备用资源

def on_failback(old_role, new_role):
    print(f"回切: {old_role.value} -> {new_role.value}")
    # 执行回切逻辑

sync_manager.register_failover_callback(on_failover)
sync_manager.register_failback_callback(on_failback)
```

### 3. 复制业务数据

```python
# 在主服务器上复制数据
if sync_manager.role == ServerRole.PRIMARY:
    data_replicator.replicate(
        key='trade:12345',
        value={'symbol': 'BTCUSD', 'price': 50000},
        priority=1  # 1-10, 数字越小优先级越高
    )
```

### 4. 业务逻辑保护

```python
# 只允许主服务器处理写操作
@app.route('/api/trade', methods=['POST'])
def trade():
    if sync_manager.role != ServerRole.PRIMARY:
        return jsonify({'error': 'Only primary server can process trades'}), 403

    # 处理交易
    # ...

    # 复制交易数据
    data_replicator.replicate(key=trade_id, value=trade_data, priority=1)

    return jsonify({'success': True})
```

## 配置说明

### server_sync_config.json

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| server_id | 服务器唯一标识 | 主机名 |
| role | 服务器角色 (primary/backup/standalone) | standalone |
| peer_server.url | 对端服务器 URL | - |
| peer_server.auth_token | 认证令牌 | - |
| heartbeat_interval | 心跳间隔(秒) | 5 |
| heartbeat_timeout | 心跳超时(秒) | 15 |
| failover_threshold | 故障转移阈值(连续失败次数) | 3 |
| sync_interval | 同步间隔(秒) | 10 |
| sync_batch_size | 同步批量大小 | 100 |

## 故障场景处理

### 场景 1: 主服务器宕机

1. 备份服务器检测到心跳超时
2. 连续失败次数达到阈值
3. 备份服务器自动升级为主服务器
4. 开始处理业务请求

### 场景 2: 网络闪断

1. 短暂的网络中断导致心跳超时
2. 故障计数器递增但未达到阈值
3. 网络恢复后心跳正常
4. 故障计数器重置

### 场景 3: 主服务器恢复

1. 原主服务器重新上线
2. 当前主服务器(原备份)检测到对端恢复
3. 验证原主服务器健康状态
4. 执行回切,降级为备份服务器

## 监控指标

### 关键指标

- **心跳延迟**: 对端心跳响应时间
- **同步队列长度**: 待同步任务数量
- **连续失败次数**: 心跳失败计数
- **角色状态**: 当前服务器角色
- **对端状态**: 对端服务器健康状态

### 告警规则

- 心跳超时 > 15 秒: 警告
- 连续失败 >= 3 次: 严重
- 同步队列 > 1000: 警告
- 角色变更: 通知

## 测试

### 单元测试

```bash
python -m pytest tests/test_server_sync.py -v
```

### 故障转移测试

1. 启动主服务器和备份服务器
2. 停止主服务器进程
3. 观察备份服务器自动升级为主服务器
4. 重启原主服务器
5. 观察自动回切

### 手动测试

```bash
# 查看当前状态
curl http://localhost:5000/api/status

# 手动触发故障转移(仅备份服务器)
curl -X POST http://localhost:5001/api/failover

# 手动触发回切(仅主服务器)
curl -X POST http://localhost:5000/api/failback
```

## 最佳实践

### 1. 部署建议

- 主备服务器部署在不同的物理机或数据中心
- 使用独立的网络连接确保心跳稳定性
- 配置防火墙规则允许心跳和同步流量

### 2. 配置建议

- 心跳间隔: 5-10 秒(根据网络延迟调整)
- 心跳超时: 心跳间隔的 3 倍
- 故障转移阈值: 3-5 次连续失败
- 同步间隔: 根据数据量和网络带宽调整

### 3. 安全建议

- 使用强认证令牌
- 启用 HTTPS 加密通信
- 定期轮换认证令牌
- 限制同步 API 的访问来源

### 4. 监控建议

- 持续监控心跳状态
- 设置告警规则
- 记录所有角色变更事件
- 定期检查同步队列堆积

## 故障排查

### 问题: 频繁触发故障转移

**可能原因**:
- 网络不稳定
- 心跳超时配置过短
- 服务器负载过高

**解决方案**:
- 增加心跳超时时间
- 提高故障转移阈值
- 优化服务器性能

### 问题: 同步队列堆积

**可能原因**:
- 对端服务器响应慢
- 网络带宽不足
- 同步任务过多

**解决方案**:
- 增加同步批量大小
- 调整同步间隔
- 优化同步数据大小

### 问题: 回切失败

**可能原因**:
- 原主服务器健康检查失败
- 数据不一致

**解决方案**:
- 检查原主服务器日志
- 验证数据同步状态
- 手动执行数据对账

## 许可证

MIT License
