#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API限流和安全防护系统
提供速率限制、IP黑名单、请求验证等安全功能
"""

import os
import sys
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from functools import wraps
import threading

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """速率限制规则"""
    max_requests: int  # 最大请求数
    window_seconds: int  # 时间窗口(秒)
    block_duration: int = 300  # 阻止时长(秒)


@dataclass
class RequestRecord:
    """请求记录"""
    client_id: str
    endpoint: str
    timestamp: float
    method: str
    ip_address: str
    user_agent: str = ""
    blocked: bool = False


@dataclass
class SecurityEvent:
    """安全事件"""
    event_type: str  # rate_limit_exceeded, suspicious_activity, blocked_ip
    client_id: str
    ip_address: str
    endpoint: str
    timestamp: float
    details: Dict = None


class RateLimiter:
    """速率限制器"""

    def __init__(self, rules: Dict[str, RateLimitRule] = None):
        # 默认规则
        self.rules = rules or {
            'default': RateLimitRule(max_requests=100, window_seconds=60),
            'auth': RateLimitRule(max_requests=10, window_seconds=60),
            'trading': RateLimitRule(max_requests=50, window_seconds=60),
            'query': RateLimitRule(max_requests=200, window_seconds=60)
        }

        # 请求记录 {client_id: {endpoint: deque([timestamp, ...])}}
        self.request_history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque())
        )

        # 阻止列表 {client_id: unblock_time}
        self.blocked_clients: Dict[str, float] = {}

        # 锁
        self.lock = threading.Lock()

    def check_rate_limit(self, client_id: str, endpoint: str) -> tuple[bool, Optional[str]]:
        """
        检查速率限制

        Args:
            client_id: 客户端ID
            endpoint: 端点名称

        Returns:
            (是否允许, 错误消息)
        """
        with self.lock:
            # 检查是否被阻止
            if client_id in self.blocked_clients:
                unblock_time = self.blocked_clients[client_id]
                if time.time() < unblock_time:
                    remaining = int(unblock_time - time.time())
                    return False, f"Client blocked. Unblock in {remaining} seconds"
                else:
                    # 解除阻止
                    del self.blocked_clients[client_id]

            # 获取规则
            rule = self._get_rule_for_endpoint(endpoint)

            # 获取请求历史
            history = self.request_history[client_id][endpoint]

            # 清理过期记录
            cutoff_time = time.time() - rule.window_seconds
            while history and history[0] < cutoff_time:
                history.popleft()

            # 检查请求数
            if len(history) >= rule.max_requests:
                # 超过限制,阻止客户端
                self.blocked_clients[client_id] = time.time() + rule.block_duration
                logger.warning(
                    f"Rate limit exceeded for {client_id} on {endpoint}. "
                    f"Blocked for {rule.block_duration}s"
                )
                return False, f"Rate limit exceeded. Try again later."

            # 记录本次请求
            history.append(time.time())

            return True, None

    def _get_rule_for_endpoint(self, endpoint: str) -> RateLimitRule:
        """获取端点的速率限制规则"""
        # 根据端点路径匹配规则
        for rule_name, rule in self.rules.items():
            if rule_name in endpoint.lower():
                return rule

        return self.rules['default']

    def reset_client(self, client_id: str):
        """重置客户端限制"""
        with self.lock:
            if client_id in self.blocked_clients:
                del self.blocked_clients[client_id]
            if client_id in self.request_history:
                del self.request_history[client_id]

    def get_client_stats(self, client_id: str) -> Dict:
        """获取客户端统计信息"""
        with self.lock:
            stats = {
                'client_id': client_id,
                'blocked': client_id in self.blocked_clients,
                'endpoints': {}
            }

            if client_id in self.blocked_clients:
                stats['unblock_time'] = self.blocked_clients[client_id]

            if client_id in self.request_history:
                for endpoint, history in self.request_history[client_id].items():
                    rule = self._get_rule_for_endpoint(endpoint)
                    cutoff_time = time.time() - rule.window_seconds
                    recent_requests = sum(1 for ts in history if ts >= cutoff_time)

                    stats['endpoints'][endpoint] = {
                        'recent_requests': recent_requests,
                        'max_requests': rule.max_requests,
                        'window_seconds': rule.window_seconds
                    }

            return stats


class IPBlacklist:
    """IP黑名单"""

    def __init__(self, blacklist_file: str = None):
        self.base_dir = Path(__file__).parent.parent
        self.blacklist_file = blacklist_file or (
            self.base_dir / "config" / "ip_blacklist.json"
        )

        # 黑名单 {ip: {reason, timestamp, expires}}
        self.blacklist: Dict[str, Dict] = {}
        self.lock = threading.Lock()

        self._load_blacklist()

    def _load_blacklist(self):
        """加载黑名单"""
        if not Path(self.blacklist_file).exists():
            return

        try:
            with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                self.blacklist = json.load(f)
            logger.info(f"已加载IP黑名单: {len(self.blacklist)} 个IP")
        except Exception as e:
            logger.error(f"加载IP黑名单失败: {e}")

    def _save_blacklist(self):
        """保存黑名单"""
        try:
            Path(self.blacklist_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(self.blacklist, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存IP黑名单失败: {e}")

    def is_blocked(self, ip_address: str) -> tuple[bool, Optional[str]]:
        """
        检查IP是否被阻止

        Args:
            ip_address: IP地址

        Returns:
            (是否被阻止, 原因)
        """
        with self.lock:
            if ip_address not in self.blacklist:
                return False, None

            entry = self.blacklist[ip_address]

            # 检查是否过期
            expires = entry.get('expires')
            if expires and time.time() > expires:
                # 过期,移除
                del self.blacklist[ip_address]
                self._save_blacklist()
                return False, None

            return True, entry.get('reason', 'IP blocked')

    def add_ip(self, ip_address: str, reason: str = "",
              duration: Optional[int] = None):
        """
        添加IP到黑名单

        Args:
            ip_address: IP地址
            reason: 原因
            duration: 阻止时长(秒), None表示永久
        """
        with self.lock:
            entry = {
                'reason': reason,
                'timestamp': time.time()
            }

            if duration:
                entry['expires'] = time.time() + duration

            self.blacklist[ip_address] = entry
            self._save_blacklist()

            logger.warning(f"已添加IP到黑名单: {ip_address} - {reason}")

    def remove_ip(self, ip_address: str):
        """从黑名单移除IP"""
        with self.lock:
            if ip_address in self.blacklist:
                del self.blacklist[ip_address]
                self._save_blacklist()
                logger.info(f"已从黑名单移除IP: {ip_address}")

    def list_blocked_ips(self) -> List[Dict]:
        """列出所有被阻止的IP"""
        with self.lock:
            blocked = []
            for ip, entry in self.blacklist.items():
                blocked.append({
                    'ip': ip,
                    'reason': entry.get('reason'),
                    'timestamp': entry.get('timestamp'),
                    'expires': entry.get('expires')
                })
            return blocked


class RequestValidator:
    """请求验证器"""

    def __init__(self):
        self.required_headers = ['User-Agent']

    def validate_request(self, headers: Dict, params: Dict = None) -> tuple[bool, Optional[str]]:
        """
        验证请求

        Args:
            headers: 请求头
            params: 请求参数

        Returns:
            (是否有效, 错误消息)
        """
        # 检查必需的请求头
        for header in self.required_headers:
            if header not in headers:
                return False, f"Missing required header: {header}"

        # 检查User-Agent
        user_agent = headers.get('User-Agent', '')
        if self._is_suspicious_user_agent(user_agent):
            return False, "Suspicious User-Agent"

        # 检查参数
        if params:
            if not self._validate_params(params):
                return False, "Invalid parameters"

        return True, None

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """检查User-Agent是否可疑"""
        suspicious_patterns = [
            'bot', 'crawler', 'spider', 'scraper',
            'curl', 'wget', 'python-requests'
        ]

        user_agent_lower = user_agent.lower()
        for pattern in suspicious_patterns:
            if pattern in user_agent_lower:
                return True

        return False

    def _validate_params(self, params: Dict) -> bool:
        """验证参数"""
        # 检查SQL注入
        sql_keywords = ['select', 'insert', 'update', 'delete', 'drop', 'union']
        for value in params.values():
            if isinstance(value, str):
                value_lower = value.lower()
                for keyword in sql_keywords:
                    if keyword in value_lower:
                        return False

        # 检查XSS
        xss_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        for value in params.values():
            if isinstance(value, str):
                value_lower = value.lower()
                for pattern in xss_patterns:
                    if pattern in value_lower:
                        return False

        return True


class APISecurityManager:
    """API安全管理器"""

    def __init__(self, config_path: str = None):
        self.base_dir = Path(__file__).parent.parent

        # 加载配置
        if config_path is None:
            config_path = self.base_dir / "config" / "api_security_config.json"

        self.config = self._load_config(config_path)

        # 初始化组件
        self.rate_limiter = RateLimiter(self._load_rate_limit_rules())
        self.ip_blacklist = IPBlacklist()
        self.request_validator = RequestValidator()

        # 安全事件记录
        self.security_events: List[SecurityEvent] = []
        self.events_lock = threading.Lock()

        # 请求日志
        self.request_log_file = self.base_dir / "logs" / "api_requests.log"
        self.request_log_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path: Path) -> Dict:
        """加载配置"""
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}

    def _load_rate_limit_rules(self) -> Dict[str, RateLimitRule]:
        """加载速率限制规则"""
        rules = {}
        rate_limits = self.config.get('rate_limits', {})

        for name, config in rate_limits.items():
            rules[name] = RateLimitRule(
                max_requests=config['max_requests'],
                window_seconds=config['window_seconds'],
                block_duration=config.get('block_duration', 300)
            )

        return rules

    def check_request(self, client_id: str, endpoint: str,
                     ip_address: str, headers: Dict,
                     params: Dict = None) -> tuple[bool, Optional[str]]:
        """
        检查请求是否允许

        Args:
            client_id: 客户端ID
            endpoint: 端点
            ip_address: IP地址
            headers: 请求头
            params: 请求参数

        Returns:
            (是否允许, 错误消息)
        """
        # 1. 检查IP黑名单
        is_blocked, reason = self.ip_blacklist.is_blocked(ip_address)
        if is_blocked:
            self._log_security_event(
                'blocked_ip',
                client_id,
                ip_address,
                endpoint,
                {'reason': reason}
            )
            return False, f"Access denied: {reason}"

        # 2. 验证请求
        is_valid, error = self.request_validator.validate_request(headers, params)
        if not is_valid:
            self._log_security_event(
                'invalid_request',
                client_id,
                ip_address,
                endpoint,
                {'error': error}
            )
            return False, error

        # 3. 检查速率限制
        allowed, error = self.rate_limiter.check_rate_limit(client_id, endpoint)
        if not allowed:
            self._log_security_event(
                'rate_limit_exceeded',
                client_id,
                ip_address,
                endpoint,
                {'error': error}
            )
            return False, error

        # 记录请求
        self._log_request(client_id, endpoint, ip_address, headers)

        return True, None

    def _log_security_event(self, event_type: str, client_id: str,
                          ip_address: str, endpoint: str, details: Dict):
        """记录安全事件"""
        event = SecurityEvent(
            event_type=event_type,
            client_id=client_id,
            ip_address=ip_address,
            endpoint=endpoint,
            timestamp=time.time(),
            details=details
        )

        with self.events_lock:
            self.security_events.append(event)

            # 保留最近1000个事件
            if len(self.security_events) > 1000:
                self.security_events = self.security_events[-1000:]

        logger.warning(
            f"Security event: {event_type} - "
            f"client={client_id}, ip={ip_address}, endpoint={endpoint}"
        )

    def _log_request(self, client_id: str, endpoint: str,
                    ip_address: str, headers: Dict):
        """记录请求"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'client_id': client_id,
                'endpoint': endpoint,
                'ip_address': ip_address,
                'user_agent': headers.get('User-Agent', '')
            }

            with open(self.request_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"记录请求日志失败: {e}")

    def get_security_stats(self) -> Dict:
        """获取安全统计"""
        with self.events_lock:
            # 统计事件类型
            event_counts = defaultdict(int)
            for event in self.security_events:
                event_counts[event.event_type] += 1

            # 最近的事件
            recent_events = []
            for event in self.security_events[-10:]:
                recent_events.append({
                    'type': event.event_type,
                    'client_id': event.client_id,
                    'ip': event.ip_address,
                    'endpoint': event.endpoint,
                    'timestamp': event.timestamp
                })

            return {
                'total_events': len(self.security_events),
                'event_counts': dict(event_counts),
                'blocked_ips': len(self.ip_blacklist.blacklist),
                'recent_events': recent_events
            }


