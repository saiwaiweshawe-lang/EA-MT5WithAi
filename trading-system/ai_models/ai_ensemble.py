# 模型集成模块
# 集成多个AI模型进行交易决策和文本分析

import os
import json
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from openai import OpenAI
import anthropic

logger = logging.getLogger(__name__)


class BaseModel(ABC):
    """AI模型基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.model_name = config.get("model", "")
        self.enabled = config.get("enabled", True)
        self.max_retries = config.get("max_retries", 3)
        self.timeout = config.get("timeout", 30)

    @abstractmethod
    def analyze(self, prompt: str, context: Optional[Dict] = None) -> str:
        """分析文本并返回结果"""
        pass

    @abstractmethod
    def generate_decision(self, market_data: Dict, indicators: Dict,
                         news: List[Dict]) -> Dict:
        """生成交易决策"""
        pass

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的量化交易分析助手。你的任务是：
1. 分析市场数据和技术指标
2. 结合新闻和基本面信息
3. 给出客观的交易建议（买入/卖出/持有）
4. 提供置信度评分（0-1）
5. 解释决策理由

回答格式必须严格遵循JSON格式：
{
    "action": "buy/sell/hold",
    "confidence": 0.85,
    "reason": "详细理由",
    "risk_level": "low/medium/high",
    "suggested_stop_loss": 价格,
    "suggested_take_profit": 价格
}"""


class OpenAIModel(BaseModel):
    """OpenAI GPT模型"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.client = OpenAI(api_key=config.get("api_key"))
        self.model = config.get("model", "gpt-4-turbo-preview")

    def analyze(self, prompt: str, context: Optional[Dict] = None) -> str:
        """分析文本"""
        try:
            messages = [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI分析失败: {e}")
            return ""

    def generate_decision(self, market_data: Dict, indicators: Dict,
                         news: List[Dict]) -> Dict:
        """生成交易决策"""
        prompt = self._build_trading_prompt(market_data, indicators, news)
        response = self.analyze(prompt)

        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError, TypeError, Exception) as e:
            return {
                "action": "hold",
                "confidence": 0,
                "reason": "AI解析失败",
                "risk_level": "high"
            }

    def _build_trading_prompt(self, market_data: Dict, indicators: Dict,
                             news: List[Dict]) -> str:
        """构建交易分析提示"""
        prompt = f"""请分析以下市场情况并给出交易建议：

【市场数据】
品种: {market_data.get('symbol', 'N/A')}
当前价格: {market_data.get('price', 'N/A')}
24小时涨跌: {market_data.get('change_24h', 'N/A')}%
24小时成交量: {market_data.get('volume_24h', 'N/A')}

【技术指标】
"""
        for key, value in indicators.items():
            prompt += f"{key}: {value}\n"

        prompt += "\n【最新新闻】\n"
        for item in news[:5]:  # 只取前5条
            prompt += f"- {item.get('title', 'N/A')}\n"

        return prompt


class AnthropicModel(BaseModel):
    """Anthropic Claude模型"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.client = anthropic.Anthropic(api_key=config.get("api_key"))
        self.model = config.get("model", "claude-3-opus-20240229")

    def analyze(self, prompt: str, context: Optional[Dict] = None) -> str:
        """分析文本"""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text

        except Exception as e:
            logger.error(f"Claude分析失败: {e}")
            return ""

    def generate_decision(self, market_data: Dict, indicators: Dict,
                         news: List[Dict]) -> Dict:
        """生成交易决策"""
        prompt = self._build_trading_prompt(market_data, indicators, news)
        response = self.analyze(prompt)

        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError, TypeError, Exception) as e:
            return {
                "action": "hold",
                "confidence": 0,
                "reason": "AI解析失败",
                "risk_level": "high"
            }

    def _build_trading_prompt(self, market_data: Dict, indicators: Dict,
                             news: List[Dict]) -> str:
        """构建交易分析提示"""
        prompt = f"""请分析以下市场情况并给出交易建议：

【市场数据】
品种: {market_data.get('symbol', 'N/A')}
当前价格: {market_data.get('price', 'N/A')}
24小时涨跌: {market_data.get('change_24h', 'N/A')}%
24小时成交量: {market_data.get('volume_24h', 'N/A')}

【技术指标】
"""
        for key, value in indicators.items():
            prompt += f"{key}: {value}\n"

        prompt += "\n【最新新闻】\n"
        for item in news[:5]:
            prompt += f"- {item.get('title', 'N/A')}\n"

        return prompt


