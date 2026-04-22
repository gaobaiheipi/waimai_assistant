# services/qwen_local.py - 修复换一批、数字选择、订单保存

import os
import re
import torch
import random
from typing import Dict, List, Callable, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer
from kivy.clock import Clock

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.mock_restaurants import get_recommendations, get_restaurant, RESTAURANTS, DISHES_BY_RESTAURANT
from utils.paths import get_model_path, get_models_dir
from utils.model_downloader import model_downloader


class QwenRouterService:
    """Qwen 模型路由服务 - 0.5B意图识别 + 3B复杂生成"""

    def __init__(self):
        self.model_small = None
        self.tokenizer_small = None
        self.model_large = None
        self.tokenizer_large = None
        self.is_ready = False
        self.is_downloading = False
        self.has_recommendation_history = False

        # 对话上下文记忆
        self.conversation_context = {
            "last_budget": 30,
            "last_keyword": None,
            "last_cuisine": None,
            "last_spicy": "微辣",
            "last_avoid": [],
            "current_recommendations": [],
            "current_order": None,
            "last_search_params": None,  # 保存上次搜索参数，用于换一批时排除已推荐
            "recommended_ids": [],  # 已推荐过的菜品ID
        }

        # 工作流触发词
        self.workflow_triggers = {
            r'(下单|提交订单|确认购买|就这个|就要这个)': 'submit_order',
            r'(查询|查看).*?(订单|外卖|状态)': 'query_order',
            r'(追踪|跟踪|到哪里|到哪了|在哪).*?(订单|外卖)': 'track_order',
            r'(取消|退掉).*?(订单|外卖)': 'cancel_order',
            r'(修改|更改).*?(地址|电话|偏好|设置)': 'modify_info',
        }

    def load_models(self, callback: Optional[Callable] = None):
        """加载两个模型"""

        def _load(dt):
            try:
                print("=" * 50)
                print("开始加载模型...")

                print("\n[1/2] 加载 0.5B 意图识别模型...")
                success = self._load_small_model()
                if not success:
                    if callback:
                        Clock.schedule_once(lambda dt: callback(False, "0.5B模型加载失败"), 0)
                    return

                print("\n[2/2] 加载 3B 生成模型...")
                success_3b = self._load_large_model()
                if success_3b:
                    print("3B 模型加载成功")
                else:
                    print("3B 模型未加载，仅使用 0.5B")

                self.is_ready = True
                if callback:
                    msg = "双模型就绪" if self.model_large else "单模型就绪(0.5B)"
                    Clock.schedule_once(lambda dt: callback(True, msg), 0)

            except Exception as e:
                print(f"加载异常: {e}")
                import traceback
                traceback.print_exc()
                if callback:
                    Clock.schedule_once(lambda dt: callback(False, str(e)), 0)

        Clock.schedule_once(_load, 0.5)

    def _load_small_model(self) -> bool:
        """加载 0.5B 轻量级模型"""
        try:
            model_name = "Qwen2.5-0.5B-Instruct"
            local_path = get_model_path(model_name)

            # 如果模型不存在，下载
            if not os.path.exists(local_path):
                print("[模型] 0.5B模型不存在，启动后台下载")
                self.is_downloading = True

                def on_download(success, msg):
                    if success:
                        print("[模型] 下载完成，加载模型")
                        self.use_mock = False
                        self._load_small_model()
                    else:
                        print(f"[模型] 下载失败: {msg}")

                model_downloader.start_download(on_download)

            print(f"加载模型 from: {local_path}")

            print("加载 tokenizer...")
            self.tokenizer_small = AutoTokenizer.from_pretrained(
                local_path,
                trust_remote_code=True,
                local_files_only=True
            )

            print("加载模型（使用 CPU 和 float32）...")

            self.model_small = AutoModelForCausalLM.from_pretrained(
                local_path,
                trust_remote_code=True,
                local_files_only=True,
                torch_dtype="auto",
                low_cpu_mem_usage=True,
                device_map=None
            )

            self.model_small = self.model_small.to("cpu")
            self.model_small.eval()

            import gc
            gc.collect()

            print("0.5B 模型加载成功")
            return True

        except Exception as e:
            print(f"0.5B模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _load_large_model(self) -> bool:
        """加载 3B 模型（可选）"""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM

            model_name = "Qwen2.5-3B-Instruct"
            local_path = get_model_path(model_name)

            if not os.path.exists(local_path):
                alt_path = f"./models/Qwen/{model_name}"
                if os.path.exists(alt_path):
                    local_path = alt_path
                else:
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
            self.tokenizer_large = None
            return False

    def _generate(self, model, tokenizer, messages, max_new_tokens=256, temperature=0.7):
        """通用生成函数"""
        import torch

        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = tokenizer([text], return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.95,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(
            outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True
        )
        return response.strip()

    def _parse_user_intent(self, user_input: str) -> dict:
        """解析用户意图，提取关键词、预算、菜系、辣度、忌口"""
        result = {
            "keyword": None,
            "budget": None,
            "cuisine": None,
            "spicy": None,
            "avoid": [],
        }

        # 提取预算 - 支持多种格式
        # 1. 数字+元/块/块钱
        budget_match = re.search(r'(\d+)(?:元|块|块钱)', user_input)
        if budget_match:
            result["budget"] = int(budget_match.group(1))

        # 2. 数字+左右（如30左右）
        budget_match2 = re.search(r'(\d+)\s*左右', user_input)
        if budget_match2 and result["budget"] is None:
            result["budget"] = int(budget_match2.group(1))

        # 3. 价格范围（如50元以下、50元以内、30元内）
        price_range_match = re.search(r'(\d+)(?:元|块|块钱)(?:以下|以内|内)', user_input)
        if price_range_match and result["budget"] is None:
            result["budget"] = int(price_range_match.group(1))

        # 4. 数字（单独出现，如"30"）
        number_match = re.search(r'(\d+)(?![元块])', user_input)
        if number_match and result["budget"] is None:
            # 排除价格范围已经匹配的情况
            if not re.search(r'\d+元', user_input):
                result["budget"] = int(number_match.group(1))

        print(f"[预算提取] 用户输入: {user_input}, 提取预算: {result['budget']}")

        # 菜系列表
        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品"]
        for c in cuisines:
            if c in user_input:
                result["cuisine"] = c
                break

        # 提取关键词
        temp_input = user_input
        if result["cuisine"]:
            temp_input = temp_input.replace(result["cuisine"], "")
        if result["budget"]:
            temp_input = re.sub(r'\d+元[以内内左右]?', '', temp_input)

        food_match = re.search(r'(?:想吃|要吃|来一份|点|帮我点)([^，,。的0-9]+)', temp_input)
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
            if avoid_item and avoid_item not in ["吃", "放", "加", "要"]:
                result["avoid"] = [avoid_item]

        return result

    def _extract_modify_items(self, user_input: str) -> dict:
        """提取修改项"""
        user_lower = user_input.lower()
        result = {
            "budget": None,
            "cuisine": None,
            "spicy": None,
            "add_avoid": [],
            "remove_avoid": [],
            "keyword": None,
        }

        budget_match = re.search(r'(\d+)(?:元|块|块钱)', user_input)
        if budget_match:
            result["budget"] = int(budget_match.group(1))

        if re.search(r'更贵|贵一点|提高预算', user_lower):
            result["budget"] = "increase"
        elif re.search(r'更便宜|便宜一点|降低预算', user_lower):
            result["budget"] = "decrease"

        cuisines = ["川菜", "粤菜", "湘菜", "东北菜", "日料", "韩餐", "西餐", "火锅", "小吃", "轻食",
                    "西北菜", "东南亚", "港式", "清真", "新疆菜", "台湾菜", "京菜", "素食", "海鲜", "鲁菜", "甜品"]
        for c in cuisines:
            if c in user_input:
                result["cuisine"] = c
                break

        for s in ["特辣", "中辣", "微辣", "不辣"]:
            if s in user_input:
                result["spicy"] = s
                break

        avoid_match = re.search(r'不要([\u4e00-\u9fa5]{1,4})', user_input)
        if avoid_match:
            avoid_item = avoid_match.group(1)
            if avoid_item and avoid_item not in ["吃", "放", "加", "要"]:
                result["add_avoid"].append(avoid_item)

        if re.search(r'减少忌口|去掉忌口|不再忌口', user_lower):
            result["remove_avoid"] = ["all"]

        food_match = re.search(r'(?:换成|改吃|想吃)([^，,。的]+)', user_input)
        if food_match:
            keyword = food_match.group(1).strip()
            if keyword and len(keyword) <= 6:
                result["keyword"] = keyword

        return result

    def _filter_by_prefs(self, recommendations: list, budget: float, keyword: str = None,
                         cuisine: str = None, spicy: str = None, avoid: list = None,
                         exclude_ids: list = None) -> list:
        """根据偏好过滤推荐列表"""
        filtered = []
        exclude_ids = exclude_ids or []

        for rec in recommendations:
            dish = rec["dish"]
            restaurant = rec["restaurant"]

            # 检查预算
            if dish["price"] > budget * 1.2:
                continue

            # 检查忌口
            if avoid:
                excluded = False
                for a in avoid:
                    if a in dish["name"]:
                        excluded = True
                        break
                if excluded:
                    continue

            # 检查菜系
            if cuisine and cuisine not in restaurant["cuisine"]:
                continue

            # 检查关键词
            if keyword and keyword not in dish["name"]:
                continue

            # 检查辣度
            if spicy:
                dish_spicy = dish.get("spicy", "微辣")
                print(f"[辣度调试] 菜品:{dish['name']}, 菜品辣度:{dish_spicy}, 用户要求:{spicy}")

                # 辣度匹配规则
                if spicy == "不辣":
                    if dish_spicy != "不辣":
                        continue
                elif spicy == "微辣":
                    # 微辣可以接受：不辣 或 微辣
                    if dish_spicy not in ["不辣", "微辣"]:
                        continue
                elif spicy == "中辣":
                    # 中辣可以接受：微辣 或 中辣
                    if dish_spicy not in ["微辣", "中辣"]:
                        continue
                elif spicy == "特辣":
                    # 特辣可以接受：中辣 或 特辣 或 麻辣
                    if dish_spicy not in ["中辣", "特辣", "麻辣"]:
                        continue

            filtered.append(rec)

        return filtered

    def _get_all_dishes_with_restaurant(self) -> list:
        """获取所有菜品"""
        all_items = []
        for restaurant in RESTAURANTS:
            dishes = DISHES_BY_RESTAURANT.get(restaurant["id"], [])
            for dish in dishes:
                all_items.append({
                    "dish": dish,
                    "restaurant": restaurant,
                    "score": restaurant["rating"] * 10
                })
        return all_items

    def _get_new_recommendations(self, budget: float, keyword: str = None,
                                 cuisine: str = None, spicy: str = None,
                                 avoid: list = None, exclude_ids: list = None) -> list:
        """获取新的推荐列表"""
        all_items = self._get_all_dishes_with_restaurant()

        filtered = self._filter_by_prefs(
            all_items, budget, keyword, cuisine, spicy, avoid, exclude_ids
        )

        filtered.sort(key=lambda x: x["restaurant"]["rating"], reverse=True)

        print(
            f"[搜索] 预算{budget}元, 菜系{cuisine}, 辣度{spicy}, 忌口{avoid}, 排除{len(exclude_ids or [])}个, 共找到{len(filtered)}个菜品")
        for item in filtered[:5]:
            print(
                f"  - {item['dish']['name']} ({item['restaurant']['name']}) {item['dish']['price']}元 辣度:{item['dish'].get('spicy', '未知')}")

        return filtered

    def _handle_recommend(self, user_input: str, user_prefs: dict) -> dict:
        """处理全新推荐"""
        parsed = self._parse_user_intent(user_input)

        # 未提及的偏好使用用户偏好表中的值
        budget = parsed["budget"] if parsed["budget"] is not None else user_prefs.get('default_budget', 30)
        keyword = parsed["keyword"]
        cuisine = parsed["cuisine"]
        spicy = parsed["spicy"] if parsed["spicy"] is not None else user_prefs.get('spicy_level', '微辣')
        avoid = parsed["avoid"] if parsed["avoid"] else user_prefs.get('avoid_foods', [])

        print(f"[全新推荐] 预算: {budget}, 关键词: {keyword}, 菜系: {cuisine}, 辣度: {spicy}, 忌口: {avoid}")

        # 保存搜索参数
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "keyword": keyword,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
        }

        # 获取全部推荐
        all_recommendations = self._get_new_recommendations(budget, keyword, cuisine, spicy, avoid)
        # 只取前3个显示
        recommendations = all_recommendations[:3]

        # 记录已推荐的ID（只记录显示的3个）
        self.conversation_context["recommended_ids"] = []
        for rec in recommendations:
            self.conversation_context["recommended_ids"].append(rec["dish"]["id"])
        print(f"[记录ID] 已推荐: {self.conversation_context['recommended_ids']}")

        self.conversation_context["last_budget"] = budget
        self.conversation_context["last_keyword"] = keyword
        self.conversation_context["last_cuisine"] = cuisine
        self.conversation_context["last_spicy"] = spicy
        self.conversation_context["last_avoid"] = avoid.copy()
        self.conversation_context["current_recommendations"] = recommendations
        self.has_recommendation_history = True

        if not recommendations:
            return {
                "success": True,
                "content": f"抱歉，在{budget}元预算内没有找到符合您需求的菜品。\n\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味，忌口{avoid if avoid else '无'}\n\n建议提高预算或放宽口味限制。",
                "model": "qwen",
                "workflow": None
            }

        content = f"根据您的偏好（{spicy}口味，预算{budget}元），为您推荐：\n\n"
        for i, rec in enumerate(recommendations[:3], 1):
            dish = rec["dish"]
            restaurant = rec["restaurant"]
            content += f"{i}. {dish['name']} - {restaurant['name']}\n"
            content += f"   评分{restaurant['rating']}分 | {dish['price']}元 | {restaurant['delivery_time']}分钟\n"
            content += f"   辣度：{dish.get('spicy', '微辣')}\n\n"

        content += "回复数字选择菜品，或说'换一批'重新推荐，说'下单'确认订单。"

        return {
            "success": True,
            "content": content,
            "model": "qwen",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_modify(self, user_input: str, user_prefs: dict) -> dict:
        """处理修改推荐"""
        modify_items = self._extract_modify_items(user_input)

        budget = self.conversation_context["last_budget"]
        keyword = self.conversation_context["last_keyword"]
        cuisine = self.conversation_context["last_cuisine"]
        spicy = self.conversation_context["last_spicy"]
        avoid = self.conversation_context["last_avoid"].copy()

        change_desc = []

        if modify_items["budget"] is not None:
            if isinstance(modify_items["budget"], int):
                budget = modify_items["budget"]
                change_desc.append(f"预算改为{budget}元")
            elif modify_items["budget"] == "increase":
                budget = min(100, budget + 10)
                change_desc.append(f"预算提高为{budget}元")
            elif modify_items["budget"] == "decrease":
                budget = max(15, budget - 10)
                change_desc.append(f"预算降低为{budget}元")

        if modify_items["cuisine"] is not None:
            cuisine = modify_items["cuisine"]
            change_desc.append(f"菜系改为{cuisine}")

        if modify_items["spicy"] is not None:
            spicy = modify_items["spicy"]
            change_desc.append(f"辣度改为{spicy}")

        if modify_items["add_avoid"]:
            for a in modify_items["add_avoid"]:
                if a not in avoid:
                    avoid.append(a)
            change_desc.append(f"排除{', '.join(modify_items['add_avoid'])}")

        if modify_items["remove_avoid"]:
            avoid = []
            change_desc.append("移除所有忌口")

        if modify_items["keyword"] is not None:
            keyword = modify_items["keyword"]
            change_desc.append(f"关键词改为{keyword}")

        if not change_desc:
            return {
                "success": True,
                "content": "请告诉我具体要修改什么，例如：提高预算、改为川菜、不要香菜等",
                "model": "qwen",
                "workflow": None
            }

        print(f"[修改推荐] 修改项: {change_desc}")

        # 更新搜索参数
        self.conversation_context["last_search_params"] = {
            "budget": budget,
            "keyword": keyword,
            "cuisine": cuisine,
            "spicy": spicy,
            "avoid": avoid.copy(),
        }

        # 获取全部推荐
        all_recommendations = self._get_new_recommendations(budget, keyword, cuisine, spicy, avoid)
        # 只取前3个显示
        recommendations = all_recommendations[:3]

        # 重置并记录新推荐的ID
        self.conversation_context["recommended_ids"] = []
        for rec in recommendations:
            self.conversation_context["recommended_ids"].append(rec["dish"]["id"])
        print(f"[记录ID] 修改后推荐: {self.conversation_context['recommended_ids']}")

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
                "model": "qwen",
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
            "model": "qwen",
            "workflow": None,
            "recommendations": recommendations
        }

    def _handle_re_recommend(self, user_prefs: dict) -> dict:
        """处理换一批 - 排除已推荐过的菜品"""
        params = self.conversation_context.get("last_search_params")
        if not params:
            return self._handle_recommend("推荐", user_prefs)

        budget = params["budget"]
        keyword = params["keyword"]
        cuisine = params["cuisine"]
        spicy = params["spicy"]
        avoid = params["avoid"]
        exclude_ids = self.conversation_context.get("recommended_ids", [])

        # 计算已经推荐了多少个
        skip_count = len(exclude_ids)
        print(f"[换一批] 预算={budget}, 菜系={cuisine}, 辣度={spicy}")
        print(f"[换一批] 已推荐{skip_count}个菜品, IDs: {exclude_ids}")

        # 获取全部符合条件的菜品（不排除任何ID，因为我们要用skip方式）
        all_recommendations = self._get_new_recommendations(budget, keyword, cuisine, spicy, avoid, [])

        # 跳过已推荐的数量，取接下来的3个
        if skip_count >= len(all_recommendations):
            # 没有新菜品了，清空已推荐记录，重新开始
            print("[换一批] 没有更多菜品，重新开始")
            self.conversation_context["recommended_ids"] = []
            skip_count = 0
            all_recommendations = self._get_new_recommendations(budget, keyword, cuisine, spicy, avoid, [])

        recommendations = all_recommendations[skip_count:skip_count + 3]

        # 记录新推荐的ID（追加）
        for rec in recommendations:
            if rec["dish"]["id"] not in self.conversation_context["recommended_ids"]:
                self.conversation_context["recommended_ids"].append(rec["dish"]["id"])
        print(f"[记录ID] 换一批后推荐: {self.conversation_context['recommended_ids']}")

        self.conversation_context["current_recommendations"] = recommendations

        if not recommendations:
            return {
                "success": True,
                "content": f"抱歉，没有更多符合您需求的菜品了。\n\n当前条件：{cuisine if cuisine else '不限'}菜系，{spicy}口味，预算{budget}元\n\n建议修改筛选条件。",
                "model": "qwen",
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
            "model": "qwen",
            "workflow": None,
            "recommendations": recommendations
        }

    def select_dish(self, choice: int) -> dict:
        """用户选择菜品 - 直接进入确认状态"""
        recommendations = self.conversation_context["current_recommendations"]

        if not recommendations or choice > len(recommendations):
            return {
                "success": False,
                "content": "请选择有效的菜品编号",
                "workflow": None
            }

        selected = recommendations[choice - 1]
        # 保存到待确认订单
        self.conversation_context["current_order"] = selected

        dish = selected["dish"]
        restaurant = selected["restaurant"]

        content = f"您选择了：{dish['name']} ({restaurant['name']})\n"
        content += f"价格：{dish['price']}元\n"
        content += f"预计送达：{restaurant['delivery_time']}分钟\n\n"
        content += "回复'下单'确认订单，回复'取消'重新选择。"

        print(f"[选择菜品] 已保存待确认订单: {dish['name']}")

        return {
            "success": True,
            "content": content,
            "model": "qwen",
            "workflow": None  # 改为 None，不触发工作流
        }

    def _handle_confirm_order(self, user_input: str, user_prefs: dict) -> dict:
        """处理确认订单"""
        user_lower = user_input.lower()

        order = self.conversation_context.get("current_order")

        if not order:
            return {
                "success": True,
                "content": "没有待确认的订单，请先选择菜品（回复数字选择）。",
                "model": "qwen",
                "workflow": None
            }

        if re.search(r'下单|确认|是的|对|好|ok', user_lower):
            dish = order["dish"]
            restaurant = order["restaurant"]

            items = [{"dish_name": dish['name'], "price": dish['price'], "quantity": 1}]

            from services.local_auth import user_session

            # 保存订单
            success, result = user_session.create_order(
                restaurant_name=restaurant['name'],
                items=items,
                total_price=dish['price']
            )

            if success:
                order_num = result

                # 如果是游客，获取刚创建的订单对象
                if user_session.is_guest:
                    # 获取最新创建的游客订单
                    guest_orders = user_session.get_orders()
                    if guest_orders:
                        new_order = guest_orders[-1]
                        # 启动模拟配送（在tracking_screen中会处理）
                        print(f"[下单] 游客订单已创建: {new_order}")

                content = f"订单已提交成功！\n\n订单号：{order_num}\n"
                content += f"商家：{restaurant['name']}\n"
                content += f"菜品：{dish['name']}\n"
                content += f"金额：{dish['price']}元\n"
                content += f"预计送达时间：{restaurant['delivery_time']}分钟\n\n"

                if user_session.is_guest:
                    content += "提示：游客订单仅在本次会话有效，退出后订单将丢失。\n"

                content += "您可以在订单历史中查看订单状态，或说'追踪订单'查看配送进度。"

                self.conversation_context["current_order"] = None

                return {
                    "success": True,
                    "content": content,
                    "model": "qwen",
                    "workflow": None
                }
            else:
                return {
                    "success": True,
                    "content": f"下单失败：{result}，请重试。",
                    "model": "qwen",
                    "workflow": None
                }

        # 用户取消下单
        elif re.search(r'取消|不要|不了|重新选|换一个|不点了', user_lower):
            self.conversation_context["current_order"] = None

            recommendations = self.conversation_context["current_recommendations"]
            if recommendations:
                content = "已取消下单，以下是推荐列表：\n\n"
                for i, rec in enumerate(recommendations[:3], 1):
                    dish = rec["dish"]
                    restaurant = rec["restaurant"]
                    content += f"{i}. {dish['name']} - {restaurant['name']}\n"
                    content += f"   评分{restaurant['rating']}分 | {dish['price']}元 | {restaurant['delivery_time']}分钟\n\n"
                content += "回复数字选择菜品，或说'换一批'重新推荐。"
            else:
                content = "已取消下单，请说'推荐'重新开始点餐。"

            return {
                "success": True,
                "content": content,
                "model": "qwen",
                "workflow": None
            }

        else:
            # 用户没有明确回复，再次提示
            dish = order["dish"]
            restaurant = order["restaurant"]
            content = f"您选择了：{dish['name']} ({restaurant['name']})\n"
            content += f"价格：{dish['price']}元\n"
            content += f"预计送达：{restaurant['delivery_time']}分钟\n\n"
            content += "请回复'下单'确认订单，或回复'取消'重新选择。"
            return {
                "success": True,
                "content": content,
                "model": "qwen",
                "workflow": "confirm_order"
            }

    def _handle_track_order(self, user_input: str, user_prefs: dict) -> dict:
        """处理追踪订单"""
        from services.local_auth import user_session

        orders = user_session.get_active_orders()

        if not orders:
            return {
                "success": True,
                "content": "您没有进行中的订单。\n\n您可以先点餐，下单后再说'追踪订单'查看配送进度。",
                "model": "qwen",
                "workflow": None
            }

        if len(orders) == 1:
            order = orders[0]
            order_id = order.get('id', '未知')
            restaurant_name = order.get('restaurant_name', '未知商家')
            status = order.get('status', '未知')
            total_price = order.get('total_price', 0)

            content = f"订单 {order_id} 配送状态：\n\n"
            content += f"商家：{restaurant_name}\n"
            content += f"金额：{total_price}元\n"
            content += f"当前状态：{status}\n\n"

            if status == "已下单":
                content += "商家正在准备接单..."
            elif status == "商家已接单":
                content += "商家已接单，正在备餐中..."
            elif status == "配送中":
                content += "骑手正在配送中，请耐心等待。"
            elif status == "即将送达":
                content += "您的订单即将送达，请准备取餐。"
            elif status == "已送达":
                content += "订单已送达，祝您用餐愉快！"

            return {
                "success": True,
                "content": content,
                "model": "qwen",
                "workflow": None
            }
        else:
            content = "您有多个进行中的订单：\n"
            for i, order in enumerate(orders[:3], 1):
                content += f"{i}. 订单{order.get('id', '未知')} - {order.get('restaurant_name', '未知')} - {order.get('status', '未知')}\n"
            content += "\n请告诉我要追踪哪个订单（回复订单号）"
            return {
                "success": True,
                "content": content,
                "model": "qwen",
                "workflow": None
            }

    def create_order(self, restaurant_name: str, items: list, total_price: float) -> tuple:
        """创建订单"""
        if self.is_guest:
            # 游客模式：生成临时订单号并保存到数据库（游客也保存）
            import time
            import sqlite3
            import json
            from datetime import datetime

            try:
                conn = sqlite3.connect("./data/waimai.db")
                cursor = conn.cursor()
                order_id = f"GUEST{int(time.time())}"
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                items_json = json.dumps(items, ensure_ascii=False)

                cursor.execute('''
                    INSERT INTO orders (user_id, restaurant_name, items_json, total_price, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (0, restaurant_name, items_json, str(total_price), '已下单', created_at))

                conn.commit()
                real_id = cursor.lastrowid
                conn.close()
                return True, real_id
            except Exception as e:
                print(f"游客订单保存失败: {e}")
                return True, order_id

        if not self.user_id:
            return False, "用户未登录"

        return self.db.create_order(int(self.user_id), restaurant_name, items, total_price)

    def chat(self, user_input: str, user_prefs: dict, context: list = None) -> dict:
        """主对话接口"""
        if not self.is_ready:
            return {"success": False, "error": "模型未加载"}

        user_input = user_input.strip()
        user_lower = user_input.lower()
        print(f"[对话] 用户输入: {user_input}")

        # 1. 优先处理数字选择（无论什么状态）
        if user_input.isdigit():
            choice = int(user_input)
            return self.select_dish(choice)

        # 2. 处理确认状态下的下单/取消
        if self.conversation_context.get("current_order"):
            if re.search(r'下单|确认', user_lower):
                return self._handle_confirm_order(user_input, user_prefs)
            elif re.search(r'取消|重新选|换一个|不点了', user_lower):
                return self._handle_confirm_order(user_input, user_prefs)

        # 3. 检测工作流
        for pattern, workflow in self.workflow_triggers.items():
            if re.search(pattern, user_lower):
                print(f"[工作流] 触发: {workflow}")
                if workflow == 'submit_order':
                    if self.conversation_context.get("current_order"):
                        return self._handle_confirm_order(user_input, user_prefs)
                    else:
                        return {
                            "success": True,
                            "content": "请先选择菜品（回复数字），然后再说'下单'确认。",
                            "model": "qwen",
                            "workflow": None
                        }
                elif workflow in ['query_order', 'track_order']:
                    return self._handle_track_order(user_input, user_prefs)
                else:
                    return {
                        "success": True,
                        "content": "",
                        "workflow": workflow,
                        "params": {"user_input": user_input},
                        "model": "workflow"
                    }

        # 4. 换一批
        if re.search(r'换一批|重新推荐|再来一批', user_lower):
            return self._handle_re_recommend(user_prefs)

        # 5. 取消（不在确认状态时）
        if re.search(r'取消', user_lower):
            content = "已取消当前操作。请说'推荐'开始点餐。"
            return {
                "success": True,
                "content": content,
                "model": "qwen",
                "workflow": None
            }

        # 6. 核心逻辑
        if not self.has_recommendation_history:
            print("[决策] 无推荐历史，执行全新推荐")
            return self._handle_recommend(user_input, user_prefs)
        else:
            print("[决策] 有推荐历史，执行修改推荐")
            return self._handle_modify(user_input, user_prefs)


# 单例
_router_service = None


def get_qwen_service():
    global _router_service
    if _router_service is None:
        _router_service = QwenRouterService()
    return _router_service

# services/qwen_local.py - 测试模式（修复导入和变量问题）
# import os
# import re
# import random
# from typing import Dict, List, Callable, Optional
# from kivy.clock import Clock
#
#
# class QwenRouterService:
#     """Qwen 模型路由服务 - 测试模式"""
#
#     def __init__(self):
#         self.is_ready = False
#
#         # 工作流触发词
#         self.workflow_triggers = {
#             r'(下单|提交订单|确认购买|就这个|就要这个|确认)': 'submit_order',
#             r'(查询|查看).*?(订单|外卖|状态)': 'query_order',
#             r'(追踪|跟踪|到哪里|到哪了|在哪).*?(订单|外卖)': 'track_order',  # 新增
#             r'(取消|退掉).*?(订单|外卖)': 'cancel_order',
#             r'(修改|更改).*?(地址|电话|偏好|设置)': 'modify_info',
#         }
#
#         # 模拟回复库
#         self.mock_responses = [
#             "您好！我是外卖助手。请问您想吃什么？",
#             "收到！正在为您推荐附近的美食...",
#             "根据您的偏好，推荐麻辣烫、黄焖鸡、盖浇饭。",
#             "好的，已为您记录。需要我帮您下单吗？",
#             "您可以说'下单'来确认订单，或者说'取消'重新选择。",
#         ]
#
#     def load_models(self, callback: Optional[Callable] = None):
#         """测试模式：直接标记为就绪"""
#         print("=" * 50)
#         print("测试模式：跳过真实模型加载")
#         print("提示：如需加载真实模型，请确保虚拟内存充足")
#         self.is_ready = True
#         if callback:
#             Clock.schedule_once(lambda dt: callback(True, "测试模式（模拟回复）"), 0)
#
#     def chat(self, user_input: str, user_prefs: dict, context: list = None) -> dict:
#         """测试模式：智能模拟回复"""
#         if not self.is_ready:
#             return {"success": False, "error": "服务未就绪"}
#
#         # 确保 user_input 是字符串
#         user_input = str(user_input) if user_input else ""
#         user_lower = user_input.lower()
#
#         # 1. 检测工作流
#         for pattern, workflow in self.workflow_triggers.items():
#             if re.search(pattern, user_lower):
#                 return {
#                     "success": True,
#                     "content": "",
#                     "workflow": workflow,
#                     "params": {"user_input": user_input},
#                     "model": "workflow"
#                 }
#
#         # 2. 关键词匹配回复
#         if any(kw in user_lower for kw in ["推荐", "吃什么", "想吃饭", "饿了"]):
#             budget = user_prefs.get('default_budget', 30)
#             spicy = user_prefs.get('spicy_level', '微辣')
#             avoid = user_prefs.get('avoid_foods', [])
#             avoid_str = f"，避开{','.join(avoid)}" if avoid else ""
#
#             content = f"🍽 根据您的偏好（{spicy}{avoid_str}，预算{budget}元），推荐：\n\n• 招牌麻辣烫 {budget - 10}元\n• 黄焖鸡米饭 {budget - 5}元\n• 酸菜鱼套餐 {budget + 5}元\n\n回复'下单'确认，或告诉我具体想吃什么～"
#
#         elif any(kw in user_lower for kw in ["麻辣烫", "黄焖鸡", "酸菜鱼", "米饭", "面条"]):
#             content = f"好的，帮您点{user_input}！\n\n请确认：\n• 商家：张记美食\n• 价格：¥{user_prefs.get('default_budget', 30)}\n• 送达：约35分钟\n\n回复'下单'确认订单。"
#
#         elif any(kw in user_lower for kw in ["辣", "不辣", "微辣", "中辣", "特辣"]):
#             spicy = "微辣"
#             if "不辣" in user_lower:
#                 spicy = "不辣"
#             elif "中辣" in user_lower:
#                 spicy = "中辣"
#             elif "特辣" in user_lower:
#                 spicy = "特辣"
#             content = f"好的，已记录您的辣度偏好：{spicy}。下次推荐会按此口味筛选～"
#
#         elif any(kw in user_lower for kw in ["不要", "忌口", "不吃"]):
#             avoid_match = re.search(r'不要[吃]?([\u4e00-\u9fa5]+)', user_input)
#             if avoid_match:
#                 food = avoid_match.group(1)
#                 content = f"好的，已记录忌口：{food}。推荐时会避开含{food}的菜品。"
#             else:
#                 content = "好的，已记录您的忌口偏好。"
#
#         elif any(kw in user_lower for kw in ["订单", "历史", "之前"]):
#             content = " 您的历史订单：\n\n1. 麻辣烫 28元 (已完成)\n2. 黄焖鸡 32元 (配送中)\n3. 酸菜鱼 45元 (已送达)"
#
#         else:
#             content = random.choice(self.mock_responses)
#
#         return {
#             "success": True,
#             "content": content,
#             "model": "mock",
#             "intent": "simple",
#             "workflow": None
#         }
#
#     def recommend_food(self, user_prefs: dict, budget: int, location: str) -> dict:
#         """测试模式：返回模拟推荐"""
#         spicy = user_prefs.get('spicy_level', '微辣')
#         avoid = user_prefs.get('avoid_foods', [])
#         avoid_str = f"，已避开{', '.join(avoid)}" if avoid else ""
#
#         content = f""" 为您推荐（预算{budget}元，{spicy}口味{avoid_str}）：
#
# ━━━━━━━━━━━━━━━━━━━━
# 1 招牌麻辣烫
#     4.8分 | ¥{budget - 8}
#     张记麻辣烫 | 35分钟
#     可定制忌口
# ━━━━━━━━━━━━━━━━━━━━
# 2 黄焖鸡米饭
#     4.6分 | ¥{budget - 5}
#     李姐厨房 | 28分钟
#     销量冠军
# ━━━━━━━━━━━━━━━━━━━━
# 3 酸菜鱼套餐
#     4.7分 | ¥{budget + 5}
#     川湘小馆 | 40分钟
#     热销推荐
# ━━━━━━━━━━━━━━━━━━━━
#
# 回复"下单"确认，或告诉我想换什么～"""
#
#         return {"success": True, "content": content, "model": "mock"}
#
#
# # 单例
# _router_service = None
#
#
# def get_qwen_service():
#     global _router_service
#     if _router_service is None:
#         _router_service = QwenRouterService()
#     return _router_service
