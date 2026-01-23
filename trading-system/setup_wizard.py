"""
交易系统配置向导
支持交互式配置所有API密钥和系统参数
"""

import json
import os
import getpass
from typing import Dict, Any


class ConfigWizard:
    """配置向导"""

    def __init__(self):
        self.config_dir = "config"
        self.configs = {
            "bot_config": {},
            "ai_config": {},
            "position_management_config": {}
        }

    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self, title: str):
        """打印标题"""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60 + "\n")

    def print_section(self, title: str):
        """打印章节"""
        print(f"\n--- {title} ---\n")

    def get_input(self, prompt: str, default: Any = None, password: bool = False) -> str:
        """获取用户输入"""
        if default is not None:
            prompt = f"{prompt} [{default}]: "
        else:
            prompt = f"{prompt}: "

        if password:
            value = getpass.getpass(prompt)
        else:
            value = input(prompt)

        return value.strip() if value.strip() else default

    def get_yes_no(self, prompt: str, default: bool = True) -> bool:
        """获取是/否输入"""
        default_str = "Y/n" if default else "y/N"
        value = input(f"{prompt} [{default_str}]: ").strip().lower()

        if not value:
            return default

        return value in ['y', 'yes', '是']

    def configure_telegram(self):
        """配置Telegram"""
        self.print_section("Telegram机器人配置")

        print("请先在Telegram中找到 @BotFather 创建机器人获取Token")
        print("参考: https://core.telegram.org/bots#6-botfather\n")

        bot_token = self.get_input("Telegram Bot Token", password=True)
        chat_id = self.get_input("Telegram Chat ID (你的Telegram用户ID)")

        self.configs["bot_config"]["telegram"] = {
            "bot_token": bot_token,
            "chat_id": chat_id,
            "enable_notifications": True
        }

        print("✓ Telegram配置完成")

    def configure_mt5(self):
        """配置MT5"""
        self.print_section("MetaTrader 5配置")

        enabled = self.get_yes_no("是否使用MT5交易外汇/黄金?", True)

        if not enabled:
            self.configs["bot_config"]["mt5"] = {"enabled": False}
            print("✓ 跳过MT5配置")
            return

        print("\nMT5账户信息:")
        account = self.get_input("MT5账号", "")
        password = self.get_input("MT5密码", password=True)
        server = self.get_input("MT5服务器", "")

        self.configs["bot_config"]["mt5"] = {
            "enabled": True,
            "account": account,
            "password": password,
            "server": server,
            "symbols": ["XAUUSD", "EURUSD", "GBPUSD"]
        }

        print("✓ MT5配置完成")

    def configure_exchanges(self):
        """配置加密货币交易所"""
        self.print_section("加密货币交易所配置")

        exchanges_config = {}

        # Binance
        if self.get_yes_no("是否配置Binance?", True):
            print("\n获取API密钥: https://www.binance.com/en/my/settings/api-management")
            api_key = self.get_input("Binance API Key", password=True)
            api_secret = self.get_input("Binance API Secret", password=True)

            exchanges_config["binance"] = {
                "enabled": True,
                "api_key": api_key,
                "api_secret": api_secret,
                "testnet": self.get_yes_no("使用测试网?", False)
            }
            print("✓ Binance配置完成")

        # OKX
        if self.get_yes_no("是否配置OKX?", False):
            print("\n获取API密钥: https://www.okx.com/account/my-api")
            api_key = self.get_input("OKX API Key", password=True)
            api_secret = self.get_input("OKX API Secret", password=True)
            passphrase = self.get_input("OKX Passphrase", password=True)

            exchanges_config["okx"] = {
                "enabled": True,
                "api_key": api_key,
                "api_secret": api_secret,
                "passphrase": passphrase
            }
            print("✓ OKX配置完成")

        # Bybit
        if self.get_yes_no("是否配置Bybit?", False):
            print("\n获取API密钥: https://www.bybit.com/app/user/api-management")
            api_key = self.get_input("Bybit API Key", password=True)
            api_secret = self.get_input("Bybit API Secret", password=True)

            exchanges_config["bybit"] = {
                "enabled": True,
                "api_key": api_key,
                "api_secret": api_secret
            }
            print("✓ Bybit配置完成")

        self.configs["bot_config"]["exchanges"] = exchanges_config

    def configure_ai_models(self):
        """配置AI模型"""
        self.print_section("AI模型配置")

        ai_models = {}

        # OpenAI
        if self.get_yes_no("是否配置OpenAI GPT-4?", False):
            print("\n获取API密钥: https://platform.openai.com/api-keys")
            api_key = self.get_input("OpenAI API Key", password=True)

            ai_models["openai"] = {
                "type": "openai",
                "enabled": True,
                "api_key": api_key,
                "model": "gpt-4-turbo-preview"
            }
            print("✓ OpenAI配置完成")

        # Anthropic Claude
        if self.get_yes_no("是否配置Anthropic Claude?", False):
            print("\n获取API密钥: https://console.anthropic.com/")
            api_key = self.get_input("Anthropic API Key", password=True)

            ai_models["anthropic"] = {
                "type": "anthropic",
                "enabled": True,
                "api_key": api_key,
                "model": "claude-3-opus-20240229"
            }
            print("✓ Anthropic配置完成")

        # DeepSeek
        if self.get_yes_no("是否配置DeepSeek(免费)?", True):
            print("\n获取API密钥: https://platform.deepseek.com/")
            api_key = self.get_input("DeepSeek API Key", "")

            ai_models["deepseek"] = {
                "type": "deepseek",
                "enabled": True,
                "api_key": api_key,
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat"
            }
            print("✓ DeepSeek配置完成")

        # 本地模型
        if self.get_yes_no("是否使用本地模型?", False):
            ai_models["local"] = {
                "type": "local",
                "enabled": True,
                "model_path": "",
                "use_transformers": False
            }
            print("✓ 本地模型配置完成")

        self.configs["ai_config"]["ai"] = {
            "models": ai_models,
            "voting_method": "weighted",
            "confidence_threshold": 0.6
        }

    def configure_data_sources(self):
        """配置免费数据源"""
        self.print_section("免费数据源配置")

        data_sources = {}

        # CryptoPanic
        if self.get_yes_no("是否配置CryptoPanic新闻源?(需要免费API key)", False):
            print("\n注册免费API: https://cryptopanic.com/developers/api/")
            api_key = self.get_input("CryptoPanic API Key", password=True)

            data_sources["cryptopanic"] = {
                "enabled": True,
                "api_key": api_key
            }
            print("✓ CryptoPanic配置完成")

        # Etherscan
        if self.get_yes_no("是否配置Etherscan链上数据?(需要免费API key)", False):
            print("\n注册免费API: https://etherscan.io/apis")
            api_key = self.get_input("Etherscan API Key", password=True)

            data_sources["etherscan"] = {
                "enabled": True,
                "api_key": api_key
            }
            print("✓ Etherscan配置完成")

        # Hugging Face
        if self.get_yes_no("是否配置Hugging Face情绪分析?(可选)", False):
            print("\n获取Token: https://huggingface.co/settings/tokens")
            api_key = self.get_input("Hugging Face Token", password=True)

            data_sources["huggingface"] = {
                "enabled": True,
                "api_key": api_key
            }
            print("✓ Hugging Face配置完成")

        # Reddit (无需API key)
        data_sources["reddit"] = {
            "enabled": True
        }

        # CoinGecko (无需API key)
        data_sources["coingecko"] = {
            "enabled": True
        }

        # Alternative.me (无需API key)
        data_sources["alternative_me"] = {
            "enabled": True
        }

        # 创建配置文件结构
        if not hasattr(self.configs, "position_management_config"):
            self.configs["position_management_config"] = {}

        self.configs["position_management_config"]["free_data_sources"] = {
            "enabled": True,
            "cache_ttl_seconds": 300,
            "news": {
                "cryptopanic": data_sources.get("cryptopanic", {"enabled": False, "api_key": ""}),
                "reddit": data_sources.get("reddit", {"enabled": True})
            },
            "onchain": {
                "etherscan": data_sources.get("etherscan", {"enabled": False, "api_key": ""}),
                "blockchain_com": {"enabled": True}
            },
            "ai_indicators": {
                "huggingface": data_sources.get("huggingface", {"enabled": False, "api_key": ""})
            },
            "crypto": {
                "coingecko": {"enabled": True},
                "alternative_me": {"enabled": True}
            }
        }

        print("✓ 免费数据源配置完成")

    def configure_risk_management(self):
        """配置风险管理"""
        self.print_section("风险管理配置")

        print("设置风险管理参数:\n")

        max_loss_per_day = float(self.get_input("每日最大亏损额度(USD)", -1000))
        max_consecutive_losses = int(self.get_input("最大连续亏损次数", 5))
        max_drawdown_pct = float(self.get_input("最大回撤百分比(%)", 10))

        self.configs["bot_config"]["circuit_breaker"] = {
            "enabled": True,
            "max_loss_per_day": max_loss_per_day,
            "max_consecutive_losses": max_consecutive_losses,
            "max_drawdown_pct": max_drawdown_pct,
            "auto_stop_trading": True,
            "notify_on_trigger": True,
            "auto_recover_after_hours": 24
        }

        print("✓ 风险管理配置完成")

    def configure_position_management(self):
        """配置持仓管理"""
        self.print_section("持仓管理配置")

        print("持仓监控和移动止损设置:\n")

        # 读取默认配置
        default_config_path = os.path.join(self.config_dir, "position_management_config.json")
        if os.path.exists(default_config_path):
            with open(default_config_path, 'r', encoding='utf-8') as f:
                default_pm_config = json.load(f)
        else:
            default_pm_config = {}

        # 合并配置
        if "position_management_config" not in self.configs:
            self.configs["position_management_config"] = default_pm_config
        else:
            # 合并free_data_sources配置
            if "free_data_sources" in default_pm_config:
                self.configs["position_management_config"]["free_data_sources"] = {
                    **default_pm_config["free_data_sources"],
                    **self.configs["position_management_config"].get("free_data_sources", {})
                }

        enabled = self.get_yes_no("启用持仓监控?", True)
        self.configs["position_management_config"]["position_monitor"] = {
            "enabled": enabled,
            "scan_interval_seconds": 60,
            "auto_execute_decisions": False
        }

        trailing_enabled = self.get_yes_no("启用高级移动止损?", True)
        if trailing_enabled:
            strategy = self.get_input(
                "移动止损策略 (dynamic/percentage/atr/support_resistance)",
                "dynamic"
            )
            self.configs["position_management_config"]["trailing_stop"] = {
                "enabled": True,
                "default_strategy": strategy,
                "activation_profit_pct": 2.0,
                "trailing_distance_pct": 1.0
            }

        print("✓ 持仓管理配置完成")

    def save_configs(self):
        """保存配置文件"""
        self.print_section("保存配置")

        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)

        # 保存bot_config.json
        bot_config_path = os.path.join(self.config_dir, "bot_config.json")
        if os.path.exists(bot_config_path):
            with open(bot_config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
            # 合并配置
            existing_config.update(self.configs["bot_config"])
            final_bot_config = existing_config
        else:
            final_bot_config = self.configs["bot_config"]

        with open(bot_config_path, 'w', encoding='utf-8') as f:
            json.dump(final_bot_config, f, indent=2, ensure_ascii=False)
        print(f"✓ 已保存: {bot_config_path}")

        # 保存ai_config.json
        ai_config_path = os.path.join(self.config_dir, "ai_config.json")
        if os.path.exists(ai_config_path):
            with open(ai_config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
            # 只更新ai.models部分
            if "ai" in self.configs["ai_config"]:
                if "ai" not in existing_config:
                    existing_config["ai"] = {}
                existing_config["ai"]["models"] = self.configs["ai_config"]["ai"]["models"]
            final_ai_config = existing_config
        else:
            final_ai_config = self.configs["ai_config"]

        with open(ai_config_path, 'w', encoding='utf-8') as f:
            json.dump(final_ai_config, f, indent=2, ensure_ascii=False)
        print(f"✓ 已保存: {ai_config_path}")

        # 保存position_management_config.json
        pm_config_path = os.path.join(self.config_dir, "position_management_config.json")
        with open(pm_config_path, 'w', encoding='utf-8') as f:
            json.dump(self.configs["position_management_config"], f, indent=2, ensure_ascii=False)
        print(f"✓ 已保存: {pm_config_path}")

        print("\n✓ 所有配置已保存成功!")

    def run(self):
        """运行配置向导"""
        self.clear_screen()
        self.print_header("MT5加密货币交易系统 - 配置向导 v2.3")

        print("本向导将帮助您配置交易系统的所有参数。")
        print("按回车键使用默认值，输入新值以覆盖。")
        print("\n提示: API密钥输入时不会显示字符(安全保护)")

        input("\n按回车键开始...")

        try:
            # 1. Telegram配置
            self.configure_telegram()

            # 2. MT5配置
            self.configure_mt5()

            # 3. 交易所配置
            self.configure_exchanges()

            # 4. AI模型配置
            self.configure_ai_models()

            # 5. 免费数据源配置
            self.configure_data_sources()

            # 6. 风险管理配置
            self.configure_risk_management()

            # 7. 持仓管理配置
            self.configure_position_management()

            # 8. 保存配置
            self.save_configs()

            self.print_header("配置完成")
            print("配置向导已完成，您可以开始使用交易系统了！")
            print("\n配置文件位置:")
            print("  - config/bot_config.json")
            print("  - config/ai_config.json")
            print("  - config/position_management_config.json")
            print("\n您可以随时手动编辑这些文件以调整配置。")

        except KeyboardInterrupt:
            print("\n\n配置向导已取消")
            return
        except Exception as e:
            print(f"\n\n错误: {e}")
            import traceback
            traceback.print_exc()
            return


if __name__ == "__main__":
    wizard = ConfigWizard()
    wizard.run()
