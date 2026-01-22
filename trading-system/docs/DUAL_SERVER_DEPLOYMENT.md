# 双服务器部署指南

本文档说明如何将交易系统部署在两台服务器上,以优化资源使用和性能。

## 概述

双服务器架构将系统分为两个角色:

- **Server1 (主服务器)**: 运行核心交易组件和用户交互服务
- **Server2 (计算服务器)**: 运行AI计算、数据分析和训练任务

## 服务器角色分配

### Server1 - 主服务器

**特点**: 低CPU占用、高优先级、实时响应

**运行组件**:
- `telegram_bot` - Telegram机器人,用户交互
- `api_server` - API服务器,远程控制
- `mt5_bridge` - MT5桥接服务
- `position_monitor` - 持仓监控
- `circuit_breaker` - 熔断保护
- `performance_monitor` - 性能监控

**资源要求**:
- CPU: 2核以上
- 内存: 2GB以上
- 磁盘: 20GB以上
- 网络: 稳定连接,低延迟

### Server2 - 计算服务器

**特点**: 高CPU密集型、可调度、批处理

**运行组件**:
- `ai_ensemble` - AI模型集成
- `news_aggregator` - 新闻聚合
- `dynamic_indicators` - 动态指标计算
- `shadow_trading` - 影子交易训练
- `self_evolution` - 自我进化
- `proprietary_model_trainer` - 自有模型训练
- `data_provider` - 实盘数据提供
- `review_system` - 复盘系统
- `daily_analyzer` - 每日分析

**资源要求**:
- CPU: 4核以上(推荐8核)
- 内存: 4GB以上(推荐8GB)
- 磁盘: 50GB以上
- 网络: 稳定连接

## 部署步骤

### 1. 准备工作

确保两台服务器都满足以下要求:

```bash
# 检查Python版本(需要3.8+)
python --version

# 检查git
git --version

# 检查网络连通性
ping -c 3 <对方服务器IP>
```

### 2. 在Server1上部署

```bash
# 克隆代码
git clone <your-repo-url> trading-system
cd trading-system

# 配置服务器角色
python utilities/server_role_manager.py server1

# 编辑部署配置
nano config/deployment_config.json
# 修改 server_roles.server1.ip 为当前服务器IP
# 修改 server_roles.server2.ip 为Server2的IP
# 修改 communication 中的API密钥

# 运行安装脚本
bash setup.sh
# 或 Windows: setup.bat

# 启动系统
bash start_system.sh
# 或 Windows: start_system.bat
```

### 3. 在Server2上部署

```bash
# 克隆代码
git clone <your-repo-url> trading-system
cd trading-system

# 配置服务器角色
python utilities/server_role_manager.py server2

# 编辑部署配置
nano config/deployment_config.json
# 修改 server_roles.server1.ip 为Server1的IP
# 修改 server_roles.server2.ip 为当前服务器IP
# 修改 communication 中的API密钥(与Server1相同)

# 运行安装脚本
bash setup.sh

# 启动系统
bash start_system.sh
```

### 4. 配置网络通信

#### 开放端口

**Server1需要开放**:
- 5000 (API服务器)

**Server2需要开放**:
- 5001 (计算服务API)

```bash
# Ubuntu/Debian
sudo ufw allow 5000/tcp
sudo ufw allow 5001/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --permanent --add-port=5001/tcp
sudo firewall-cmd --reload
```

#### 配置API密钥

编辑 `config/deployment_config.json`:

```json
{
  "communication": {
    "method": "http_api",
    "server1_to_server2": {
      "base_url": "http://<Server2的IP>:5001",
      "api_key": "your-secret-key-here",
      "timeout_seconds": 30,
      "retry_times": 3
    },
    "server2_to_server1": {
      "base_url": "http://<Server1的IP>:5000",
      "api_key": "your-secret-key-here",
      "timeout_seconds": 10,
      "retry_times": 3
    }
  }
}
```

**重要**: 两台服务器的API密钥必须相同!

### 5. 验证部署

#### 在Server1上验证

```bash
# 查看组件状态
python component_launcher.py --status

# 检查远程服务器连接
python -c "from utilities.server_role_manager import ServerRoleManager; m = ServerRoleManager(); print('远程健康:', m.check_remote_health())"

# 查看运行日志
tail -f logs/bot.log
tail -f logs/api.log
```

#### 在Server2上验证

```bash
# 查看组件状态
python component_launcher.py --status

# 检查远程服务器连接
python -c "from utilities.server_role_manager import ServerRoleManager; m = ServerRoleManager(); print('远程健康:', m.check_remote_health())"

# 查看性能监控
tail -f logs/performance/performance_*.jsonl
```

## CPU智能限制

系统集成了CPU智能限制功能,防止长时间高CPU占用。

### 配置CPU限制

编辑 `config/cpu_limiter_config.json`:

```json
{
  "max_cpu_percent": 85,
  "warning_cpu_percent": 80,
  "check_interval_seconds": 30,
  "high_cpu_window_minutes": 30,
  "cooldown_duration_seconds": 300,
  "auto_throttle": true,
  "notify_on_throttle": true,
  "throttle_actions": {
    "reduce_ai_requests": true,
    "increase_sleep_time": true,
    "pause_non_critical": true
  }
}
```

