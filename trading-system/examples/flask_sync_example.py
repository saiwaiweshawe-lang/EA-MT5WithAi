#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 服务器同步集成示例
展示如何在 Flask 应用中集成服务器同步功能
"""

from flask import Flask, request, jsonify
from utilities.server_sync import ServerSyncManager, DataReplicator, ServerRole
import logging

logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__)

# 创建同步管理器
sync_manager = ServerSyncManager()
data_replicator = DataReplicator(sync_manager)


def on_failover(old_role, new_role):
    """故障转移回调"""
    logger.critical(f"故障转移: {old_role.value} -> {new_role.value}")
    # 这里可以添加额外的故障转移逻辑
    # 例如: 更新负载均衡配置, 发送通知等


def on_failback(old_role, new_role):
    """回切回调"""
    logger.info(f"回切: {old_role.value} -> {new_role.value}")
    # 这里可以添加额外的回切逻辑


# 注册回调
sync_manager.register_failover_callback(on_failover)
sync_manager.register_failback_callback(on_failback)


@app.route('/api/heartbeat', methods=['POST'])
def receive_heartbeat():
    """接收对端心跳"""
    try:
        data = request.get_json()
        sync_manager.receive_heartbeat(data)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"接收心跳失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    status = sync_manager.get_status()
    return jsonify({
        'status': 'healthy',
        'server_id': status['server_id'],
        'role': status['role']
    })


@app.route('/api/sync/state', methods=['POST'])
def sync_state():
    """接收状态同步"""
    try:
        data = request.get_json()
        # 处理状态同步
        logger.info(f"接收状态同步: {data.keys()}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"状态同步失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/sync/config', methods=['POST'])
def sync_config():
    """接收配置同步"""
    try:
        data = request.get_json()
        # 处理配置同步
        logger.info(f"接收配置同步: {data.keys()}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"配置同步失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/sync/data', methods=['POST'])
def sync_data():
    """接收数据同步"""
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')

        if key and value is not None:
            data_replicator.receive_replicated_data(key, value)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Missing key or value'}), 400
    except Exception as e:
        logger.error(f"数据同步失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取同步状态"""
    status = sync_manager.get_status()
    return jsonify(status)


@app.route('/api/failover', methods=['POST'])
def trigger_failover():
    """手动触发故障转移"""
    try:
        sync_manager.force_failover()
        return jsonify({'success': True, 'message': '故障转移已触发'})
    except Exception as e:
        logger.error(f"故障转移失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/failback', methods=['POST'])
def trigger_failback():
    """手动触发回切"""
    try:
        sync_manager.force_failback()
        return jsonify({'success': True, 'message': '回切已触发'})
    except Exception as e:
        logger.error(f"回切失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


# 业务 API 示例
@app.route('/api/trade', methods=['POST'])
def trade():
    """交易接口示例 - 展示如何在业务逻辑中使用数据复制"""
    # 只有主服务器可以处理交易
    if sync_manager.role != ServerRole.PRIMARY:
        return jsonify({
            'success': False,
            'error': 'Only primary server can process trades'
        }), 403

    try:
        data = request.get_json()
        trade_id = data.get('trade_id')

        # 处理交易逻辑
        # ...

        # 复制交易数据到备份服务器
        data_replicator.replicate(
            key=f'trade:{trade_id}',
            value=data,
            priority=1  # 高优先级
        )

        return jsonify({'success': True, 'trade_id': trade_id})
    except Exception as e:
        logger.error(f"交易处理失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


def start_server(host='0.0.0.0', port=5000):
    """启动服务器"""
    # 启动同步管理器
    sync_manager.start()

    # 启动 Flask 应用
    logger.info(f"启动服务器: {host}:{port} (角色: {sync_manager.role.value})")
    app.run(host=host, port=port)


if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='Flask 服务器同步示例')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5000, help='监听端口')

    args = parser.parse_args()

    start_server(host=args.host, port=args.port)