class DeepSeekModel(BaseModel):
    """DeepSeek模型（免费API）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.deepseek.com/v1")
        self.model = config.get("model", "deepseek-chat")

    def analyze(self, prompt: str, context: Optional[Dict] = None) -> str:
        """分析文本"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            messages = [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ]

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=self.timeout
            )

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"DeepSeek分析失败: {e}")
            return ""

    def generate_decision(self, market_data: Dict, indicators: Dict,
                         news: List[Dict]) -> Dict:
        """生成交易决策"""
        prompt = self._build_trading_prompt(market_data, indicators, news)
        response = self.analyze(prompt)

        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError, TypeError, Exception) as e:
            return {
                "action": "hold",
                "confidence": 0,
                "reason": "AI解析失败",
                "risk_level": "high"
            }

    def _build_trading_prompt(self, market_data: Dict, indicators: Dict,
                             news: List[Dict]) -> str:
        """构建交易分析提示"""
        prompt = f"""请分析以下市场情况并给出交易建议：

【市场数据】
品种: {market_data.get('symbol', 'N/A')}
当前价格: {market_data.get('price', 'N/A')}
24小时涨跌: {market_data.get('change_24h', 'N/A')}%
24小时成交量: {market_data.get('volume_24h', 'N/A')}

【技术指标】
"""
        for key, value in indicators.items():
            prompt += f"{key}: {value}\n"

        prompt += "\n【最新新闻】\n"
        for item in news[:5]:
            prompt += f"- {item.get('title', 'N/A')}\n"

        return prompt


class LocalModel(BaseModel):
    """本地模型（使用轻量级模型）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.model_path = config.get("model_path", "")
        self.use_transformers = config.get("use_transformers", False)

        if self.use_transformers:
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                self.model = AutoModelForCausalLM.from_pretrained(self.model_path)
                self.available = True
            except Exception as e:
                logger.warning(f"无法加载本地模型: {e}")
                self.available = False
        else:
            self.available = False

    def analyze(self, prompt: str, context: Optional[Dict] = None) -> str:
        """分析文本"""
        if not self.available:
            return self._simple_analysis(prompt, context)

        try:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            outputs = self.model.generate(**inputs, max_new_tokens=500)
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response
        except Exception as e:
            logger.error(f"本地模型分析失败: {e}")
            return ""

    def generate_decision(self, market_data: Dict, indicators: Dict,
                         news: List[Dict]) -> Dict:
        """生成交易决策"""
        if not self.available:
            return self._rule_based_decision(market_data, indicators, news)

        prompt = self._build_trading_prompt(market_data, indicators, news)
        response = self.analyze(prompt)

        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError, TypeError, Exception) as e:
            return self._rule_based_decision(market_data, indicators, news)

    def _simple_analysis(self, prompt: str, context: Optional[Dict]) -> str:
        """简单分析（当模型不可用时）"""
        return "本地模型不可用，使用规则引擎"

    def _rule_based_decision(self, market_data: Dict, indicators: Dict,
                           news: List[Dict]) -> Dict:
        """基于规则的决策"""
        # 简单规则示例
        rsi = indicators.get("RSI", 50)
        ma_cross = indicators.get("MA_CROSS", "neutral")

        if rsi < 30 and ma_cross == "bullish":
            return {
                "action": "buy",
                "confidence": 0.6,
                "reason": "RSI超卖且MA看多",
                "risk_level": "medium"
            }
        elif rsi > 70 and ma_cross == "bearish":
            return {
                "action": "sell",
                "confidence": 0.6,
                "reason": "RSI超买且MA看空",
                "risk_level": "medium"
            }
        else:
            return {
                "action": "hold",
                "confidence": 0.5,
                "reason": "无明显信号",
                "risk_level": "low"
            }

    def _build_trading_prompt(self, market_data: Dict, indicators: Dict,
                             news: List[Dict]) -> str:
        """构建交易分析提示"""
        prompt = f"""分析市场数据并给出交易建议：
