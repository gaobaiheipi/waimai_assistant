# utils/paths.py
import os
import sys
from pathlib import Path
try:
    from android.storage import app_storage_path
    ANDROID_AVAILABLE = True
except ImportError:
    ANDROID_AVAILABLE = False
    app_storage_path = None


def get_app_root():
    """获取应用根目录"""
    # 检查是否在打包环境中
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的 exe
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir():
    """获取数据目录（数据库文件存放位置）"""
    from kivy.utils import platform

    if platform == 'android' and ANDROID_AVAILABLE:
        # Android 应用私有存储目录
        try:
            data_dir = app_storage_path()
            print(f"[路径] Android 数据目录: {data_dir}")
        except Exception as e:
            print(f"[路径] Android 存储路径获取失败: {e}")
            # 备用方案
            data_dir = '/data/data/org.test.waimai/files'
    elif platform == 'android':
        # Android 但没有 android.storage 模块
        data_dir = '/data/data/org.test.waimai/files'
    else:
        # Windows/Linux 开发环境
        data_dir = os.path.join(get_app_root(), 'data')

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_db_path():
    """获取数据库文件路径"""
    return os.path.join(get_data_dir(), 'waimai.db')


def get_models_dir():
    """获取模型目录"""
    from kivy.utils import platform

    if platform == 'android':
        # Android 上模型放在应用私有目录
        models_dir = os.path.join(get_data_dir(), 'models')
    else:
        # 开发环境
        models_dir = os.path.join(get_app_root(), 'models')

    os.makedirs(models_dir, exist_ok=True)
    return models_dir


def get_model_path(model_name):
    """获取模型路径"""
    return os.path.join(get_models_dir(), model_name)


def get_font_path():
    """获取中文字体路径"""
    from kivy.utils import platform

    # 优先使用打包的字体
    packaged_font = os.path.join(get_app_root(), 'assets', 'fonts', 'msyh.ttc')
    if os.path.exists(packaged_font):
        return packaged_font

    if platform == 'android':
        # Android 系统字体
        android_fonts = [
            "/system/fonts/NotoSansCJK-Regular.ttc",
            "/system/fonts/DroidSansFallback.ttf",
            "/system/fonts/NotoSansSC-Regular.otf",
        ]
        for font in android_fonts:
            if os.path.exists(font):
                return font
        return None
    else:
        # Windows 开发环境
        windows_fonts = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
        for font in windows_fonts:
            if os.path.exists(font):
                return font
        return None


def get_assets_dir():
    """获取资源目录"""
    return os.path.join(get_app_root(), 'assets')
