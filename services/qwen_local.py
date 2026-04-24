# services/qwen_local.py
import os
import re
import json
import requests
import random
from typing import Dict, List, Callable, Optional
from kivy.clock import Clock
from kivy.utils import platform

# 导入 mock 数据集
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mock_restaurants import get_recommendations, get_restaurant, RESTAURANTS, DISHES_BY_RESTAURANT


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
            print("[模式] Android 环境，使用云端 API")
            return 'cloud'
        else:
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
                # self._load_large_model()  # 默认不加载，避免内存不足

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

    def _get_all_restaurant_names(self) -> list:
        """获取所有餐厅名称"""
        return [r["name"] for r in RESTAURANTS]

    def _get_all_dish_names(self) -> list:
        """获取所有菜品名称"""
        all_dishes = self._get_all_dishes_with_restaurant()
        return [item["dish"]["name"] for item in all_dishes]

    def _get_all_dishes_with_restaurant(self) -> list:
        """获取所有菜品（带餐厅信息）"""
        all_items = []
        for restaurant in RESTAURANTS:
            dishes = DISHES_BY_RESTAURANT.get(restaurant["id"], [])
            for dish in dishes:
                all_items.append({
                    "dish": dish,
                    "restaurant": restaurant,
                })
        return all_items

    def _parse_user_intent(self, user_input: str) -> dict:
        """解析用户意图，提取关键词、预算、菜系、辣度、忌口"""
        result = {
            "keyword": None,
            "budget": None,
            "cuisine": None,
            "spicy": None,
            "avoid": [],
            "restaurant": None,
            "dish_name": None,
        }

        # 提取预算
        budget_match = re.search(r'(\d+)(?:元|块|块钱)', user_input)
        if budget_match:
            result["budget"] = int(budget_match.group(1))

        price_range_match = re.search(r'(\d+)(?:元|块|块钱)(?:以下|以内|内|左右)', user_input)
        if price_range_match:
            result["budget"] = int(price_range_match.group(1))

        # 菜系列表
        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品"]
        for c in cuisines:
            if c in user_input:
                result["cuisine"] = c
                break

        # 提取餐厅名
        all_restaurants = self._get_all_restaurant_names()
        for r in all_restaurants:
            if r in user_input:
                result["restaurant"] = r
                break

        # 提取菜品名
        if not result["restaurant"]:
            all_dishes = self._get_all_dish_names()
            all_dishes.sort(key=len, reverse=True)
            for dish in all_dishes:
                if dish in user_input:
                    result["dish_name"] = dish
                    break
            if not result["dish_name"]:
                potential_names = re.findall(r'([\u4e00-\u9fa5]{2,4})', user_input)
                for pn in potential_names:
                    for dish in all_dishes:
                        if pn in dish and len(pn) >= 2:
                            result["dish_name"] = dish
                            break
                    if result["dish_name"]:
                        break

        # 提取关键词
        temp_input = user_input
        if result["restaurant"]:
            temp_input = temp_input.replace(result["restaurant"], "")
        if result["dish_name"]:
            temp_input = temp_input.replace(result["dish_name"], "")
        if result["cuisine"]:
            temp_input = temp_input.replace(result["cuisine"], "")
        if result["budget"]:
            temp_input = re.sub(r'\d+元[以内内左右]?', '', temp_input)

        food_match = re.search(r'(?:想吃|要吃|来一份|点|帮我点)([^，,。的]+)', temp_input)
        if food_match:
            keyword = food_match.group(1).strip()
            stop_words = ["菜", "饭", "餐", "外卖", "一份", "左右", "以内", "内", "的", "吧", "啊", "哦"]
            if keyword and len(keyword) <= 6 and keyword not in stop_words:
                result["keyword"] = keyword

        # 提取辣度
        spicy_levels = ["特辣", "中辣", "微辣", "不辣"]
        for s in spicy_levels:
            if s in user_input:
                result["spicy"] = s
                break

        # 提取忌口
        avoid_match = re.search(r'不要([\u4e00-\u9fa5]{1,4})', user_input)
        if avoid_match:
            avoid_item = avoid_match.group(1)
            allergen_normalize = {
                "奶": "乳制品", "牛奶": "乳制品", "芝士": "乳制品", "奶酪": "乳制品",
                "香菜": "香菜", "芫荽": "香菜",
                "蒜": "蒜", "大蒜": "蒜",
                "花生": "花生",
            }
            if avoid_item in allergen_normalize:
                avoid_item = allergen_normalize[avoid_item]
            if avoid_item and avoid_item not in ["吃", "放", "加", "要"]:
                result["avoid"] = [avoid_item]

        return result

    def _filter_by_prefs(self, recommendations: list, budget: float, keyword: str = None,
                         cuisine: str = None, spicy: str = None, avoid: list = None,
                         exclude_ids: list = None) -> list:
        """根据偏好过滤推荐列表"""
        filtered = []
        exclude_ids = exclude_ids or []

        def match_spicy(dish_spicy: str, user_spicy: str) -> bool:
            if not user_spicy or user_spicy == "不限":
                return True
            return dish_spicy == user_spicy

        for rec in recommendations:
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            dish_name = dish["name"]

            if avoid:
                dish_allergens = dish.get("allergens", [])
                is_avoided = False
                for a in avoid:
                    if a in dish_allergens:
                        is_avoided = True
                        break
                if is_avoided:
                    continue

            if dish["price"] > budget * 1.2:
                continue

            if cuisine and cuisine not in restaurant["cuisine"]:
                continue

            if keyword and keyword not in dish_name:
                continue

            if spicy:
                dish_spicy = dish.get("spicy", "微辣")
                if not match_spicy(dish_spicy, spicy):
                    continue

            if dish["id"] in exclude_ids:
                continue

            filtered.append(rec)

        filtered.sort(key=lambda x: (-x["restaurant"]["rating"], x["dish"]["price"]))
        return filtered

    def _get_recommendations_from_mock(self, budget: float, keyword: str = None,
                                       cuisine: str = None, spicy: str = None,
                                       avoid: list = None, exclude_ids: list = None) -> list:
        """从 mock 数据集获取推荐"""
        all_items = self._get_all_dishes_with_restaurant()
        filtered = self._filter_by_prefs(
            all_items, budget, keyword, cuisine, spicy, avoid, exclude_ids
        )
        return filtered[:5]

    def _ai_filter_dishes(self, all_items: list, user_input: str, user_prefs: dict,
                          budget: float, cuisine: str, spicy: str, avoid: list, keyword: str) -> list:
        """让 AI 从所有菜品中筛选出最符合用户需求的菜品"""

        # 首先根据菜系预筛选，减少传给 AI 的选项
        prefiltered = []
        for item in all_items:
            restaurant = item["restaurant"]
            # 如果指定了菜系，只保留该菜系的餐厅
            if cuisine and cuisine not in restaurant["cuisine"]:
                continue
            # 其他基本过滤
            dish = item["dish"]
            if dish["price"] > budget * 1.2:
                continue
            if spicy and dish.get("spicy", "微辣") != spicy:
                continue
            if avoid:
                dish_allergens = dish.get("allergens", [])
                if any(a in dish_allergens for a in avoid):
                    continue
            prefiltered.append(item)

        # 如果预筛选后没有菜品，返回空
        if not prefiltered:
            return []

        # 限制传给 AI 的菜品数量
        prefiltered = prefiltered[:50]

        # 构建菜品摘要
        dishes_summary = []
        for item in prefiltered:
            dish = item["dish"]
            restaurant = item["restaurant"]
            dishes_summary.append({
                "id": dish["id"],
                "name": dish["name"],
                "price": dish["price"],
                "restaurant": restaurant["name"],
                "rating": restaurant["rating"],
                "spicy": dish.get("spicy", "微辣")
            })

        # 构建提示词，明确要求菜系
        cuisine_text = f"必须从【{cuisine}】菜系中选择" if cuisine else "不限菜系"

        prompt = f"""根据用户需求，从以下菜品列表中选择3-5个最合适的菜品。

    用户需求：{user_input}
    用户要求菜系：{cuisine_text}
    用户辣度要求：{spicy}
    用户忌口：{', '.join(avoid) if avoid else '无'}
    用户预算：{budget}元

    菜品列表：
    {json.dumps(dishes_summary, ensure_ascii=False, indent=2)[:2500]}

    要求：
    1. 只返回菜品ID列表，格式为 [id1, id2, id3, ...]
    2. 必须选择{cuisine}菜系的菜品
    3. 优先选择评分高、价格符合预算的菜品
    4. 不要返回任何解释文字"""

        messages = [
            {"role": "system",
             "content": f"你是外卖推荐助手，只能从【{cuisine}】菜系中选择菜品，只返回菜品ID列表。" if cuisine else "你是外卖推荐助手，从给定列表中筛选菜品，只返回菜品ID列表。"},
            {"role": "user", "content": prompt}
        ]

        if self.mode == 'cloud':
            result = self._call_cloud_api(messages)
        else:
            if not self.is_ready or self.model_small is None:
                return []
            try:
                response = self._generate_local(
                    self.model_small, self.tokenizer_small,
                    messages, max_new_tokens=200
                )
                result = {"success": True, "content": response}
            except Exception as e:
                print(f"AI筛选失败: {e}")
                return []

        if result.get("success"):
            try:
                content = result["content"]
                ids = re.findall(r'[a-zA-Z0-9_]+', content)
                selected = []
                for item in prefiltered:
                    if item["dish"]["id"] in ids and item not in selected:
                        # 再次确认菜系
                        if cuisine and cuisine not in item["restaurant"]["cuisine"]:
                            continue
                        selected.append(item)
                return selected[:5]
            except Exception as e:
                print(f"解析AI结果失败: {e}")
                return []
        return []

    def _format_recommendation_response(self, recommendations: list, budget: int, spicy: str,
                                        user_input: str, user_prefs: dict) -> str:
        """按照固定格式生成推荐回复"""

        content = f"根据您的偏好（{spicy}口味，预算{budget}元），为您推荐：\n\n"
        for i, rec in enumerate(recommendations[:3], 1):
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {dish['price']}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   {dish.get('description', '人气推荐')}\n\n"

        content += "-" * 30 + "\n"
        content += "健康提示："

        # 生成健康提示
        tip = self._generate_health_tip(user_input, recommendations, user_prefs)
        content += tip + "\n"
        content += "-" * 30 + "\n\n"
        content += "回复数字选择菜品，或说'换一批'重新推荐，说'下单'确认订单。"

        return content

    def _handle_recommend(self, user_input: str, user_prefs: dict) -> dict:
        """处理推荐请求 - AI 从 mock 数据集中筛选并格式化输出"""

        parsed = self._parse_user_intent(user_input)

        budget = parsed["budget"] if parsed["budget"] is not None else user_prefs.get('default_budget', 30)
        keyword = parsed["keyword"]
        cuisine = parsed["cuisine"]
        spicy = parsed["spicy"] if parsed["spicy"] is not None else user_prefs.get('spicy_level', '微辣')
        avoid = parsed["avoid"] if parsed["avoid"] else user_prefs.get('avoid_foods', [])

        print(f"[全新推荐] 预算: {budget}, 菜系: {cuisine}, 辣度: {spicy}, 忌口: {avoid}, 关键词: {keyword}")

        # 先尝试规则推荐（确保有结果）
        recommendations = self._get_recommendations_from_mock(budget, keyword, cuisine, spicy, avoid)

        # 如果没有找到任何菜品，放宽辣度限制再试一次
        if not recommendations:
            print("[推荐] 未找到菜品，尝试放宽辣度限制")
            recommendations = self._get_recommendations_from_mock(budget, keyword, cuisine, None, avoid)

        # 如果还是没有，尝试用 AI 筛选
        if not recommendations or len(recommendations) < 2:
            all_items = self._get_all_dishes_with_restaurant()
            ai_results = self._ai_filter_dishes(all_items, user_input, user_prefs, budget, cuisine, spicy, avoid,
                                                keyword)
            if ai_results:
                # 合并 AI 结果和规则结果，去重
                existing_ids = [r["dish"]["id"] for r in recommendations]
                for item in ai_results:
                    if item["dish"]["id"] not in existing_ids:
                        recommendations.append(item)
                    if len(recommendations) >= 5:
                        break

        # 记录ID和上下文
        for rec in recommendations:
            self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_keyword"] = keyword
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid.copy()
        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context["last_search_params"] = {
            "budget": budget, "keyword": keyword, "cuisine": cuisine,
            "spicy": spicy, "avoid": avoid.copy(),
        }

        if not recommendations:
            # 提供更友好的提示信息
            tip = f"没有找到{cuisine if cuisine else ''}菜系中符合预算{budget}元、辣度{spicy}的菜品。"
            tip += "\n\n建议：\n- 提高预算\n- 放宽口味限制\n- 尝试其他菜系"
            return {
                "success": True,
                "content": tip,
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        content = self._format_recommendation_response(recommendations, budget, spicy, user_input, user_prefs)

        if recommendations:
            self.conversation_context["current_order"] = recommendations[0]

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_re_recommend(self, user_prefs: dict) -> dict:
        """处理换一批"""
        params = self.conversation_context.get("last_search_params")
        if not params:
            return self._handle_recommend("推荐", user_prefs)

        budget = params["budget"]
        keyword = params["keyword"]
        cuisine = params["cuisine"]
        spicy = params["spicy"]
        avoid = params["avoid"]
        exclude_ids = self.conversation_context.get("recommended_ids", [])

        print(f"[换一批] 预算={budget}, 菜系={cuisine}, 辣度={spicy}")

        recommendations = self._get_recommendations_from_mock(budget, keyword, cuisine, spicy, avoid, exclude_ids)

        if not recommendations:
            print("[换一批] 没有更多菜品，重新开始")
            self.conversation_context["recommended_ids"] = []
            recommendations = self._get_recommendations_from_mock(budget, keyword, cuisine, spicy, avoid, [])

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["current_recommendations"] = recommendations

        if not recommendations:
            return {
                "success": True,
                "content": f"抱歉，没有更多符合您需求的菜品了。\n\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味，预算{budget}元\n\n建议修改筛选条件。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        content = f"为您换一批推荐（预算{budget}元，{spicy}口味）：\n\n"
        for i, rec in enumerate(recommendations[:3], 1):
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {dish['price']}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   辣度：{dish.get('spicy', '微辣')}\n\n"

        content += "回复数字选择，或说'换一批'继续。"

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_modify(self, user_input: str, user_prefs: dict) -> dict:
        """处理修改推荐请求"""
        user_lower = user_input.lower()

        budget = self.conversation_context["last_budget"]
        keyword = self.conversation_context["last_keyword"]
        cuisine = self.conversation_context["last_cuisine"]
        spicy = self.conversation_context["last_spicy"]
        avoid = self.conversation_context["last_avoid"].copy()

        change_desc = []

        if re.search(r'更贵|贵一点|提高预算', user_lower):
            budget = min(100, budget + 10)
            change_desc.append(f"预算提高为{budget}元")
        elif re.search(r'更便宜|便宜一点|降低预算', user_lower):
            budget = max(15, budget - 10)
            change_desc.append(f"预算降低为{budget}元")

        budget_match = re.search(r'(\d+)(?:元|块|块钱)', user_input)
        if budget_match:
            budget = int(budget_match.group(1))
            change_desc.append(f"预算改为{budget}元")

        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品"]
        for c in cuisines:
            if c in user_input:
                cuisine = c
                change_desc.append(f"菜系改为{cuisine}")
                break

        for s in ["特辣", "中辣", "微辣", "不辣"]:
            if s in user_input:
                spicy = s
                change_desc.append(f"辣度改为{spicy}")
                break

        exclude_match = re.search(r'不要([\u4e00-\u9fa5]{1,4})', user_input)
        if exclude_match:
            exclude_item = exclude_match.group(1)
            if exclude_item not in avoid:
                avoid.append(exclude_item)
            change_desc.append(f"排除{exclude_item}")

        if not change_desc:
            return {
                "success": True,
                "content": "请告诉我具体要修改什么，例如：提高预算、改为川菜、不要香菜等",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        print(f"[修改推荐] 修改项: {change_desc}")

        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "keyword": keyword,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
        }
        self.conversation_context["recommended_ids"] = []

        recommendations = self._get_recommendations_from_mock(budget, keyword, cuisine, spicy, avoid)

        for rec in recommendations:
            self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_keyword"] = keyword
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["current_recommendations"] = recommendations

        if not recommendations:
            return {
                "success": True,
                "content": f"抱歉，调整后仍没有找到符合您需求的菜品。\n\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味，预算{budget}元，忌口{avoid if avoid else '无'}\n\n建议提高预算或放宽口味限制。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        change_text = "，".join(change_desc)
        content = f"{change_text}，为您重新推荐：\n\n"
        for i, rec in enumerate(recommendations[:3], 1):
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {dish['price']}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   辣度：{dish.get('spicy', '微辣')}\n\n"

        content += "回复数字选择，或继续调整。"

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
            "recommendations": recommendations
        }

    def select_dish(self, choice: int) -> dict:
        """用户选择菜品"""
        recommendations = self.conversation_context.get("current_recommendations", [])

        if not recommendations or choice > len(recommendations):
            return {
                "success": False,
                "content": "请选择有效的菜品编号",
                "workflow": None
            }

        selected = recommendations[choice - 1]
        self.conversation_context["current_order"] = selected

        dish = selected["dish"]
        restaurant = selected["restaurant"]

        content = f"您选择了：{dish['name']} ({restaurant['name']})\n"
        content += f"价格：{dish['price']}元\n"
        content += f"预计送达：{restaurant['delivery_time']}分钟\n\n"
        content += "回复'下单'确认订单，或回复'取消'重新选择。"

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None
        }

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
        """主对话接口 - 工作流优先，AI 回复兜底"""
        user_input = user_input.strip()
        user_lower = user_input.lower()

        print(f"[对话] 用户输入: {user_input}")

        # 1. 工作流触发词检测（下单、追踪等）
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

        # 2. 纯数字选择菜品
        if user_input.isdigit():
            return self.select_dish(int(user_input))

        # 3. 换一批
        if re.search(r'换一批|重新推荐|再来一批', user_lower):
            return self._handle_re_recommend(user_prefs)

        # 4. 推荐相关
        if any(kw in user_lower for kw in ["推荐", "吃什么", "想吃饭", "饿了", "有什么", "点", "想吃", "来一份"]):
            return self._handle_recommend(user_input, user_prefs)

        # 5. 修改推荐
        if re.search(r'更贵|贵一点|提高预算|更便宜|便宜一点|降低预算|改为|换成|不要', user_lower):
            return self._handle_modify(user_input, user_prefs)

        # 6. 确认下单
        if re.search(r'下单|确认', user_lower):
            order = self.conversation_context.get("current_order")
            if order:
                return {
                    "success": True,
                    "content": "",
                    "workflow": "submit_order",
                    "params": {"user_input": user_input},
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                }
            else:
                return {
                    "success": True,
                    "content": "请先选择菜品（回复数字），然后再说'下单'确认。",
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None
                }

        # 7. 取消订单
        if re.search(r'取消|重新选|换一个', user_lower):
            self.conversation_context["current_order"] = None
            recs = self.conversation_context.get("current_recommendations", [])
            if recs:
                content = "已取消，以下是推荐列表：\n\n"
                for i, rec in enumerate(recs[:3], 1):
                    dish = rec["dish"]
                    restaurant = rec["restaurant"]
                    content += f"{i}. {dish['name']} - {restaurant['name']}\n"
                    content += f"   评分{restaurant['rating']}分 | {dish['price']}元 | {restaurant['delivery_time']}分钟\n\n"
                content += "回复数字选择菜品，或说'换一批'重新推荐。"
            else:
                content = "已取消，请说'推荐'重新开始点餐。"
            return {
                "success": True,
                "content": content,
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        # 8. 其他情况：使用 AI 生成回复
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

        if self.mode == 'cloud':
            print("[路由] 使用云端 API")
            result = self._call_cloud_api(messages)
            if result.get("success"):
                result["model"] = "Deepseek"
            return result
        else:
            print("[路由] 使用本地模型")
            if not self.is_ready or self.model_small is None:
                return self._generate_mock_response(user_input, user_prefs)
            try:
                response = self._generate_local(
                    self.model_small, self.tokenizer_small,
                    messages, max_new_tokens=150
                )
                return {
                    "success": True,
                    "content": response,
                    "model": "qwen-0.5b (0.5B)",
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
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        return {
            "success": True,
            "content": f"收到：{user_input}\n\n我是外卖助手，可以说'推荐美食'开始点餐。",
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None
        }

    def _call_cloud_api_for_tip(self, messages: list, selected_dishes: list) -> str:
        """调用云端 API 生成健康提示"""
        headers = {
            "Authorization": f"Bearer {self.cloud_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 100,
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
                content = re.sub(r'[\U00010000-\U0010ffff]', '', content)
                return content.strip()
            else:
                return self._get_fallback_tip(selected_dishes)

        except Exception as e:
            print(f"云端健康提示生成失败: {e}")
            return self._get_fallback_tip(selected_dishes)

    def _generate_local_tip(self, messages: list, selected_dishes: list) -> str:
        """使用本地模型生成健康提示"""
        if not self.is_ready or self.model_small is None:
            return self._get_fallback_tip(selected_dishes)

        try:
            import torch

            text = self.tokenizer_small.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            inputs = self.tokenizer_small([text], return_tensors="pt")

            with torch.no_grad():
                outputs = self.model_small.generate(
                    **inputs,
                    max_new_tokens=100,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.95,
                    pad_token_id=self.tokenizer_small.eos_token_id
                )

            response = self.tokenizer_small.decode(
                outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True
            )
            response = re.sub(r'[\U00010000-\U0010ffff]', '', response)
            return response.strip()

        except Exception as e:
            print(f"本地健康提示生成失败: {e}")
            return self._get_fallback_tip(selected_dishes)

    def _generate_health_tip(self, user_input: str, selected_dishes: list, user_prefs: dict) -> str:
        """根据用户点单需求生成健康提示"""
        dishes_text = ""
        for dish in selected_dishes[:3]:
            dishes_text += f"- {dish['dish']['name']} ({dish['restaurant']['name']})\n"

        prompt = f"""根据用户的点餐需求，生成一句简短的健康饮食提示（不超过25字）。

用户需求：{user_input}
用户选择的菜品：
{dishes_text}
用户偏好：辣度={user_prefs.get('spicy_level', '微辣')}，忌口={user_prefs.get('avoid_foods', [])}

要求：
- 只输出提示内容，不要加任何前缀
- 不要使用表情符号
- 提示要针对用户选择的菜品
- 语言亲切自然"""

        messages = [
            {"role": "system", "content": "你是营养健康助手，生成简洁的健康饮食提示。"},
            {"role": "user", "content": prompt}
        ]

        if self.mode == 'cloud':
            print("[健康提示] 使用云端 API 生成")
            return self._call_cloud_api_for_tip(messages, selected_dishes)
        else:
            print("[健康提示] 使用本地模型生成")
            return self._generate_local_tip(messages, selected_dishes)

    def _get_fallback_tip(self, selected_dishes: list) -> str:
        """降级方案：通用健康提示"""
        if not selected_dishes:
            return "祝您用餐愉快，注意饮食均衡。"

        dish = selected_dishes[0]["dish"]
        name = dish["name"]

        if "辣" in name:
            return "麻辣食物适量食用，可搭配酸奶缓解肠胃刺激。"
        elif "炸" in name or "烤" in name:
            return "油炸烧烤类食物建议搭配蔬菜一起食用，营养更均衡。"
        elif "面" in name or "饭" in name:
            return "主食搭配蛋白质和蔬菜，营养更全面。"
        elif "蛋糕" in name or "甜品" in name:
            return "甜品适量食用，建议选择低糖版本。"
        else:
            return "祝您用餐愉快，记得细嚼慢咽，享受美食。"


# 单例
_router_service = None


def get_qwen_service():
    global _router_service
    if _router_service is None:
        _router_service = QwenRouterService()
    return _router_service
