# services/local_auth.py
from kivy.event import EventDispatcher
from kivy.properties import StringProperty, DictProperty, BooleanProperty
from services.db_service import get_db_service
from utils.paths import get_db_path


class UserSession(EventDispatcher):
    """用户会话（支持 Kivy 事件绑定）"""

    nickname = StringProperty("游客")
    user_id = StringProperty("")
    phone = StringProperty("")
    is_guest = BooleanProperty(True)
    preferences = DictProperty({})

    def __init__(self):
        super().__init__()
        self.db = get_db_service()
        self.reset()

    def reset(self):
        self.user_id = ""
        self.nickname = "游客"
        self.phone = ""
        self.is_guest = True
        self._prefs = {}
        self.preferences = {}

        self.guest_orders = []
        self.guest_order_counter = 0

    def is_logged_in(self) -> bool:
        return not self.is_guest and bool(self.user_id)

    def get_user_data(self) -> dict:
        if self.is_guest or not self.user_id:
            return {}

        user = self.db.get_user(int(self.user_id))
        if user:
            return {
                "user_id": user["id"],
                "phone": user["phone"],
                "nickname": user["username"],
                "preferences": self.get_prefs()
            }
        return {}

    def login(self, username: str, password: str) -> tuple:
        success, result = self.db.login_user(username, password)
        if success:
            self.user_id = str(result['id'])
            self.nickname = result['username']
            self.phone = result['phone']
            self.is_guest = False
            self._prefs = self.db.get_preferences(result['id'])
            self.preferences = self._prefs.copy()
            return True, "登录成功"
        return False, result

    def login_guest(self) -> dict:
        self.reset()
        self.is_guest = True
        return {
            "user_id": None,
            "phone": None,
            "nickname": "游客",
            "preferences": self.get_prefs()
        }

    def register(self, username: str, password: str, phone: str) -> tuple:
        success, result = self.db.register_user(username, password, phone)
        if success:
            return True, result
        return False, result

    def logout(self):
        self.reset()

    def get_prefs(self) -> dict:
        if self.is_guest:
            if hasattr(self, '_guest_prefs') and self._guest_prefs:
                return self._guest_prefs
            default_prefs = {
                'spiciness_level': '微辣',
                'budget_range': '30',
                'default_address': '',
                'avoid_foods': [],
                'default_budget': 30,
                'spicy_level': '微辣',
            }
            return default_prefs
        if not self._prefs and self.user_id:
            self._prefs = self.db.get_preferences(int(self.user_id))
            self.preferences = self._prefs.copy()
        return self._prefs

    def update_prefs(self, prefs: dict) -> bool:
        self._prefs.update(prefs)
        self.preferences = self._prefs.copy()

        if self.is_guest:
            if not hasattr(self, '_guest_prefs'):
                self._guest_prefs = {}
            self._guest_prefs.update(prefs)
            return True

        if self.user_id:
            return self.db.update_preferences(int(self.user_id), self._prefs)
        return True

    def clear_guest_prefs(self):
        if hasattr(self, '_guest_prefs'):
            self._guest_prefs = {}

    def create_order(self, restaurant_name: str, items: list, total_price: float) -> tuple:
        from datetime import datetime

        if self.is_guest:
            self.guest_order_counter += 1
            order_id = f"GUEST{self.guest_order_counter}"
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            order = {
                "id": order_id,
                "order_seq": self.guest_order_counter,
                "restaurant_name": restaurant_name,
                "items": items,
                "total_price": total_price,
                "status": "已下单",
                "created_at": created_at,
            }
            self.guest_orders.append(order)
            return True, order_id

        if not self.user_id:
            return False, "用户未登录"

        return self.db.create_order(int(self.user_id), restaurant_name, items, total_price)

    def get_orders(self) -> list:
        if self.is_guest:
            return self.guest_orders

        if not self.user_id:
            return []

        return self.db.get_user_orders(int(self.user_id), limit=20)

    def get_order_tracking(self, order_id: int) -> dict:
        if self.is_guest:
            return None

        try:
            order_id_int = int(order_id)
        except (ValueError, TypeError):
            return None

        return self.db.get_order_tracking_info(order_id_int)

    def get_active_orders(self) -> list:
        if self.is_guest:
            active_statuses = ['已下单', '商家已接单', '配送中', '即将送达']
            return [o for o in self.guest_orders if o.get('status') in active_statuses]

        if not self.user_id:
            return []

        orders = self.db.get_user_orders(int(self.user_id))
        active_statuses = ['已下单', '商家已接单', '配送中', '即将送达']
        return [o for o in orders if o.get('status') in active_statuses]

    def get_order_by_id(self, order_id: str) -> dict:
        if self.is_guest:
            for order in self.guest_orders:
                if order.get("id") == order_id:
                    return order
            return None

        if not self.user_id:
            return None

        try:
            order_id_int = int(order_id.split('_')[-1] if '_' in str(order_id) else order_id)
        except:
            order_id_int = None

        if order_id_int:
            return self.db.get_order_by_id(order_id_int)
        return None

    def update_order_status(self, order_id: str, status: str) -> bool:
        if self.is_guest:
            for order in self.guest_orders:
                if order.get("id") == order_id:
                    order["status"] = status
                    return True
            return False

        try:
            order_id_int = int(order_id.split('_')[-1] if '_' in str(order_id) else order_id)
            return self.db.update_order_status(order_id_int, status)
        except:
            return False

    def change_password(self, old_password: str, new_password: str) -> tuple:
        if self.is_guest:
            return False, "游客模式无法修改密码"

        if not self.user_id:
            return False, "未登录"

        if len(new_password) < 6:
            return False, "新密码至少6位"

        if old_password == new_password:
            return False, "新密码不能与旧密码相同"

        return self.db.change_password(int(self.user_id), old_password, new_password)

    def validate_phone(self, phone: str) -> bool:
        import re
        return bool(re.match(r'^1[3-9]\d{9}$', phone))


user_session = UserSession()
local_auth = user_session
