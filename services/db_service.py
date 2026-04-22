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
        # 确保目录存在
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
                updated_at VARCHAR(20) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # orders 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
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
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # 检查并添加缺失的列
        self._add_missing_columns(cursor)

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

    # ========== 用户相关 ==========

    def register_user(self, username: str, password: str, phone: str) -> tuple:
        """注册用户"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 检查用户名是否存在
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return False, "用户名已存在"

            # 密码哈希
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 插入用户
            cursor.execute('''
                INSERT INTO users (username, password_hash, phone, created_at)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, phone, created_at))

            user_id = cursor.lastrowid

            # 初始化默认偏好
            cursor.execute('''
                INSERT INTO preferences (user_id, spiciness_level, budget_range, avoid_foods, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, '微辣', '30', '[]', created_at))

            conn.commit()
            conn.close()
            return True, user_id

        except Exception as e:
            return False, str(e)

    def login_user(self, username: str, password: str) -> tuple:
        """用户登录"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            password_hash = hashlib.sha256(password.encode()).hexdigest()

            cursor.execute('''
                SELECT id, username, phone FROM users 
                WHERE username = ? AND password_hash = ?
            ''', (username, password_hash))

            user = cursor.fetchone()
            conn.close()

            if user:
                return True, dict(user)
            else:
                return False, "用户名或密码错误"

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

            # 验证旧密码
            old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            cursor.execute(
                "SELECT id FROM users WHERE id = ? AND password_hash = ?",
                (user_id, old_hash)
            )
            if not cursor.fetchone():
                return False, "旧密码错误"

            # 更新新密码
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

    # ========== 偏好相关 ==========

    def get_preferences(self, user_id: int) -> Dict:
        """获取用户偏好"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM preferences WHERE user_id = ?", (user_id,))
        prefs = cursor.fetchone()
        conn.close()

        if prefs:
            prefs_dict = dict(prefs)
            # 解析 avoid_foods JSON
            try:
                avoid_foods = prefs_dict.get('avoid_foods', '[]')
                if isinstance(avoid_foods, str):
                    prefs_dict['avoid_foods'] = json.loads(avoid_foods)
                else:
                    prefs_dict['avoid_foods'] = avoid_foods if avoid_foods else []
            except:
                prefs_dict['avoid_foods'] = []

            # 关键修复：spicy_level 应该等于 spiciness_level（数据库存的值）
            prefs_dict['spicy_level'] = prefs_dict.get('spiciness_level', '微辣')
            prefs_dict['default_budget'] = int(prefs_dict.get('budget_range', '30'))

            print(f"从数据库读取偏好: spicy_level={prefs_dict['spicy_level']}, budget={prefs_dict['default_budget']}")
            return prefs_dict
        else:
            print(f"用户 {user_id} 没有偏好记录，返回默认")
            return {
                'user_id': user_id,
                'spiciness_level': '微辣',
                'spicy_level': '微辣',
                'budget_range': '30',
                'default_budget': 30,
                'default_address': '',
                'avoid_foods': []
            }

    def update_preferences(self, user_id: int, prefs: Dict) -> bool:
        """更新用户偏好"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 处理 avoid_foods 为 JSON 字符串
            avoid_foods = prefs.get('avoid_foods', [])
            if isinstance(avoid_foods, list):
                avoid_foods_json = json.dumps(avoid_foods, ensure_ascii=False)
            else:
                avoid_foods_json = '[]'

            # 修复：优先使用 spicy_level，如果没有再用 spiciness_level
            # 用户保存时传的是 spicy_level，所以要先取 spicy_level
            spiciness = prefs.get('spicy_level', prefs.get('spiciness_level', '微辣'))

            # 修复：优先使用 default_budget，如果没有再用 budget_range
            budget = prefs.get('default_budget', prefs.get('budget_range', '30'))

            # 获取地址
            address = prefs.get('default_address', '')

            print(f"保存到数据库: spicy_level={spiciness}, budget={budget}, avoid={avoid_foods_json}")

            # 使用 INSERT OR REPLACE 确保数据存在
            cursor.execute('''
                INSERT OR REPLACE INTO preferences 
                (user_id, spiciness_level, budget_range, default_address, avoid_foods, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                spiciness,
                str(budget),
                address,
                avoid_foods_json,
                updated_at
            ))

            conn.commit()

            # 验证是否保存成功
            cursor.execute("SELECT * FROM preferences WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                print(f"偏好保存成功: user_id={user_id}, spiciness_level={result['spiciness_level']}")
                return True
            else:
                print(f"偏好保存失败: user_id={user_id}")
                return False

        except Exception as e:
            print(f"更新偏好失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ========== 订单相关 ==========

    def create_order(self, user_id: int, restaurant_name: str,
                     items: List[Dict], total_price: float) -> tuple:
        """创建订单"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            items_json = json.dumps(items, ensure_ascii=False)

            cursor.execute('''
                INSERT INTO orders 
                (user_id, restaurant_name, items_json, total_price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, restaurant_name, items_json, str(total_price), '已下单', created_at))

            order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return True, order_id

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
            try:
                order_dict['items'] = json.loads(order_dict['items_json'])
            except:
                order_dict['items'] = []
            del order_dict['items_json']
            result.append(order_dict)

        return result

    def get_order_by_id(self, order_id: int) -> Optional[Dict]:
        """根据ID获取订单"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()

        if order:
            order_dict = dict(order)
            try:
                order_dict['items'] = json.loads(order_dict['items_json'])
            except:
                order_dict['items'] = []
            del order_dict['items_json']
            return order_dict
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

    def get_order_tracking_info(self, order_id: int) -> Optional[Dict]:
        """获取订单追踪信息"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 使用 id 而不是 order_id（因为主键是 id）
            cursor.execute('''
                SELECT id, restaurant_name, status, created_at, 
                       estimated_delivery_time, rider_name, rider_phone, 
                       rider_location, current_status_time
                FROM orders 
                WHERE id = ?
            ''', (order_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            print(f"获取追踪信息失败: {e}")
            import traceback
            traceback.print_exc()
            return None


# 单例
_db_service = None


def get_db_service():
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
