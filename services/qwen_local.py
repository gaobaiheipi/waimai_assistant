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

from services.db_service import get_db_service

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mock_restaurants import get_recommendations, get_restaurant, RESTAURANTS, DISHES_BY_RESTAURANT
from services.local_auth import user_session


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
            "last_budget_min": None,
            "last_budget_max": None,
            "last_budget_type": "exact",
            "last_keyword": None,
            "last_cuisine": None,
            "last_spicy": "微辣",
            "last_avoid": [],
            "current_recommendations": [],
            "current_order": None,
            "last_search_params": None,
            "recommended_ids": [],
            "recommended_restaurant_ids": [],
            "recommended_broth_ids": [],
            "user_frequent_dishes": None,
            "user_frequent_restaurants": None,
            "try_new_mode": False,
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
                self._load_large_model()

                self.is_ready = True
                if callback:
                    msg = "单模型就绪(0.5B)"
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

    def _parse_budget_from_input(self, user_input: str, default_budget: int = 30) -> dict:
        """从用户输入中解析预算信息"""
        result = {
            "budget": default_budget,
            "budget_min": None,
            "budget_max": None,
            "budget_type": "exact"
        }

        # 提取预算数值
        budget_match = re.search(r'(\d+)', user_input)
        if budget_match:
            result["budget"] = int(budget_match.group(1))

        # 解析范围预算
        if re.search(r'(\d+)[-到](\d+)', user_input):
            result["budget_type"] = "range"
            match = re.search(r'(\d+)[-到](\d+)', user_input)
            if match:
                result["budget_min"] = int(match.group(1))
                result["budget_max"] = int(match.group(2))
                result["budget"] = (result["budget_min"] + result["budget_max"]) // 2
        # 解析以内预算
        elif re.search(r'(\d+)(?:元|块)?(?:以内|以下|内)', user_input):
            result["budget_type"] = "within"
            match = re.search(r'(\d+)(?:元|块)?(?:以内|以下|内)', user_input)
            if match:
                result["budget_max"] = int(match.group(1))
                result["budget_min"] = 0
                result["budget"] = result["budget_max"]
        # 解析左右预算
        elif re.search(r'(\d+)(?:元|块)?(?:左右|上下|大约)', user_input):
            result["budget_type"] = "around"
            match = re.search(r'(\d+)(?:元|块)?(?:左右|上下|大约)', user_input)
            if match:
                base = int(match.group(1))
                result["budget"] = base
                result["budget_min"] = base - 5
                result["budget_max"] = base + 5
        else:
            # 精确预算
            result["budget_type"] = "exact"
            result["budget_min"] = int(result["budget"] * 0.9)
            result["budget_max"] = int(result["budget"] * 1.1)

        print(f"[预算解析] {result['budget_type']}: {result['budget_min']}-{result['budget_max']}元")
        return result

    def _parse_user_intent(self, user_input: str, user_prefs: dict) -> dict:
        """解析用户意图（规则匹配，作为AI的兜底）"""
        result = {
            "keyword": None,
            "budget": None,
            "budget_min": None,
            "budget_max": None,
            "cuisine": None,
            "spicy": None,
            "avoid": [],
            "restaurant": None,
            "dish_name": None,
            "exclude_restaurant": None,
            "budget_type": "exact",
            "is_drink": False,
            "action": "recommend",
        }

        user_input_lower = user_input.lower()

        budget_info = self._parse_budget_from_input(user_input, user_prefs.get('default_budget', 30))
        result["budget"] = budget_info["budget"]
        result["budget_min"] = budget_info["budget_min"]
        result["budget_max"] = budget_info["budget_max"]
        result["budget_type"] = budget_info["budget_type"]

        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品",
                    "烧烤", "串串", "饮品"]
        for c in cuisines:
            if c in user_input:
                result["cuisine"] = c
                break

        if result["cuisine"] in ["甜品", "饮品"]:
            result["spicy"] = "不辣"

        if re.search(r'不吃辣|不要辣|我不吃辣', user_input_lower):
            result["spicy"] = "不辣"
        elif "特辣" in user_input:
            result["spicy"] = "特辣"
        elif "中辣" in user_input:
            result["spicy"] = "中辣"
        elif "微辣" in user_input:
            result["spicy"] = "微辣"

        avoid_match = re.search(r'不要([\u4e00-\u9fa5]{2,4})', user_input)
        if avoid_match:
            result["avoid"] = [avoid_match.group(1)]

        user_lower = user_input.lower()

        if re.search(r'想尝试新的|尝试新|换换口味|新口味', user_lower):
            result["action"] = "recommend_new"
        elif re.search(r'提高预算|降低预算|更贵|更便宜|改为|换成|不要|排除|换一批|重新推荐', user_lower):
            result["action"] = "modify"
        elif re.search(r'下单|确认|就这个', user_lower):
            result["action"] = "order"
        elif re.search(r'订单状态|追踪|查询', user_lower):
            result["action"] = "query"
        elif re.search(r'取消', user_lower):
            result["action"] = "cancel"
        else:
            result["action"] = "recommend"

        print(
            f"[规则解析] action={result['action']}, budget={result['budget']}, budget_type={result['budget_type']}, cuisine={result['cuisine']}")

        return result

    def _classify_intent_with_ai(self, user_input: str, user_prefs: dict, context_info: dict = None) -> Optional[dict]:
        """使用 AI 识别用户意图"""

        context_text = ""
        if context_info:
            context_text = f"""
    当前对话上下文：
    - 上一轮菜系：{context_info.get('cuisine', '无')}
    - 上一轮辣度：{context_info.get('spicy', '无')}
    - 上一轮预算：{context_info.get('budget', '无')}元
    - 上一轮忌口：{context_info.get('avoid', [])}"""

        prompt = f"""你是一个外卖助手的意图识别模块。分析用户输入，判断意图类型并提取预算。

    用户输入："{user_input}"
    用户默认偏好：辣度={user_prefs.get('spicy_level', '微辣')}，忌口={user_prefs.get('avoid_foods', [])}，默认预算={user_prefs.get('default_budget', 30)}元

    意图类型定义：

    1. recommend - 用户想要系统推荐菜品。用户还没有看到具体的推荐结果，需要系统给出选项。
       典型说法：帮我点、推荐、想吃、点一份、来一份、有什么好吃的、给我推荐

    2. re_recommend - 用户对当前推荐不满意，想要换一批新的推荐。
       典型说法：换一批、重新推荐、再来一批、换一家、别的

    3. recommend_new - 用户想要尝试新的口味，排除常点菜品。
       典型说法：新的、尝试新、新口味

    4. modify - 用户想修改筛选条件（预算、口味、忌口、菜系、排除特定菜品）。
       典型说法：提高预算、降低预算、改为、换成、不要XX、排除XX、更贵、更便宜、改成川菜、不要夫妻肺片

    5. order - 用户已经看到了推荐，明确要下单购买。
       典型说法：下单、确认订单、就这个、付款、我要这个

    6. query - 用户查询订单状态。
       典型说法：订单状态、到哪了、查询订单

    7. cancel - 用户取消当前操作。
       典型说法：取消、不要了、算了

    关键区分规则：
    - 说"不要XX"（如不要香菜、不要夫妻肺片）→ modify，不是 recommend
    - 说"帮我点XXX" → recommend
    - 说"换一批" → re_recommend
    - 说"想尝试新的" → recommend_new
    - 说"就这个" → order

    预算提取规则：
    - "40以内" → budget=40, budget_min=0, budget_max=40, budget_type="within"
    - "40左右" → budget=40, budget_min=35, budget_max=45, budget_type="around"
    - "30元" → budget=30, budget_min=27, budget_max=33, budget_type="exact"

    如果用户输入中没有明确预算且菜品不是火锅或者串串，则 budget、budget_min、budget_max、budget_type 都设为 null。
    如果用户输入中没有明确预算但菜品是火锅或者串串，则 budget_max 设为 100。

    请只返回 JSON 格式的结果。JSON 格式：
    {{"action": "意图类型", "budget": 数字或null, "budget_min": 数字或null, "budget_max": 数字或null, "budget_type": "类型或null", "cuisine": null, "spicy": null, "avoid": []}}

    示例：
    输入："帮我点40以内的外卖"
    输出：{{"action":"recommend", "budget":40, "budget_min":0, "budget_max":40, "budget_type":"within", "cuisine":null, "spicy":null, "avoid":[]}}

    输入："换一批"
    输出：{{"action":"re_recommend", "budget":null, "budget_min":null, "budget_max":null, "budget_type":null, "cuisine":null, "spicy":null, "avoid":[]}}

    输入："想尝试新的"
    输出：{{"action":"recommend_new", "budget":null, "budget_min":null, "budget_max":null, "budget_type":null, "cuisine":null, "spicy":null, "avoid":[]}}

    输入："不要夫妻肺片"
    输出：{{"action":"modify", "budget":null, "budget_min":null, "budget_max":null, "budget_type":null, "cuisine":null, "spicy":null, "avoid":["夫妻肺片"]}}

    输入："提高预算到50"
    输出：{{"action":"modify", "budget":50, "budget_min":45, "budget_max":55, "budget_type":"exact", "cuisine":null, "spicy":null, "avoid":[]}}

    输入："就这个"
    输出：{{"action":"order", "budget":null, "budget_min":null, "budget_max":null, "budget_type":null, "cuisine":null, "spicy":null, "avoid":[]}}

    现在请分析用户输入："{user_input}"
    """

        messages = [
            {"role": "system",
             "content": "你是外卖助手意图识别器。只返回JSON。action字段必须是小写英文字母和下划线，例如 recommend、re_recommend、recommend_new、modify、order、query、cancel。不要返回其他格式。"},
            {"role": "user", "content": prompt}
        ]

        try:
            if self.mode == 'cloud':
                result = self._call_cloud_api(messages)
            else:
                if not self.is_ready or self.model_small is None:
                    return None
                response = self._generate_local(
                    self.model_small, self.tokenizer_small,
                    messages, max_new_tokens=200
                )
                result = {"success": True, "content": response}

            if result.get("success"):
                content = result["content"]
                content = content.strip()
                json_match = re.search(r'\{[^{}]*\}', content)
                if json_match:
                    intent = json.loads(json_match.group())
                    print(
                        f"[AI意图识别] action={intent.get('action')}, budget={intent.get('budget')}, budget_type={intent.get('budget_type')}")
                    return intent
        except Exception as e:
            print(f"AI意图识别失败: {e}")

        return None

    def _get_all_restaurant_names(self) -> list:
        """获取所有餐厅名称"""
        return [r["name"] for r in RESTAURANTS]

    def _get_all_dish_names(self) -> list:
        """获取所有菜品名称"""
        all_dishes = self._get_all_dishes_with_restaurant()
        return list(set([item["dish"]["name"] for item in all_dishes]))

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

    def _contains_avoid_ingredient(self, dish_name: str, avoid_list: list) -> bool:
        """判断菜品是否包含忌口食材"""
        if not avoid_list:
            return False

        avoid_mapping = {
            "酸菜": ["酸菜鱼", "酸菜饺子", "酸菜炖排骨"],
            "豆腐": ["豆腐", "麻婆豆腐", "家常豆腐"],
            "花生": ["花生", "花生米", "宫保鸡丁"],
            "香菜": ["香菜", "芫荽", "香菜牛肉"],
            "蒜": ["蒜", "大蒜", "蒜蓉", "蒜泥"],
            "奶": ["奶", "牛奶", "奶茶", "奶黄包", "芝士", "奶油", "双皮奶"],
        }

        for a in avoid_list:
            if a in avoid_mapping:
                for kw in avoid_mapping[a]:
                    if kw in dish_name:
                        return True
            else:
                if a in dish_name:
                    return True
        return False

    def _filter_by_prefs_with_price_range(self, recommendations: list,
                                          price_min: float, price_max: float,
                                          budget: float,
                                          keyword: str = None, cuisine: str = None,
                                          spicy: str = None, avoid: list = None,
                                          exclude_ids: list = None) -> list:
        """根据偏好和价格范围过滤推荐列表"""
        from services.db_service import get_db_service
        from services.local_auth import user_session

        filtered = []
        exclude_ids = exclude_ids or []
        avoid = avoid or []

        user_id = None
        if not user_session.is_guest:
            try:
                user_id = int(user_session.user_id)
            except:
                pass

        favorite_dishes = set()
        blacklist_dishes = set()

        if user_id:
            db = get_db_service()
            for fav in db.get_favorites(user_id):
                favorite_dishes.add((fav['restaurant_name'], fav['dish_name']))
            for bl in db.get_blacklist(user_id):
                blacklist_dishes.add((bl['restaurant_name'], bl['dish_name']))

        try_new_mode = self.conversation_context.get('try_new_mode', False)
        frequent_dish_names = []
        frequent_restaurant_names = []

        if not try_new_mode:
            frequent_dishes = self.conversation_context.get('user_frequent_dishes', [])
            frequent_restaurants = self.conversation_context.get('user_frequent_restaurants', [])
            frequent_dish_names = [d[0] for d in frequent_dishes[:3]] if frequent_dishes else []
            frequent_restaurant_names = [r[0] for r in frequent_restaurants[:3]] if frequent_restaurants else []

        def match_spicy(dish_spicy: str, user_spicy: str) -> bool:
            if not user_spicy or user_spicy == "不限":
                return True
            if user_spicy == "不辣":
                return dish_spicy == "不辣"
            elif user_spicy == "微辣":
                return dish_spicy in ["不辣", "微辣", "中辣"]
            elif user_spicy == "中辣":
                return dish_spicy in ["微辣", "中辣", "特辣"]
            elif user_spicy == "特辣":
                return dish_spicy in ["中辣", "特辣", "麻辣"]
            return False

        for rec in recommendations:
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            dish_name = dish["name"]
            restaurant_name = restaurant["name"]
            price = dish["price"]

            if price < price_min or price > price_max:
                continue
            if cuisine and cuisine not in restaurant["cuisine"]:
                continue
            if keyword and keyword not in dish_name:
                continue
            if spicy:
                dish_spicy = dish.get("spicy", "微辣")
                if not match_spicy(dish_spicy, spicy):
                    continue
            if avoid:
                if self._contains_avoid_ingredient(dish_name, avoid):
                    continue
            if dish["id"] in exclude_ids:
                continue

            if (restaurant_name, dish_name) in blacklist_dishes:
                print(f"[避雷过滤] 跳过避雷菜品: {restaurant_name} - {dish_name}")
                continue

            is_favorite = (restaurant_name, dish_name) in favorite_dishes

            is_frequent = False
            if not is_favorite:
                if dish_name in frequent_dish_names:
                    is_frequent = True
                elif restaurant_name in frequent_restaurant_names:
                    is_frequent = True

            rec['is_favorite'] = is_favorite
            rec['is_frequent'] = is_frequent
            filtered.append(rec)

        if try_new_mode:
            filtered.sort(key=lambda x: (
                -x.get('is_favorite', False),
                -x["restaurant"]["rating"],
                x["dish"]["price"]
            ))
        else:
            filtered.sort(key=lambda x: (
                -x.get('is_favorite', False),
                -x.get('is_frequent', False),
                -x["restaurant"]["rating"],
                x["dish"]["price"]
            ))

        return filtered

    def _get_recommendations_from_mock(self, budget: float, keyword: str = None,
                                       cuisine: str = None, spicy: str = None,
                                       avoid: list = None, exclude_ids: list = None,
                                       budget_min: float = None, budget_max: float = None,
                                       exclude_restaurant: str = None,
                                       budget_type: str = "exact") -> list:
        """从 mock 数据集获取推荐"""
        all_items = self._get_all_dishes_with_restaurant()

        if budget_type == "range" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        elif budget_type == "within" and budget_max is not None:
            price_min = 0
            price_max = budget_max
        elif budget_type == "around" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        else:
            price_min = int(budget * 0.9)
            price_max = int(budget * 1.1)

        filtered = self._filter_by_prefs_with_price_range(
            all_items, price_min, price_max, budget,
            keyword, cuisine, spicy, avoid, exclude_ids
        )

        if exclude_restaurant:
            filtered = [r for r in filtered if exclude_restaurant not in r["restaurant"]["name"]]

        return filtered[:5]

    def _get_recommendations_from_mock_exclude_hotpot(self, budget: float, keyword: str = None,
                                                      cuisine: str = None, spicy: str = None,
                                                      avoid: list = None, exclude_ids: list = None,
                                                      budget_min: float = None, budget_max: float = None,
                                                      budget_type: str = "exact") -> list:
        """从 mock 数据集获取推荐（排除火锅、串串、甜品、饮品）"""
        all_items = self._get_all_dishes_with_restaurant()

        dessert_keywords = ["蛋糕", "慕斯", "芝士", "提拉米苏", "泡芙", "马卡龙", "布丁", "双皮奶", "班戟", "千层", "冰淇淋",
                            "甜品", "甜点", "奶油", "巧克力蛋糕", "芒果慕斯", "芝士蛋糕", "杨枝甘露"]

        drinks_keywords = ["奶茶", "咖啡", "柠檬茶", "果茶", "拿铁", "卡布奇诺", "美式", "焦糖", "抹茶", "百香果", "金桔",
                           "养乐多", "可乐", "雪碧", "果汁", "红茶", "绿茶", "乌龙茶", "奶盖", "波霸", "珍珠", "椰奶"]

        dessert_drink_cuisines = ["甜品", "饮品"]

        filtered_items = []
        for item in all_items:
            restaurant_cuisine = item["restaurant"]["cuisine"]
            dish_name = item["dish"]["name"]

            if restaurant_cuisine == "火锅" or restaurant_cuisine == "串串":
                continue

            if cuisine in dessert_drink_cuisines:
                if restaurant_cuisine != cuisine:
                    continue
                is_match = False
                if cuisine == "饮品":
                    for kw in drinks_keywords:
                        if kw in dish_name:
                            is_match = True
                            break
                elif cuisine == "甜品":
                    for kw in dessert_keywords:
                        if kw in dish_name:
                            is_match = True
                            break
                if not is_match:
                    continue
            else:
                if restaurant_cuisine in dessert_drink_cuisines:
                    continue
                is_dessert_or_drink = False
                for kw in dessert_keywords:
                    if kw in dish_name:
                        is_dessert_or_drink = True
                        break
                if not is_dessert_or_drink:
                    for kw in drinks_keywords:
                        if kw in dish_name:
                            is_dessert_or_drink = True
                            break
                if is_dessert_or_drink:
                    continue

            filtered_items.append(item)

        print(f"[排除火锅串串甜品饮品] 剩余菜品数: {len(filtered_items)}")

        if budget_type == "range" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        elif budget_type == "within" and budget_max is not None:
            price_min = 0
            price_max = budget_max
        elif budget_type == "around" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        else:
            price_min = int(budget * 0.9)
            price_max = int(budget * 1.1)

        filtered = self._filter_by_prefs_with_price_range(
            filtered_items, price_min, price_max, budget,
            keyword, cuisine, spicy, avoid, exclude_ids
        )

        return filtered[:5]

    def _get_hotpot_recommendations(self, budget: float, spicy: str, avoid: list = None,
                                    budget_min: float = None, budget_max: float = None,
                                    budget_type: str = "exact") -> dict:
        """获取火锅推荐（预算必须足够锅底+至少一个配菜）"""
        avoid = avoid or []

        if budget_type == "range" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        elif budget_type == "within" and budget_max is not None:
            price_min = 0
            price_max = budget_max
        elif budget_type == "around" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        else:
            price_min = int(budget * 0.9)
            price_max = int(budget * 1.1)
        recommended_restaurant_ids = self.conversation_context.get("recommended_restaurant_ids", [])

        hotpot_restaurants = [r for r in RESTAURANTS if r["cuisine"] == "火锅"]
        if not hotpot_restaurants:
            return None

        available_restaurants = [r for r in hotpot_restaurants if r["id"] not in recommended_restaurant_ids]
        if not available_restaurants:
            self.conversation_context["recommended_restaurant_ids"] = []
            available_restaurants = hotpot_restaurants

        for restaurant in sorted(available_restaurants, key=lambda x: x["rating"], reverse=True):
            all_dishes = []
            for item in self._get_all_dishes_with_restaurant():
                if item["restaurant"]["id"] == restaurant["id"]:
                    all_dishes.append(item)

            broths = []
            side_dishes = []

            for item in all_dishes:
                dish = item["dish"]
                if "锅底" in dish["name"]:
                    broths.append(item)
                else:
                    side_dishes.append(item)

            recommended_broth_ids = self.conversation_context.get("recommended_broth_ids", [])
            available_broths = [b for b in broths if b["dish"]["id"] not in recommended_broth_ids]
            if not available_broths:
                self.conversation_context["recommended_broth_ids"] = []
                available_broths = broths

            selected_broth = None
            for b in available_broths:
                dish_spicy = b["dish"]["spicy"]
                if spicy == "不辣" and dish_spicy == "不辣":
                    selected_broth = b
                    break
                elif spicy == "微辣" and dish_spicy in ["不辣", "微辣"]:
                    selected_broth = b
                    break
                elif spicy == "中辣" and dish_spicy == "中辣":
                    selected_broth = b
                    break
                elif spicy == "特辣" and dish_spicy in ["中辣", "特辣"]:
                    selected_broth = b
                    break

            if not selected_broth and available_broths:
                selected_broth = available_broths[0]

            if not selected_broth:
                continue

            broth_price = selected_broth["dish"]["price"]

            if side_dishes:
                min_side_price = min(s["dish"]["price"] for s in side_dishes)
                if budget < broth_price + min_side_price:
                    print(f"[火锅] 预算{budget}元只够锅底({broth_price}元)，不够配菜({min_side_price}元)，跳过此餐厅")
                    continue

            remaining_budget = budget - broth_price
            if remaining_budget <= 0:
                print(f"[火锅] 预算{budget}元只够锅底({broth_price}元)，没有剩余预算买配菜，跳过")
                continue

            selected_sides = []
            sorted_sides = sorted(side_dishes, key=lambda x: x["dish"]["price"])

            for side in sorted_sides:
                dish = side["dish"]
                if avoid and self._contains_avoid_ingredient(dish["name"], avoid):
                    continue
                if dish["price"] <= remaining_budget:
                    selected_sides.append(side)
                    remaining_budget -= dish["price"]

            if not selected_sides:
                print(f"[火锅] 预算{budget}元下，餐厅{restaurant['name']}没有找到合适的配菜，跳过")
                continue

            self.conversation_context["recommended_restaurant_ids"].append(restaurant["id"])
            self.conversation_context["recommended_broth_ids"].append(selected_broth["dish"]["id"])

            return {
                "restaurant": restaurant,
                "broth": selected_broth,
                "sides": selected_sides,
                "total_price": broth_price + sum(s["dish"]["price"] for s in selected_sides),
                "type": "hotpot"
            }

        return None

    def _get_chuanchuan_recommendations(self, budget: float, spicy: str, avoid: list = None,
                                        budget_min: float = None, budget_max: float = None,
                                        budget_type: str = "exact") -> dict:
        """获取串串推荐（预算必须足够锅底+至少一个串串）"""
        avoid = avoid or []

        if budget_type == "range" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        elif budget_type == "within" and budget_max is not None:
            price_min = 0
            price_max = budget_max
        elif budget_type == "around" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
        else:
            price_min = int(budget * 0.9)
            price_max = int(budget * 1.1)

        recommended_restaurant_ids = self.conversation_context.get("recommended_restaurant_ids", [])

        chuanchuan_restaurants = [r for r in RESTAURANTS if r["cuisine"] == "串串"]
        if not chuanchuan_restaurants:
            return None

        available_restaurants = [r for r in chuanchuan_restaurants if r["id"] not in recommended_restaurant_ids]
        if not available_restaurants:
            self.conversation_context["recommended_restaurant_ids"] = []
            available_restaurants = chuanchuan_restaurants

        for restaurant in sorted(available_restaurants, key=lambda x: x["rating"], reverse=True):
            all_dishes = []
            for item in self._get_all_dishes_with_restaurant():
                if item["restaurant"]["id"] == restaurant["id"]:
                    all_dishes.append(item)

            broths = []
            skewers = []

            for item in all_dishes:
                dish = item["dish"]
                if "锅底" in dish["name"]:
                    broths.append(item)
                else:
                    skewers.append(item)

            recommended_broth_ids = self.conversation_context.get("recommended_broth_ids", [])
            available_broths = [b for b in broths if b["dish"]["id"] not in recommended_broth_ids]
            if not available_broths:
                self.conversation_context["recommended_broth_ids"] = []
                available_broths = broths

            selected_broth = None
            for b in available_broths:
                if b["dish"]["spicy"] == "中辣":
                    selected_broth = b
                    break

            if not selected_broth and available_broths:
                selected_broth = available_broths[0]

            if not selected_broth:
                continue

            broth_price = selected_broth["dish"]["price"]

            if skewers:
                min_skewer_price = min(s["dish"]["price"] for s in skewers)
                if budget < broth_price + min_skewer_price:
                    print(f"[串串] 预算{budget}元只够锅底({broth_price}元)，不够串串({min_skewer_price}元)，跳过")
                    continue

            remaining_budget = budget - broth_price
            if remaining_budget <= 0:
                print(f"[串串] 预算{budget}元只够锅底({broth_price}元)，没有剩余预算买串串，跳过")
                continue

            selected_skewers = []
            sorted_skewers = sorted(skewers, key=lambda x: x["dish"]["price"])

            for skewer in sorted_skewers:
                dish = skewer["dish"]
                if avoid and self._contains_avoid_ingredient(dish["name"], avoid):
                    continue
                if dish["price"] <= remaining_budget:
                    selected_skewers.append(skewer)
                    remaining_budget -= dish["price"]
                if len(selected_skewers) >= 8:
                    break

            if not selected_skewers:
                print(f"[串串] 预算{budget}元下，餐厅{restaurant['name']}没有找到合适的串串，跳过")
                continue

            self.conversation_context["recommended_restaurant_ids"].append(restaurant["id"])
            self.conversation_context["recommended_broth_ids"].append(selected_broth["dish"]["id"])

            return {
                "restaurant": restaurant,
                "broth": selected_broth,
                "skewers": selected_skewers,
                "total_price": broth_price + sum(s["dish"]["price"] for s in selected_skewers),
                "type": "chuanchuan"
            }

        return None

    def _format_hotpot_response(self, recommendation: dict, budget: float, spicy: str, user_input: str,
                                user_prefs: dict) -> str:
        """格式化火锅/串串推荐回复"""
        restaurant = recommendation["restaurant"]
        broth = recommendation["broth"]
        total_price = recommendation["total_price"]

        broth_price = f"{broth['dish']['price']:.2f}"
        total_price_str = f"{total_price:.2f}"

        content = f"根据您的偏好（{spicy}口味，预算{budget}元），为您推荐{restaurant['name']}：\n\n"
        content += f"锅底：{broth['dish']['name']}\n"
        content += f"   价格：{broth_price}元 | 辣度：{broth['dish']['spicy']}\n\n"

        if recommendation["type"] == "hotpot":
            sides = recommendation["sides"]
            if sides:
                content += "推荐配菜：\n"
                for i, side in enumerate(sides[:6], 1):
                    side_price = f"{side['dish']['price']:.2f}"
                    content += f"   {i}. {side['dish']['name']} - {side_price}元\n"
                content += "\n"
        else:
            skewers = recommendation["skewers"]
            if skewers:
                content += "推荐串串：\n"
                cheap_skewers = [s for s in skewers if s["dish"]["price"] < 5]
                normal_skewers = [s for s in skewers if 5 <= s["dish"]["price"] < 10]
                if cheap_skewers:
                    content += "   实惠串串："
                    for s in cheap_skewers[:4]:
                        content += f"{s['dish']['name']}、"
                    content = content.rstrip('、') + "\n"
                if normal_skewers:
                    content += "   特色串串："
                    for s in normal_skewers[:4]:
                        content += f"{s['dish']['name']}、"
                    content = content.rstrip('、') + "\n"
                content += "\n"

        content += f"合计：{total_price_str}元\n\n"
        content += "-" * 30 + "\n"
        content += "健康提示：祝您用餐愉快，注意饮食均衡。\n"
        content += "-" * 30 + "\n\n"
        content += "回复'下单'确认订单，或说'换一批'重新推荐。"

        return content

    def _format_recommendation_response(self, recommendations: list, budget: int, spicy: str,
                                        user_input: str, user_prefs: dict) -> str:
        """格式化普通菜品推荐回复"""
        if not recommendations:
            return f"抱歉，在{budget}元预算内没有找到符合您需求的菜品。\n\n建议提高预算或放宽口味限制。"

        content = f"根据您的偏好（{spicy}口味，预算{budget}元），为您推荐：\n\n"
        for i, rec in enumerate(recommendations[:3], 1):
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            price = f"{dish['price']:.2f}"

            # 添加标注
            tags = []
            if rec.get('is_favorite', False):
                tags.append("收藏")
            if rec.get('is_frequent', False):
                tags.append("你的常点")

            tag_text = " " + " ".join(tags) if tags else ""

            content += f"{i}. {dish['name']}{tag_text} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {price}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   {dish.get('description', '人气推荐')}\n\n"

        content += "-" * 30 + "\n"
        content += "健康提示：祝您用餐愉快，注意饮食均衡。\n"
        content += "-" * 30 + "\n\n"
        content += "回复数字选择菜品，或说'换一批'重新推荐，说'下单'确认订单。"

        return content

        return content

    def _handle_recommend(self, user_input: str, user_prefs: dict) -> dict:
        """处理推荐请求（全新推荐）"""
        # 解析预算信息
        budget_info = self._parse_budget_from_input(user_input, user_prefs.get('default_budget', 30))
        budget = budget_info["budget"]
        budget_min = budget_info["budget_min"]
        budget_max = budget_info["budget_max"]
        budget_type = budget_info["budget_type"]
        cuisine = None
        spicy = user_prefs.get('spicy_level', '微辣')
        avoid = []
        specific_dish = None
        specific_restaurant = None

        all_dish_names = self._get_all_dish_names()
        for dish in all_dish_names:
            if dish in user_input:
                specific_dish = dish
                print(f"[菜品匹配] 匹配到具体菜品: {dish}")
                break

        all_restaurant_names = self._get_all_restaurant_names()
        for restaurant in all_restaurant_names:
            if restaurant in user_input:
                specific_restaurant = restaurant
                print(f"[餐厅匹配] 匹配到具体餐厅: {restaurant}")
                for r in RESTAURANTS:
                    if r["name"] == restaurant:
                        cuisine = r["cuisine"]
                        print(f"[餐厅匹配] 菜系确定为: {cuisine}")
                        break
                break

        if specific_dish is not None:
            print(f"[菜品匹配] 已匹配到菜品，跳过菜系关键词匹配")
        else:
            # 解析菜系
            cuisine = None
            spicy = user_prefs.get('spicy_level', '微辣')
            avoid = []
            specific_dish = None

            cuisine_keywords = {
                "川菜": ["川菜", "川味", "麻辣"],
                "粤菜": ["粤菜", "广式", "广东菜"],
                "湘菜": ["湘菜", "湖南菜"],
                "东北菜": ["东北菜", "东北"],
                "日料": ["日料", "日本料理", "寿司", "刺身", "拉面"],
                "韩餐": ["韩餐", "韩国料理", "韩式", "炸鸡", "年糕"],
                "西餐": ["西餐", "西式", "牛排", "意面", "披萨"],
                "火锅": ["火锅", "涮锅"],
                "小吃": ["小吃", "麻辣烫", "炸串"],
                "轻食": ["轻食", "沙拉", "健康餐"],
                "西北菜": ["西北菜", "西北"],
                "东南亚": ["东南亚", "泰式", "越南"],
                "港式": ["港式", "茶餐厅"],
                "清真": ["清真"],
                "新疆菜": ["新疆菜", "新疆"],
                "台湾菜": ["台湾菜", "台湾"],
                "京菜": ["京菜", "北京菜"],
                "素食": ["素食", "素菜"],
                "海鲜": ["海鲜"],
                "鲁菜": ["鲁菜", "山东菜"],
                "甜品": ["甜品", "甜点", "蛋糕", "冰淇淋", "布丁", "双皮奶", "杨枝甘露", "慕斯", "提拉米苏"],
                "烧烤": ["烧烤", "烤串"],
                "串串": ["串串", "串串香"],
                "饮品": ["奶茶", "咖啡", "果汁", "茶饮", "柠檬茶", "果茶", "拿铁", "卡布奇诺", "美式", "可乐", "雪碧",
                         "饮品"],
            }

            for cuisine_name, keywords in cuisine_keywords.items():
                for kw in keywords:
                    if kw in user_input:
                        cuisine = cuisine_name
                        print(f"[菜系解析] 关键词 '{kw}' 匹配到菜系: {cuisine}")
                        break
                if cuisine is not None:
                    break

            cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                        "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品",
                        "烧烤", "串串", "饮品"]
            for c in cuisines:
                if c in user_input:
                    cuisine = c
                    break
            pass

        if cuisine == "甜品" or cuisine == "饮品":
            spicy = "不辣"
            print(f"[推荐] 菜系为{cuisine}，辣度自动设为不辣")

        if "不辣" in user_input or "不吃辣" in user_input:
            spicy = "不辣"
        elif "特辣" in user_input:
            spicy = "特辣"
        elif "中辣" in user_input:
            spicy = "中辣"
        elif "微辣" in user_input:
            spicy = "微辣"

        avoid_pattern = r'不要([\u4e00-\u9fa5]{2,6})(?=[，,。！？\s]|$)'
        avoid_matches = re.findall(avoid_pattern, user_input)

        for avoid_item in avoid_matches:
            if avoid_item == "吃辣" or "辣" in avoid_item:
                continue
            if avoid_item not in avoid:
                avoid.append(avoid_item)
                print(f"[忌口解析] 添加忌口: {avoid_item}")

        if not avoid:
            if "不要" in user_input:
                parts = user_input.split("不要")
                if len(parts) > 1:
                    after_buyao = parts[1]
                    chinese_match = re.search(r'^([\u4e00-\u9fa5]{2,6})', after_buyao)
                    if chinese_match:
                        candidate = chinese_match.group(1)
                        if candidate not in avoid and candidate != "吃辣":
                            avoid.append(candidate)
                            print(f"[忌口解析] 备用方案添加: {candidate}")

        print(f"[全新推荐] 预算: {budget} ({budget_type}: {budget_min}-{budget_max}), 菜系: {cuisine}, 辣度: {spicy}, 忌口: {avoid}")

        exclude_ids = self.conversation_context.get("recommended_ids", [])

        if specific_restaurant:
            print(f"[推荐] 用户指定餐厅: {specific_restaurant}")
            return self._handle_specific_restaurant_recommend(
                specific_restaurant, budget, spicy, avoid, user_input, user_prefs,
                budget_min, budget_max, budget_type
            )

        if specific_dish:
            print(f"[推荐] 用户指定菜品: {specific_dish}")
            return self._handle_specific_dish_recommend(
                specific_dish, budget, spicy, avoid, user_input, user_prefs,
                budget_min, budget_max, budget_type
            )

        if cuisine is not None:
            print(f"[推荐] 用户指定菜系: {cuisine}")
            if cuisine == "火锅":
                return self._handle_hotpot_recommend(budget, spicy, avoid, user_input, user_prefs,
                                                     budget_min, budget_max, budget_type)
            elif cuisine == "串串":
                return self._handle_chuanchuan_recommend(budget, spicy, avoid, user_input, user_prefs,
                                                         budget_min, budget_max, budget_type)
            else:
                return self._handle_normal_recommend(budget, spicy, avoid, user_input, user_prefs, cuisine,
                                                     budget_min, budget_max, budget_type)

        print("[推荐] 用户未指定菜系，优先普通菜系推荐")

        normal_recommendations = self._get_recommendations_from_mock_exclude_hotpot(
            budget, None, None, spicy, avoid, exclude_ids,
            budget_min, budget_max, budget_type
        )

        if normal_recommendations:
            print("[推荐] 找到普通菜系推荐，使用普通格式")
            return self._handle_normal_recommend_with_data(budget, spicy, avoid, user_input, user_prefs,
                                                           normal_recommendations, cuisine,
                                                           budget_min, budget_max, budget_type)

        if budget >= 60:
            print(f"[推荐] 预算{budget}元充足，尝试火锅推荐")
            hotpot_rec = self._get_hotpot_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)
            if hotpot_rec:
                return self._handle_hotpot_recommend(budget, spicy, avoid, user_input, user_prefs,
                                                     budget_min, budget_max, budget_type)

            print("[推荐] 火锅推荐失败，尝试串串推荐")
            chuanchuan_rec = self._get_chuanchuan_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)
            if chuanchuan_rec:
                return self._handle_chuanchuan_recommend(budget, spicy, avoid, user_input, user_prefs,
                                                         budget_min, budget_max, budget_type)

        print("[推荐] 放宽条件，重新尝试普通推荐")
        normal_recommendations = self._get_recommendations_from_mock(
            budget, None, None, spicy, avoid, exclude_ids,
            budget_min, budget_max, None, budget_type
        )

        if normal_recommendations:
            return self._handle_normal_recommend_with_data(budget, spicy, avoid, user_input, user_prefs,
                                                           normal_recommendations, cuisine,
                                                           budget_min, budget_max, budget_type)

        return {
            "success": True,
            "content": f"没有找到符合条件的菜品。\n当前条件：{spicy}口味，预算{budget}元\n\n建议提高预算或放宽口味限制。",
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None
        }

    def _handle_specific_restaurant_recommend(self, restaurant_name: str, budget: float, spicy: str, avoid: list,
                                              user_input: str, user_prefs: dict,
                                              budget_min: float = None, budget_max: float = None,
                                              budget_type: str = "exact") -> dict:
        """处理用户指定具体餐厅的推荐"""

        from data.mock_restaurants import RESTAURANTS, DISHES_BY_RESTAURANT

        restaurant = None
        restaurant_id = None
        for r in RESTAURANTS:
            if r["name"] == restaurant_name:
                restaurant = r
                restaurant_id = r["id"]
                break

        if not restaurant:
            print(f"[指定餐厅] 未找到餐厅: {restaurant_name}，降级为普通推荐")
            return self._handle_recommend(user_input, user_prefs)

        print(f"[指定餐厅] 找到餐厅: {restaurant_name}, 菜系: {restaurant['cuisine']}")

        dishes = DISHES_BY_RESTAURANT.get(restaurant_id, [])

        recommendations = []
        for dish in dishes:
            price = dish["price"]
            dish_spicy = dish.get("spicy", "微辣")

            if budget_type == "within":
                if price > budget_max:
                    continue
            elif budget_type == "around":
                if price < budget_min or price > budget_max:
                    continue
            else:
                if price < budget_min or price > budget_max:
                    continue

            if spicy == "不辣" and dish_spicy != "不辣":
                continue
            elif spicy == "微辣" and dish_spicy not in ["不辣", "微辣", "中辣"]:
                continue
            elif spicy == "中辣" and dish_spicy not in ["微辣", "中辣", "特辣"]:
                continue
            elif spicy == "特辣" and dish_spicy not in ["中辣", "特辣", "麻辣"]:
                continue

            if avoid:
                if self._contains_avoid_ingredient(dish["name"], avoid):
                    continue

            recommendations.append({
                "dish": dish,
                "restaurant": restaurant,
            })

        recommendations.sort(key=lambda x: x["dish"]["price"])

        if not recommendations:
            cuisine_text = restaurant["cuisine"] if restaurant["cuisine"] else ""
            return {
                "success": True,
                "content": f"抱歉，在{budget}元预算内没有找到{restaurant_name}符合您要求的菜品。\n\n当前条件：{spicy}口味，预算{budget}元\n\n您可以尝试提高预算或修改口味偏好。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        return self._handle_normal_recommend_with_data(budget, spicy, avoid, user_input, user_prefs,
                                                       recommendations[:5], restaurant["cuisine"],
                                                       budget_min, budget_max, budget_type)

    def _handle_specific_dish_recommend(self, dish_name: str, budget: float, spicy: str, avoid: list,
                                        user_input: str, user_prefs: dict,
                                        budget_min: float = None, budget_max: float = None,
                                        budget_type: str = "exact") -> dict:
        """处理用户指定具体菜品的推荐"""

        all_items = self._get_all_dishes_with_restaurant()
        target_dish = None
        target_restaurant = None

        for item in all_items:
            if item["dish"]["name"] == dish_name:
                target_dish = item["dish"]
                target_restaurant = item["restaurant"]
                break

        if not target_dish:
            print(f"[指定菜品] 未找到菜品: {dish_name}，降级为普通推荐")
            return self._handle_recommend(user_input, user_prefs)

        print(f"[指定菜品] 找到菜品: {dish_name}, 价格: {target_dish['price']}, 餐厅: {target_restaurant['name']}")

        dish_price = target_dish["price"]

        if budget_type == "within":
            if dish_price > budget_max:
                return {
                    "success": True,
                    "content": f"您指定的{dish_name}价格为{dish_price}元，超出预算{budget}元。\n\n建议提高预算或选择其他菜品。",
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None
                }
        elif budget_type == "around":
            if dish_price < budget_min or dish_price > budget_max:
                return {
                    "success": True,
                    "content": f"您指定的{dish_name}价格为{dish_price}元，不在预算{budget}元范围内。\n\n建议提高预算或选择其他菜品。",
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None
                }
        else:
            if dish_price < budget_min or dish_price > budget_max:
                return {
                    "success": True,
                    "content": f"您指定的{dish_name}价格为{dish_price}元，不在预算{budget}元范围内。\n\n建议提高预算或选择其他菜品。",
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None
                }

        dish_spicy = target_dish.get("spicy", "微辣")
        if spicy == "不辣" and dish_spicy != "不辣":
            return {
                "success": True,
                "content": f"您指定的{dish_name}辣度为{dish_spicy}，与您的不辣偏好不符。\n\n您可以修改口味偏好或选择其他菜品。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        if avoid:
            if self._contains_avoid_ingredient(target_dish["name"], avoid):
                avoid_text = "、".join(avoid)
                return {
                    "success": True,
                    "content": f"您指定的{dish_name}包含忌口食材（{avoid_text}）。\n\n建议修改忌口设置或选择其他菜品。",
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None
                }

        recommendations = [{
            "dish": target_dish,
            "restaurant": target_restaurant,
        }]

        other_dishes = []
        for item in all_items:
            if item["restaurant"]["id"] == target_restaurant["id"] and item["dish"]["name"] != dish_name:
                price = item["dish"]["price"]
                if budget_type == "within":
                    if price <= budget_max:
                        other_dishes.append(item)
                elif budget_type == "around":
                    if budget_min <= price <= budget_max:
                        other_dishes.append(item)
                else:
                    if budget_min <= price <= budget_max:
                        other_dishes.append(item)

        other_dishes.sort(key=lambda x: x["dish"]["price"])
        recommendations.extend(other_dishes[:4])

        return self._handle_normal_recommend_with_data(budget, spicy, avoid, user_input, user_prefs,
                                                       recommendations[:5], target_restaurant["cuisine"],
                                                       budget_min, budget_max, budget_type)

    def _handle_normal_recommend_with_data(self, budget: float, spicy: str, avoid: list,
                                           user_input: str, user_prefs: dict,
                                           recommendations: list, cuisine: str = None,
                                           budget_min: float = None, budget_max: float = None,
                                           budget_type: str = "exact") -> dict:
        """处理普通推荐（已有推荐数据）"""

        if not user_session.is_guest and self.conversation_context.get('user_frequent_dishes') is None:
            try:
                from services.order_stats import order_stats
                user_analysis = order_stats.analyze_user_preferences()

                if user_analysis:
                    self.conversation_context['user_frequent_dishes'] = user_analysis.get('frequent_dishes', [])
                    self.conversation_context['user_frequent_restaurants'] = user_analysis.get('frequent_restaurants', [])
                    print(f"[常点分析] 订单数: {user_analysis.get('total_orders', 0)}")
                    print(f"[常点分析] 常点菜品: {user_analysis['frequent_dishes'][:3]}")
                    print(f"[常点分析] 常点餐厅: {user_analysis['frequent_restaurants'][:3]}")
                else:
                    self.conversation_context['user_frequent_dishes'] = []
                    self.conversation_context['user_frequent_restaurants'] = []
            except Exception as e:
                print(f"[常点分析] 失败: {e}")
                self.conversation_context['user_frequent_dishes'] = []
                self.conversation_context['user_frequent_restaurants'] = []

        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": None,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": None,
        }

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["current_recommendations"] = recommendations

        content = self._format_recommendation_response(recommendations, budget, spicy, user_input, user_prefs)

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_normal_recommend(self, budget: float, spicy: str, avoid: list,
                                 user_input: str, user_prefs: dict,
                                 cuisine: str = None,
                                 budget_min: float = None, budget_max: float = None,
                                 budget_type: str = "exact") -> dict:
        """处理普通推荐"""
        exclude_ids = self.conversation_context.get("recommended_ids", [])

        recommendations = self._get_recommendations_from_mock(
            budget, None, cuisine, spicy, avoid, exclude_ids,
            budget_min, budget_max, None, budget_type
        )

        return self._handle_normal_recommend_with_data(budget, spicy, avoid, user_input, user_prefs,
                                                       recommendations, cuisine,
                                                       budget_min, budget_max, budget_type)

    def _handle_recommend_new(self, user_input: str, user_prefs: dict) -> dict:
        """处理"尝试新的"推荐请求"""
        last_params = self.conversation_context.get("last_search_params")

        if not last_params:
            print("[尝试新的] 没有历史记录，降级为普通推荐")
            return self._handle_recommend(user_input, user_prefs)

        budget = last_params.get("budget", 30)
        budget_min = last_params.get("budget_min")
        budget_max = last_params.get("budget_max")
        budget_type = last_params.get("budget_type", "exact")
        cuisine = last_params.get("cuisine")
        spicy = last_params.get("spicy", "微辣")
        avoid = last_params.get("avoid", []).copy()

        print(
            f"[尝试新的] 使用参数: 预算={budget} ({budget_type}: {budget_min}-{budget_max}), 菜系={cuisine}, 辣度={spicy}, 忌口={avoid}")

        self.conversation_context['try_new_mode'] = True

        exclude_ids = self.conversation_context.get("recommended_ids", [])

        recommendations = self._get_recommendations_from_mock_exclude_hotpot(
            budget, None, cuisine, spicy, avoid, exclude_ids,
            budget_min, budget_max, budget_type
        )

        if not recommendations:
            print("[尝试新的] 没有找到新菜品")
            self.conversation_context['try_new_mode'] = False

            cuisine_text = cuisine if cuisine else "不限"
            return {
                "success": True,
                "content": f"抱歉，在{budget}元预算内没有找到更多{cuisine_text}新菜品了。\n\n当前条件：{cuisine_text}菜系，{spicy}口味\n\n您可以尝试提高预算或修改口味偏好。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": None,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": None,
        }

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context['try_new_mode'] = False

        content = self._format_recommendation_response(recommendations, budget, spicy, user_input, user_prefs)

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_hotpot_recommend(self, budget: float, spicy: str, avoid: list, user_input: str,
                                 user_prefs: dict,
                                 budget_min: float = None, budget_max: float = None,
                                 budget_type: str = "exact") -> dict:
        """处理火锅推荐"""
        hotpot_rec = self._get_hotpot_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)

        if not hotpot_rec:
            return {
                "success": True,
                "content": f"抱歉，在{budget}元预算内没有找到合适的火锅组合。\n\n火锅需要锅底+配菜，建议预算至少30-40元。\n\n您也可以尝试其他菜系，或说'提高预算'。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        content = self._format_hotpot_response(hotpot_rec, budget, spicy, user_input, user_prefs)
        recommendations = [hotpot_rec["broth"]] + hotpot_rec.get("sides", [])

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_cuisine"] = "火锅"
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": None,
            "cuisine": "火锅",
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": None,
        }

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
        }

    def _handle_chuanchuan_recommend(self, budget: float, spicy: str, avoid: list, user_input: str,
                                     user_prefs: dict,
                                     budget_min: float = None, budget_max: float = None,
                                     budget_type: str = "exact") -> dict:
        """处理串串推荐"""
        chuanchuan_rec = self._get_chuanchuan_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)

        if not chuanchuan_rec:
            return {
                "success": True,
                "content": f"抱歉，在{budget}元预算内没有找到合适的串串组合。\n\n串串需要锅底+串串，建议预算至少30-40元。\n\n您也可以尝试其他菜系，或说'提高预算'。",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        content = self._format_hotpot_response(chuanchuan_rec, budget, spicy, user_input, user_prefs)
        recommendations = [chuanchuan_rec["broth"]] + chuanchuan_rec.get("skewers", [])

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_cuisine"] = "串串"
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": None,
            "cuisine": "串串",
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": None,
        }

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
        }

    def _handle_modify(self, user_input: str, user_prefs: dict) -> dict:
        """处理修改推荐请求"""
        user_lower = user_input.lower()

        last_params = self.conversation_context.get("last_search_params")
        if last_params:
            budget = last_params.get("budget", 30)
            budget_min = last_params.get("budget_min")
            budget_max = last_params.get("budget_max")
            budget_type = last_params.get("budget_type", "exact")
            cuisine = last_params.get("cuisine")
            spicy = last_params.get("spicy", "微辣")
            avoid = last_params.get("avoid", []).copy()
            print(f"[修改推荐] 从last_search_params读取: 预算={budget} ({budget_type}), 菜系={cuisine}, 辣度={spicy}, 忌口={avoid}")
        else:
            budget = self.conversation_context.get("last_budget", 30)
            budget_min = None
            budget_max = None
            budget_type = "exact"
            cuisine = self.conversation_context.get("last_cuisine")
            spicy = self.conversation_context.get("last_spicy", "微辣")
            avoid = self.conversation_context.get("last_avoid", []).copy()
            print(f"[修改推荐] 从last_budget读取: 预算={budget}, 菜系={cuisine}, 辣度={spicy}, 忌口={avoid}")

        change_desc = []
        new_excluded_dishes = []

        if re.search(r'换一批|重新推荐|再来一批', user_lower):
            if cuisine == "火锅":
                return self._handle_hotpot_change(user_prefs)
            elif cuisine == "串串":
                return self._handle_chuanchuan_change(user_prefs)
            else:
                return self._handle_re_recommend(user_prefs)

        if re.search(r'提高预算|更贵|贵一点', user_lower):
            budget = min(100, budget + 10)
            budget_min = int(budget * 0.9)
            budget_max = int(budget * 1.1)
            budget_type = "exact"
            change_desc.append(f"预算提高为{budget}元")
        elif re.search(r'降低预算|更便宜|便宜一点', user_lower):
            budget = max(15, budget - 10)
            budget_min = int(budget * 0.9)
            budget_max = int(budget * 1.1)
            budget_type = "exact"
            change_desc.append(f"预算降低为{budget}元")

        budget_match = re.search(r'(\d+)', user_input)
        if budget_match and not re.search(r'不要', user_lower):
            budget = int(budget_match.group(1))
            budget_min = int(budget * 0.9)
            budget_max = int(budget * 1.1)
            budget_type = "exact"
            change_desc.append(f"预算改为{budget}元")

        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品",
                    "烧烤", "串串", "饮品"]
        for c in cuisines:
            if c in user_input:
                cuisine = c
                change_desc.append(f"菜系改为{cuisine}")
                if cuisine in ["甜品", "饮品"]:
                    spicy = "不辣"
                    change_desc.append(f"辣度改为不辣")
                break

        for s in ["特辣", "中辣", "微辣", "不辣"]:
            if s in user_input:
                spicy = s
                change_desc.append(f"辣度改为{spicy}")
                break

        exclude_match = re.search(r'不要([\u4e00-\u9fa5]{2,6})', user_input)
        if exclude_match:
            exclude_item = exclude_match.group(1)
            if exclude_item not in avoid:
                avoid.append(exclude_item)
                change_desc.append(f"排除{exclude_item}")

        all_dish_names = self._get_all_dish_names()
        for dish in all_dish_names:
            if f"不要{dish}" in user_input or f"不要吃{dish}" in user_input:
                if dish not in new_excluded_dishes:
                    new_excluded_dishes.append(dish)
                    change_desc.append(f"排除{dish}")
                break

        if not change_desc:
            return {
                "success": True,
                "content": "请告诉我具体要修改什么，例如：提高预算、改为川菜、不要香菜、不要糖醋鲤鱼等",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        print(f"[修改推荐] 修改项: {change_desc}")
        print(f"[修改推荐] 当前搜索参数 - 预算: {budget} ({budget_type}: {budget_min}-{budget_max}), 菜系: {cuisine}, 辣度: {spicy}, 忌口: {avoid}")

        for dish_name in new_excluded_dishes:
            all_items = self._get_all_dishes_with_restaurant()
            for item in all_items:
                if item["dish"]["name"] == dish_name:
                    if item["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                        self.conversation_context["recommended_ids"].append(item["dish"]["id"])
                        print(f"[排除菜品] 将 {dish_name} 加入排除列表")
                    break

        exclude_ids = self.conversation_context.get("recommended_ids", [])
        print(f"[修改推荐] 排除菜品ID列表: {exclude_ids}")

        recommendations = self._get_recommendations_from_mock_exclude_hotpot(
            budget, None, cuisine, spicy, avoid, exclude_ids,
            budget_min, budget_max, budget_type
        )

        print(f"[修改推荐] 找到 {len(recommendations)} 个推荐菜品")
        if recommendations:
            for rec in recommendations[:3]:
                print(f"  - {rec['dish']['name']} ({rec['restaurant']['name']}) - {rec['dish']['price']}元")

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": None,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": None,
        }

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        if not recommendations:
            return {
                "success": True,
                "content": f"抱歉，调整后没有找到符合您需求的菜品。\n\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味，预算{budget}元，忌口{avoid if avoid else '无'}",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        change_text = "，".join(change_desc)
        content = f"{change_text}，为您重新推荐：\n\n"
        for i, rec in enumerate(recommendations[:3], 1):
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            price = f"{dish['price']:.2f}"
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {price}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   辣度：{dish.get('spicy', '微辣')}\n\n"

        content += "回复数字选择，或继续调整。"

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_hotpot_change(self, user_prefs: dict) -> dict:
        """处理火锅换一批"""
        params = self.conversation_context.get("last_search_params")
        if not params:
            return self._handle_recommend("推荐火锅", user_prefs)

        budget = params["budget"]
        budget_min = params.get("budget_min")
        budget_max = params.get("budget_max")
        budget_type = params.get("budget_type", "exact")
        spicy = params["spicy"]
        avoid = params["avoid"]

        self.conversation_context["recommended_broth_ids"] = []

        hotpot_rec = self._get_hotpot_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)

        if not hotpot_rec:
            return {
                "success": True,
                "content": f"抱歉，没有更多火锅餐厅了。\n\n当前预算{budget}元，{spicy}口味",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        content = self._format_hotpot_response(hotpot_rec, budget, spicy, "换一家", user_prefs)
        recommendations = [hotpot_rec["broth"]] + hotpot_rec.get("sides", [])

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context["last_search_params"]["cuisine"] = "火锅"

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
        }

    def _handle_chuanchuan_change(self, user_prefs: dict) -> dict:
        """处理串串换一批"""
        params = self.conversation_context.get("last_search_params")
        if not params:
            return self._handle_recommend("推荐串串", user_prefs)

        budget = params["budget"]
        budget_min = params.get("budget_min")
        budget_max = params.get("budget_max")
        budget_type = params.get("budget_type", "exact")
        spicy = params["spicy"]
        avoid = params["avoid"]

        self.conversation_context["recommended_broth_ids"] = []

        chuanchuan_rec = self._get_chuanchuan_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)

        if not chuanchuan_rec:
            return {
                "success": True,
                "content": f"抱歉，没有更多串串餐厅了。\n\n当前预算{budget}元，{spicy}口味",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        content = self._format_hotpot_response(chuanchuan_rec, budget, spicy, "换一家", user_prefs)
        recommendations = [chuanchuan_rec["broth"]] + chuanchuan_rec.get("skewers", [])

        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["current_recommendations"] = recommendations
        self.conversation_context["last_search_params"]["cuisine"] = "串串"

        return {
            "success": True,
            "content": content,
            "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
            "workflow": None,
        }

    def _handle_re_recommend(self, user_prefs: dict) -> dict:
        """处理换一批 - 排除上次已推荐的菜品"""
        params = self.conversation_context.get("last_search_params")
        if not params:
            return self._handle_recommend("推荐", user_prefs)

        budget = params.get("budget", 30)
        budget_min = params.get("budget_min")
        budget_max = params.get("budget_max")
        budget_type = params.get("budget_type", "exact")

        if budget_min is None or budget_max is None:
            if budget_type == "around":
                budget_min = budget - 5
                budget_max = budget + 5
            elif budget_type == "within":
                budget_min = 0
                budget_max = budget
            else:
                budget_min = int(budget * 0.9)
                budget_max = int(budget * 1.1)

        keyword = params.get("keyword")
        cuisine = params.get("cuisine")
        spicy = params.get("spicy", "微辣")
        avoid = params.get("avoid", [])
        exclude_restaurant = params.get("exclude_restaurant")

        exclude_ids = self.conversation_context.get("recommended_ids", [])

        print(f"[换一批] 使用相同条件: 预算={budget} ({budget_type}: {budget_min}-{budget_max}), 菜系={cuisine}, 辣度={spicy}")
        print(f"[换一批] 已推荐 {len(exclude_ids)} 个菜品")

        recommendations = self._get_recommendations_from_mock_exclude_hotpot(
            budget, keyword, cuisine, spicy, avoid, exclude_ids,
            budget_min, budget_max, budget_type
        )

        if not recommendations:
            print("[换一批] 没有更多菜品，重新开始")
            self.conversation_context["recommended_ids"] = []
            recommendations = self._get_recommendations_from_mock_exclude_hotpot(
                budget, keyword, cuisine, spicy, avoid, [],
                budget_min, budget_max, budget_type
            )

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
            price = f"{dish['price']:.2f}"
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {price}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   辣度：{dish.get('spicy', '微辣')}\n\n"

        content += "回复数字选择，或说'换一批'继续。"

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
        content += f"价格：{dish['price']:.2f}元\n"
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
        """主对话接口 - AI 意图识别优先"""
        user_input = user_input.strip()
        user_lower = user_input.lower()

        print(f"[对话] 用户输入: {user_input}")

        # ========== 1. 纯数字选择 ==========
        if user_input.isdigit():
            return self.select_dish(int(user_input))

        # ========== 2. 尝试新的快速检测 ==========
        if re.search(r'想尝试新的|尝试新|换换口味|新口味', user_lower):
            print(f"[快速检测] 检测到尝试新的 -> recommend_new")
            return self._handle_recommend_new(user_input, user_prefs)

        # ========== 3. 工作流触发词 ==========
        for pattern, workflow in self.workflow_triggers.items():
            if re.search(pattern, user_lower):
                print(f"[工作流] 触发: {workflow}")
                if workflow == 'submit_order':
                    order = self.conversation_context.get("current_order")
                    if order:
                        return {
                            "success": True,
                            "content": "",
                            "workflow": workflow,
                            "params": {"user_input": user_input},
                            "model": "workflow"
                        }
                    else:
                        return self._handle_recommend(user_input, user_prefs)
                else:
                    return {
                        "success": True,
                        "content": "",
                        "workflow": workflow,
                        "params": {"user_input": user_input},
                        "model": "workflow"
                    }

        # ========== 4. AI 意图识别 ==========
        context_info = {
            "cuisine": self.conversation_context.get("last_cuisine"),
            "spicy": self.conversation_context.get("last_spicy"),
            "budget": self.conversation_context.get("last_budget"),
            "avoid": self.conversation_context.get("last_avoid", []),
        }

        ai_intent = self._classify_intent_with_ai(user_input, user_prefs, context_info)

        if ai_intent:
            action = ai_intent.get("action", "recommend")
            action = action.lower().strip().replace(" ", "_")
            if action in ["re_recommend", "rerecommend"]:
                action = "re_recommend"
            print(f"[AI决策] action={action}")

            if action == "recommend_new":
                return self._handle_recommend_new(user_input, user_prefs)
            elif action == "re_recommend":
                return self._handle_re_recommend(user_prefs)
            elif action == "modify":
                return self._handle_modify(user_input, user_prefs)
            elif action == "order":
                order = self.conversation_context.get("current_order")
                if order:
                    return {
                        "success": True,
                        "content": "",
                        "workflow": "submit_order",
                        "params": {"user_input": user_input},
                        "model": "workflow"
                    }
                else:
                    return self._handle_recommend(user_input, user_prefs)
            elif action == "query":
                return {
                    "success": True,
                    "content": "",
                    "workflow": "query_order",
                    "params": {"user_input": user_input},
                    "model": "workflow"
                }
            elif action == "cancel":
                self.conversation_context["current_order"] = None
                return {
                    "success": True,
                    "content": "已取消当前操作。",
                    "model": "ai",
                    "workflow": None
                }
            elif action == "recommend":
                return self._handle_recommend(user_input, user_prefs)

            return self._handle_recommend(user_input, user_prefs)

        return self._handle_recommend(user_input, user_prefs)


# 单例
_router_service = None


def get_qwen_service():
    global _router_service
    if _router_service is None:
        _router_service = QwenRouterService()
    return _router_service