品种: {market_data.get('symbol')}
价格: {market_data.get('price')}
指标: {indicators}
"""
        return prompt


class AIEnsemble:
    """AI集成器 - 整合多个AI模型的决策"""

    def __init__(self, config: Dict):
        self.config = config
        self.models: List[BaseModel] = []
        self.voting_method = config.get("voting_method", "weighted")  # weighted, majority, consensus
        self.confidence_threshold = config.get("confidence_threshold", 0.6)
        self.model_weights = config.get("model_weights", {})

        self._init_models()

    def _init_models(self):
        """初始化所有AI模型"""
        models_config = self.config.get("models", {})

        for model_name, model_config in models_config.items():
            if not model_config.get("enabled", False):
                continue

            model_type = model_config.get("type", "openai")

            try:
                if model_type == "openai":
                    model = OpenAIModel(model_config)
                elif model_type == "anthropic":
                    model = AnthropicModel(model_config)
                elif model_type == "deepseek":
                    model = DeepSeekModel(model_config)
                elif model_type == "local":
                    model = LocalModel(model_config)
                else:
                    logger.warning(f"未知模型类型: {model_type}")
                    continue

                self.models.append(model)
                logger.info(f"已加载AI模型: {model_name}")

            except Exception as e:
                logger.error(f"加载模型 {model_name} 失败: {e}")

    def generate_trading_decision(self, market_data: Dict,
                                 indicators: Dict,
                                 news: List[Dict]) -> Dict:
        """生成集成交易决策"""
        if not self.models:
            logger.warning("没有可用的AI模型")
            return {
                "action": "hold",
                "confidence": 0,
                "reason": "无AI模型可用"
            }

        # 收集所有模型的决策
        decisions = []
        for model in self.models:
            try:
                decision = model.generate_decision(market_data, indicators, news)
                if decision:
                    decisions.append({
                        "model": model.__class__.__name__,
                        "decision": decision
                    })
            except Exception as e:
                logger.error(f"模型决策失败: {e}")

        # 集成决策
        if not decisions:
            return {
                "action": "hold",
                "confidence": 0,
                "reason": "所有模型决策失败"
            }

        if self.voting_method == "weighted":
            return self._weighted_voting(decisions)
        elif self.voting_method == "majority":
            return self._majority_voting(decisions)
        elif self.voting_method == "consensus":
            return self._consensus_voting(decisions)
        else:
            return decisions[0]["decision"]

    def _weighted_voting(self, decisions: List[Dict]) -> Dict:
        """加权投票"""
        action_scores = {"buy": 0, "sell": 0, "hold": 0}
        total_weight = 0

        for item in decisions:
            model_name = item["model"]
            decision = item["decision"]
            weight = self.model_weights.get(model_name, 1.0)
            confidence = decision.get("confidence", 0.5)

            action = decision.get("action", "hold")
            action_scores[action] += weight * confidence
            total_weight += weight

        # 找出得分最高的动作
        best_action = max(action_scores, key=action_scores.get)
        avg_confidence = action_scores[best_action] / max(total_weight, 1)

        # 整合理由
        reasons = []
        for item in decisions:
            reasons.append(f"{item['model']}: {item['decision'].get('reason', '')}")

        return {
            "action": best_action,
            "confidence": min(avg_confidence, 1.0),
            "reason": " | ".join(reasons),
            "individual_decisions": decisions,
            "voting_method": "weighted"
        }

    def _majority_voting(self, decisions: List[Dict]) -> Dict:
        """多数投票"""
        action_counts = {"buy": 0, "sell": 0, "hold": 0}

        for item in decisions:
            action = item["decision"].get("action", "hold")
            action_counts[action] += 1

        # 找出多数票
        max_count = max(action_counts.values())
        best_actions = [a for a, c in action_counts.items() if c == max_count]

        if len(best_actions) == 1:
            best_action = best_actions[0]
        else:
            # 平局时选择hold
            best_action = "hold"

        # 计算平均置信度
        confidences = [d["decision"].get("confidence", 0.5) for d in decisions
                      if d["decision"].get("action") == best_action]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "action": best_action,
            "confidence": avg_confidence,
            "reason": f"多数投票结果: {action_counts}",
            "individual_decisions": decisions,
            "voting_method": "majority"
        }

    def _consensus_voting(self, decisions: List[Dict]) -> Dict:
        """共识投票（只有所有模型同意才执行）"""
        actions = [d["decision"].get("action", "hold") for d in decisions]

        if all(a == actions[0] for a in actions):
            # 达成共识
            best_action = actions[0]
            confidences = [d["decision"].get("confidence", 0.5) for d in decisions]
            avg_confidence = sum(confidences) / len(confidences)

            return {
                "action": best_action,
                "confidence": avg_confidence,
                "reason": f"所有模型一致: {best_action}",
                "individual_decisions": decisions,
                "voting_method": "consensus"
            }
        else:
            # 未达成共识
            return {
                "action": "hold",
                "confidence": 0.3,
                "reason": "模型意见分歧",
                "individual_decisions": decisions,
                "voting_method": "consensus"
            }

    def analyze_text(self, text: str, context: Optional[Dict] = None) -> str:
        """分析文本（使用第一个可用模型）"""
        for model in self.models:
            if model.enabled:
                result = model.analyze(text, context)
                if result:
                    return result

        return "所有模型分析失败"

    def get_model_status(self) -> List[Dict]:
        """获取所有模型状态"""
        status = []
        for model in self.models:
            status.append({
                "name": model.__class__.__name__,
                "model_name": model.model_name,
                "enabled": model.enabled,
                "available": getattr(model, "available", True)
            })
        return status


class SentimentAnalyzer:
    """情绪分析器"""

    def __init__(self, config: Dict):
        self.use_local = config.get("use_local", True)
        self.threshold_positive = config.get("threshold_positive", 0.6)
        self.threshold_negative = config.get("threshold_negative", 0.4)

    def analyze_news_sentiment(self, news: List[Dict]) -> Dict:
        """分析新闻情绪"""
        if not news:
            return {
                "sentiment": "neutral",
                "score": 0.5,
                "confidence": 0,
                "reason": "无新闻数据"
            }

        # 汇总所有新闻标题
        headlines = [item.get("title", "") for item in news]
        combined_text = " ".join(headlines)

        # 简单关键词分析
        positive_keywords = [
            "bull", "bullish", "rally", "surge", "gain", "rise", "up",
            "breakthrough", "positive", "growth", "strong", "upgrade",
            "涨", "上涨", "突破", "利好", "增长", "强势"
        ]
        negative_keywords = [
            "bear", "bearish", "crash", "plunge", "drop", "fall", "down",
            "crisis", "negative", "decline", "weak", "downgrade",
            "跌", "下跌", "暴跌", "危机", "利空", "衰退", "弱势"
        ]

        positive_count = sum(1 for word in positive_keywords if word in combined_text.lower())
        negative_count = sum(1 for word in negative_keywords if word in combined_text.lower())
        total_count = positive_count + negative_count

        if total_count == 0:
            sentiment = "neutral"
            score = 0.5
        else:
            positive_ratio = positive_count / total_count
            if positive_ratio > 0.6:
                sentiment = "positive"
                score = 0.5 + (positive_ratio - 0.5) * 0.5
            elif positive_ratio < 0.4:
                sentiment = "negative"
                score = 0.5 - (0.5 - positive_ratio) * 0.5
            else:
                sentiment = "neutral"
                score = 0.5

        return {
            "sentiment": sentiment,
            "score": score,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "total_news": len(news),
            "confidence": min(total_count / 10, 1.0)
        }


def create_ai_ensemble(config_path: str) -> AIEnsemble:
    """创建AI集成器"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return AIEnsemble(config.get("ai", {}))


if __name__ == "__main__":
    # 测试代码
    config = {
        "models": {
            "openai": {
                "type": "openai",
                "enabled": False,
                "api_key": ""
            },
            "deepseek": {
                "type": "deepseek",
                "enabled": True,
                "api_key": "your-api-key"
            },
            "local": {
                "type": "local",
                "enabled": True,
                "use_transformers": False
            }
        },
        "voting_method": "weighted",
        "model_weights": {
            "OpenAIModel": 1.0,
            "DeepSeekModel": 0.8,
            "LocalModel": 0.5
        }
    }

    ensemble = AIEnsemble(config)
    print("AI集成器已创建")
    print("模型状态:", ensemble.get_model_status())
