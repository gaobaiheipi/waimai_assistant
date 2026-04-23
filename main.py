# main.py
import os
import sys

modules_to_remove = [k for k in sys.modules.keys() if 'qwen' in k]
for m in modules_to_remove:
    del sys.modules[m]

if sys.platform == 'win32':
    os.environ['KIVY_TEXT'] = 'pil'
    os.environ['SDL_IME_SHOW_UI'] = '1'

from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import StringProperty, ListProperty, NumericProperty

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDLabel

# 导入字体配置
from utils.fonts import chinese_font

# 注册字体
if chinese_font:
    LabelBase.register('Roboto', chinese_font)
    LabelBase.register('Noto', chinese_font)
    from kivy.config import Config
    Config.set('kivy', 'default_font', ['Roboto', chinese_font])

if sys.platform == 'win32':
    from kivy.core.window import Window
    Window.size = (375, 812)

from screens.login_screen import LoginScreen
from screens.home_screen import HomeScreen
from screens.chat_screen import ChatScreen
from screens.order_screen import OrderScreen
from screens.preferences_screen import PreferencesScreen
from screens.tracking_screen import TrackingScreen
from services.local_auth import user_session, local_auth


class WaimaiManager(MDScreenManager):
    pass


class WaimaiApp(MDApp):
    title = "智能外卖助手"

    user_session = user_session

    user_nickname = StringProperty("游客")
    user_budget = NumericProperty(30)
    user_spicy = StringProperty("微辣")
    user_avoid = ListProperty([])

    def build(self):
        # Android 屏幕适配
        if sys.platform == 'android':
            from kivy.core.window import Window
            # 获取实际屏幕大小
            Window.size = (Window.width, Window.height)
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "DeepOrange"
        self.theme_cls.accent_palette = "Orange"

        user_session.bind(preferences=self._on_prefs_change)
        user_session.bind(nickname=self._on_user_change)

        sm = WaimaiManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ChatScreen(name='chat'))
        sm.add_widget(OrderScreen(name='orders'))
        sm.add_widget(PreferencesScreen(name='preferences'))
        sm.add_widget(TrackingScreen(name='tracking'))

        if chinese_font:
            Clock.schedule_once(self._fix_all_fonts, 0.5)
            Clock.schedule_once(self._fix_icon_buttons, 0.5)

        self._update_user_display()

        return sm

    def _fix_all_fonts(self, dt):
        """递归修复所有控件的字体"""

        def set_font(widget):
            if hasattr(widget, 'font_name'):
                try:
                    widget.font_name = chinese_font
                except:
                    pass
            if hasattr(widget, 'children'):
                for child in widget.children:
                    set_font(child)

        for screen in self.root.screens:
            set_font(screen)

    def _fix_icon_buttons(self, dt):
        """修复图标按钮字体"""
        icon_font = 'Icons'
        for screen in self.root.screens:
            for child in screen.walk():
                if isinstance(child, MDIconButton):
                    child.font_name = icon_font
                elif isinstance(child, MDTopAppBar):
                    if hasattr(child, 'ids') and child.ids.get('label_title'):
                        child.ids.label_title.font_name = chinese_font

    def _on_user_change(self, instance, value):
        Clock.schedule_once(lambda dt: setattr(self, 'user_nickname', value), 0)

    def _on_prefs_change(self, instance, value):
        Clock.schedule_once(lambda dt: self._update_user_display(), 0)

    def _update_user_display(self):
        prefs = user_session.get_prefs()
        self.user_budget = prefs.get("default_budget", 30)
        self.user_spicy = prefs.get("spicy_level", "微辣")
        self.user_avoid = prefs.get("avoid_foods", [])

    def on_start(self):
        pass


if __name__ == '__main__':
    WaimaiApp().run()