# Flask装饰器
def require_api_security(security_manager: APISecurityManager):
    """
    Flask路由装饰器 - 添加API安全检查

    使用示例:
    @app.route('/api/endpoint')
    @require_api_security(security_manager)
    def endpoint():
        return {'status': 'ok'}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify

            # 获取请求信息
            client_id = request.headers.get('X-Client-ID', request.remote_addr)
            endpoint = request.endpoint or request.path
            ip_address = request.remote_addr
            headers = dict(request.headers)
            params = dict(request.args)

            # 安全检查
            allowed, error = security_manager.check_request(
                client_id, endpoint, ip_address, headers, params
            )

            if not allowed:
                return jsonify({'error': error}), 429

            # 继续执行
            return func(*args, **kwargs)

        return wrapper
    return decorator


def main():
    """主函数 - 测试和管理"""
    import argparse

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='API安全管理')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # stats命令
    subparsers.add_parser('stats', help='查看安全统计')

    # blacklist命令
    parser_blacklist = subparsers.add_parser('blacklist', help='管理IP黑名单')
    parser_blacklist.add_argument('action', choices=['list', 'add', 'remove'],
                                 help='操作')
    parser_blacklist.add_argument('--ip', help='IP地址')
    parser_blacklist.add_argument('--reason', help='原因')
    parser_blacklist.add_argument('--duration', type=int, help='阻止时长(秒)')

    # reset命令
    parser_reset = subparsers.add_parser('reset', help='重置客户端限制')
    parser_reset.add_argument('client_id', help='客户端ID')

    args = parser.parse_args()

    manager = APISecurityManager()

    if args.command == 'stats':
        stats = manager.get_security_stats()
        print("\nAPI安全统计:")
        print("=" * 60)
        print(f"总安全事件数: {stats['total_events']}")
        print(f"被阻止的IP数: {stats['blocked_ips']}")
        print("\n事件统计:")
        for event_type, count in stats['event_counts'].items():
            print(f"  {event_type}: {count}")
        print("\n最近的事件:")
        for event in stats['recent_events']:
            ts = datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S')
            print(f"  [{ts}] {event['type']} - {event['client_id']} @ {event['endpoint']}")

    elif args.command == 'blacklist':
        if args.action == 'list':
            blocked = manager.ip_blacklist.list_blocked_ips()
            print(f"\nIP黑名单 ({len(blocked)} 个):")
            print("=" * 60)
            for entry in blocked:
                ts = datetime.fromtimestamp(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{entry['ip']:20s} - {entry['reason']}")
                print(f"  添加时间: {ts}")
                if entry.get('expires'):
                    expires = datetime.fromtimestamp(entry['expires']).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  过期时间: {expires}")

        elif args.action == 'add':
            if not args.ip:
                print("错误: 需要指定 --ip")
                return
            manager.ip_blacklist.add_ip(
                args.ip,
                args.reason or "Manual block",
                args.duration
            )
            print(f"✓ 已添加IP到黑名单: {args.ip}")

        elif args.action == 'remove':
            if not args.ip:
                print("错误: 需要指定 --ip")
                return
            manager.ip_blacklist.remove_ip(args.ip)
            print(f"✓ 已从黑名单移除IP: {args.ip}")

    elif args.command == 'reset':
        manager.rate_limiter.reset_client(args.client_id)
        print(f"✓ 已重置客户端限制: {args.client_id}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
