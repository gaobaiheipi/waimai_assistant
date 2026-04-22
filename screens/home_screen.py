from kivy.clock import Clock
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import Snackbar


class HomeScreen(MDScreen):
    """主页：快速下单入口"""

    def on_enter(self):
        """进入页面时聚焦输入框"""
        Clock.schedule_once(lambda dt: setattr(self.ids.order_input, 'focus', True), 0.3)

    def submit_order(self):
        """提交用户输入"""
        input_field = self.ids.order_input
        user_text = input_field.text.strip()

        if not user_text:
            Snackbar(text="请输入想吃的食物").open()
            return

        # 清空输入并切换到对话页
        input_field.text = ""
        chat_screen = self.manager.get_screen('chat')
        chat_screen.process_user_input(user_text)
        self.manager.current = 'chat'

    def view_history(self):
        """查看历史订单"""
        self.manager.current = 'orders'

    def go_preferences(self):
        """跳转到偏好设置"""
        self.manager.current = 'preferences'
        