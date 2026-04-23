# screens/order_screen.py
from kivy.clock import Clock
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineListItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton

from services.local_auth import user_session

from utils.fonts import chinese_font


class OrderScreen(MDScreen):
    """订单历史页"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 不再使用 OrderManager，改用 user_session

    def on_enter(self):
        """进入时加载订单（强制刷新）"""
        from services.local_auth import user_session

        print(f"[订单页面] 当前用户: {user_session.nickname}, 是否游客: {user_session.is_guest}")

        # 清空现有数据，强制重新加载
        orders_list = self.ids.orders_list
        orders_list.clear_widgets()

        self.load_orders()

    def load_orders(self):
        """加载历史订单"""
        orders_list = self.ids.orders_list
        orders_list.clear_widgets()

        empty_label = self.ids.get('empty_label')

        from services.local_auth import user_session

        # 设置空标签字体
        if empty_label and chinese_font:
            empty_label.font_name = chinese_font

        orders = user_session.get_orders()

        if not orders:
            if hasattr(self.ids, 'scroll_view'):
                self.ids.scroll_view.opacity = 0
                self.ids.scroll_view.disabled = True
            if empty_label:
                empty_label.opacity = 1
                if user_session.is_guest:
                    empty_label.text = "暂无订单\n（游客订单仅在本次会话有效）"
                else:
                    empty_label.text = "暂无订单"
            return

        if hasattr(self.ids, 'scroll_view'):
            self.ids.scroll_view.opacity = 1
            self.ids.scroll_view.disabled = False
        if empty_label:
            empty_label.opacity = 0

        for order in orders:
            shop_name = order.get('restaurant_name', '未知商家')
            total_price = order.get('total_price', 0)
            status = order.get('status', '未知状态')

            created_at = order.get('created_at', '')
            if created_at and len(created_at) > 16:
                created_at = created_at[:16]

            item = OneLineListItem(
                text=f"{shop_name}  {total_price}元  {status}",
                secondary_text=f"时间: {created_at}",
                on_release=lambda x, o=order: self.view_order_detail(o)
            )
            # 设置列表项字体
            if chinese_font:
                item.font_name = chinese_font
                if hasattr(item, 'ids') and 'text' in item.ids:
                    item.ids.text.font_name = chinese_font
            orders_list.add_widget(item)

    def view_order_detail(self, order):
        """查看订单详情"""
        from kivymd.uix.button import MDRaisedButton

        order_id = order.get('id', order.get('order_id', ''))
        status = order.get('status', '未知状态')

        # 判断是否为进行中的订单
        is_active = status in ['已下单', '商家已接单', '配送中', '即将送达']

        buttons = [
            MDFlatButton(
                text="关闭",
                on_release=lambda x: dialog.dismiss()
            )
        ]

        if is_active and order_id:
            buttons.append(
                MDRaisedButton(
                    text="追踪订单",
                    on_release=lambda x: [
                        dialog.dismiss(),
                        self.track_order(order_id)
                    ]
                )
            )

        dialog = MDDialog(
            title=f"订单 {order_id}",
            text=f"商家：{order.get('restaurant_name', order.get('shop', '未知'))}\n"
                 f"金额：¥{order.get('total_price', order.get('price', 0))}\n"
                 f"状态：{status}\n"
                 f"时间：{order.get('created_at', order.get('create_time', '未知'))}",
            buttons=buttons
        )
        dialog.open()

    def track_order(self, order_id):
        """跳转到追踪页面"""
        tracking_screen = self.manager.get_screen('tracking')
        tracking_screen._order_id = order_id
        self.manager.current = 'tracking'

    def go_home(self):
        """返回首页"""
        self.manager.current = 'home'
