# utils/fonts.py
import os
from utils.paths import get_font_path

# 获取中文字体路径
chinese_font = get_font_path()

if chinese_font:
    print(f"中文字体: {chinese_font}")
else:
    print("警告: 未找到中文字体")
