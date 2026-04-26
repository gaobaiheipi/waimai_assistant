# screens/order_screen.py
from kivy.clock import Clock
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineListItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.snackbar import Snackbar

from services.db_service import get_db_service
from services.local_auth import user_session
from utils.fonts import chinese_font


class OrderScreen(MDScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_enter(self):
        from services.local_auth import user_session

        print(f"[订单页面] 当前用户: {user_session.nickname}, 是否游客: {user_session.is_guest}")

        orders_list = self.ids.orders_list
        orders_list.clear_widgets()

        self.load_orders()

    def load_orders(self):
        """加载历史订单"""
        orders_list = self.ids.orders_list
        orders_list.clear_widgets()

        empty_label = self.ids.get('empty_label')

        from services.local_auth import user_session

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

        # 按 order_seq 数值降序排序（最新的在前）
        if user_session.is_guest:
            # 游客订单按创建时间排序
            orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        else:
            # 注册用户按 order_seq 数值降序排序
            orders.sort(key=lambda x: x.get('order_seq', 0), reverse=True)

        for order in orders:
            shop_name = order.get('restaurant_name', '未知商家')
            total_price = order.get('total_price', 0)
            status = order.get('status', '未知状态')

            # 使用 display_order_id 作为订单号显示
            order_id = order.get('display_order_id', order.get('id', ''))
            created_at = order.get('created_at', '')
            if created_at and len(created_at) > 16:
                created_at = created_at[:16]

            # 格式化显示
            display_text = f"订单 {order_id}  {shop_name}  {total_price}元  {status}"

            item = OneLineListItem(
                text=display_text,
                secondary_text=f"时间: {created_at}",
                on_release=lambda x, o=order: self.view_order_detail(o)
            )
            if chinese_font:
                item.font_name = chinese_font
                if hasattr(item, 'ids') and 'text' in item.ids:
                    item.ids.text.font_name = chinese_font
            orders_list.add_widget(item)

    def view_order_detail(self, order):
        """查看订单详情"""

        order_id = order.get('display_order_id', order.get('id', ''))
        status = order.get('status', '未知状态')
        restaurant_name = order.get('restaurant_name', '')

        items = order.get('items', [])
        first_item = items[0] if items else {}
        dish_name = first_item.get('dish_name', '')
        dish_price = first_item.get('price', 0)

        is_active = status in ['已下单', '商家已接单', '配送中', '即将送达']
        is_completed = status in ['已完成', '已送达']

        content = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            padding=20,
            adaptive_height=True
        )

        content_text = (
            f"商家：{restaurant_name}\n"
            f"菜品：{dish_name}\n"
            f"金额：¥{order.get('total_price', 0)}\n"
            f"状态：{status}\n"
            f"时间：{order.get('created_at', '未知')}"
        )

        info_label = MDLabel(
            text=content_text,
            halign="left",
            size_hint_y=None,
            height=180
        )
        if chinese_font:
            info_label.font_name = chinese_font

        content.add_widget(info_label)

        buttons = [
            MDFlatButton(
                text="关闭",
                on_release=lambda x: dialog.dismiss()
            )
        ]

        if is_active and order_id:
            track_btn = MDRaisedButton(
                text="追踪订单",
                on_release=lambda x: [
                    dialog.dismiss(),
                    self.track_order(order_id)
                ]
            )
            if chinese_font:
                track_btn.font_name = chinese_font
            buttons.append(track_btn)

        if is_completed and not user_session.is_guest:
            db = get_db_service()
            user_id = int(user_session.user_id)

            is_faved = db.is_favorite(user_id, restaurant_name, dish_name)
            is_blocked = db.is_blacklisted(user_id, restaurant_name, dish_name)

            def add_favorite(*args):
                if is_blocked:
                    snackbar = Snackbar(
                        MDLabel(text="该菜品已在避雷列表中，无法收藏", theme_text_color="Custom",
                                text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()
                    return
                if db.add_favorite(user_id, restaurant_name, dish_name, dish_price):
                    snackbar = Snackbar(
                        MDLabel(text="已添加到收藏", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()
                    dialog.dismiss()
                else:
                    snackbar = Snackbar(
                        MDLabel(text="添加失败", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()

            def remove_favorite(*args):
                if db.remove_favorite(user_id, restaurant_name, dish_name):
                    snackbar = Snackbar(
                        MDLabel(text="已移除收藏", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()
                    dialog.dismiss()
                else:
                    snackbar = Snackbar(
                        MDLabel(text="移除失败", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()

            def add_blacklist(*args):
                if is_faved:
                    snackbar = Snackbar(
                        MDLabel(text="该菜品已在收藏列表中，无法避雷", theme_text_color="Custom",
                                text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()
                    return
                if db.add_blacklist(user_id, restaurant_name, dish_name):
                    snackbar = Snackbar(
                        MDLabel(text="已添加到避雷列表", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()
                    dialog.dismiss()
                else:
                    snackbar = Snackbar(
                        MDLabel(text="添加失败", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()

            def remove_blacklist(*args):
                if db.remove_blacklist(user_id, restaurant_name, dish_name):
                    snackbar = Snackbar(
                        MDLabel(text="已移除避雷", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()
                    dialog.dismiss()
                else:
                    snackbar = Snackbar(
                        MDLabel(text="移除失败", theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                        duration=1.5
                    )
                    snackbar.open()

            if is_faved:
                fav_btn = MDRaisedButton(text="取消收藏", on_release=remove_favorite)
            else:
                fav_btn = MDRaisedButton(text="收藏", on_release=add_favorite)

            if is_blocked:
                block_btn = MDRaisedButton(text="取消避雷", on_release=remove_blacklist)
            else:
                block_btn = MDRaisedButton(text="避雷", on_release=add_blacklist)

            if is_faved:
                block_btn.disabled = True
                block_btn.md_bg_color = (0.7, 0.7, 0.7, 1)
            if is_blocked:
                fav_btn.disabled = True
                fav_btn.md_bg_color = (0.7, 0.7, 0.7, 1)

            if chinese_font:
                fav_btn.font_name = chinese_font
                block_btn.font_name = chinese_font

            buttons.insert(0, fav_btn)
            buttons.insert(1, block_btn)

        dialog = MDDialog(
            title=f"[font={chinese_font}]订单 {order_id}[/font]" if chinese_font else f"订单 {order_id}",
            type="custom",
            content_cls=content,
            buttons=buttons
        )

        # 设置标题和按钮字体
        if chinese_font:
            if hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            for btn in dialog.buttons:
                if hasattr(btn, 'font_name'):
                    btn.font_name = chinese_font
            # 设置内容字体
            for child in content.children:
                if hasattr(child, 'font_name'):
                    child.font_name = chinese_font

        dialog.open()

    def track_order(self, order_id):
        tracking_screen = self.manager.get_screen('tracking')
        tracking_screen._order_id = order_id
        self.manager.current = 'tracking'

    def go_home(self):
        self.manager.current = 'home'
