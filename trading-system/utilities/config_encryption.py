#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加密工具 - 加密/解密敏感配置信息
"""

import os
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class ConfigEncryption:
    """配置加密管理器"""

    def __init__(self, key_file: str = None):
        self.base_dir = Path(__file__).parent.parent

        if key_file is None:
            key_file = self.base_dir / "config" / ".encryption_key"

        self.key_file = Path(key_file)
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)

        # 需要加密的字段
        self.sensitive_fields = [
            'password',
            'api_key',
            'api_secret',
            'secret',
            'token',
            'passphrase',
            'private_key',
            'access_token',
            'refresh_token'
        ]

    def _load_or_generate_key(self) -> bytes:
        """加载或生成加密密钥"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            # 生成新密钥
            key = Fernet.generate_key()
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # 设置文件权限为只读
            os.chmod(self.key_file, 0o600)
            logger.info(f"已生成新的加密密钥: {self.key_file}")
            return key

    def encrypt_value(self, value: str) -> str:
        """加密单个值"""
        if not isinstance(value, str):
            value = str(value)

        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        """解密单个值"""
        try:
            encrypted = base64.b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return encrypted_value

    def _is_sensitive_field(self, key: str) -> bool:
        """判断是否为敏感字段"""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.sensitive_fields)

    def _is_encrypted(self, value: str) -> bool:
        """判断值是否已加密"""
        return isinstance(value, str) and value.startswith("encrypted:")

    def encrypt_config(self, config: Dict, in_place: bool = False) -> Dict:
        """加密配置中的敏感信息"""
        if not in_place:
            config = json.loads(json.dumps(config))  # 深拷贝

        def encrypt_recursive(obj, parent_key=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{parent_key}.{key}" if parent_key else key

                    if isinstance(value, (dict, list)):
                        encrypt_recursive(value, full_key)
                    elif self._is_sensitive_field(key) and isinstance(value, str):
                        if not self._is_encrypted(value) and value:
                            obj[key] = f"encrypted:{self.encrypt_value(value)}"
                            logger.debug(f"已加密字段: {full_key}")

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        encrypt_recursive(item, f"{parent_key}[{i}]")

        encrypt_recursive(config)
        return config

    def decrypt_config(self, config: Dict, in_place: bool = False) -> Dict:
        """解密配置中的敏感信息"""
        if not in_place:
            config = json.loads(json.dumps(config))  # 深拷贝

        def decrypt_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (dict, list)):
                        decrypt_recursive(value)
                    elif isinstance(value, str) and self._is_encrypted(value):
                        encrypted_part = value.replace("encrypted:", "")
                        obj[key] = self.decrypt_value(encrypted_part)
                        logger.debug(f"已解密字段: {key}")

            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        decrypt_recursive(item)

        decrypt_recursive(config)
        return config

    def encrypt_config_file(self, config_path: str, output_path: str = None, backup: bool = True):
        """加密配置文件"""
        config_path = Path(config_path)

        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return False

        try:
            # 读取配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 备份原文件
            if backup:
                backup_path = config_path.with_suffix('.json.backup')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                logger.info(f"已备份原配置: {backup_path}")

            # 加密
            encrypted_config = self.encrypt_config(config)

            # 写入文件
            if output_path is None:
                output_path = config_path

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(encrypted_config, f, indent=2, ensure_ascii=False)

            logger.info(f"配置文件已加密: {output_path}")
            return True

        except Exception as e:
            logger.error(f"加密配置文件失败: {e}")
            return False

    def decrypt_config_file(self, config_path: str, output_path: str = None):
        """解密配置文件"""
        config_path = Path(config_path)

        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return False

        try:
            # 读取配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 解密
            decrypted_config = self.decrypt_config(config)

            # 写入文件
            if output_path is None:
                output_path = config_path.with_suffix('.decrypted.json')

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(decrypted_config, f, indent=2, ensure_ascii=False)

            logger.info(f"配置文件已解密: {output_path}")
            logger.warning(f"警告: 解密后的配置包含明文敏感信息,请妥善保管")
            return True

        except Exception as e:
            logger.error(f"解密配置文件失败: {e}")
            return False

    def encrypt_all_configs(self, config_dir: str = None):
        """加密所有配置文件"""
        if config_dir is None:
            config_dir = self.base_dir / "config"
        else:
            config_dir = Path(config_dir)

        if not config_dir.exists():
            logger.error(f"配置目录不存在: {config_dir}")
            return

        config_files = list(config_dir.glob("*.json"))

        # 排除已加密或备份文件
        config_files = [
            f for f in config_files
            if not f.name.endswith('.backup') and not f.name.startswith('.')
        ]

        logger.info(f"发现 {len(config_files)} 个配置文件")

        for config_file in config_files:
            logger.info(f"正在加密: {config_file.name}")
            self.encrypt_config_file(config_file)

        logger.info("所有配置文件加密完成")

    def load_encrypted_config(self, config_path: str) -> Dict:
        """加载并解密配置文件"""
        config_path = Path(config_path)

        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            return self.decrypt_config(config)

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}


class SecureConfigLoader:
    """安全配置加载器 - 自动处理加密配置"""

    def __init__(self):
        self.encryption = ConfigEncryption()

    def load_config(self, config_path: str) -> Dict:
        """加载配置(自动解密)"""
        return self.encryption.load_encrypted_config(config_path)

    def get(self, config_path: str, key_path: str, default: Any = None) -> Any:
        """获取配置值(支持点号路径,如 'mt5_config.password')"""
        config = self.load_config(config_path)

        keys = key_path.split('.')
        value = config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='配置加密工具')
    parser.add_argument('action', choices=['encrypt', 'decrypt', 'encrypt-all', 'test'],
                       help='操作类型')
    parser.add_argument('--file', help='配置文件路径')
    parser.add_argument('--output', help='输出文件路径')
    parser.add_argument('--no-backup', action='store_true', help='不备份原文件')

    args = parser.parse_args()

    encryptor = ConfigEncryption()

    if args.action == 'encrypt':
        if not args.file:
            print("错误: 请指定配置文件 --file")
            return

        success = encryptor.encrypt_config_file(
            args.file,
            args.output,
            backup=not args.no_backup
        )

        if success:
            print(f"✓ 配置文件已加密: {args.output or args.file}")
        else:
            print("✗ 加密失败")

    elif args.action == 'decrypt':
        if not args.file:
            print("错误: 请指定配置文件 --file")
            return

        success = encryptor.decrypt_config_file(args.file, args.output)

        if success:
            print(f"✓ 配置文件已解密: {args.output or args.file}")
            print("⚠ 警告: 解密后的文件包含明文敏感信息,请妥善保管")
        else:
            print("✗ 解密失败")

    elif args.action == 'encrypt-all':
        encryptor.encrypt_all_configs()
        print("✓ 所有配置文件已加密")

    elif args.action == 'test':
        # 测试加密/解密
        test_data = {
            "username": "user123",
            "password": "my-secret-password",
            "api_key": "sk-1234567890",
            "normal_field": "not-encrypted",
            "nested": {
                "api_secret": "secret-key-here",
                "other": "value"
            }
        }

        print("\n原始配置:")
        print(json.dumps(test_data, indent=2, ensure_ascii=False))

        encrypted = encryptor.encrypt_config(test_data)
        print("\n加密后配置:")
        print(json.dumps(encrypted, indent=2, ensure_ascii=False))

        decrypted = encryptor.decrypt_config(encrypted)
        print("\n解密后配置:")
        print(json.dumps(decrypted, indent=2, ensure_ascii=False))

        print("\n✓ 测试完成")


if __name__ == "__main__":
    main()
