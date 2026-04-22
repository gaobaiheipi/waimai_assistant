# services/qwen_local.py
import os
import re
import json
import requests
from typing import Dict, List, Callable, Optional
from kivy.clock import Clock
from kivy.utils import platform


class QwenRouterService:
    """Qwen 模型路由服务 - 支持本地模型和云端 API 双模式"""

    def __init__(self):
        # 模式：'local' 或 'cloud'
        self.mode = self._get_default_mode()

        # 本地模型相关
        self.model_small = None
        self.tokenizer_small = None
        self.model_large = None
        self.tokenizer_large = None
        self.is_ready = False
        self.is_loading = False

        # 云端 API 相关
        self.cloud_api_url = "https://api.deepseek.com/v1/chat/completions"
        self.cloud_api_key = "sk-0e98b648f2204bf89604e9bfbe6ae449"

        # 对话上下文记忆
        self.conversation_context = {
            "last_budget": 30,
            "last_keyword": None,
            "last_cuisine": None,
            "last_spicy": "微辣",
            "last_avoid": [],
            "current_recommendations": [],
            "current_order": None,
            "last_search_params": None,
            "recommended_ids": [],
        }

        # 工作流触发词
        self.workflow_triggers = {
            r'(下单|提交订单|确认购买|就这个|就要这个)': 'submit_order',
            r'(查询|查看).*?(订单|外卖|状态)': 'query_order',
            r'(追踪|跟踪|到哪里|到哪了|在哪).*?(订单|外卖)': 'track_order',
            r'(取消|退掉).*?(订单|外卖)': 'cancel_order',
            r'(修改|更改).*?(地址|电话|偏好|设置)': 'modify_info',
        }

    def _get_default_mode(self):
        """根据运行环境自动选择模式"""
        if platform == 'android':
            # 手机端使用云端 API
            print("[模式] Android 环境，使用云端 API")
            return 'cloud'
        else:
            # PC 端使用本地模型
            print("[模式] PC 环境，使用本地模型")
            return 'local'

    def set_mode(self, mode: str):
        """手动切换模式：'local' 或 'cloud'"""
        if mode in ['local', 'cloud']:
            self.mode = mode
            print(f"[模式] 切换到 {mode} 模式")
            if mode == 'local' and not self.is_ready:
                self.load_models()
        else:
            print(f"[模式] 无效模式: {mode}")

    def load_models(self, callback: Optional[Callable] = None):
        """加载本地模型（仅在 local 模式下使用）"""
        if self.mode == 'cloud':
            self.is_ready = True
            if callback:
                Clock.schedule_once(lambda dt: callback(True, "云端模式，无需加载模型"), 0)
            return

        if self.is_loading:
            if callback:
                callback(False, "模型正在加载中")
            return

        self.is_loading = True

        def _load():
            try:
                print("=" * 50)
                print("开始加载本地模型...")

                print("\n[1/2] 加载 0.5B 意图识别模型...")
                success = self._load_small_model()
                if not success:
                    if callback:
                        Clock.schedule_once(lambda dt: callback(False, "0.5B模型加载失败"), 0)
                    return

                print("\n[2/2] 尝试加载 3B 生成模型...")
                self._load_large_model()

                self.is_ready = True
                if callback:
                    msg = "双模型就绪" if self.model_large else "单模型就绪(0.5B)"
                    Clock.schedule_once(lambda dt: callback(True, msg), 0)

            except Exception as e:
                print(f"加载异常: {e}")
                if callback:
                    Clock.schedule_once(lambda dt: callback(False, str(e)), 0)
            finally:
                self.is_loading = False

        import threading
        threading.Thread(target=_load, daemon=True).start()

    def _load_small_model(self) -> bool:
        """加载 0.5B 模型（本地）"""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM

            local_path = "./models/Qwen/Qwen2.5-0.5B-Instruct"

            if not os.path.exists(local_path):
                print(f"模型路径不存在: {local_path}")
                return False

            print("加载 tokenizer...")
            self.tokenizer_small = AutoTokenizer.from_pretrained(
                local_path, trust_remote_code=True, local_files_only=True
            )

            print("加载模型...")
            self.model_small = AutoModelForCausalLM.from_pretrained(
                local_path,
                trust_remote_code=True,
                local_files_only=True,
                low_cpu_mem_usage=True,
                device_map="cpu"
            )
            self.model_small.eval()

            print("0.5B 模型加载成功")
            return True

        except Exception as e:
            print(f"0.5B模型失败: {e}")
            return False

    def _load_large_model(self) -> bool:
        """加载 3B 模型（本地）"""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM

            local_path = "./models/Qwen/Qwen2.5-3B-Instruct"

            if not os.path.exists(local_path):
                print("3B模型未下载，跳过")
                return False

            print("加载 tokenizer...")
            self.tokenizer_large = AutoTokenizer.from_pretrained(
                local_path, trust_remote_code=True, local_files_only=True
            )

            print("加载模型...")
            self.model_large = AutoModelForCausalLM.from_pretrained(
                local_path,
                trust_remote_code=True,
                local_files_only=True,
                low_cpu_mem_usage=True,
                device_map="cpu"
            )
            self.model_large.eval()

            print("3B 模型加载成功")
            return True

        except Exception as e:
            print(f"3B模型加载失败: {e}")
            self.model_large = None
            return False

    def _call_cloud_api(self, messages: list) -> dict:
        """调用 DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {self.cloud_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
            "stream": False
        }

        try:
            response = requests.post(
                self.cloud_api_url,
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return {"success": True, "content": content, "model": "deepseek"}
            else:
                return {"success": False, "error": f"API错误: {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_local(self, model, tokenizer, messages, max_new_tokens=256):
        """本地模型生成"""
        import torch

        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = tokenizer([text], return_tensors="pt")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(
            outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True
        )
        return response.strip()

    def chat(self, user_input: str, user_prefs: dict, context: list = None) -> dict:
        """主对话接口 - 根据模式路由"""
        # 1. 检测工作流（优先级最高）
        user_lower = user_input.lower()
        for pattern, workflow in self.workflow_triggers.items():
            if re.search(pattern, user_lower):
                print(f"[工作流] 触发: {workflow}")
                return {
                    "success": True,
                    "content": "",
                    "workflow": workflow,
                    "params": {"user_input": user_input},
                    "model": "workflow"
                }

        # 2. 构建消息
        prefs_text = f"""
