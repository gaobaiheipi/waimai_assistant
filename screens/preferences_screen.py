# screens/preferences_screen.py
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.chip import MDChip, MDChipText
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.list import MDList, OneLineListItem, OneLineAvatarIconListItem
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDIconButton
from kivymd.uix.list import OneLineAvatarIconListItem

from services.db_service import get_db_service
from services.local_auth import user_session, local_auth
from services.order_stats import order_stats

from utils.fonts import chinese_font


class PreferencesScreen(MDScreen):
    """用户偏好设置界面"""

    user_session = user_session

    spicy_level = StringProperty("微辣")
    avoid_foods = ListProperty([])
    budget_text = StringProperty("30")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_ui = False

    def on_enter(self):
        """进入屏幕时更新数据并修复显示"""
        from services.local_auth import user_session
        self.current_user = user_session.nickname or "游客"
        self.avoid_foods = user_session.get_prefs().get("avoid_foods", [])
        self.load_preferences()

        Clock.schedule_once(self._fix_chinese_display, 0)
        Clock.schedule_once(self._update_ui, 0.1)

        if not user_session.is_guest:
            Clock.schedule_once(self._check_order_summary_popup, 0.5)

    def _fix_chinese_display(self, dt):
        """修复中文显示：遍历所有子部件设置中文字体"""
        if not chinese_font:
            return

        for child in self.walk():
            if hasattr(child, 'font_name') and hasattr(child, 'text'):
                text = str(child.text)
                if self._contains_chinese(text):
                    child.font_name = chinese_font

    def _contains_chinese(self, text):
        """检查是否包含中文字符"""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    def show_snackbar(self, text):
        """显示底部提示"""
        snackbar = MDSnackbar(MDLabel(text=text))
        snackbar.open()

    def load_preferences(self):
        """从会话加载偏好到UI"""
        prefs = user_session.get_prefs()

        self.spicy_level = prefs.get("spicy_level", "微辣")
        self.avoid_foods = prefs.get("avoid_foods", []).copy()
        self.budget_text = str(prefs.get("default_budget", 30))

    def _update_ui(self, dt):
        """更新UI显示（安全版本，检查控件是否存在）"""
        if hasattr(self.ids, 'budget_input') and self.ids.budget_input:
            self.ids.budget_input.text = self.budget_text

        prefs = user_session.get_prefs()
        if hasattr(self.ids, 'address_input') and self.ids.address_input:
            self.ids.address_input.text = prefs.get("default_address", "") or ""

        if hasattr(self.ids, 'nickname_label') and self.ids.nickname_label:
            if user_session.is_guest:
                self.ids.nickname_label.text = "当前用户：游客"
            else:
                nickname = user_session.nickname
                if not nickname or nickname == "":
                    nickname = f"用户{user_session.user_id}"
                self.ids.nickname_label.text = f"当前用户：{nickname}"

        self._update_spicy_chips()
        self._update_avoid_list()

    def _update_spicy_chips(self):
        """更新辣度选择状态"""
        levels = ["不辣", "微辣", "中辣", "特辣"]
        for level in levels:
            chip_id = f"chip_{level}"
            if hasattr(self.ids, chip_id) and self.ids[chip_id]:
                chip = self.ids[chip_id]
                if level == self.spicy_level:
                    chip.md_bg_color = self.theme_cls.primary_color
                    chip.selected = True
                else:
                    chip.md_bg_color = (0.9, 0.9, 0.9, 1)
                    chip.selected = False

    def _update_avoid_list(self):
        """更新忌口食物列表"""
        avoid_list = getattr(self.ids, 'avoid_list', None)
        if not avoid_list:
            return

        avoid_list.clear_widgets()

        if not self.avoid_foods:
            avoid_list.add_widget(
                MDLabel(
                    text="暂无忌口设置",
                    halign="center",
                    theme_text_color="Hint",
                    size_hint_y=None,
                    height=dp(40)
                )
            )
            return

        for food in self.avoid_foods:
            item = OneLineAvatarIconListItem(
                text=food,
                on_release=lambda x, f=food: self.confirm_remove_avoid(f)
            )
            icon_btn = MDIconButton(
                icon="close",
                on_release=lambda x, f=food: self.confirm_remove_avoid(f)
            )
            item.add_widget(icon_btn)
            avoid_list.add_widget(item)

    # ========== 辣度选择 ==========

    def select_spicy(self, level):
        """选择辣度"""
        self.spicy_level = level
        self._update_spicy_chips()
        MDSnackbar(MDLabel(text=f"辣度偏好：{level}")).open()

    # ========== 忌口管理 ==========

    def add_avoid_food(self):
        """添加忌口食物"""
        input_field = getattr(self.ids, 'avoid_input', None)
        if not input_field:
            return

        food = input_field.text.strip()
        if not food:
            return

        if food in self.avoid_foods:
            MDSnackbar(MDLabel(text=f"{food} 已在忌口列表中")).open()
            return

        self.avoid_foods.append(food)
        input_field.text = ""
        self._update_avoid_list()
        MDSnackbar(MDLabel(text=f"已添加忌口：{food}")).open()

    def confirm_remove_avoid(self, food):
        """确认删除忌口"""
        dialog = MDDialog(
            title=f"[font={chinese_font}]删除忌口[/font]" if chinese_font else "删除忌口",
            text=f"确定要删除 {food} 吗？",
            buttons=[
                MDFlatButton(
                    text="取消",
                    on_release=lambda x: dialog.dismiss()
                ),
                MDRaisedButton(
                    text="删除",
                    on_release=lambda x: [dialog.dismiss(), self.remove_avoid_food(food)]
                )
            ]
        )

        def fix_dialog_font(dt):
            if chinese_font:
                for child in dialog.walk():
                    if hasattr(child, 'font_name') and hasattr(child, 'text'):
                        text = str(child.text)
                        if self._contains_chinese(text):
                            child.font_name = chinese_font

        dialog.open()
        Clock.schedule_once(fix_dialog_font, 0.05)

    def remove_avoid_food(self, food):
        """删除忌口食物"""
        if food in self.avoid_foods:
            self.avoid_foods.remove(food)
            self._update_avoid_list()
            MDSnackbar(MDLabel(text=f"已删除：{food}")).open()

    # ========== 订单总结弹窗 ==========

    def _check_order_summary_popup(self, dt):
        """检查并显示订单总结弹窗"""
        if user_session.is_guest:
            return

        result = order_stats.get_order_summary_popup()

        if result.get('should_show'):
            self._show_order_summary_dialog(result['summary'])

    def _show_order_summary_dialog(self, summary):
        """显示订单总结弹窗"""

        avg_budget = summary.get('avg_budget', 30)
        spicy = summary.get('spicy', '微辣')
        orders_since_last = summary.get('orders_since_last', 20)
        total_orders = summary.get('total_orders', 0)

        print(f"[订单总结弹窗] 总订单: {total_orders}, 自上次以来: {orders_since_last}")

        content_layout = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            padding=20,
            adaptive_height=True
        )

        message = (
            f"您最近 {orders_since_last} 个订单总结偏好\n\n"
            f"预算：{avg_budget} 元\n"
            f"辣度：{spicy}\n\n"
            f"是否更新偏好设置？"
        )

        msg_label = MDLabel(
            text=message,
            halign="left",
            size_hint_y=None,
            height=150
        )
        if chinese_font:
            msg_label.font_name = chinese_font

        content_layout.add_widget(msg_label)

        new_milestone = (total_orders // 20) * 20
        print(f"[订单总结弹窗] 新里程碑: {new_milestone}")

        def cancel_and_update_count(*args):
            """取消但更新计数，避免重复弹窗"""
            current_prefs = user_session.get_prefs()
            current_prefs['last_summary_count'] = new_milestone
            if 'last_summary_order_count' in current_prefs:
                del current_prefs['last_summary_order_count']
            result = user_session.update_prefs(current_prefs)
            print(f"[订单总结] 取消，保存 last_summary_count = {new_milestone}, 结果: {result}")

            # 立即验证
            verify_prefs = user_session.get_prefs()
            print(f"[订单总结] 验证读取: last_summary_count = {verify_prefs.get('last_summary_count', 0)}")

            dialog.dismiss()

        def apply_preferences(*args):
            """应用弹窗中的偏好"""
            db = get_db_service()
            user_id = int(user_session.user_id)
            current_prefs = user_session.get_prefs()
            current_prefs['default_budget'] = avg_budget
            current_prefs['budget_range'] = str(avg_budget)
            current_prefs['spicy_level'] = spicy
            current_prefs['spiciness_level'] = spicy
            current_prefs['last_summary_count'] = new_milestone
            if 'last_summary_order_count' in current_prefs:
                del current_prefs['last_summary_order_count']

            user_session.update_prefs(current_prefs)
            print(f"[订单总结] 保存 last_summary_count = {new_milestone}")

            self.load_preferences()
            self._update_ui(0)

            dialog.dismiss()
            self.show_snackbar("偏好已更新")

        dialog = MDDialog(
            title=f"[font={chinese_font}]订单总结[/font]" if chinese_font else "订单总结",
            type="custom",
            content_cls=content_layout,
            buttons=[
                MDFlatButton(
                    text="取消",
                    on_release=lambda x: cancel_and_update_count()
                ),
                MDRaisedButton(
                    text="修改偏好",
                    on_release=lambda x: apply_preferences()
                )
            ]
        )

        # 设置字体
        if chinese_font:
            if hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            for btn in dialog.buttons:
                if hasattr(btn, 'font_name'):
                    btn.font_name = chinese_font

        dialog.open()

    # ========== 保存设置 ==========

    def save_preferences(self):
        """保存所有偏好设置"""
        print("=" * 50)
        print("开始保存偏好设置...")

        prefs = {
            "spicy_level": self.spicy_level,
            "avoid_foods": self.avoid_foods.copy(),
        }

        # 预算
        if hasattr(self.ids, 'budget_input') and self.ids.budget_input:
            try:
                budget = int(self.ids.budget_input.text)
                if 10 <= budget <= 500:
                    prefs["default_budget"] = budget
                    prefs["budget_range"] = str(budget)
                else:
                    self.show_snackbar("预算范围：10-500元")
                    return
            except ValueError:
                self.show_snackbar("请输入有效的预算金额")
                return

        # 地址
        if hasattr(self.ids, 'address_input') and self.ids.address_input:
            prefs["default_address"] = self.ids.address_input.text.strip()

        # 同时更新 spiciness_level 字段（兼容数据库）
        prefs["spiciness_level"] = self.spicy_level

        print(f"准备保存的偏好: {prefs}")

        # 更新会话（游客也会保存到内存）
        user_session.update_prefs(prefs)

        print(f"会话中的偏好: {user_session.get_prefs()}")

        if not user_session.is_guest:
            # 注册用户：保存到数据库
            result = local_auth.update_prefs(prefs)
            if result:
                print("偏好保存到数据库成功")
                self.show_snackbar("偏好设置已保存")
            else:
                print("偏好保存到数据库失败")
                self.show_snackbar("保存失败，请重试")
        else:
            print("游客模式：设置已保存到内存（本次会话有效）")
            self.show_snackbar("游客模式：设置仅本次有效")

        # 刷新 UI 显示
        self._update_ui(0)

    # ========== 收藏和避雷列表 ==========

    def show_favorites(self):
        """显示收藏列表（带编号）"""

        if user_session.is_guest:
            self.show_snackbar("游客模式无法使用收藏功能")
            return

        db = get_db_service()
        user_id = int(user_session.user_id)
        favorites = db.get_favorites(user_id)

        print(f"[收藏列表] 获取到 {len(favorites)} 条记录")

        if not favorites:
            dialog = MDDialog(
                title=f"[font={chinese_font}]我的收藏[/font]" if chinese_font else "我的收藏",
                type="simple",
                text="暂无收藏菜品",
                buttons=[MDFlatButton(text="关闭", on_release=lambda x: dialog.dismiss())]
            )
            if chinese_font and hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            dialog.open()
            return

        # 构建显示文本
        text_lines = []
        for idx, item in enumerate(favorites, 1):
            text_lines.append(f"{idx}. {item['restaurant_name']} - {item['dish_name']}")

        # 保存 favorites 列表供后续使用
        self.current_favorites = favorites

        # 内容布局
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(20),
            size_hint_y=None,
            height=dp(300)
        )

        # 显示列表的标签
        list_text = "\n".join(text_lines)
        list_label = MDLabel(
            text=list_text,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(250)
        )
        list_label.bind(size=list_label.setter('text_size'))
        if chinese_font:
            list_label.font_name = chinese_font

        # 编号输入框
        input_label = MDLabel(
            text="请输入要移除的编号:",
            size_hint_y=None,
            height=dp(30)
        )
        if chinese_font:
            input_label.font_name = chinese_font

        number_input = MDTextField(
            hint_text="编号",
            input_filter="int",
            size_hint_y=None,
            height=dp(40),
            mode="rectangle"
        )
        if chinese_font:
            number_input.font_name = chinese_font

        content.add_widget(list_label)
        content.add_widget(input_label)
        content.add_widget(number_input)

        def do_remove(*args):
            try:
                num = int(number_input.text.strip())
                if 1 <= num <= len(favorites):
                    item_to_remove = favorites[num - 1]
                    db.remove_favorite(user_id, item_to_remove['restaurant_name'], item_to_remove['dish_name'])
                    self.show_snackbar(f"已移除: {item_to_remove['restaurant_name']} - {item_to_remove['dish_name']}")
                    dialog.dismiss()
                    # 延迟刷新
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.show_favorites(), 0.2)
                else:
                    self.show_snackbar(f"请输入 1-{len(favorites)} 之间的编号")
            except ValueError:
                self.show_snackbar("请输入有效的编号")

        dialog = MDDialog(
            title=f"[font={chinese_font}]我的收藏[/font]" if chinese_font else "我的收藏",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="取消", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(text="移除", on_release=do_remove)
            ]
        )

        if chinese_font:
            if hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            for btn in dialog.buttons:
                if hasattr(btn, 'font_name'):
                    btn.font_name = chinese_font

        dialog.open()

    def show_blacklist(self):
        """显示避雷列表（带编号）"""

        if user_session.is_guest:
            self.show_snackbar("游客模式无法使用避雷功能")
            return

        db = get_db_service()
        user_id = int(user_session.user_id)
        blacklist = db.get_blacklist(user_id)

        print(f"[避雷列表] 获取到 {len(blacklist)} 条记录")

        if not blacklist:
            dialog = MDDialog(
                title=f"[font={chinese_font}]我的避雷[/font]" if chinese_font else "我的避雷",
                type="simple",
                text="暂无避雷菜品",
                buttons=[MDFlatButton(text="关闭", on_release=lambda x: dialog.dismiss())]
            )
            if chinese_font and hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            dialog.open()
            return

        # 构建显示文本
        text_lines = []
        for idx, item in enumerate(blacklist, 1):
            line = f"{idx}. {item['restaurant_name']} - {item['dish_name']}"
            if item.get('reason'):
                line += f"（原因：{item['reason']}）"
            text_lines.append(line)

        self.current_blacklist = blacklist

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(20),
            size_hint_y=None,
            height=dp(300)
        )

        list_text = "\n".join(text_lines)
        list_label = MDLabel(
            text=list_text,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(250)
        )
        list_label.bind(size=list_label.setter('text_size'))
        if chinese_font:
            list_label.font_name = chinese_font

        input_label = MDLabel(
            text="请输入要移除的编号:",
            size_hint_y=None,
            height=dp(30)
        )
        if chinese_font:
            input_label.font_name = chinese_font

        number_input = MDTextField(
            hint_text="编号",
            input_filter="int",
            size_hint_y=None,
            height=dp(40),
            mode="rectangle"
        )
        if chinese_font:
            number_input.font_name = chinese_font

        content.add_widget(list_label)
        content.add_widget(input_label)
        content.add_widget(number_input)

        def do_remove(*args):
            try:
                num = int(number_input.text.strip())
                if 1 <= num <= len(blacklist):
                    item_to_remove = blacklist[num - 1]
                    db.remove_blacklist(user_id, item_to_remove['restaurant_name'], item_to_remove['dish_name'])
                    self.show_snackbar(f"已移除: {item_to_remove['restaurant_name']} - {item_to_remove['dish_name']}")
                    dialog.dismiss()
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.show_blacklist(), 0.2)
                else:
                    self.show_snackbar(f"请输入 1-{len(blacklist)} 之间的编号")
            except ValueError:
                self.show_snackbar("请输入有效的编号")

        dialog = MDDialog(
            title=f"[font={chinese_font}]我的避雷[/font]" if chinese_font else "我的避雷",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="取消", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(text="移除", on_release=do_remove)
            ]
        )

        if chinese_font:
            if hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            for btn in dialog.buttons:
                if hasattr(btn, 'font_name'):
                    btn.font_name = chinese_font

        dialog.open()

    # ========== 账号管理 ==========

    def go_home(self):
        """返回首页"""
        self.manager.current = 'home'

    def logout(self):
        """退出登录"""
        # 清空聊天记录
        chat_screen = self.manager.get_screen('chat')
        chat_screen.messages = []
        chat_screen.clear_chat()

        # 清空Qwen服务中的推荐历史
        from services.qwen_local import get_qwen_service
        qwen = get_qwen_service()
        qwen.conversation_context = {
            "last_budget": 30,
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
        }

        # 退出登录
        local_auth.logout()
        user_session.logout()
        self.manager.current = 'login'

    def show_change_password(self):
        """显示修改密码对话框"""
        from kivy.uix.boxlayout import BoxLayout

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20), size_hint_y=None, height=dp(200))

        old_pass = MDTextField(
            hint_text="旧密码",
            password=True,
            mode="rectangle",
            helper_text="请输入当前密码",
            helper_text_mode="on_focus",
        )

        new_pass = MDTextField(
            hint_text="新密码",
            password=True,
            mode="rectangle",
            helper_text="请输入新密码",
            helper_text_mode="on_focus",
        )

        confirm_pass = MDTextField(
            hint_text="确认新密码",
            password=True,
            mode="rectangle",
            helper_text="请再次输入新密码",
            helper_text_mode="on_focus",
        )

        if chinese_font:
            old_pass.font_name = chinese_font
            new_pass.font_name = chinese_font
            confirm_pass.font_name = chinese_font

        content.add_widget(old_pass)
        content.add_widget(new_pass)
        content.add_widget(confirm_pass)

        def do_change_password(*args):
            old = old_pass.text
            new = new_pass.text
            confirm = confirm_pass.text

            if not all([old, new, confirm]):
                self.show_snackbar("请填写所有密码字段")
                return

            if new != confirm:
                self.show_snackbar("两次输入的新密码不一致")
                return

            from services.local_auth import local_auth
            result = local_auth.change_password(old, new)

            if isinstance(result, tuple):
                success, msg = result
            else:
                success = result
                msg = "密码修改成功" if success else "密码修改失败"

            if success:
                self.show_snackbar(msg)
                dialog.dismiss()
            else:
                self.show_snackbar(f"密码修改失败: {msg}")

        dialog = MDDialog(
            title=f"[font={chinese_font}]修改密码[/font]" if chinese_font else "修改密码",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="取消",
                    on_release=lambda x: dialog.dismiss()
                ),
                MDRaisedButton(
                    text="确认修改",
                    on_release=do_change_password
                ),
            ],
        )

        # 设置字体
        if chinese_font:
            if hasattr(dialog, 'title_label'):
                dialog.title_label.font_name = chinese_font
            for btn in dialog.buttons:
                if hasattr(btn, 'font_name'):
                    btn.font_name = chinese_font

        dialog.open()