### CPU限制行为

当系统检测到CPU使用率≥85%持续30分钟时:

1. **减少AI请求**: 暂停或减少AI模型调用
2. **增加睡眠时间**: 将sleep时间翻倍
3. **暂停非关键任务**: 暂停数据聚合、分析等

CPU使用率恢复正常后,等待5分钟冷却期再恢复正常运行。

### Server2的CPU调度

Server2支持CPU密集型任务的时间调度:

```json
{
  "resource_limits": {
    "server2": {
      "cpu_intensive_schedule": {
        "ai_training": {
          "enabled": true,
          "allowed_hours": [0, 1, 2, 3, 4, 5, 22, 23],
          "max_concurrent_tasks": 2
        },
        "model_evolution": {
          "enabled": true,
          "allowed_hours": [2, 3, 4, 5],
          "max_concurrent_tasks": 1
        }
      }
    }
  }
}
```

这样可以将高CPU任务安排在低峰时段(夜间)运行。

## 日常管理

### 查看系统状态

```bash
# 查看组件状态
python component_launcher.py --status

# 查看性能指标
python utilities/performance_monitor.py

# 查看CPU限制状态
python utilities/cpu_limiter.py
```

### 重启系统

```bash
# Server1
./stop_system.sh && ./start_system.sh

# Server2
./stop_system.sh && ./start_system.sh
```

### 更新系统

```bash
# 在两台服务器上都执行
./update_system.sh
# 或 Windows: update_system.bat
```

### 切换服务器角色

如果需要更换服务器角色:

```bash
# 方法1: 使用工具
python utilities/server_role_manager.py server2

# 方法2: 手动编辑
nano config/server_local.json
# 修改 server_role 为 "server1" 或 "server2"

# 重启系统
./stop_system.sh && ./start_system.sh
```

## 故障排查

### Server间无法通信

1. 检查防火墙设置
2. 检查IP地址配置
3. 检查API密钥是否一致
4. 测试网络连通性: `curl http://<对方IP>:5000/api/health`

### CPU限制过于频繁

1. 调高CPU阈值: `max_cpu_percent: 90`
2. 延长触发时间: `high_cpu_window_minutes: 60`
3. 减少并发任务: `max_concurrent_tasks: 1`

### 组件未启动

1. 查看日志: `tail -f logs/*.log`
2. 检查组件脚本是否存在
3. 检查Python依赖: `python utilities/system_checker.py`
4. 手动测试组件: `python <组件路径>`

## 性能优化建议

### Server1优化

- 保持低CPU使用率(< 70%)
- 优先响应用户请求
- 使用SSD存储提升响应速度
- 配置稳定网络连接

### Server2优化

- 使用多核CPU
- 增加内存以支持并发训练
- 配置任务调度避免峰时运行
- 定期清理日志和缓存

### 网络优化

- 使用内网IP通信(如在同一IDC)
- 配置CDN加速外部数据获取
- 压缩服务器间传输数据
- 设置合理的超时和重试

## 监控与告警

### 性能监控

系统会自动记录性能指标到:
- `logs/performance/performance_YYYYMMDD.jsonl`

可以使用第三方工具如Grafana可视化这些数据。

### CPU告警

CPU限制器会在以下情况发送告警:
- CPU使用率超过警告阈值(80%)
- 激活CPU限制
- 内存使用率过高
- 磁盘空间不足

告警会记录到日志,也可以配置Telegram通知。

## 单服务器模式

如果只有一台服务器,系统会自动以单服务器模式运行:

1. 所有组件都在同一台服务器上运行
2. 不需要配置服务器间通信
3. CPU限制仍然生效
4. 建议配置更严格的CPU阈值

要强制使用单服务器模式:

```bash
# 设置角色为server1
python utilities/server_role_manager.py server1

# 编辑deployment_config.json,将deployment_mode改为"single_server"
```

## 常见问题

### Q: 能否在一台服务器上运行所有组件?

A: 可以,系统会自动检测并以单服务器模式运行。但建议使用双服务器以优化性能。

### Q: Server1和Server2能否角色互换?

A: 可以,只需重新配置服务器角色并重启系统即可。

### Q: 能否使用3台或更多服务器?

A: 当前架构设计为双服务器,如需更多服务器,需要修改`deployment_config.json`添加新的服务器角色。

### Q: 服务器间通信是否加密?

A: 当前使用HTTP+API密钥,如需加密,建议配置HTTPS或VPN。

### Q: CPU限制会影响交易吗?

A: 不会。高优先级的交易组件(如mt5_bridge、telegram_bot)不受CPU限制影响,只有训练、分析等非关键任务会被限制。

## 技术支持

如遇到问题,请检查:
1. 日志文件 (`logs/`)
2. 系统自检 (`python utilities/system_checker.py`)
3. 组件状态 (`python component_launcher.py --status`)
4. CPU限制状态 (`python utilities/cpu_limiter.py`)

---

**版本**: v2.5
**更新日期**: 2024
