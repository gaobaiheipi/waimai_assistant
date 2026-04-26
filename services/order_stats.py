# services/order_stats.py
import json
from collections import Counter
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from services.db_service import get_db_service
from services.local_auth import user_session


class OrderStatsService:
    """订单统计分析服务"""

    def __init__(self):
        self.db = get_db_service()

    # 甜品关键词
    DESSERT_KEYWORDS = ["蛋糕", "慕斯", "芝士", "提拉米苏", "泡芙", "马卡龙", "布丁", "双皮奶", "班戟", "千层",
                        "冰淇淋",
                        "甜品", "甜点", "奶油", "巧克力蛋糕", "芒果慕斯", "芝士蛋糕", "杨枝甘露"]

    # 饮品关键词
    DRINKS_KEYWORDS = ["奶茶", "咖啡", "柠檬茶", "果茶", "拿铁", "卡布奇诺", "美式", "焦糖", "抹茶", "百香果", "金桔",
                       "养乐多", "可乐", "雪碧", "果汁", "红茶", "绿茶", "乌龙茶", "奶盖", "波霸", "珍珠", "椰奶"]

    # 甜品和饮品菜系
    DESSERT_DRINK_CUISINES = ["甜品", "饮品"]

    # 火锅串串菜系
    HOTPOT_CHUANCHUAN_CUISINES = ["火锅", "串串"]

    def is_dessert_or_drink(self, dish_name: str, cuisine: str = None) -> bool:
        """判断是否为甜品或饮品"""
        # 按菜系判断
        if cuisine in self.DESSERT_DRINK_CUISINES:
            return True

        # 按关键词判断
        for kw in self.DESSERT_KEYWORDS:
            if kw in dish_name:
                return True
        for kw in self.DRINKS_KEYWORDS:
            if kw in dish_name:
                return True
        return False

    def is_hotpot_or_chuanchuan(self, restaurant_cuisine: str) -> bool:
        """判断是否为火锅或串串"""
        return restaurant_cuisine in self.HOTPOT_CHUANCHUAN_CUISINES

    def get_non_drink_orders(self, user_id: int = None) -> List[Dict]:
        """兼容旧方法名，实际调用 get_non_dessert_drink_orders"""
        return self.get_non_dessert_drink_orders(user_id)

    def get_non_dessert_drink_orders(self, user_id: int = None) -> List[Dict]:
        """获取非甜品和非饮品订单（排除火锅串串）"""
        if user_session.is_guest:
            return []

        if user_id is None and not user_session.is_guest:
            user_id = int(user_session.user_id) if user_session.user_id else None

        if not user_id:
            return []

        all_orders = self.db.get_user_orders(user_id, limit=200)
        filtered_orders = []

        for order in all_orders:
            items = order.get('items', [])
            restaurant_name = order.get('restaurant_name', '')

            # 检查餐厅是否为火锅串串
            restaurant = self._get_restaurant_by_name(restaurant_name)
            if restaurant and self.is_hotpot_or_chuanchuan(restaurant.get('cuisine', '')):
                continue

            # 检查订单中的菜品是否为甜品或饮品
            is_dessert_drink_order = False
            for item in items:
                dish_name = item.get('dish_name', '')
                if self.is_dessert_or_drink(dish_name):
                    is_dessert_drink_order = True
                    break

            if not is_dessert_drink_order:
                filtered_orders.append(order)

        return filtered_orders

    def _get_restaurant_by_name(self, name: str) -> Optional[Dict]:
        """根据餐厅名获取餐厅信息"""
        from data.mock_restaurants import RESTAURANTS
        for r in RESTAURANTS:
            if r['name'] == name:
                return r
        return None

    def get_dish_spicy_from_mock(self, dish_name: str, restaurant_name: str) -> str:
        """从 mock 数据集中获取菜品的辣度"""
        from data.mock_restaurants import RESTAURANTS, DISHES_BY_RESTAURANT

        for restaurant in RESTAURANTS:
            if restaurant['name'] == restaurant_name:
                dishes = DISHES_BY_RESTAURANT.get(restaurant['id'], [])
                for dish in dishes:
                    if dish['name'] == dish_name:
                        return dish.get('spicy', '微辣')
                break
        return '微辣'

    def analyze_user_preferences(self, user_id: int = None) -> Optional[Dict]:
        """
        分析用户偏好（排除火锅串串、甜品、饮品）
        返回: {
            'frequent_restaurants': [('餐厅名', 次数), ...],
            'frequent_dishes': [('菜品名', 次数), ...],
            'avg_budget': 平均预算取整十,
            'most_common_spicy': 最常点的辣度,
            'total_orders': 总订单数
        }
        """
        orders = self.get_non_dessert_drink_orders(user_id)

        if len(orders) < 20:
            return None

        # 统计餐厅
        restaurant_counter = Counter()
        # 统计菜品
        dish_counter = Counter()
        # 统计预算
        total_budget = 0
        # 统计辣度
        spicy_counter = Counter()

        for order in orders:
            restaurant_name = order.get('restaurant_name', '')
            if restaurant_name:
                restaurant_counter[restaurant_name] += 1

            total_price = order.get('total_price', 0)
            try:
                total_budget += float(total_price)
            except (ValueError, TypeError):
                pass

            items = order.get('items', [])
            for item in items:
                dish_name = item.get('dish_name', '')
                if dish_name:
                    dish_counter[dish_name] += 1
                    # 获取辣度
                    spicy = self.get_dish_spicy_from_mock(dish_name, restaurant_name)
                    spicy_counter[spicy] += 1

        avg_budget = round(total_budget / len(orders) / 10) * 10
        if avg_budget < 20:
            avg_budget = 20
        if avg_budget > 100:
            avg_budget = 100

        # 获取最常点的辣度
        most_common_spicy = spicy_counter.most_common(1)
        most_common_spicy = most_common_spicy[0][0] if most_common_spicy else '微辣'

        return {
            'frequent_restaurants': restaurant_counter.most_common(5),
            'frequent_dishes': dish_counter.most_common(5),
            'avg_budget': avg_budget,
            'most_common_spicy': most_common_spicy,
            'total_orders': len(orders)
        }

    def get_order_summary_popup(self, user_id: int = None) -> dict:
        """获取订单总结弹窗信息"""
        from services.local_auth import user_session

        if user_session.is_guest:
            return {'should_show': False}

        orders = self.get_non_dessert_drink_orders(user_id)
        total_orders = len(orders)

        print(f"[订单总结] 总订单数: {total_orders}")

        if total_orders < 20:
            return {'should_show': False}

        prefs = user_session.get_prefs()
        last_summary_count = prefs.get('last_summary_count', 0)
        print(f"[订单总结] 上次总结时订单数(last_summary_count): {last_summary_count}")

        current_milestone = (total_orders // 20) * 20
        print(f"[订单总结] 当前里程碑: {current_milestone}")

        should_show = current_milestone > last_summary_count

        print(f"[订单总结] 是否弹窗: {should_show}")

        if not should_show:
            return {'should_show': False}

        start_idx = total_orders - 20
        recent_orders = orders[start_idx:] if start_idx >= 0 else orders
        budget_sum = 0
        spicy_counter = Counter()

        for order in recent_orders:
            total_price = order.get('total_price', 0)
            try:
                budget_sum += float(total_price)
            except (ValueError, TypeError):
                pass

            items = order.get('items', [])
            restaurant_name = order.get('restaurant_name', '')
            for item in items:
                dish_name = item.get('dish_name', '')
                if dish_name:
                    spicy = self.get_dish_spicy_from_mock(dish_name, restaurant_name)
                    spicy_counter[spicy] += 1

        avg_budget = round(budget_sum / len(recent_orders) / 10) * 10
        if avg_budget < 20:
            avg_budget = 20
        if avg_budget > 100:
            avg_budget = 100

        most_common_spicy = spicy_counter.most_common(1)
        most_common_spicy = most_common_spicy[0][0] if most_common_spicy else '微辣'

        return {
            'should_show': True,
            'summary': {
                'avg_budget': avg_budget,
                'spicy': most_common_spicy,
                'total_orders': total_orders,
                'orders_since_last': total_orders - last_summary_count
            }
        }

    def update_last_summary_count(self, user_id: int = None):
        """更新上次总结时的订单数量"""
        if user_session.is_guest:
            return
        orders = self.get_non_dessert_drink_orders(user_id)
        current_prefs = user_session.get_prefs()
        current_prefs['last_summary_order_count'] = len(orders)
        user_session.update_prefs(current_prefs)


order_stats = OrderStatsService()