用户偏好：
- 辣度：{user_prefs.get('spicy_level', '微辣')}
- 忌口：{', '.join(user_prefs.get('avoid_foods', [])) or '无'}
- 预算：{user_prefs.get('default_budget', 30)}元
"""

        messages = [
            {"role": "system", "content": f"你是智能外卖助手。{prefs_text} 回答简洁。"}
        ]

        if context:
            messages.extend(context[-5:])

        messages.append({"role": "user", "content": user_input})

        # 3. 根据模式路由
        if self.mode == 'cloud':
            print("[路由] 使用云端 API")
            return self._call_cloud_api(messages)
        else:
            print("[路由] 使用本地模型")
            if not self.is_ready or self.model_small is None:
                # 降级到模拟回复
                return self._generate_mock_response(user_input, user_prefs)

            try:
                response = self._generate_local(
                    self.model_small, self.tokenizer_small,
                    messages, max_new_tokens=150
                )
                return {
                    "success": True,
                    "content": response,
                    "model": "qwen-0.5b",
                    "workflow": None
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    def _generate_mock_response(self, user_input: str, user_prefs: dict) -> dict:
        """模拟回复（降级用）"""
        user_lower = user_input.lower()

        if any(kw in user_lower for kw in ["推荐", "吃什么", "想吃饭"]):
            budget = user_prefs.get('default_budget', 30)
            return {
                "success": True,
                "content": f"根据您的偏好，推荐：\n1. 招牌麻辣烫 ¥{budget - 8}\n2. 黄焖鸡米饭 ¥{budget - 5}\n\n回复数字选择",
                "model": "mock",
                "workflow": None
            }

        return {
            "success": True,
            "content": f"收到：{user_input}\n\n我是外卖助手，可以说'推荐美食'开始点餐。",
            "model": "mock",
            "workflow": None
        }


# 单例
_router_service = None


def get_qwen_service():
    global _router_service
    if _router_service is None:
        _router_service = QwenRouterService()
    return _router_service
