# screens/login_screen.py
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import Snackbar

from services.local_auth import local_auth, user_session


class LoginScreen(MDScreen):
    """本地账号登录界面 - 简化版，无 MDTabs"""

    status_text = StringProperty("")
    show_register = BooleanProperty(False)

    def on_enter(self):
        """检查已有登录"""
        if local_auth.is_logged_in():
            self.auto_login()

    def auto_login(self):
        """自动登录"""
        user_data = local_auth.get_user_data()
        if user_data:
            # 已经登录了，直接跳转
            self.go_home()

    def toggle_mode(self):
        """切换登录/注册模式"""
        self.show_register = not self.show_register
        self.status_text = "注册新账号" if self.show_register else "账号登录"

    def do_login(self):
        """账号密码登录"""
        phone = self.ids.login_phone.text.strip()  # 这是手机号
        password = self.ids.login_password.text

        if not phone or not password:
            self.show_snackbar("请输入手机号和密码")
            return

        result = local_auth.login(phone, password)  # phone 是手机号

        if result[0]:
            user_info = result[1] if isinstance(result[1], dict) else {"nickname": phone}
            nickname = user_info.get('nickname', user_info.get('username', phone))
            self.show_snackbar(f"欢迎回来, {nickname}")
            Clock.schedule_once(lambda dt: self.go_home(), 1)
        else:
            self.show_snackbar("手机号或密码错误")

    def guest_login(self):
        """游客模式"""
        # 直接使用 login_guest 方法，它会自动设置会话状态
        guest_info = local_auth.login_guest()
        self.show_snackbar("以游客模式进入")
        Clock.schedule_once(lambda dt: self.go_home(), 0.5)

    def do_register(self):
        """注册新账号"""
        phone = self.ids.reg_phone.text.strip()  # 手机号
        password = self.ids.reg_password.text
        password2 = self.ids.reg_password2.text
        nickname = self.ids.reg_nickname.text.strip()  # 昵称

        if not phone or not password:
            self.show_snackbar("请填写完整信息")
            return

        if not local_auth.validate_phone(phone):
            self.show_snackbar("请输入正确的11位手机号")
            return

        if password != password2:
            self.show_snackbar("两次密码不一致")
            return

        if len(password) < 6:
            self.show_snackbar("密码至少6位")
            return

        if not nickname:
            nickname = phone  # 如果没有昵称，使用手机号作为昵称

        success, result = local_auth.register(nickname, password, phone)
        if success:
            self.show_snackbar("注册成功，请登录")
            self.toggle_mode()
            self.ids.login_phone.text = phone
            self.ids.login_password.text = ""
        else:
            self.show_snackbar(result)

    def show_snackbar(self, message):
        """显示提示（兼容 KivyMD 1.2.0）"""
        snackbar = Snackbar(
            MDLabel(
                text=message,
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1)
            ),
            duration=2
        )
        snackbar.open()

    def go_home(self):
        """跳转到首页"""
        self.manager.current = 'home'

    def on_leave(self):
        """清理输入"""
        for id_name in ['login_phone', 'login_password', 'reg_phone',
                        'reg_password', 'reg_password2', 'reg_nickname']:
            if self.ids.get(id_name):
                self.ids[id_name].text = ""
