# screens/preferences_screen.py
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.chip import MDChip, MDChipText
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.list import MDList, OneLineListItem, OneLineAvatarIconListItem
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog

from services.local_auth import user_session, local_auth

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

        # 延迟执行，确保KV部件已创建
        Clock.schedule_once(self._fix_chinese_display, 0)
        Clock.schedule_once(self._update_ui, 0.1)

    def _fix_chinese_display(self, dt):
        """修复中文显示：遍历所有子部件设置中文字体"""
        import sys
        main_module = sys.modules.get('__main__')
        chinese_font = getattr(main_module, 'chinese_font', None)

        if not chinese_font:
            chinese_font = "C:/Windows/Fonts/msyh.ttc"

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
        # 预算输入
        if hasattr(self.ids, 'budget_input') and self.ids.budget_input:
            self.ids.budget_input.text = self.budget_text

        # 地址输入
        prefs = user_session.get_prefs()
        if hasattr(self.ids, 'address_input') and self.ids.address_input:
            self.ids.address_input.text = prefs.get("default_address", "") or ""

        # 昵称显示
        if hasattr(self.ids, 'nickname_label') and self.ids.nickname_label:
            self.ids.nickname_label.text = f"当前用户：{user_session.nickname}"

        # 更新辣度芯片
        self._update_spicy_chips()

        # 更新忌口列表
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
        import sys
        main_module = sys.modules.get('__main__')
        chinese_font = getattr(main_module, 'chinese_font', None)
        if not chinese_font:
            chinese_font = "C:/Windows/Fonts/msyh.ttc"

        dialog = MDDialog(
            title="删除忌口",
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
            for child in dialog.walk():
                if hasattr(child, 'font_name') and hasattr(child, 'text'):
                    text = str(child.text)
                    if any('\u4e00' <= c <= '\u9fff' for c in text):
                        child.font_name = chinese_font

        dialog.open()
        Clock.schedule_once(fix_dialog_font, 0.05)

    def remove_avoid_food(self, food):
        """删除忌口食物"""
        if food in self.avoid_foods:
            self.avoid_foods.remove(food)
            self._update_avoid_list()
            MDSnackbar(MDLabel(text=f"已删除：{food}")).open()

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
                    prefs["budget_range"] = str(budget)  # 同时设置两个字段
                else:
                    MDSnackbar(MDLabel(text="预算范围：10-500元")).open()
                    return
            except ValueError:
                MDSnackbar(MDLabel(text="请输入有效的预算金额")).open()
                return

        # 地址
        if hasattr(self.ids, 'address_input') and self.ids.address_input:
            prefs["default_address"] = self.ids.address_input.text.strip()

        print(f"准备保存的偏好: {prefs}")

        # 更新会话
        user_session.update_prefs(prefs)

        print(f"会话中的偏好: {user_session.get_prefs()}")

        if not user_session.is_guest:
            # 再次确认数据库是否保存成功
            result = local_auth.update_prefs(prefs)
            if result:
                print("偏好保存到数据库成功")
                MDSnackbar(MDLabel(text="偏好设置已保存")).open()
            else:
                print("偏好保存到数据库失败")
                MDSnackbar(MDLabel(text="保存失败，请重试")).open()
        else:
            print("游客模式：设置仅本次有效")
            MDSnackbar(MDLabel(text="游客模式：设置仅本次有效")).open()

        # 刷新 UI 显示
        self._update_ui(0)

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
        qwen.has_recommendation_history = False
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
        }

        # 退出登录
        local_auth.logout()
        user_session.logout()
        self.manager.current = 'login'

    def show_change_password(self):
        """显示修改密码对话框"""
        from kivy.uix.boxlayout import BoxLayout

        import sys
        main_module = sys.modules.get('__main__')
        chinese_font = getattr(main_module, 'chinese_font', "C:/Windows/Fonts/msyh.ttc")

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20), size_hint_y=None, height=dp(200))

        old_pass = MDTextField(
            hint_text="旧密码",
            password=True,
            mode="rectangle",
            font_name=chinese_font,
            helper_text="请输入当前密码",
            helper_text_mode="on_focus",
        )

        new_pass = MDTextField(
            hint_text="新密码",
            password=True,
            mode="rectangle",
            font_name=chinese_font,
            helper_text="请输入新密码",
            helper_text_mode="on_focus",
        )

        confirm_pass = MDTextField(
            hint_text="确认新密码",
            password=True,
            mode="rectangle",
            font_name=chinese_font,
            helper_text="请再次输入新密码",
            helper_text_mode="on_focus",
        )

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
            title="修改密码",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="取消",
                    font_name=chinese_font,
                    on_release=lambda x: dialog.dismiss()
                ),
                MDRaisedButton(
                    text="确认修改",
                    font_name=chinese_font,
                    on_release=do_change_password
                ),
            ],
        )

        def fix_dialog_font(dt):
            for child in dialog.walk():
                if hasattr(child, 'font_name') and hasattr(child, 'text'):
                    text = str(child.text)
                    if any('\u4e00' <= c <= '\u9fff' for c in text):
                        child.font_name = chinese_font

        dialog.open()
        Clock.schedule_once(fix_dialog_font, 0.05)