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
        }

        user_input_lower = user_input.lower()

        # 0. 检测是否是饮品需求（奶茶、咖啡、果汁等）
        drink_keywords = ["奶茶", "咖啡", "果汁", "柠檬茶", "果茶", "拿铁", "卡布奇诺", "美式", "波霸", "珍珠奶茶",
                          "抹茶拿铁"]
        for kw in drink_keywords:
            if kw in user_input:
                result["is_drink"] = True
                result["cuisine"] = "饮品"  # 自动设置菜系为饮品
                print(f"[饮品检测] 检测到饮品需求: {kw}，自动设置辣度为不辣")
                break

            # 0.5 检测特定菜品（麻辣烫、火锅等）→ 自动设置菜系
            dish_to_cuisine = {
                "麻辣烫": "小吃",
                "酸辣粉": "小吃",
                "凉皮": "小吃",
                "肉夹馍": "小吃",
                "煎饼果子": "小吃",
                "炸鸡": "韩餐",
                "披萨": "西餐",
                "汉堡": "西餐",
                "寿司": "日料",
                "拉面": "日料",
                "烤肉": "韩餐",
                "火锅": "火锅",
                "串串": "串串",
            }
            for dish, cuisine in dish_to_cuisine.items():
                if dish in user_input:
                    result["cuisine"] = cuisine
                    result["dish_name"] = dish
                    print(f"[菜品匹配] 检测到 {dish}，自动设置菜系为 {cuisine}")
                    break

        # 1. 范围预算：20-30、20到30、20-30元
        budget_range_match = re.search(r'(\d+)[-到](\d+)(?:元|块|块钱)?', user_input)
        if budget_range_match:
            result["budget_min"] = int(budget_range_match.group(1))
            result["budget_max"] = int(budget_range_match.group(2))
            result["budget"] = (result["budget_min"] + result["budget_max"]) // 2
            result["budget_type"] = "range"
            print(f"[预算解析] 范围预算: {result['budget_min']}-{result['budget_max']}元")

        # 2. 以内/以下预算：100以内、100内、100以下、100元以内
        within_match = re.search(r'(\d+)(?:元|块|块钱)?(?:以内|以下|内)', user_input)
        if within_match:
            result["budget_max"] = int(within_match.group(1))
            result["budget_min"] = 0
            result["budget"] = result["budget_max"]
            result["budget_type"] = "within"
            print(f"[预算解析] 以内预算: ≤{result['budget_max']}元")

        # 3. 左右/大约预算：30左右、30元左右、大概30
        around_match = re.search(r'(\d+)(?:元|块|块钱)?(?:左右|上下|大约|大概)', user_input)
        if around_match:
            base = int(around_match.group(1))
            result["budget_min"] = int(base * 0.8)
            result["budget_max"] = int(base * 1.2)
            result["budget"] = base
            result["budget_type"] = "around"
            print(f"[预算解析] 左右预算: {result['budget_min']}-{result['budget_max']}元")

        # 4. 精确预算：30、30元、30块
        if result["budget"] is None:
            budget_match = re.search(r'(\d+)(?:元|块|块钱)?', user_input)
            if budget_match:
                # 确保不是范围或以内的一部分
                num = int(budget_match.group(1))
                # 如果已经匹配到范围或以内，跳过
                if result["budget_min"] is None and result["budget_max"] is None:
                    result["budget"] = num
                    result["budget_min"] = num
                    result["budget_max"] = num
                    result["budget_type"] = "exact"
                    print(f"[预算解析] 精确预算: {result['budget']}元")

            # 5. 提取辣度（饮品默认不辣）
            if result["is_drink"]:
                result["spicy"] = "不辣"
                print(f"[辣度解析] 饮品需求，辣度自动设为不辣")
            elif re.search(r'不吃辣|不要辣|我不吃辣|忌口辣|不吃辣椒|不能吃辣', user_input_lower):
                result["spicy"] = "不辣"
                print(f"[辣度解析] 用户不吃辣 → 设置为不辣")
            elif "特辣" in user_input:
                result["spicy"] = "特辣"
            elif "中辣" in user_input:
                result["spicy"] = "中辣"
            elif "微辣" in user_input:
                result["spicy"] = "微辣"

        # 6. 提取菜系
        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品",
                    "烧烤", "串串", "饮品"]
        for c in cuisines:
            if c in user_input:
                result["cuisine"] = c
                break

        # 7. 提取排除的餐厅
        exclude_restaurant_match = re.search(r'不要[去]?([\u4e00-\u9fa5]{2,10})(?:餐厅|店)', user_input)
        if exclude_restaurant_match:
            result["exclude_restaurant"] = exclude_restaurant_match.group(1)

        # 8. 提取忌口
        avoid_patterns = [
            r'不要([\u4e00-\u9fa5]{1,4})',
            r'忌口([\u4e00-\u9fa5]{1,4})',
            r'不吃([\u4e00-\u9fa5]{1,4})',
            r'避开([\u4e00-\u9fa5]{1,4})',
        ]

        for pattern in avoid_patterns:
            avoid_match = re.search(pattern, user_input)
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
                    result["avoid"].append(avoid_item)
                    print(f"[解析] 提取忌口: {avoid_item}")
                break

        # 9. 提取指定餐厅名
        all_restaurants = self._get_all_restaurant_names()
        for r in all_restaurants:
            if r in user_input:
                result["restaurant"] = r
                break

        # 提取指定菜品名（优先从 dish_to_cuisine 匹配）
        if not result["dish_name"]:
            all_dishes = self._get_all_dish_names()
            all_dishes.sort(key=len, reverse=True)
            for dish in all_dishes:
                if dish in user_input:
                    result["dish_name"] = dish
                    print(f"[菜品匹配] 检测到菜品: {dish}")
                    break
            if not result["dish_name"]:
                potential_names = re.findall(r'([\u4e00-\u9fa5]{2,4})', user_input)
                for pn in potential_names:
                    for dish in all_dishes:
                        if pn in dish and len(pn) >= 2:
                            result["dish_name"] = dish
                            print(f"[菜品匹配] 模糊匹配到菜品: {dish} (关键词: {pn})")
                            break
                    if result["dish_name"]:
                        break

        # 11. 提取关键词
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

        return result

    def _quick_contains_avoid(self, dish_name: str, avoid_list: list) -> bool:
        """快速关键词匹配（降级方案）"""
        avoid_keywords = {
            "香菜": ["香菜", "芫荽"],
            "蒜": ["蒜", "大蒜", "蒜蓉", "蒜泥"],
            "花生": ["花生", "花生米", "花生碎"],
            "乳制品": ["奶", "乳", "芝士", "奶酪", "黄油", "奶油", "酸奶", "双皮奶", "奶茶", "奶盖"],
        }

        for a in avoid_list:
            if a in avoid_keywords:
                for kw in avoid_keywords[a]:
                    if kw in dish_name:
                        return True
            else:
                if a in dish_name:
                    return True
        return False

    def _contains_avoid_ingredient(self, dish_name: str, avoid_list: list) -> bool:
        """判断菜品是否包含忌口食材（精确匹配）"""
        if not avoid_list:
            return False

        # 精确匹配映射表
        avoid_mapping = {
            "酸菜": ["酸菜鱼", "酸菜饺子", "酸菜炖排骨", "酸菜粉", "酸菜炒肉"],
            "豆腐": ["豆腐", "麻婆豆腐", "家常豆腐", "豆腐汤", "砂锅豆腐", "冻豆腐", "油豆腐"],
            "花生": ["花生", "花生米", "花生碎", "宫保鸡丁", "老醋花生"],
            "香菜": ["香菜", "芫荽", "香菜牛肉", "香菜拌木耳"],
            "蒜": ["蒜", "大蒜", "蒜蓉", "蒜泥", "蒜香", "糖蒜"],
            "奶": ["奶", "牛奶", "奶茶", "奶黄包", "奶酪", "芝士", "奶油", "双皮奶"],
            "猪肉": ["猪肉", "五花肉", "回锅肉", "红烧肉", "排骨", "叉烧", "卤肉"],
            "牛肉": ["牛肉", "肥牛", "牛腩", "牛排", "牛肉丸"],
            "鸡肉": ["鸡肉", "鸡丁", "鸡块", "鸡腿", "鸡翅", "宫保鸡丁", "辣子鸡"],
            "鱼肉": ["鱼", "鱼片", "酸菜鱼", "水煮鱼", "烤鱼", "鱼香"],
            "虾": ["虾", "虾仁", "虾滑", "虾饺", "小龙虾"],
        }

        for a in avoid_list:
            if a in avoid_mapping:
                for kw in avoid_mapping[a]:
                    if kw in dish_name:
                        print(f"[忌口过滤] {dish_name} 包含 {kw}（忌口：{a}）")
                        return True
            else:
                if a in dish_name and len(a) >= 2:
                    print(f"[忌口过滤] {dish_name} 名称包含 {a}")
                    return True

        return False

    def _filter_by_prefs_with_price_range(self, recommendations: list,
                                          price_min: float, price_max: float,
                                          budget: float,
                                          keyword: str = None, cuisine: str = None,
                                          spicy: str = None, avoid: list = None,
                                          exclude_ids: list = None) -> list:
        """根据偏好和价格范围过滤推荐列表"""
        filtered = []
        exclude_ids = exclude_ids or []
        avoid = avoid or []

        print(f"[DEBUG_FILTER] 价格范围: {price_min:.0f}-{price_max:.0f}元")
        print(f"[DEBUG_FILTER] 菜系: {cuisine}, 用户辣度要求: {spicy}")

        def match_spicy(dish_spicy: str, user_spicy: str) -> bool:
            if not user_spicy or user_spicy == "不限":
                return True
            # 直接比较
            return dish_spicy == user_spicy

        # 统计符合条件的菜品
        price_match_count = 0
        cuisine_match_count = 0
        spicy_match_count = 0

        for rec in recommendations:
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            dish_name = dish["name"]
            price = dish["price"]
            dish_spicy = dish.get("spicy", "未知")

            # 价格范围过滤
            if price < price_min or price > price_max:
                continue
            price_match_count += 1

            # 菜系过滤
            if cuisine and cuisine not in restaurant["cuisine"]:
                continue
            cuisine_match_count += 1

            # 打印前10个符合条件的菜品的辣度
            if cuisine_match_count <= 10:
                print(f"[DEBUG] 菜品: {dish_name}, 价格: {price}, 辣度: {dish_spicy}")

            # 辣度过滤
            if spicy:
                if not match_spicy(dish_spicy, spicy):
                    continue
            spicy_match_count += 1

            # 忌口过滤
            if avoid:
                if self._contains_avoid_ingredient(dish_name, avoid):
                    continue

            # 排除已推荐
            if dish["id"] in exclude_ids:
                continue

            filtered.append(rec)

        print(
            f"[DEBUG_FILTER] 统计: 价格匹配={price_match_count}, 菜系匹配={cuisine_match_count}, 辣度匹配={spicy_match_count}, 输出={len(filtered)}")
        filtered.sort(key=lambda x: (-x["restaurant"]["rating"], x["dish"]["price"]))
        return filtered

    def _get_recommendations_from_mock(self, budget: float, keyword: str = None,
                                       cuisine: str = None, spicy: str = None,
                                       avoid: list = None, exclude_ids: list = None,
                                       budget_min: float = None, budget_max: float = None,
                                       exclude_restaurant: str = None,
                                       budget_type: str = "exact") -> list:
        """从 mock 数据集获取推荐（根据预算类型过滤）"""
        all_items = self._get_all_dishes_with_restaurant()

        print(f"[DEBUG] budget_type: {budget_type}")
        print(f"[DEBUG] budget_min: {budget_min}, budget_max: {budget_max}, budget: {budget}")

        # 根据预算类型设置价格范围
        if budget_type == "range" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
            effective_budget = (budget_min + budget_max) // 2
            print(f"[预算过滤] 范围: {price_min}-{price_max}元")
        elif budget_type == "within" and budget_max is not None:
            price_min = 0
            price_max = budget_max
            effective_budget = budget_max
            print(f"[预算过滤] 以内: ≤{price_max}元")
        elif budget_type == "around" and budget_min is not None and budget_max is not None:
            price_min = budget_min
            price_max = budget_max
            effective_budget = (budget_min + budget_max) // 2
            print(f"[预算过滤] 左右: {price_min}-{price_max}元")
        else:
            # 精确预算：允许上下浮动10%
            price_min = budget * 0.9
            price_max = budget * 1.1
            effective_budget = budget
            print(f"[预算过滤] 精确: {price_min:.0f}-{price_max:.0f}元")

        # 先统计符合条件的川菜数量
        matching_items = []
        for rec in all_items:
            if cuisine and cuisine not in rec["restaurant"]["cuisine"]:
                continue
            dish = rec["dish"]
            if price_min <= dish["price"] <= price_max:
                matching_items.append(rec)

        print(f"[DEBUG] 价格和菜系都符合条件的数量: {len(matching_items)}")
        for rec in matching_items[:5]:
            dish = rec["dish"]
            print(f"[DEBUG] 示例: {dish['name']} - {dish['price']}元 - {rec['restaurant']['cuisine']}")

        filtered = self._filter_by_prefs_with_price_range(
            all_items, price_min, price_max, effective_budget,
            keyword, cuisine, spicy, avoid, exclude_ids
        )

        # 排除指定餐厅
        if exclude_restaurant:
            filtered = [r for r in filtered if exclude_restaurant not in r["restaurant"]["name"]]

        # 如果找不到菜品，增加调试信息
        if not filtered:
            print(f"[警告] 没有找到符合条件的菜品！")
            print(f"  - 条件: 菜系={cuisine}, 辣度={spicy}, 价格范围={price_min:.0f}-{price_max:.0f}")
            print(f"  - 符合价格和菜系的菜品: {len(matching_items)}个")

        return filtered[:5]

    def _get_hotpot_recommendations(self, budget: float, spicy: str, avoid: list = None,
                                    budget_min: float = None, budget_max: float = None,
                                    budget_type: str = "exact") -> dict:
        """获取火锅推荐（锅底 + 配菜组合）"""
        avoid = avoid or []

        # 确定价格范围
        if budget_type == "range" and budget_min and budget_max:
            price_min = budget_min
            price_max = budget_max
        elif budget_type == "within" and budget_max:
            price_min = 0
            price_max = budget_max
        elif budget_type == "around" and budget_min and budget_max:
            price_min = budget_min
            price_max = budget_max
        else:
            price_min = budget * 0.9
            price_max = budget * 1.1

        hotpot_restaurants = [r for r in RESTAURANTS if r["cuisine"] == "火锅"]
        if not hotpot_restaurants:
            return None

        best_restaurant = sorted(hotpot_restaurants, key=lambda x: x["rating"], reverse=True)[0]

        all_dishes = []
        for item in self._get_all_dishes_with_restaurant():
            if item["restaurant"]["id"] == best_restaurant["id"]:
                all_dishes.append(item)

        broths = []
        side_dishes = []

        for item in all_dishes:
            dish = item["dish"]
            if "锅底" in dish["name"]:
                broths.append(item)
            else:
                side_dishes.append(item)

        selected_broth = None
        if spicy == "不辣":
            for b in broths:
                if b["dish"]["spicy"] == "不辣" and price_min <= b["dish"]["price"] <= price_max:
                    selected_broth = b
                    break
        elif spicy == "微辣":
            for b in broths:
                if b["dish"]["spicy"] in ["不辣", "微辣"] and price_min <= b["dish"]["price"] <= price_max:
                    selected_broth = b
                    break
        elif spicy == "中辣":
            for b in broths:
                if b["dish"]["spicy"] == "中辣" and price_min <= b["dish"]["price"] <= price_max:
                    selected_broth = b
                    break
        else:
            for b in broths:
                if b["dish"]["spicy"] in ["中辣", "特辣"] and price_min <= b["dish"]["price"] <= price_max:
                    selected_broth = b
                    break

        if not selected_broth and broths:
            selected_broth = broths[0]

        if not selected_broth:
            return None

        broth_price = selected_broth["dish"]["price"]
        remaining_budget = budget - broth_price

        selected_sides = []
        sorted_sides = sorted(side_dishes, key=lambda x: x["dish"]["price"])

        for side in sorted_sides:
            dish = side["dish"]
            if avoid:
                if self._contains_avoid_ingredient(dish["name"], avoid):
                    continue
            if dish["price"] <= remaining_budget:
                selected_sides.append(side)
                remaining_budget -= dish["price"]

        return {
            "restaurant": best_restaurant,
            "broth": selected_broth,
            "sides": selected_sides,
            "total_price": broth_price + sum(s["dish"]["price"] for s in selected_sides),
            "type": "hotpot"
        }

    def _get_chuanchuan_recommendations(self, budget: float, spicy: str, avoid: list = None,
                                        budget_min: float = None, budget_max: float = None,
                                        budget_type: str = "exact") -> dict:
        """获取串串推荐（锅底 + 串串组合）"""
        avoid = avoid or []

        if budget_type == "range" and budget_min and budget_max:
            price_min = budget_min
            price_max = budget_max
        elif budget_type == "within" and budget_max:
            price_min = 0
            price_max = budget_max
        elif budget_type == "around" and budget_min and budget_max:
            price_min = budget_min
            price_max = budget_max
        else:
            price_min = budget * 0.9
            price_max = budget * 1.1

        chuanchuan_restaurants = [r for r in RESTAURANTS if r["cuisine"] == "串串"]
        if not chuanchuan_restaurants:
            return None

        best_restaurant = sorted(chuanchuan_restaurants, key=lambda x: x["rating"], reverse=True)[0]

        all_dishes = []
        for item in self._get_all_dishes_with_restaurant():
            if item["restaurant"]["id"] == best_restaurant["id"]:
                all_dishes.append(item)

        broths = []
        skewers = []

        for item in all_dishes:
            dish = item["dish"]
            if "锅底" in dish["name"]:
                broths.append(item)
            else:
                skewers.append(item)

        selected_broth = None
        for b in broths:
            if b["dish"]["spicy"] == "中辣" and price_min <= b["dish"]["price"] <= price_max:
                selected_broth = b
                break

        if not selected_broth and broths:
            selected_broth = broths[0]

        if not selected_broth:
            return None

        broth_price = selected_broth["dish"]["price"]
        remaining_budget = budget - broth_price

        selected_skewers = []
        sorted_skewers = sorted(skewers, key=lambda x: x["dish"]["price"])

        for skewer in sorted_skewers:
            dish = skewer["dish"]
            if avoid:
                if self._contains_avoid_ingredient(dish["name"], avoid):
                    continue
            if dish["price"] <= remaining_budget:
                selected_skewers.append(skewer)
                remaining_budget -= dish["price"]
            if len(selected_skewers) >= 8:
                break

        return {
            "restaurant": best_restaurant,
            "broth": selected_broth,
            "skewers": selected_skewers,
            "total_price": broth_price + sum(s["dish"]["price"] for s in selected_skewers),
            "type": "chuanchuan"
        }

    def _format_hotpot_response(self, recommendation: dict, budget: float, spicy: str, user_input: str,
                                user_prefs: dict) -> str:
        """格式化火锅/串串推荐回复"""
        restaurant = recommendation["restaurant"]
        broth = recommendation["broth"]
        total_price = recommendation["total_price"]

        # 格式化价格为保留两位小数
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

        tip = self._get_fallback_tip([broth] + recommendation.get("sides", []) + recommendation.get("skewers", []))
        content += f"健康提示：{tip}\n"
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
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {price}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   {dish.get('description', '人气推荐')}\n\n"

        content += "-" * 30 + "\n"

        tip = self._get_fallback_tip(recommendations)
        content += f"健康提示：{tip}\n"
        content += "-" * 30 + "\n\n"
        content += "回复数字选择菜品，或说'换一批'重新推荐，说'下单'确认订单。"

        return content

    def _handle_recommend(self, user_input: str, user_prefs: dict) -> dict:
        """处理推荐请求"""
        parsed = self._parse_user_intent(user_input)

        # 获取预算
        if parsed["budget"] is not None:
            budget = parsed["budget"]
        else:
            budget = user_prefs.get('default_budget', 30)

        budget_min = parsed["budget_min"]
        budget_max = parsed["budget_max"]
        budget_type = parsed["budget_type"]

        keyword = parsed["keyword"]

        # 处理菜系和辣度
        if parsed.get("is_drink", False):
            cuisine = "饮品"
            spicy = "不辣"
            print(f"[饮品模式] 菜系=饮品, 辣度=不辣")
        else:
            cuisine = parsed.get("cuisine")
            if parsed.get("spicy") is not None:
                spicy = parsed["spicy"]
            else:
                spicy = user_prefs.get('spicy_level', '微辣')
        specific_dish = parsed.get("dish_name")
        spicy_loose_dishes = ["麻辣烫", "酸辣粉", "辣子鸡", "水煮鱼", "麻婆豆腐", "宫保鸡丁"]

        if specific_dish and specific_dish in spicy_loose_dishes:
            # 放宽辣度限制，不严格匹配
            print(f"[辣度放宽] 菜品 {specific_dish} 本身带辣，放宽辣度限制")
            # 不进行辣度过滤
            spicy = None

        # 处理忌口
        avoid = parsed["avoid"] if parsed["avoid"] else []
        user_avoid = user_prefs.get('avoid_foods', [])
        for a in user_avoid:
            if a not in avoid:
                avoid.append(a)

        exclude_restaurant = parsed["exclude_restaurant"]
        specific_dish = parsed.get("dish_name")

        print(
            f"[全新推荐] 预算: {budget}, 预算类型: {budget_type}, 菜系: {cuisine}, 辣度: {spicy}, 忌口: {avoid}, 指定菜品: {specific_dish}")

        # 火锅特殊处理
        if cuisine == "火锅":
            hotpot_rec = self._get_hotpot_recommendations(budget, spicy, avoid, budget_min, budget_max, budget_type)
            if hotpot_rec:
                content = self._format_hotpot_response(hotpot_rec, budget, spicy, user_input, user_prefs)
                self.conversation_context["last_cuisine"] = cuisine
                self.conversation_context["last_spicy"] = spicy
                self.conversation_context["last_avoid"] = avoid.copy()
                recommendations = [hotpot_rec["broth"]] + hotpot_rec.get("sides", [])
                if recommendations:
                    self.conversation_context["current_order"] = recommendations[0]
                return {
                    "success": True,
                    "content": content,
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None,
                    "recommendations": recommendations
                }

        # 串串特殊处理
        if cuisine == "串串":
            chuanchuan_rec = self._get_chuanchuan_recommendations(budget, spicy, avoid, budget_min, budget_max,
                                                                  budget_type)
            if chuanchuan_rec:
                content = self._format_hotpot_response(chuanchuan_rec, budget, spicy, user_input, user_prefs)
                self.conversation_context["last_cuisine"] = cuisine
                self.conversation_context["last_spicy"] = spicy
                self.conversation_context["last_avoid"] = avoid.copy()
                recommendations = [chuanchuan_rec["broth"]] + chuanchuan_rec.get("skewers", [])
                if recommendations:
                    self.conversation_context["current_order"] = recommendations[0]
                return {
                    "success": True,
                    "content": content,
                    "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                    "workflow": None,
                    "recommendations": recommendations
                }

        # 普通菜品推荐
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": keyword,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": exclude_restaurant,
        }
        self.conversation_context["recommended_ids"] = []

        recommendations = self._get_recommendations_from_mock(
            budget, keyword, cuisine, spicy, avoid, None,
            budget_min, budget_max, exclude_restaurant, budget_type
        )

        # 优先推荐用户指定的菜品（如麻辣烫）
        if specific_dish:
            # 从所有菜品中直接搜索匹配的菜品，不依赖过滤结果
            all_items = self._get_all_dishes_with_restaurant()

            exact_match = None
            for rec in all_items:
                dish_name = rec["dish"]["name"]
                # 完全匹配
                if dish_name == specific_dish:
                    exact_match = rec
                    print(f"[优先推荐] 从全集中找到完全匹配: {dish_name}")
                    break
                # 或者包含匹配（如"麻辣烫"匹配"麻辣烫"）
                elif specific_dish in dish_name:
                    exact_match = rec
                    print(f"[优先推荐] 从全集中找到包含匹配: {dish_name}")
                    break

            if exact_match:
                # 检查价格是否符合预算要求
                price = exact_match["dish"]["price"]
                if budget_type == "range" and budget_min and budget_max:
                    if price < budget_min or price > budget_max:
                        print(f"[优先推荐] 价格 {price} 不在预算范围 {budget_min}-{budget_max}，但仍优先推荐")
                elif budget_type == "within" and budget_max:
                    if price > budget_max:
                        print(f"[优先推荐] 价格 {price} 超过预算 {budget_max}，但仍优先推荐")
                elif budget_type == "around" and budget_min and budget_max:
                    if price < budget_min or price > budget_max:
                        print(f"[优先推荐] 价格 {price} 不在范围 {budget_min}-{budget_max}，但仍优先推荐")

                # 将匹配的菜品添加到推荐列表最前面
                if exact_match not in recommendations:
                    recommendations.insert(0, exact_match)
                    print(f"[优先推荐] 将 {exact_match['dish']['name']} 添加到推荐列表首位")
                else:
                    recommendations.remove(exact_match)
                    recommendations.insert(0, exact_match)
                    print(f"[优先推荐] 将 {exact_match['dish']['name']} 移至首位")

        # 移除重复项
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            dish_id = rec["dish"]["id"]
            if dish_id not in seen:
                seen.add(dish_id)
                unique_recommendations.append(rec)
        recommendations = unique_recommendations[:5]

        for rec in recommendations:
            self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_budget_min"] = budget_min
        self.conversation_context["last_budget_max"] = budget_max
        self.conversation_context["last_budget_type"] = budget_type
        self.conversation_context["last_keyword"] = keyword
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid.copy()
        self.conversation_context["last_exclude_restaurant"] = exclude_restaurant
        self.conversation_context["current_recommendations"] = recommendations

        if not recommendations:
            tip = f"没有找到符合条件的菜品。\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味"
            if budget_type == "range":
                tip += f"，预算{budget_min}-{budget_max}元"
            elif budget_type == "within":
                tip += f"，预算{budget_max}元以内"
            elif budget_type == "around":
                tip += f"，预算{budget_min}-{budget_max}元"
            else:
                tip += f"，预算{budget}元"
            if avoid:
                tip += f"，忌口{', '.join(avoid)}"
            tip += "\n\n建议提高预算或放宽口味限制。"
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
        budget_min = params.get("budget_min")
        budget_max = params.get("budget_max")
        budget_type = params.get("budget_type", "exact")
        keyword = params["keyword"]
        cuisine = params["cuisine"]
        spicy = params["spicy"]
        avoid = params["avoid"]
        exclude_restaurant = params.get("exclude_restaurant")
        exclude_ids = self.conversation_context.get("recommended_ids", [])

        print(f"[换一批] 预算={budget}, 菜系={cuisine}, 辣度={spicy}")

        recommendations = self._get_recommendations_from_mock(
            budget, keyword, cuisine, spicy, avoid, exclude_ids,
            budget_min, budget_max, exclude_restaurant, budget_type
        )

        if not recommendations:
            print("[换一批] 没有更多菜品，重新开始")
            self.conversation_context["recommended_ids"] = []
            recommendations = self._get_recommendations_from_mock(
                budget, keyword, cuisine, spicy, avoid, [],
                budget_min, budget_max, exclude_restaurant, budget_type
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

        # 获取当前上下文中的完整条件
        budget = self.conversation_context["last_budget"]
        budget_min = self.conversation_context.get("last_budget_min")
        budget_max = self.conversation_context.get("last_budget_max")
        budget_type = self.conversation_context.get("last_budget_type", "exact")
        keyword = self.conversation_context["last_keyword"]
        cuisine = self.conversation_context["last_cuisine"]
        spicy = self.conversation_context["last_spicy"]
        avoid = self.conversation_context["last_avoid"].copy()
        exclude_restaurant = self.conversation_context.get("last_exclude_restaurant")
        current_recommendations = self.conversation_context["current_recommendations"].copy()

        change_desc = []
        new_avoid_items = []

        # 标记修改类型
        is_budget_change = False
        is_cuisine_change = False
        is_spicy_change = False
        is_avoid_change = False
        is_exclude_restaurant_change = False

        # 1. 处理预算调整
        if re.search(r'更贵|贵一点|提高预算', user_lower):
            if budget_type == "range" and budget_min is not None and budget_max is not None:
                budget_min += 10
                budget_max += 10
                budget = (budget_min + budget_max) // 2
            elif budget_type == "within" and budget_max is not None:
                budget_max += 10
                budget = budget_max
            elif budget_type == "around" and budget_min is not None and budget_max is not None:
                budget_min += 8
                budget_max += 8
                budget = (budget_min + budget_max) // 2
            else:
                budget += 10
            is_budget_change = True
            change_desc.append(f"预算提高为{budget}元")
        elif re.search(r'更便宜|便宜一点|降低预算', user_lower):
            if budget_type == "range" and budget_min is not None and budget_max is not None:
                budget_min = max(0, budget_min - 10)
                budget_max = max(0, budget_max - 10)
                budget = (budget_min + budget_max) // 2
            elif budget_type == "within" and budget_max is not None:
                budget_max = max(0, budget_max - 10)
                budget = budget_max
            elif budget_type == "around" and budget_min is not None and budget_max is not None:
                budget_min = max(0, budget_min - 8)
                budget_max = max(0, budget_max - 8)
                budget = (budget_min + budget_max) // 2
            else:
                budget = max(15, budget - 10)
            is_budget_change = True
            change_desc.append(f"预算降低为{budget}元")

        # 处理直接预算修改
        budget_match = re.search(r'(\d+)(?:元|块|块钱)', user_input)
        if budget_match:
            new_budget = int(budget_match.group(1))
            if budget_type == "range" and budget_min is not None and budget_max is not None:
                width = budget_max - budget_min
                budget_min = max(0, new_budget - width // 2)
                budget_max = new_budget + width // 2
                budget = new_budget
            elif budget_type == "within" and budget_max is not None:
                budget_max = new_budget
                budget = new_budget
            elif budget_type == "around" and budget_min is not None and budget_max is not None:
                budget_min = int(new_budget * 0.8)
                budget_max = int(new_budget * 1.2)
                budget = new_budget
            else:
                budget = new_budget
                budget_type = "exact"
            is_budget_change = True
            change_desc.append(f"预算改为{budget}元")

        # 2. 处理菜系修改
        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品"]
        for c in cuisines:
            if c in user_input:
                cuisine = c
                is_cuisine_change = True
                change_desc.append(f"菜系改为{cuisine}")
                break

        # 3. 处理辣度修改
        for s in ["特辣", "中辣", "微辣", "不辣"]:
            if s in user_input:
                spicy = s
                is_spicy_change = True
                change_desc.append(f"辣度改为{spicy}")
                break
        # 额外处理"不吃辣"表达
        if re.search(r'不吃辣|不要辣|我不吃辣', user_lower) and "不辣" not in change_desc:
            spicy = "不辣"
            is_spicy_change = True
            change_desc.append(f"辣度改为不辣")

        # 4. 处理排除餐厅（不要XX餐厅/店）
        exclude_restaurant_match = re.search(r'不要([\u4e00-\u9fa5]{2,10})(?:餐厅|店)', user_input)
        if exclude_restaurant_match:
            exclude_restaurant = exclude_restaurant_match.group(1)
            is_exclude_restaurant_change = True
            change_desc.append(f"排除{exclude_restaurant}餐厅")
            print(f"[修改] 排除餐厅: {exclude_restaurant}")

        # 5. 处理排除菜品/忌口（不要XX菜/不要XX）
        if not exclude_restaurant_match:
            exclude_match = re.search(r'不要([\u4e00-\u9fa5]{2,6})', user_input)
            if exclude_match:
                exclude_item = exclude_match.group(1)
                # 检查是否是餐厅名
                all_restaurants = self._get_all_restaurant_names()
                if exclude_item in all_restaurants:
                    # 是餐厅名
                    exclude_restaurant = exclude_item
                    is_exclude_restaurant_change = True
                    change_desc.append(f"排除{exclude_item}餐厅")
                    print(f"[修改] 排除餐厅: {exclude_item}")
                else:
                    # 是菜品名或忌口
                    valid_avoids = ["酸菜", "豆腐", "花生", "香菜", "蒜", "奶", "猪肉", "牛肉", "鸡肉", "鱼肉", "虾",
                                    "辣", "麻"]
                    if exclude_item in valid_avoids or len(exclude_item) >= 2:
                        if exclude_item not in avoid:
                            avoid.append(exclude_item)
                            new_avoid_items.append(exclude_item)
                            is_avoid_change = True
                            change_desc.append(f"排除{exclude_item}")
                            print(f"[修改] 添加忌口: {exclude_item}")

        # 6. 如果没有变化，返回提示
        if not change_desc:
            return {
                "success": True,
                "content": "请告诉我具体要修改什么，例如：提高预算、改为川菜、不要香菜等",
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        # 7. 根据修改类型决定搜索方式
        if is_avoid_change and not is_budget_change and not is_cuisine_change and not is_spicy_change and not is_exclude_restaurant_change:
            # 只有忌口修改：在当前推荐中筛选
            print("[修改] 仅忌口修改，在当前推荐中筛选")
            filtered_recommendations = []
            for rec in current_recommendations:
                dish = rec["dish"]
                dish_name = dish["name"]

                excluded = False
                for a in new_avoid_items:
                    if self._contains_avoid_ingredient(dish_name, [a]):
                        print(f"[忌口过滤] 从当前推荐中移除 {dish_name}，包含忌口 {a}")
                        excluded = True
                        break

                if not excluded:
                    filtered_recommendations.append(rec)

            # 如果过滤后数量不足，从数据库补充
            if len(filtered_recommendations) < 3:
                print(f"[修改] 过滤后只剩{len(filtered_recommendations)}个，从数据库补充")
                existing_ids = [r["dish"]["id"] for r in filtered_recommendations]
                exclude_ids = self.conversation_context.get("recommended_ids", []) + existing_ids

                if budget_type == "range" and budget_min is not None and budget_max is not None:
                    new_recs = self._get_recommendations_from_mock(
                        budget, keyword, cuisine, spicy, avoid, exclude_ids,
                        budget_min, budget_max, exclude_restaurant, budget_type
                    )
                elif budget_type == "within" and budget_max is not None:
                    new_recs = self._get_recommendations_from_mock(
                        budget, keyword, cuisine, spicy, avoid, exclude_ids,
                        0, budget_max, exclude_restaurant, budget_type
                    )
                elif budget_type == "around" and budget_min is not None and budget_max is not None:
                    new_recs = self._get_recommendations_from_mock(
                        budget, keyword, cuisine, spicy, avoid, exclude_ids,
                        budget_min, budget_max, exclude_restaurant, budget_type
                    )
                else:
                    new_recs = self._get_recommendations_from_mock(
                        budget, keyword, cuisine, spicy, avoid, exclude_ids,
                        None, None, exclude_restaurant, "exact"
                    )

                for rec in new_recs:
                    if rec not in filtered_recommendations:
                        filtered_recommendations.append(rec)
                    if len(filtered_recommendations) >= 5:
                        break
        else:
            # 预算、菜系、辣度、排除餐厅修改：全量搜索
            print("[修改] 预算/菜系/辣度/排除餐厅修改，全量搜索")

            # 全量搜索时，如果之前有排除餐厅，需要保留
            if budget_type == "range" and budget_min is not None and budget_max is not None:
                filtered_recommendations = self._get_recommendations_from_mock(
                    budget, keyword, cuisine, spicy, avoid, None,
                    budget_min, budget_max, exclude_restaurant, budget_type
                )
            elif budget_type == "within" and budget_max is not None:
                filtered_recommendations = self._get_recommendations_from_mock(
                    budget, keyword, cuisine, spicy, avoid, None,
                    0, budget_max, exclude_restaurant, budget_type
                )
            elif budget_type == "around" and budget_min is not None and budget_max is not None:
                filtered_recommendations = self._get_recommendations_from_mock(
                    budget, keyword, cuisine, spicy, avoid, None,
                    budget_min, budget_max, exclude_restaurant, budget_type
                )
            else:
                filtered_recommendations = self._get_recommendations_from_mock(
                    budget, keyword, cuisine, spicy, avoid, None,
                    None, None, exclude_restaurant, "exact"
                )

            # 重置推荐ID列表（全新搜索）
            self.conversation_context["recommended_ids"] = []
            for rec in filtered_recommendations:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])

        # 8. 更新上下文
        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_budget_min"] = budget_min
        self.conversation_context["last_budget_max"] = budget_max
        self.conversation_context["last_budget_type"] = budget_type
        self.conversation_context["last_keyword"] = keyword
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid
        self.conversation_context["last_exclude_restaurant"] = exclude_restaurant
        self.conversation_context["current_recommendations"] = filtered_recommendations
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "budget_type": budget_type,
            "keyword": keyword,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
            "exclude_restaurant": exclude_restaurant,
        }

        # 9. 如果没有推荐结果
        if not filtered_recommendations:
            tip = f"抱歉，调整后没有找到符合您需求的菜品。\n\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味"
            if budget_type == "range":
                tip += f"，预算{budget_min}-{budget_max}元"
            elif budget_type == "within":
                tip += f"，预算{budget_max}元以内"
            elif budget_type == "around":
                tip += f"，预算{budget_min}-{budget_max}元"
            else:
                tip += f"，预算{budget}元"
            if avoid:
                tip += f"，忌口{', '.join(avoid)}"
            if exclude_restaurant:
                tip += f"，排除{exclude_restaurant}餐厅"
            tip += "\n\n建议提高预算或放宽口味限制。"
            return {
                "success": True,
                "content": tip,
                "model": "qwen-0.5b (0.5B)" if self.mode == 'local' else "Deepseek",
                "workflow": None
            }

        # 10. 构建回复
        change_text = "，".join(change_desc)
        content = f"{change_text}，为您重新推荐：\n\n"
        for i, rec in enumerate(filtered_recommendations[:3], 1):
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
            "recommendations": filtered_recommendations
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
        """主对话接口"""
        user_input = user_input.strip()
        user_lower = user_input.lower()

        print(f"[对话] 用户输入: {user_input}")

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

        if user_input.isdigit():
            return self.select_dish(int(user_input))

        if re.search(r'换一批|重新推荐|再来一批', user_lower):
            return self._handle_re_recommend(user_prefs)

        if any(kw in user_lower for kw in ["推荐", "吃什么", "想吃饭", "饿了", "有什么", "点", "想吃", "来一份"]):
            return self._handle_recommend(user_input, user_prefs)

        if re.search(r'更贵|贵一点|提高预算|更便宜|便宜一点|降低预算|改为|换成|不要', user_lower):
            return self._handle_modify(user_input, user_prefs)

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
