# screens/tracking_screen.py - 优化刷新逻辑
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivymd.uix.boxlayout import MDBoxLayout

from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog

from services.local_auth import user_session
import random

from utils.fonts import chinese_font


class TrackingScreen(MDScreen):
    """订单追踪界面"""

    order_id = StringProperty("")
    status_text = StringProperty("加载中...")
    progress_value = NumericProperty(0)
    rider_info = StringProperty("")
    rider_phone = StringProperty("")
    eta_text = StringProperty("计算中...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.update_clock = None
        self.is_simulating = False
        self.status_to_value = {
            '已下单': 0,
            '商家已接单': 25,
            '配送中': 50,
            '即将送达': 75,
            '已送达': 100
        }

    def on_enter(self):
        """进入界面时加载追踪信息"""
        from services.local_auth import user_session

        print(f"[追踪页面] 当前用户: {user_session.nickname}, 是否游客: {user_session.is_guest}")

        self.simulation_step = 0
        self.sim_status = None
        self.sim_rider_name = None
        self.sim_rider_phone = None

        if self.update_clock:
            self.update_clock.cancel()
            self.update_clock = None

        if hasattr(self, '_order_id') and self._order_id:
            self.load_tracking(self._order_id)
        else:
            self.load_active_order()

    def load_tracking(self, order_id):
        """加载订单追踪信息"""
        self.order_id = str(order_id)
        self._load_tracking_info()

        if self.update_clock:
            self.update_clock.cancel()
        self.update_clock = Clock.schedule_interval(self._refresh_tracking, 10)

        if self.status_text not in ["已送达", "已完成"]:
            self._start_delivery_simulation()

    def _load_tracking_info(self):
        """加载追踪信息"""
        try:
            if not self.order_id or self.order_id == "无":
                return

            from services.local_auth import user_session

            order = None

            if user_session.is_guest:
                order = user_session.get_order_by_id(self.order_id)
            else:
                try:
                    if '_' in str(self.order_id):
                        for o in user_session.get_orders():
                            if o.get('display_order_id') == self.order_id:
                                order = o
                                break
                    else:
                        order = user_session.get_order_tracking(int(self.order_id))
                except (ValueError, TypeError):
                    for o in user_session.get_orders():
                        if o.get('display_order_id') == self.order_id:
                            order = o
                            break

            if order:
                self.order = order
                status = order.get('status', '未知')
                self.status_text = status
                self.progress_value = self.status_to_value.get(status, 0) / 100

                rider_name = order.get('rider_name') or ""
                phone = order.get('rider_phone') or ""
                self.rider_phone = str(phone) if phone else ""

                if rider_name:
                    self.rider_info = f"骑手：{rider_name}\n电话：{self.rider_phone}"
                else:
                    self.rider_info = "骑手正在分配中..."
            else:
                self.status_text = "订单不存在"
                self.rider_info = ""
                self.rider_phone = ""
                self.progress_value = 0

        except Exception as e:
            print(f"加载追踪信息失败: {e}")

    def load_active_order(self):
        """加载最新的进行中订单"""
        orders = user_session.get_active_orders()
        print(f"[追踪] 进行中订单: {orders}")
        if orders:
            self.load_tracking(orders[0]['id'])
        else:
            self.status_text = "没有进行中的订单"
            self.rider_info = "暂无配送信息"
            self.rider_phone = ""
            self.order_id = "无"
            self.eta_text = ""
            self.progress_value = 0

    def _load_from_database(self):
        """从数据库加载订单状态 - 只在非模拟状态下更新UI"""
        try:
            if not self.order_id or self.order_id == "无":
                return

            order_id_int = int(self.order_id)
            result = user_session.get_order_tracking(order_id_int)

            if result:
                status = result.get('status', '已下单')

                if self.is_simulating:
                    current_progress = self.progress_value
                    db_progress = self.status_to_value.get(status, 0)
                    if db_progress > current_progress:
                        self.status_text = status
                        self.progress_value = db_progress
                        print(f"[数据库] 进度更新: {db_progress} > {current_progress}")
                    else:
                        print(f"[数据库] 跳过更新，当前进度 {current_progress} >= 数据库 {db_progress}")
                    return

                self.status_text = status
                self.progress_value = self.status_to_value.get(status, 0)

                rider_name = result.get('rider_name') or ""
                phone = result.get('rider_phone') or ""
                self.rider_phone = str(phone) if phone else ""

                if rider_name:
                    self.rider_info = f"骑手：{rider_name}\n电话：{self.rider_phone}"
                else:
                    self.rider_info = "骑手正在分配中..."

                if status == "已送达":
                    self.eta_text = "已送达"
                elif status == "即将送达":
                    self.eta_text = "约5分钟"
                elif status == "配送中":
                    self.eta_text = "预计20-30分钟"
                elif status == "商家已接单":
                    self.eta_text = "预计30-40分钟"
                else:
                    self.eta_text = "计算中..."
            else:
                if not self.is_simulating:
                    self.status_text = "订单不存在"
                    self.rider_info = ""
                    self.rider_phone = ""
                    self.progress_value = 0

        except Exception as e:
            print(f"加载追踪信息失败: {e}")

    def _update_database_status(self, status, rider_name=None, rider_phone=None):
        """更新数据库中的订单状态"""
        try:
            if not self.order_id or self.order_id == "无":
                return

            order_id_int = int(self.order_id)

            user_session.db.update_order_status(order_id_int, status)

            if rider_name and rider_phone:
                import sqlite3
                conn = sqlite3.connect("./data/waimai.db")
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE orders SET rider_name = ?, rider_phone = ? WHERE id = ?",
                    (rider_name, rider_phone, order_id_int)
                )
                conn.commit()
                conn.close()

            print(f"[数据库] 订单 {self.order_id} 状态更新为: {status}")

        except Exception as e:
            print(f"更新数据库失败: {e}")

    def _start_delivery_simulation(self):
        """启动模拟配送流程"""
        current_status = self.status_text
        print(f"[模拟] 启动配送，当前状态: {current_status}")

        self.is_simulating = True

        if current_status == "已下单":
            Clock.schedule_once(self._simulate_rider_accept, 3)
        elif current_status == "商家已接单":
            Clock.schedule_once(self._simulate_start_delivery, 3)
        elif current_status == "配送中":
            Clock.schedule_once(self._simulate_almost_arrive, 5)
        elif current_status == "即将送达":
            Clock.schedule_once(self._simulate_delivered, 3)

    def _simulate_rider_accept(self, dt):
        """模拟骑手接单"""
        if self.status_text != "已下单":
            print(f"[模拟] 状态已变化，跳过接单")
            return

        rider_names = ["张师傅", "李师傅", "王师傅", "刘师傅", "陈师傅"]
        phone = f"138{random.randint(10000000, 99999999)}"
        rider_name = random.choice(rider_names)

        self._update_database_status("商家已接单", rider_name, phone)

        self.status_text = "商家已接单"
        self.progress_value = 25
        self.rider_phone = phone
        self.rider_info = f"骑手：{rider_name}\n电话：{phone}"
        self.eta_text = "预计30-40分钟"

        print(f"[模拟] {rider_name} 已接单，电话：{phone}")

        Clock.schedule_once(self._simulate_start_delivery, 3)

    def _simulate_start_delivery(self, dt):
        """模拟开始配送"""
        if self.status_text not in ["商家已接单", "已下单"]:
            print(f"[模拟] 状态已变化，跳过开始配送")
            return

        self._update_database_status("配送中")

        self.status_text = "配送中"
        self.progress_value = 50
        self.eta_text = "预计20-30分钟"

        print("[模拟] 骑手正在赶往商家取餐...")

        Clock.schedule_once(self._simulate_almost_arrive, 5)

    def _simulate_almost_arrive(self, dt):
        """模拟即将送达"""
        if self.status_text != "配送中":
            print(f"[模拟] 状态已变化，跳过即将送达")
            return

        self._update_database_status("即将送达")

        self.status_text = "即将送达"
        self.progress_value = 75
        self.eta_text = "约5分钟"

        print("[模拟] 您的餐品即将送达，请准备取餐")

        Clock.schedule_once(self._simulate_delivered, 3)

    def _simulate_delivered(self, dt):
        """模拟已送达"""
        if self.status_text == "已送达":
            return

        self._update_database_status("已完成")

        self.status_text = "已送达"
        self.progress_value = 100
        self.eta_text = "已送达"
        self.is_simulating = False

        print("[模拟] 您的餐品已送达，祝您用餐愉快！")

        if self.update_clock:
            self.update_clock.cancel()
            self.update_clock = None

    def _refresh_tracking(self, dt):
        """刷新追踪信息"""
        self._load_from_database()

    def on_leave(self):
        """离开界面时停止定时器"""
        print("[追踪] 离开追踪页面")
        if self.update_clock:
            self.update_clock.cancel()
            self.update_clock = None
        self.is_simulating = False

    def go_back(self):
        """返回上一页"""
        self.manager.current = 'orders'

    def call_rider(self):
        """联系骑手 - 显示骑手电话"""

        if self.rider_phone:
            content = MDBoxLayout(
                orientation="vertical",
                spacing=10,
                padding=20,
                adaptive_height=True
            )

            info_label = MDLabel(
                text=f"骑手电话：{self.rider_phone}",
                halign="center",
                size_hint_y=None,
                height=50
            )
            if chinese_font:
                info_label.font_name = chinese_font

            content.add_widget(info_label)

            dialog = MDDialog(
                title=f"[font={chinese_font}]联系骑手[/font]" if chinese_font else "联系骑手",
                type="custom",
                content_cls=content,
                buttons=[
                    MDFlatButton(
                        text="关闭",
                        on_release=lambda x: dialog.dismiss()
                    ),
                    MDRaisedButton(
                        text="呼叫",
                        on_release=lambda x: [
                            dialog.dismiss(),
                            self.show_snackbar(f"正在呼叫 {self.rider_phone}...")
                        ]
                    )
                ]
            )

            if chinese_font:
                if hasattr(dialog, 'title_label'):
                    dialog.title_label.font_name = chinese_font
                for btn in dialog.buttons:
                    if hasattr(btn, 'font_name'):
                        btn.font_name = chinese_font

            dialog.open()
        else:
            self.show_snackbar("暂无可联系的骑手")

    def show_snackbar(self, text):
        """显示提示"""
        from kivymd.uix.snackbar import MDSnackbar
        from kivymd.uix.label import MDLabel
        snackbar = MDSnackbar(MDLabel(text=text))
        snackbar.open()
