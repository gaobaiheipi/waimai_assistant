# screens/chat_screen.py - 简化版 ChatMessage，避免属性绑定错误

from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from threading import Thread

from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.boxlayout import MDBoxLayout

from services.qwen_local import get_qwen_service
from services.local_auth import user_session

from utils.fonts import chinese_font


class ChatMessage(BoxLayout):
    """单条聊天消息 - 简化版"""

    def __init__(self, sender, content, is_user=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.padding = [dp(10), dp(8), dp(10), dp(8)]
        self.spacing = dp(4)

        # 根据发送者设置背景和位置
        if is_user:
            self.md_bg_color = (0.95, 0.87, 0.82, 1)
            self.pos_hint = {"right": 1}
            self.size_hint_x = 0.75
        else:
            self.md_bg_color = (0.9, 0.9, 0.9, 1)
            self.pos_hint = {"x": 0}
            self.size_hint_x = 0.8

        # 发送者标签
        sender_label = MDLabel(
            text=sender,
            theme_text_color="Secondary",
            font_style="Caption",
            size_hint_y=None,
            height=dp(20)
        )

        # 内容标签 - 不绑定 texture_size 到 height，直接让标签自适应
        content_label = MDLabel(
            text=content,
            theme_text_color="Primary",
            size_hint_y=None,
            halign="left",
            valign="top",
            text_size=(self.width - dp(20), None)
        )
        # 让标签高度根据内容自动调整
        content_label.bind(
            texture_size=lambda instance, size: setattr(instance, 'height', size[1])
        )
        # 当容器宽度变化时更新 text_size
        self.bind(width=lambda instance, w: setattr(content_label, 'text_size', (w - dp(20), None)))

        self.add_widget(sender_label)
        self.add_widget(content_label)

        # 计算总高度
        self.bind(minimum_height=self.setter('height'))


class ChatScreen(MDScreen):
    chat_history = StringProperty("")
    is_model_ready = BooleanProperty(False)
    is_generating = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.qwen = get_qwen_service()
        self.messages = []
        self._pending_message = None

    def on_enter(self):
        """进入界面时检查模型"""
        if not self.qwen.is_ready:
            self._check_model()
        else:
            self._add_system_message("AI 助手已就绪，请输入您的问题")

    def _check_model(self):
        """检查并加载模型"""
        self._show_loading_dialog("正在初始化...")

        # 显示当前模式
        mode = "云端模式" if self.qwen.mode == 'cloud' else "本地模式"
        self._add_system_message(f"当前使用{mode}")

        def on_loaded(success, msg):
            def update_ui(dt):
                self._dismiss_loading_dialog()
                if success:
                    self.is_model_ready = True
                    self._add_system_message(f"AI 助手已就绪 [{msg}]")
                    if self._pending_message:
                        pending = self._pending_message
                        self._pending_message = None
                        self.send_message(pending)
                else:
                    self._add_system_message("初始化失败：" + msg)

            Clock.schedule_once(update_ui, 0)

        Thread(target=lambda: self.qwen.load_models(on_loaded), daemon=True).start()

    def _show_loading_dialog(self, text):
        """显示加载对话框（修复中文显示）"""
        from kivymd.uix.spinner import MDSpinner
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.dialog import MDDialog
        from kivy.metrics import dp
        from utils.fonts import chinese_font

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(20),
            adaptive_height=True
        )

        spinner = MDSpinner(size_hint=(None, None), size=(dp(46), dp(46)))
        spinner.pos_hint = {"center_x": 0.5}

        label = MDLabel(
            text=text,
            halign="center",
            size_hint_y=None,
            height=dp(40)
        )
        if chinese_font:
            label.font_name = chinese_font

        content.add_widget(spinner)
        content.add_widget(label)

        self.loading_dialog = MDDialog(
            title=f"[font={chinese_font}]请稍候[/font]" if chinese_font else "请稍候",
            type="custom",
            content_cls=content
        )

        # 设置标题字体
        if chinese_font:
            if hasattr(self.loading_dialog, 'title_label'):
                self.loading_dialog.title_label.font_name = chinese_font
            # 设置内容字体
            if hasattr(self.loading_dialog, 'content_cls'):
                for child in self.loading_dialog.content_cls.children:
                    if hasattr(child, 'font_name'):
                        child.font_name = chinese_font

        self.loading_dialog.open()

    def _dismiss_loading_dialog(self):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            try:
                self.loading_dialog.dismiss()
            except Exception as e:
                print(f"关闭对话框失败: {e}")
            finally:
                self.loading_dialog = None

    def process_user_input(self, text):
        """从主页接收输入"""
        if not text:
            return
        self.manager.current = 'chat'
        Clock.schedule_once(lambda dt: self.send_message(text), 0.3)

    def _handle_response(self, result):
        """处理 AI 响应"""
        self._remove_typing_indicator()
        self.is_generating = False

        if not result["success"]:
            self._add_system_message("请求失败：" + result.get("error", "未知错误"))
            return

        workflow = result.get("workflow")
        if workflow:
            self._execute_workflow(workflow, result.get("params", {}))
            return

        content = result["content"]

        # 保存推荐结果
        if result.get("recommendations"):
            self.qwen.current_recommendations = result["recommendations"]

        model_tag = result.get("model", "unknown")
        self._add_message(f"AI [{model_tag}]", content, is_user=False)
        self.messages.append({"role": "assistant", "content": content})

        if len(self.messages) > 20:
            self.messages = self.messages[-20:]

    def send_message(self, text=None):
        """发送消息"""
        if text is None:
            chat_input = self.ids.get('chat_input')
            if chat_input:
                text = chat_input.text.strip()
            else:
                text = ""

        if not text:
            return

        if not self.is_model_ready:
            self._add_system_message("模型加载中，请稍候...")
            self._pending_message = text
            return

        self._pending_message = None

        chat_input = self.ids.get('chat_input')
        if chat_input:
            chat_input.text = ""

        self._add_message("你", text, is_user=True)
        self.messages.append({"role": "user", "content": text})

        self.is_generating = True
        self._add_typing_indicator()

        # 获取用户偏好（包含用户设置的辣度、预算、忌口）
        prefs = user_session.get_prefs()
        print(f"[偏好] 当前用户偏好: {prefs}")

        def infer():
            result = self.qwen.chat(text, prefs, self.messages[:-1])
            Clock.schedule_once(lambda dt: self._handle_response(result), 0)

        Thread(target=infer, daemon=True).start()

    def _execute_workflow(self, workflow_name: str, params: dict):
        """执行工作流"""
        workflows = {
            'submit_order': self._wf_submit_order,
            'query_order': self._wf_query_order,
            'track_order': self._wf_track_order,  # 确保这一行存在
            'cancel_order': self._wf_cancel_order,
            'modify_info': self._wf_modify_info,
        }

        handler = workflows.get(workflow_name)
        if handler:
            handler(params)
        else:
            self._add_system_message(f"未知工作流: {workflow_name}")

    def _wf_track_order(self, params):
        """工作流：追踪订单"""
        orders = user_session.get_active_orders()

        if not orders:
            self._add_message("系统", "您没有进行中的订单", is_user=False)
            return

        if len(orders) == 1:
            # 只有一个订单，直接追踪
            order_id = orders[0]['id']
            self._add_message("系统", f"正在追踪订单 {order_id}...", is_user=False)
            Clock.schedule_once(lambda dt: self._go_to_tracking(order_id), 1)
        else:
            # 多个订单，让用户选择
            msg = "您有多个进行中的订单：\n"
            for i, o in enumerate(orders[:3], 1):
                msg += f"{i}. 订单 {o['id']} - {o.get('restaurant_name', '未知商家')} - {o['status']}\n"
            msg += "\n请告诉我要追踪哪个订单（回复订单号）"
            self._add_message("系统", msg, is_user=False)

    def _go_to_tracking(self, order_id):
        """跳转到追踪页面"""
        # 确保 tracking 屏幕存在
        if self.manager.has_screen('tracking'):
            tracking_screen = self.manager.get_screen('tracking')
            tracking_screen._order_id = order_id
            self.manager.current = 'tracking'
        else:
            self._add_message("系统", "追踪功能暂不可用", is_user=False)

    def _wf_submit_order(self, params):
        """工作流：提交订单 - 使用用户实际选择的菜品"""
        from services.local_auth import user_session
        import random

        # 从 qwen 服务的上下文中获取当前待确认的订单
        order = self.qwen.conversation_context.get("current_order")

        if not order:
            self._add_message("系统", "没有待确认的订单，请先选择菜品。", is_user=False)
            return

        dish = order["dish"]
        restaurant = order["restaurant"]

        # 构建订单项
        items = [{
            "dish_name": dish['name'],
            "price": dish['price'],
            "quantity": 1
        }]

        self._add_message("系统", f"正在提交订单：{dish['name']} ({restaurant['name']})...", is_user=False)

        # 创建订单
        success, result = user_session.create_order(
            restaurant_name=restaurant['name'],
            items=items,
            total_price=dish['price']
        )

        if success:
            order_num = result if result else f"WM{random.randint(100000, 999999)}"
            content = f"订单已提交成功！\n\n订单号：{order_num}\n"
            content += f"商家：{restaurant['name']}\n"
            content += f"菜品：{dish['name']}\n"
            content += f"金额：{dish['price']}元\n"
            content += f"预计送达：{restaurant['delivery_time']}分钟"
            self._add_message("系统", content, is_user=False)

            # 清空待确认订单
            self.qwen.conversation_context["current_order"] = None

            # 可选：跳转到订单页面
            Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'orders'), 2)
        else:
            self._add_message("系统", f"下单失败：{result}", is_user=False)

    def _wf_query_order(self, params):
        """工作流：查询订单"""
        orders = user_session.get_orders()

        if not orders:
            self._add_message("系统", "您还没有任何订单", is_user=False)
            return

        recent = orders[:3]
        msg = " 最近订单：\n"
        for o in recent:
            items = o.get('items', [])
            item_names = ", ".join([i.get('dish_name', '未知') for i in items])
            msg += f"  • {item_names}  ¥{o['total_price']}  {o['status']}\n"

        self._add_message("系统", msg, is_user=False)

    def _wf_cancel_order(self, params):
        """工作流：取消订单"""
        self._add_message("系统", "请提供需要取消的订单号", is_user=False)

    def _wf_modify_info(self, params):
        """工作流：修改信息"""
        self._add_message("系统", "正在跳转到设置页面...", is_user=False)
        Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'preferences'), 1)

    def _add_message(self, sender, content, is_user=False):
        """添加消息到界面"""
        msg_widget = ChatMessage(sender, content, is_user)
        chat_list = self.ids.get('chat_list')
        if chat_list:
            chat_list.add_widget(msg_widget)
            self._scroll_to_bottom()

    def _add_system_message(self, text):
        """添加系统消息"""
        label = MDLabel(
            text=text,
            theme_text_color="Hint",
            halign="center",
            size_hint_y=None,
            height=dp(40)
        )
        chat_list = self.ids.get('chat_list')
        if chat_list:
            chat_list.add_widget(label)
            self._scroll_to_bottom()

    def _add_typing_indicator(self):
        """显示思考中"""
        self.typing_label = MDLabel(
            text=" AI 思考中...",
            theme_text_color="Secondary",
            halign="left",
            size_hint_y=None,
            height=dp(30)
        )
        chat_list = self.ids.get('chat_list')
        if chat_list:
            chat_list.add_widget(self.typing_label)
            self._scroll_to_bottom()

    def _remove_typing_indicator(self):
        """移除思考中"""
        if hasattr(self, 'typing_label') and self.typing_label.parent:
            self.typing_label.parent.remove_widget(self.typing_label)

    def _scroll_to_bottom(self):
        """滚动到底部"""
        scroll_view = self.ids.get('chat_scroll')
        if scroll_view:
            Clock.schedule_once(lambda dt: setattr(scroll_view, 'scroll_y', 0), 0.1)

    def quick_recommend(self):
        """一键推荐"""
        if not self.is_model_ready:
            self._add_system_message("模型加载中...")
            return

        prefs = user_session.get_prefs()
        budget = prefs.get("default_budget", 30)
        address = prefs.get("default_address", "当前位置")

        self._add_message("你", "给我推荐外卖", is_user=True)
        self._add_typing_indicator()

        def infer():
            result = self.qwen.recommend_food(prefs, budget, address)
            Clock.schedule_once(lambda dt: self._handle_recommend(result), 0)

        Thread(target=infer, daemon=True).start()

    def _handle_recommend(self, result):
        """处理推荐结果"""
        self._remove_typing_indicator()

        if result["success"]:
            content = result["content"]
            model_tag = result.get("model", "unknown")
            self._add_message(f"AI [{model_tag}]", content, is_user=False)
            self.messages.append({"role": "assistant", "content": content})
        else:
            self._add_system_message("推荐失败：" + result.get("error", "未知错误"))

    def clear_chat(self):
        """清空对话"""
        self.messages = []
        chat_list = self.ids.get('chat_list')
        if chat_list:
            chat_list.clear_widgets()
        self._add_system_message("对话已清空")

    def go_back(self):
        """返回首页"""
        self.manager.current = 'home'

    def view_orders(self):
        """查看历史订单"""
        self.manager.current = 'orders'
