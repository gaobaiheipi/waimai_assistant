"""应用配置"""

# 应用信息
APP_NAME = "智能外卖助手"
VERSION = "1.0.0"

# 主题配置
THEME_STYLE = "Light"
PRIMARY_PALETTE = "DeepOrange"
ACCENT_PALETTE = "Orange"

# AI 配置（预留云端 LLM 接口）
AI_CONFIG = {
    'use_local': True,      # 使用本地规则引擎
    'api_url': '',          # LLM API 地址
    'api_key': '',
    'model': 'qwen-7b-chat'
}

# 外卖平台配置（无企业资质，使用替代方案）
PLATFORM_CONFIG = {
    'meituan': {
        'enabled': False,   # 未申请 API，使用模拟数据/无障碍服务
        'app_id': '',
        'app_secret': ''
    },
    'eleme': {
        'enabled': False,
        'app_id': '',
        'app_secret': ''
    }
}

# 开发模式（使用模拟数据）
DEV_MODE = True

# 默认预算范围
DEFAULT_MIN_BUDGET = 10
DEFAULT_MAX_BUDGET = 100
