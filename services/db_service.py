# services/db_service.py
import sqlite3
import json
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, List

from utils.paths import get_db_path, get_data_dir


class DatabaseService:
    """SQLite 数据库服务"""

    def __init__(self):
        self.db_path = get_db_path()
        self._init_db()

    def _get_connection(self):
        """获取数据库连接"""
        db_dir = os.path.dirname(self.db_path)
        os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # users 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                created_at VARCHAR(20) NOT NULL
            )
        ''')

        # preferences 表
        cursor.execute('''
                CREATE TABLE IF NOT EXISTS preferences (
                    user_id INTEGER PRIMARY KEY,
                    spiciness_level VARCHAR(20) NOT NULL DEFAULT '微辣',
                    budget_range VARCHAR(20) DEFAULT '30',
                    default_address VARCHAR(200),
                    avoid_foods TEXT,
                    last_summary_count INTEGER DEFAULT 0,
                    updated_at VARCHAR(20) NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

        cursor.execute("PRAGMA table_info(preferences)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        if 'last_summary_count' not in existing_columns:
            cursor.execute('ALTER TABLE preferences ADD COLUMN last_summary_count INTEGER DEFAULT 0')
            print("[数据库] 已为 preferences 表添加 last_summary_count 字段")

        # orders 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_seq INTEGER NOT NULL DEFAULT 1,
                restaurant_name VARCHAR(100) NOT NULL,
                items_json TEXT NOT NULL,
                total_price VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT '已下单',
                created_at VARCHAR(20) NOT NULL,
                completed_at VARCHAR(20),
                estimated_delivery_time VARCHAR(20),
                rider_name VARCHAR(50),
                rider_phone VARCHAR(20),
                rider_location VARCHAR(100),
                current_status_time VARCHAR(20),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, order_seq)
            )
        ''')

        # 收藏表
        cursor.execute('''
               CREATE TABLE IF NOT EXISTS favorites (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER NOT NULL,
                   restaurant_name VARCHAR(100) NOT NULL,
                   dish_name VARCHAR(100) NOT NULL,
                   dish_price DECIMAL(10,2),
                   created_at VARCHAR(20) NOT NULL,
                   FOREIGN KEY (user_id) REFERENCES users(id),
                   UNIQUE(user_id, restaurant_name, dish_name)
               )
           ''')

        # 避雷表
        cursor.execute('''
               CREATE TABLE IF NOT EXISTS blacklist (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER NOT NULL,
                   restaurant_name VARCHAR(100) NOT NULL,
                   dish_name VARCHAR(100) NOT NULL,
                   reason VARCHAR(200),
                   created_at VARCHAR(20) NOT NULL,
                   FOREIGN KEY (user_id) REFERENCES users(id),
                   UNIQUE(user_id, restaurant_name, dish_name)
               )
           ''')

        self._add_missing_columns(cursor)

        cursor.execute("PRAGMA table_info(orders)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        if 'order_seq' not in existing_columns:
            cursor.execute('ALTER TABLE orders ADD COLUMN order_seq INTEGER DEFAULT 1')
            cursor.execute('''
                UPDATE orders SET order_seq = (
                    SELECT COUNT(*) FROM orders o2 
                    WHERE o2.user_id = orders.user_id AND o2.id <= orders.id
                )
            ''')
            print("[数据库] 已为现有订单填充 order_seq")
        self._create_demo_data(cursor)

        conn.commit()
        conn.close()
        print(f"数据库初始化完成: {self.db_path}")

    def _add_missing_columns(self, cursor):
        """为已存在的表添加缺失的列"""
        cursor.execute("PRAGMA table_info(orders)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        new_columns = {
            'estimated_delivery_time': 'VARCHAR(20)',
            'rider_name': 'VARCHAR(50)',
            'rider_phone': 'VARCHAR(20)',
            'rider_location': 'VARCHAR(100)',
            'current_status_time': 'VARCHAR(20)'
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE orders ADD COLUMN {col_name} {col_type}')
                    print(f"已添加列: {col_name}")
                except Exception as e:
                    print(f"添加列 {col_name} 失败: {e}")


    def register_user(self, username: str, password: str, phone: str) -> tuple:
        """注册用户
        username: 昵称
        phone: 手机号
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE phone = ?", (phone,))
            if cursor.fetchone():
                return False, "该手机号已注册"

            password_hash = hashlib.sha256(password.encode()).hexdigest()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO users (username, password_hash, phone, created_at)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, phone, created_at))

            user_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO preferences (user_id, spiciness_level, budget_range, avoid_foods, last_summary_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, '微辣', '30', '[]', 0, created_at))

            conn.commit()
            conn.close()
            return True, user_id

        except Exception as e:
            return False, str(e)

    def login_user(self, phone: str, password: str) -> tuple:
        """用户登录
        phone: 手机号
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            password_hash = hashlib.sha256(password.encode()).hexdigest()

            # 用手机号查询
            cursor.execute('''
                SELECT id, username, phone FROM users 
                WHERE phone = ? AND password_hash = ?
            ''', (phone, password_hash))

            user = cursor.fetchone()
            conn.close()

            if user:
                return True, dict(user)
            else:
                return False, "手机号或密码错误"

        except Exception as e:
            return False, str(e)

    def get_user(self, user_id: int) -> Optional[Dict]:
        """获取用户信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        conn.close()
        return dict(user) if user else None

    def change_password(self, user_id: int, old_password: str, new_password: str) -> tuple:
        """修改用户密码"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            cursor.execute(
                "SELECT id FROM users WHERE id = ? AND password_hash = ?",
                (user_id, old_hash)
            )
            if not cursor.fetchone():
                return False, "旧密码错误"

            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id)
            )

            conn.commit()
            conn.close()
            return True, "密码修改成功"

        except Exception as e:
            return False, str(e)

    def get_preferences(self, user_id: int) -> Dict:
        """获取用户偏好"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM preferences WHERE user_id = ?", (user_id,))
        prefs = cursor.fetchone()
        conn.close()

        if prefs:
            prefs_dict = dict(prefs)
            # 解析 avoid_foods
            try:
                avoid_foods = prefs_dict.get('avoid_foods', '[]')
                if isinstance(avoid_foods, str):
                    prefs_dict['avoid_foods'] = json.loads(avoid_foods)
                else:
                    prefs_dict['avoid_foods'] = avoid_foods if avoid_foods else []
            except:
                prefs_dict['avoid_foods'] = []

            prefs_dict['spicy_level'] = prefs_dict.get('spiciness_level', '微辣')
            prefs_dict['default_budget'] = int(prefs_dict.get('budget_range', '30'))

            # 确保 last_summary_count 存在
            if 'last_summary_count' not in prefs_dict:
                prefs_dict['last_summary_count'] = 0

            print(f"[数据库] 读取偏好: user_id={user_id}, last_summary_count={prefs_dict.get('last_summary_count', 0)}")
            return prefs_dict
        else:
            print(f"[数据库] 用户 {user_id} 没有偏好记录，返回默认")
            return {
                'user_id': user_id,
                'spiciness_level': '微辣',
                'spicy_level': '微辣',
                'budget_range': '30',
                'default_budget': 30,
                'default_address': '',
                'avoid_foods': [],
                'last_summary_count': 0
            }

    def update_preferences(self, user_id: int, prefs: Dict) -> bool:
        """更新用户偏好"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            avoid_foods = prefs.get('avoid_foods', [])
            if isinstance(avoid_foods, list):
                avoid_foods_json = json.dumps(avoid_foods, ensure_ascii=False)
            else:
                avoid_foods_json = '[]'

            spiciness = prefs.get('spicy_level', prefs.get('spiciness_level', '微辣'))
            budget = prefs.get('default_budget', prefs.get('budget_range', '30'))
            address = prefs.get('default_address', '')
            last_summary_count = prefs.get('last_summary_count', 0)

            print(f"[数据库] 保存偏好: user_id={user_id}, last_summary_count={last_summary_count}")

            cursor.execute("SELECT 1 FROM preferences WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone()

            if exists:
                cursor.execute('''
                    UPDATE preferences 
                    SET spiciness_level=?, budget_range=?, default_address=?, 
                        avoid_foods=?, last_summary_count=?, updated_at=?
                    WHERE user_id=?
                ''', (spiciness, str(budget), address, avoid_foods_json, last_summary_count, updated_at, user_id))
            else:
                cursor.execute('''
                    INSERT INTO preferences 
                    (user_id, spiciness_level, budget_range, default_address, avoid_foods, last_summary_count, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, spiciness, str(budget), address, avoid_foods_json, last_summary_count, updated_at))

            conn.commit()

            cursor.execute("SELECT last_summary_count FROM preferences WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                print(f"[数据库] 保存后验证: last_summary_count={row[0]}")

            conn.close()
            return True

        except Exception as e:
            print(f"更新偏好失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_order(self, user_id: int, restaurant_name: str,
                     items: List[Dict], total_price: float) -> tuple:
        """创建订单，返回 (success, display_order_id)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            items_json = json.dumps(items, ensure_ascii=False)

            # 获取该用户的最大订单序号
            cursor.execute(
                "SELECT COALESCE(MAX(order_seq), 0) FROM orders WHERE user_id = ?",
                (user_id,)
            )
            max_seq = cursor.fetchone()[0]
            new_seq = max_seq + 1

            cursor.execute('''
                INSERT INTO orders 
                (user_id, order_seq, restaurant_name, items_json, total_price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, new_seq, restaurant_name, items_json, str(total_price), '已下单', created_at))

            conn.commit()
            conn.close()

            display_order_id = f"{user_id}_{new_seq}"
            return True, display_order_id

        except Exception as e:
            return False, str(e)

    def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict]:
        """获取用户订单列表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM orders 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))

        orders = cursor.fetchall()
        conn.close()

        result = []
        for order in orders:
            order_dict = dict(order)
            order_dict['display_order_id'] = f"{user_id}_{order_dict['order_seq']}"
            try:
                order_dict['items'] = json.loads(order_dict['items_json'])
            except:
                order_dict['items'] = []
            del order_dict['items_json']
            result.append(order_dict)

        return result

    def get_order_by_id(self, order_id: int) -> Optional[Dict]:
        """根据数据库ID获取订单"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()

        if order:
            order_dict = dict(order)
            order_dict['display_order_id'] = f"{order_dict['user_id']}_{order_dict['order_seq']}"
            try:
                order_dict['items'] = json.loads(order_dict['items_json'])
            except:
                order_dict['items'] = []
            del order_dict['items_json']
            return order_dict
        return None

    def get_order_tracking_info(self, order_id: int) -> Optional[Dict]:
        """获取订单追踪信息"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, user_id, order_seq, restaurant_name, status, created_at, 
                       estimated_delivery_time, rider_name, rider_phone, 
                       rider_location, current_status_time
                FROM orders 
                WHERE id = ?
            ''', (order_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                result = dict(row)
                result['display_order_id'] = f"{result['user_id']}_{result['order_seq']}"
                return result
            return None

        except Exception as e:
            print(f"获取追踪信息失败: {e}")
            return None

    def update_order_status(self, order_id: int, status: str) -> bool:
        """更新订单状态"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == '已完成' else None

            if completed_at:
                cursor.execute('''
                    UPDATE orders SET status = ?, completed_at = ? WHERE id = ?
                ''', (status, completed_at, order_id))
            else:
                cursor.execute('''
                    UPDATE orders SET status = ? WHERE id = ?
                ''', (status, order_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"更新订单状态失败: {e}")
            return False

    def add_favorite(self, user_id: int, restaurant_name: str, dish_name: str, dish_price: float = None) -> bool:
        """添加收藏"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT OR IGNORE INTO favorites (user_id, restaurant_name, dish_name, dish_price, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, restaurant_name, dish_name, dish_price, created_at))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加收藏失败: {e}")
            return False

    def remove_favorite(self, user_id: int, restaurant_name: str, dish_name: str) -> bool:
        """移除收藏"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM favorites 
                WHERE user_id = ? AND restaurant_name = ? AND dish_name = ?
            ''', (user_id, restaurant_name, dish_name))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"移除收藏失败: {e}")
            return False

    def get_favorites(self, user_id: int) -> List[Dict]:
        """获取用户收藏列表"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, restaurant_name, dish_name, dish_price, created_at
                FROM favorites 
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))

            rows = cursor.fetchall()
            conn.close()
            result = [dict(row) for row in rows]
            print(f"[DB] get_favorites 返回 {len(result)} 条记录")
            return result
        except Exception as e:
            print(f"获取收藏列表失败: {e}")
            return []

    def is_favorite(self, user_id: int, restaurant_name: str, dish_name: str) -> bool:
        """检查是否已收藏"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT 1 FROM favorites 
                WHERE user_id = ? AND restaurant_name = ? AND dish_name = ?
            ''', (user_id, restaurant_name, dish_name))

            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            print(f"检查收藏失败: {e}")
            return False

    def add_blacklist(self, user_id: int, restaurant_name: str, dish_name: str, reason: str = None) -> bool:
        """添加避雷"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT OR IGNORE INTO blacklist (user_id, restaurant_name, dish_name, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, restaurant_name, dish_name, reason, created_at))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加避雷失败: {e}")
            return False

    def remove_blacklist(self, user_id: int, restaurant_name: str, dish_name: str) -> bool:
        """移除避雷"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM blacklist 
                WHERE user_id = ? AND restaurant_name = ? AND dish_name = ?
            ''', (user_id, restaurant_name, dish_name))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"移除避雷失败: {e}")
            return False

    def get_blacklist(self, user_id: int) -> List[Dict]:
        """获取用户避雷列表"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, restaurant_name, dish_name, reason, created_at
                FROM blacklist 
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))

            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"获取避雷列表失败: {e}")
            return []

    def is_blacklisted(self, user_id: int, restaurant_name: str, dish_name: str) -> bool:
        """检查是否已避雷"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT 1 FROM blacklist 
                WHERE user_id = ? AND restaurant_name = ? AND dish_name = ?
            ''', (user_id, restaurant_name, dish_name))

            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            print(f"检查避雷失败: {e}")
            return False

    def _create_demo_data(self, cursor):
        """创建演示数据（仅当 test1 用户不存在时）"""
        import hashlib
        import json
        from datetime import datetime, timedelta
        import random

        cursor.execute("SELECT id FROM users WHERE username = 'test_20dingdan'")
        existing_user = cursor.fetchone()

        if existing_user:
            print("[演示数据] 用户 test_20dingdan 已存在，跳过创建")
            return

        print("[演示数据] 正在创建演示用户 test_20dingdan...")

        try:
            from data.mock_restaurants import RESTAURANTS, DISHES_BY_RESTAURANT
        except ImportError:
            print("[演示数据] 无法导入 mock 数据，跳过")
            return

        cursor.execute("SELECT MAX(id) FROM users")
        max_id = cursor.fetchone()[0]
        user_id = max_id + 1 if max_id else 100

        username = "test_20dingdan"
        password_hash = hashlib.sha256("123456".encode()).hexdigest()
        phone = "13800138000"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO users (id, username, password_hash, phone, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, password_hash, phone, created_at))

        cursor.execute('''
            INSERT INTO preferences (user_id, spiciness_level, budget_range, default_address, avoid_foods, last_summary_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, '微辣', '20', '', '[]', 0, created_at))

        all_items = []
        drinks_keywords = ["奶茶", "咖啡", "柠檬茶", "果茶", "拿铁", "卡布奇诺", "美式", "果汁", "可乐", "雪碧"]

        for restaurant in RESTAURANTS:
            if restaurant["cuisine"] in ["火锅", "串串"]:
                continue
            dishes = DISHES_BY_RESTAURANT.get(restaurant["id"], [])
            for dish in dishes:
                dish_name = dish["name"]
                is_drink = any(kw in dish_name for kw in drinks_keywords)
                if not is_drink:
                    all_items.append({
                        "restaurant_name": restaurant["name"],
                        "dish_name": dish_name,
                        "dish_price": dish["price"],
                    })

        print(f"[演示数据] 可用菜品数量: {len(all_items)}")

        if not all_items:
            print("[演示数据] 没有可用菜品，跳过订单创建")
            return

        current_time = datetime.now()

        for i in range(19):
            item = random.choice(all_items)
            order_seq = i + 1
            total_price = round(random.uniform(35, 45), 1)
            items_json = json.dumps([{
                "dish_name": item["dish_name"],
                "price": item["dish_price"],
                "quantity": 1
            }], ensure_ascii=False)

            days_ago = 19 - i
            created_at_order = (current_time - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO orders 
                (user_id, order_seq, restaurant_name, items_json, total_price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
            user_id, order_seq, item["restaurant_name"], items_json, str(total_price), '已完成', created_at_order))

        print(f"[演示数据] 创建完成！")
        print(f"  用户ID: {user_id}")
        print(f"  账号: test_20dingdan")
        print(f"  密码: 123456")
        print(f"  订单数: 19")


# 单例
_db_service = None


def get_db_service():
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
