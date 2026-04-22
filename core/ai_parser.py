# core/ai_parser.py
import re
from typing import Dict, Any, Optional


class AIParser:
    """AI 指令解析器 - 规则引擎 + 可选 LLM 增强"""

    def __init__(self, qwen_service=None):
        """
        参数:
            qwen_service: 可选，QwenRouterService 实例，用于 LLM 增强解析
        """
        self.qwen = qwen_service
        self.patterns = {
            'food': r'(点|买|要|想吃|订)(?:个|份|碗)?(.*?)(?:，|。|$|预算|价格|左右)',
            'budget': r'(\d+)(?:元|块|块钱)(?:左右|以内|以下)?',
            'avoid': r'不要|忌口|别放(.*?)(?:，|。|$)',
            'spicy': r'(微辣|中辣|特辣|不要辣|免辣)',
            'time': r'(现在|马上|尽快|(\d+)[点:：](\d+)?)'
        }

    def parse(self, text: str) -> Dict[str, Any]:
        """解析用户自然语言指令（规则引擎）"""
        text = text.strip()
        result = {
            'action': 'order',
            'food': '',
            'budget': 30,
            'preferences': {
                'avoid': [],
                'spicy': None,
                'time': 'immediate'
            },
            'raw_text': text
        }

        # 提取食物
        food_match = re.search(self.patterns['food'], text)
        if food_match:
            food = food_match.group(2).strip()
            food = re.sub(r'^(?:个|份|碗|的)', '', food)
            result['food'] = food if food else '外卖'

        # 提取预算
        budget_matches = re.findall(self.patterns['budget'], text)
        if budget_matches:
            result['budget'] = int(budget_matches[0])

        # 提取忌口
        avoid_matches = re.findall(self.patterns['avoid'], text)
        if avoid_matches:
            result['preferences']['avoid'] = [a.strip() for a in avoid_matches if a.strip()]

        # 提取辣度
        spicy_match = re.search(self.patterns['spicy'], text)
        if spicy_match:
            result['preferences']['spicy'] = spicy_match.group(1)

        # 提取时间
        time_match = re.search(self.patterns['time'], text)
        if time_match:
            if time_match.group(2):
                result['preferences']['time'] = f"{time_match.group(2)}:{time_match.group(3) or '00'}"

        # 查询意图判断
        query_keywords = ['到哪了', '状态', '进度', '还有多久', '查询']
        if any(kw in text for kw in query_keywords):
            result['action'] = 'query'

        return result

    def parse_with_model(self, text: str, user_prefs: dict = None) -> Dict[str, Any]:
        """
        使用本地模型增强解析（需要 qwen 服务）

        参数:
            text: 用户输入
            user_prefs: 用户偏好（用于上下文）

        返回:
            解析结果，格式同 parse()
        """
        if not self.qwen or not self.qwen.is_ready:
            # 降级到规则引擎
            return self.parse(text)

        try:
            # 构建解析提示词
            prefs_text = ""
            if user_prefs:
                prefs_text = f"""
用户偏好：
- 辣度：{user_prefs.get('spicy_level', '未设置')}
- 忌口：{', '.join(user_prefs.get('avoid_foods', [])) or '无'}
- 预算：{user_prefs.get('default_budget', 30)}元
"""

            prompt = f"""从以下用户输入中提取点餐信息，返回JSON格式：
{prefs_text}

用户输入：{text}

请提取：
- food: 想吃的食物（如果没有则填"外卖"）
- budget: 预算金额（数字，没有则30）
- spicy: 辣度要求（微辣/中辣/特辣/不辣，没有则null）
- avoid: 忌口列表（数组）
- action: 意图（order/query/cancel）

只返回JSON，不要其他内容。"""

            result = self.qwen.chat(prompt, user_prefs or {})
            if result.get('success'):
                import json
                # 尝试解析JSON
                content = result['content']
                # 提取JSON部分
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    return {
                        'action': parsed.get('action', 'order'),
                        'food': parsed.get('food', '外卖'),
                        'budget': parsed.get('budget', 30),
                        'preferences': {
                            'avoid': parsed.get('avoid', []),
                            'spicy': parsed.get('spicy'),
                            'time': 'immediate'
                        },
                        'raw_text': text
                    }
        except Exception as e:
            print(f"LLM解析失败，降级到规则引擎: {e}")

        return self.parse(text)
