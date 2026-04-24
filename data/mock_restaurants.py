# data/mock_restaurants.py
import random
import json
from typing import List, Dict, Optional

# ========== 餐厅数据 ==========
RESTAURANTS = [
    # 川菜
    {"id": 1, "name": "川湘小馆", "cuisine": "川菜", "rating": 4.8, "avg_price": 35, "delivery_time": 35, "sales": 2300,
     "tags": ["麻辣", "正宗", "老字号"]},
    {"id": 2, "name": "蜀味轩", "cuisine": "川菜", "rating": 4.7, "avg_price": 32, "delivery_time": 32, "sales": 1850,
     "tags": ["麻辣", "性价比高"]},
    {"id": 3, "name": "麻辣诱惑", "cuisine": "川菜", "rating": 4.9, "avg_price": 40, "delivery_time": 38, "sales": 3100,
     "tags": ["麻辣", "网红店"]},

    # 粤菜
    {"id": 4, "name": "粤式茶餐厅", "cuisine": "粤菜", "rating": 4.7, "avg_price": 42, "delivery_time": 30,
     "sales": 1850, "tags": ["清淡", "广式"]},
    {"id": 5, "name": "港岛茶餐厅", "cuisine": "粤菜", "rating": 4.8, "avg_price": 45, "delivery_time": 32,
     "sales": 2100, "tags": ["港式", "茶餐厅"]},
    {"id": 6, "name": "点都德", "cuisine": "粤菜", "rating": 4.9, "avg_price": 50, "delivery_time": 35, "sales": 2800,
     "tags": ["点心", "老字号"]},

    # 湘菜
    {"id": 7, "name": "湘味轩", "cuisine": "湘菜", "rating": 4.8, "avg_price": 38, "delivery_time": 32, "sales": 1980,
     "tags": ["香辣", "下饭"]},
    {"id": 8, "name": "毛家饭店", "cuisine": "湘菜", "rating": 4.7, "avg_price": 42, "delivery_time": 35, "sales": 1750,
     "tags": ["传统", "湘菜"]},
    {"id": 9, "name": "辣妹子", "cuisine": "湘菜", "rating": 4.6, "avg_price": 35, "delivery_time": 30, "sales": 1650,
     "tags": ["香辣", "家常"]},

    # 东北菜
    {"id": 10, "name": "东北饺子馆", "cuisine": "东北菜", "rating": 4.7, "avg_price": 30, "delivery_time": 30,
     "sales": 1780, "tags": ["饺子", "实惠"]},
    {"id": 11, "name": "雪乡人家", "cuisine": "东北菜", "rating": 4.6, "avg_price": 32, "delivery_time": 32,
     "sales": 1450, "tags": ["家常", "分量足"]},

    # 日料
    {"id": 12, "name": "日式料理屋", "cuisine": "日料", "rating": 4.8, "avg_price": 55, "delivery_time": 32,
     "sales": 1240, "tags": ["寿司", "刺身"]},
    {"id": 13, "name": "元气寿司", "cuisine": "日料", "rating": 4.7, "avg_price": 48, "delivery_time": 30,
     "sales": 1560, "tags": ["寿司", "回转"]},
    {"id": 14, "name": "一兰拉面", "cuisine": "日料", "rating": 4.6, "avg_price": 42, "delivery_time": 28,
     "sales": 1340, "tags": ["拉面", "日式"]},

    # 韩餐
    {"id": 15, "name": "韩式炸鸡", "cuisine": "韩餐", "rating": 4.6, "avg_price": 32, "delivery_time": 28,
     "sales": 2100, "tags": ["炸鸡", "啤酒"]},
    {"id": 16, "name": "火炉火", "cuisine": "韩餐", "rating": 4.7, "avg_price": 45, "delivery_time": 35, "sales": 1450,
     "tags": ["烤肉", "韩式"]},

    # 西餐
    {"id": 17, "name": "西式简餐", "cuisine": "西餐", "rating": 4.6, "avg_price": 45, "delivery_time": 35,
     "sales": 1320, "tags": ["牛排", "意面"]},
    {"id": 18, "name": "萨莉亚", "cuisine": "西餐", "rating": 4.4, "avg_price": 35, "delivery_time": 28, "sales": 2500,
     "tags": ["实惠", "意餐"]},
    {"id": 19, "name": "必胜客", "cuisine": "西餐", "rating": 4.5, "avg_price": 50, "delivery_time": 32, "sales": 2100,
     "tags": ["披萨", "连锁"]},

    # 火锅（锅底贵，配菜便宜）
    {"id": 20, "name": "重庆火锅", "cuisine": "火锅", "rating": 4.9, "avg_price": 85, "delivery_time": 45,
     "sales": 2450, "tags": ["麻辣", "火锅"]},
    {"id": 21, "name": "海底捞", "cuisine": "火锅", "rating": 4.9, "avg_price": 100, "delivery_time": 50, "sales": 3500,
     "tags": ["服务好", "火锅"]},
    {"id": 22, "name": "潮汕牛肉火锅", "cuisine": "火锅", "rating": 4.8, "avg_price": 90, "delivery_time": 40,
     "sales": 1430, "tags": ["牛肉", "鲜嫩"]},

    # 烧烤
    {"id": 23, "name": "木屋烧烤", "cuisine": "烧烤", "rating": 4.8, "avg_price": 55, "delivery_time": 40,
     "sales": 2100, "tags": ["烧烤", "夜宵"]},
    {"id": 24, "name": "很久以前", "cuisine": "烧烤", "rating": 4.7, "avg_price": 60, "delivery_time": 42,
     "sales": 1650, "tags": ["羊肉串", "烧烤"]},
    {"id": 25, "name": "丰茂烧烤", "cuisine": "烧烤", "rating": 4.6, "avg_price": 58, "delivery_time": 38,
     "sales": 1450, "tags": ["烧烤", "延边"]},

    # 串串（锅底贵，串串便宜）
    {"id": 26, "name": "钢管厂小郡肝", "cuisine": "串串", "rating": 4.7, "avg_price": 55, "delivery_time": 35,
     "sales": 1890, "tags": ["串串", "麻辣"]},
    {"id": 27, "name": "马路边边", "cuisine": "串串", "rating": 4.8, "avg_price": 58, "delivery_time": 32,
     "sales": 2100, "tags": ["串串", "怀旧"]},
    {"id": 28, "name": "玉林串串香", "cuisine": "串串", "rating": 4.6, "avg_price": 52, "delivery_time": 30,
     "sales": 1560, "tags": ["串串", "老字号"]},

    # 小吃
    {"id": 29, "name": "张记麻辣烫", "cuisine": "小吃", "rating": 4.9, "avg_price": 28, "delivery_time": 35,
     "sales": 3200, "tags": ["麻辣", "自选"]},
    {"id": 30, "name": "沙县小吃", "cuisine": "小吃", "rating": 4.4, "avg_price": 20, "delivery_time": 22,
     "sales": 4500, "tags": ["实惠", "国民"]},
    {"id": 31, "name": "兰州拉面", "cuisine": "小吃", "rating": 4.5, "avg_price": 22, "delivery_time": 22,
     "sales": 2890, "tags": ["拉面", "实惠"]},

    # 轻食
    {"id": 32, "name": "轻食主义沙拉", "cuisine": "轻食", "rating": 4.6, "avg_price": 38, "delivery_time": 25,
     "sales": 890, "tags": ["健康", "低卡"]},
    {"id": 33, "name": "wagas", "cuisine": "轻食", "rating": 4.7, "avg_price": 48, "delivery_time": 28, "sales": 760,
     "tags": ["轻食", "网红"]},

    # 西北菜
    {"id": 34, "name": "西北风味", "cuisine": "西北菜", "rating": 4.7, "avg_price": 45, "delivery_time": 40,
     "sales": 1560, "tags": ["面食", "羊肉"]},
    {"id": 35, "name": "西贝莜面村", "cuisine": "西北菜", "rating": 4.8, "avg_price": 60, "delivery_time": 38,
     "sales": 2100, "tags": ["西北", "连锁"]},

    # 东南亚
    {"id": 36, "name": "泰式风情", "cuisine": "东南亚", "rating": 4.5, "avg_price": 48, "delivery_time": 38,
     "sales": 950, "tags": ["酸辣", "咖喱"]},
    {"id": 37, "name": "南洋美食", "cuisine": "东南亚", "rating": 4.6, "avg_price": 45, "delivery_time": 35,
     "sales": 890, "tags": ["东南亚", "异国"]},

    # 港式
    {"id": 38, "name": "港式茶餐厅", "cuisine": "港式", "rating": 4.7, "avg_price": 45, "delivery_time": 30,
     "sales": 1670, "tags": ["奶茶", "菠萝包"]},
    {"id": 39, "name": "翠华餐厅", "cuisine": "港式", "rating": 4.6, "avg_price": 52, "delivery_time": 32,
     "sales": 1230, "tags": ["港式", "茶餐厅"]},

    # 清真
    {"id": 40, "name": "清真拉面", "cuisine": "清真", "rating": 4.6, "avg_price": 30, "delivery_time": 25,
     "sales": 1890, "tags": ["拉面", "牛肉"]},
    {"id": 41, "name": "西域美食", "cuisine": "清真", "rating": 4.5, "avg_price": 38, "delivery_time": 30, "sales": 980,
     "tags": ["清真", "西北"]},

    # 新疆菜
    {"id": 42, "name": "新疆大盘鸡", "cuisine": "新疆菜", "rating": 4.7, "avg_price": 45, "delivery_time": 38,
     "sales": 1120, "tags": ["大盘鸡", "羊肉串"]},
    {"id": 43, "name": "天山美食", "cuisine": "新疆菜", "rating": 4.6, "avg_price": 43, "delivery_time": 35,
     "sales": 890, "tags": ["新疆", "特色"]},

    # 台湾菜
    {"id": 44, "name": "台湾小吃", "cuisine": "台湾菜", "rating": 4.5, "avg_price": 32, "delivery_time": 28,
     "sales": 980, "tags": ["卤肉饭", "奶茶"]},
    {"id": 45, "name": "鼎泰丰", "cuisine": "台湾菜", "rating": 4.8, "avg_price": 60, "delivery_time": 32,
     "sales": 1560, "tags": ["小笼包", "精致"]},

    # 京菜
    {"id": 46, "name": "北京烤鸭店", "cuisine": "京菜", "rating": 4.8, "avg_price": 70, "delivery_time": 45,
     "sales": 870, "tags": ["烤鸭", "精品"]},
    {"id": 47, "name": "大董烤鸭", "cuisine": "京菜", "rating": 4.9, "avg_price": 85, "delivery_time": 50,
     "sales": 1200, "tags": ["烤鸭", "高端"]},

    # 素食
    {"id": 48, "name": "素食主义", "cuisine": "素食", "rating": 4.6, "avg_price": 38, "delivery_time": 28, "sales": 760,
     "tags": ["素食", "健康"]},
    {"id": 49, "name": "素生活", "cuisine": "素食", "rating": 4.5, "avg_price": 35, "delivery_time": 25, "sales": 580,
     "tags": ["素食", "清净"]},

    # 海鲜
    {"id": 50, "name": "海鲜大排档", "cuisine": "海鲜", "rating": 4.7, "avg_price": 60, "delivery_time": 42,
     "sales": 1340, "tags": ["海鲜", "实惠"]},
    {"id": 51, "name": "海鲜码头", "cuisine": "海鲜", "rating": 4.8, "avg_price": 75, "delivery_time": 45, "sales": 980,
     "tags": ["海鲜", "新鲜"]},

    # 鲁菜
    {"id": 52, "name": "黄焖鸡米饭", "cuisine": "鲁菜", "rating": 4.6, "avg_price": 28, "delivery_time": 28,
     "sales": 3100, "tags": ["黄焖鸡", "快餐"]},
    {"id": 53, "name": "鲁味斋", "cuisine": "鲁菜", "rating": 4.7, "avg_price": 38, "delivery_time": 32, "sales": 1200,
     "tags": ["鲁菜", "传统"]},
    {"id": 54, "name": "孔府家宴", "cuisine": "鲁菜", "rating": 4.8, "avg_price": 48, "delivery_time": 38, "sales": 980,
     "tags": ["鲁菜", "精致"]},

    # 甜品
    {"id": 55, "name": "甜品工坊", "cuisine": "甜品", "rating": 4.7, "avg_price": 28, "delivery_time": 25,
     "sales": 1670, "tags": ["甜品", "蛋糕"]},
    {"id": 56, "name": "满记甜品", "cuisine": "甜品", "rating": 4.8, "avg_price": 35, "delivery_time": 28,
     "sales": 1890, "tags": ["甜品", "连锁"]},

    # 饮品店
    {"id": 57, "name": "喜茶", "cuisine": "饮品", "rating": 4.8, "avg_price": 28, "delivery_time": 25, "sales": 3500,
     "tags": ["奶茶", "果茶"]},
    {"id": 58, "name": "奈雪的茶", "cuisine": "饮品", "rating": 4.7, "avg_price": 30, "delivery_time": 25,
     "sales": 2800, "tags": ["奶茶", "欧包"]},
    {"id": 59, "name": "蜜雪冰城", "cuisine": "饮品", "rating": 4.5, "avg_price": 12, "delivery_time": 20,
     "sales": 5000, "tags": ["奶茶", "实惠"]},
    {"id": 60, "name": "星巴克", "cuisine": "饮品", "rating": 4.6, "avg_price": 38, "delivery_time": 20, "sales": 3200,
     "tags": ["咖啡", "连锁"]},
]

# ========== 菜品模板 ==========
DISH_TEMPLATES = {
    "川菜": ["麻婆豆腐", "宫保鸡丁", "水煮鱼", "回锅肉", "鱼香肉丝", "辣子鸡", "毛血旺", "酸菜鱼", "夫妻肺片", "口水鸡",
             "干煸豆角", "水煮肉片", "担担面", "酸辣粉", "红油抄手"],
    "粤菜": ["叉烧饭", "烧鹅饭", "白切鸡", "虾饺", "肠粉", "凤爪", "奶黄包", "流沙包", "糯米鸡", "干炒牛河", "云吞面",
             "煲仔饭", "菠萝包", "蛋挞", "杨枝甘露"],
    "湘菜": ["剁椒鱼头", "小炒黄牛肉", "辣椒炒肉", "湘西外婆菜", "臭豆腐", "口味虾", "腊味合蒸", "毛氏红烧肉", "东安鸡",
             "血鸭", "长沙米粉", "糖油粑粑"],
    "东北菜": ["锅包肉", "地三鲜", "小鸡炖蘑菇", "猪肉炖粉条", "溜肉段", "酸菜炖排骨", "酱骨架", "东北大拉皮",
               "韭菜盒子", "酸菜饺子", "拔丝地瓜", "雪衣豆沙"],
    "日料": ["三文鱼刺身", "鳗鱼寿司", "加州卷", "天妇罗", "日式拉面", "照烧鸡排饭", "牛肉饭", "亲子丼", "咖喱猪排饭",
             "章鱼小丸子", "大福", "抹茶蛋糕"],
    "韩餐": ["原味炸鸡", "甜辣炸鸡", "韩式年糕", "泡菜炒饭", "石锅拌饭", "韩式冷面", "泡菜汤", "大酱汤", "韩式烤肉",
             "紫菜包饭", "部队火锅", "辣炒年糕"],
    "西餐": ["牛排", "意面", "汉堡", "披萨", "沙拉", "薯条", "奶油蘑菇汤", "提拉米苏", "芝士蛋糕", "马卡龙", "罗宋汤",
             "焗饭"],
    "火锅": ["麻辣锅底", "番茄锅底", "菌菇锅底", "清汤锅底", "肥牛卷", "肥羊卷", "虾滑", "毛肚", "鸭肠", "黄喉",
             "午餐肉", "蔬菜拼盘", "金针菇", "藕片", "土豆片"],
    "烧烤": ["羊肉串", "牛肉串", "烤鸡翅", "烤茄子", "烤韭菜", "烤玉米", "烤面包", "烤大虾", "烤生蚝", "烤扇贝",
             "烤鱿鱼", "烤馒头片"],
    "串串": ["麻辣锅底", "番茄锅底", "菌菇锅底", "清汤锅底", "牛肉串串", "羊肉串串", "鸡胗串串", "鸭肠串串", "藕片串串",
             "土豆串串", "金针菇串串", "豆腐皮串串", "鱼丸串串", "虾滑串串", "午餐肉串串", "年糕串串"],
    "小吃": ["麻辣烫", "炸串", "烤冷面", "煎饼果子", "肉夹馍", "凉皮", "酸辣粉", "臭豆腐", "烤面筋", "烤鱿鱼", "章鱼烧",
             "炸鸡排"],
    "轻食": ["鸡胸肉沙拉", "牛油果沙拉", "三文鱼沙拉", "藜麦沙拉", "酸奶碗", "水果杯", "全麦三明治", "素食卷", "能量碗",
             "思慕雪", "波奇饭", "减脂餐"],
    "西北菜": ["羊肉泡馍", "肉夹馍", "凉皮", "油泼面", "臊子面", "羊肉串", "大盘鸡", "手抓羊肉", "烤羊排", "拉条子",
               "丁丁炒面", "馕包肉"],
    "东南亚": ["冬阴功汤", "绿咖喱鸡", "黄咖喱蟹", "芒果糯米饭", "泰式炒河粉", "菠萝炒饭", "泰式奶茶", "海南鸡饭",
               "肉骨茶", "叻沙", "越南河粉", "印尼炒饭"],
    "港式": ["烧鹅饭", "叉烧饭", "云吞面", "牛腩面", "虾饺", "烧卖", "凤爪", "奶黄包", "流沙包", "蛋挞", "菠萝包",
             "丝袜奶茶"],
    "清真": ["牛肉拉面", "羊肉拉面", "牛肉炒面", "羊肉泡馍", "牛肉饺子", "羊肉饺子", "烤羊肉串", "手抓羊肉", "大盘鸡",
             "馕包肉", "酸奶", "奶茶"],
    "新疆菜": ["大盘鸡", "羊肉串", "手抓饭", "馕包肉", "烤羊排", "烤包子", "拉条子", "丁丁炒面", "新疆酸奶", "奶茶",
               "烤全羊", "胡辣羊蹄"],
    "台湾菜": ["卤肉饭", "鸡肉饭", "蚵仔煎", "盐酥鸡", "大肠包小肠", "担仔面", "牛肉面", "芋圆", "珍珠奶茶", "凤梨酥",
               "烧仙草", "棺材板"],
    "京菜": ["北京烤鸭", "京酱肉丝", "宫保鸡丁", "老北京炸酱面", "爆肚", "卤煮火烧", "炒肝", "豆汁", "焦圈", "驴打滚",
             "豌豆黄", "艾窝窝"],
    "素食": ["素菜包", "素饺子", "素春卷", "素烧鹅", "素鸡", "素鸭", "素什锦", "素炒面", "素炒饭", "素汤", "素火锅",
             "素蛋糕"],
    "海鲜": ["清蒸鲈鱼", "蒜蓉扇贝", "椒盐皮皮虾", "香辣蟹", "白灼虾", "蒜蓉生蚝", "烤生蚝", "海鲜炒饭", "海鲜面",
             "海鲜粥", "海鲜拼盘", "海鲜大咖"],
    "鲁菜": ["黄焖鸡", "葱烧海参", "九转大肠", "糖醋鲤鱼", "油爆双脆", "德州扒鸡", "奶汤蒲菜", "泰山三美", "孔府菜",
             "周村烧饼", "锅塌豆腐", "红烧大肠"],
    "甜品": ["芒果慕斯", "巧克力蛋糕", "芝士蛋糕", "提拉米苏", "泡芙", "马卡龙", "布丁", "双皮奶", "杨枝甘露",
             "芒果班戟", "千层蛋糕", "冰淇淋"],
    "饮品": ["珍珠奶茶", "波霸奶茶", "芋圆奶茶", "焦糖奶茶", "抹茶拿铁", "咖啡拿铁", "美式咖啡", "卡布奇诺", "柠檬茶",
             "金桔柠檬", "百香果茶", "杨枝甘露"],
}

# ========== 辣度生成函数 ==========
# 饮品关键词（无论什么菜系都默认为不辣）
DRINKS_KEYWORDS = ["奶茶", "咖啡", "柠檬茶", "果茶", "拿铁", "卡布奇诺", "美式", "焦糖", "抹茶", "百香果", "金桔",
                   "养乐多"]


def get_spicy_level(dish_name: str, cuisine: str) -> str:
    """根据菜品名称和菜系返回辣度等级"""

    for kw in DRINKS_KEYWORDS:
        if kw in dish_name:
            return "不辣"

    if cuisine in ["甜品", "轻食", "饮品"]:
        return "不辣"

    # 火锅锅底：只有麻辣锅底是中辣，其他锅底不辣
    if cuisine == "火锅" and "锅底" in dish_name:
        if "麻辣" in dish_name:
            return "中辣"
        else:
            return "不辣"

    # 串串锅底：默认中辣
    if cuisine == "串串" and "锅底" in dish_name:
        if "麻辣" in dish_name:
            return "中辣"
        else:
            return "微辣"

    # 串串菜品：默认微辣或中辣
    if cuisine == "串串":
        return random.choice(["微辣", "中辣"])

    # 不辣关键词
    if any(kw in dish_name for kw in ["清蒸", "白灼", "清淡", "不辣", "原味", "清汤"]):
        return "不辣"

    # 特辣关键词
    if any(kw in dish_name for kw in ["特辣", "变态辣", "魔鬼辣"]):
        return "特辣"

    # 中辣关键词
    if any(kw in dish_name for kw in ["中辣", "香辣", "麻辣"]):
        return "中辣"

    # 微辣关键词
    if any(kw in dish_name for kw in ["微辣", "酸辣", "泡椒"]):
        return "微辣"

    # 川菜、湘菜
    if cuisine in ["川菜", "湘菜"]:
        if "辣" in dish_name:
            return random.choice(["微辣", "中辣", "特辣"])
        return random.choice(["微辣", "中辣"])

    # 火锅配菜
    if cuisine == "火锅":
        return random.choice(["不辣", "微辣"])

    # 烧烤
    if cuisine == "烧烤":
        return random.choice(["不辣", "微辣"])

    # 西北菜、新疆菜、东南亚
    if cuisine in ["西北菜", "新疆菜", "东南亚"]:
        return random.choice(["不辣", "微辣", "中辣"])

    # 鲁菜、京菜、粤菜、港式、台湾菜、清真
    if cuisine in ["鲁菜", "京菜", "粤菜", "港式", "台湾菜", "清真"]:
        return random.choice(["不辣", "微辣"])

    # 日料、韩餐、西餐、海鲜、小吃
    if cuisine in ["日料", "韩餐", "西餐", "海鲜", "小吃"]:
        return random.choice(["不辣", "微辣"])

    return "不辣"


# ========== 忌口检测函数 ==========
def get_allergens(dish_name: str) -> list:
    """根据菜品名称返回忌口标签"""
    allergens = []

    if "香菜" in dish_name or "芫荽" in dish_name:
        allergens.append("香菜")

    if "蒜" in dish_name or "大蒜" in dish_name or "蒜蓉" in dish_name or "蒜泥" in dish_name:
        allergens.append("蒜")

    if "花生" in dish_name or "花生米" in dish_name or "花生碎" in dish_name:
        allergens.append("花生")

    dairy_keywords = ["奶", "乳", "芝士", "奶酪", "黄油", "奶油", "酸奶", "双皮奶", "奶茶", "奶盖", "冰淇淋", "拿铁",
                      "卡布奇诺"]
    for kw in dairy_keywords:
        if kw in dish_name:
            allergens.append("乳制品")
            break

    return allergens


# ========== 生成菜品 ==========
def generate_dishes():
    """生成所有餐厅的菜品"""
    dishes_by_restaurant = {}

    for restaurant in RESTAURANTS:
        cuisine = restaurant["cuisine"]
        templates = DISH_TEMPLATES.get(cuisine, DISH_TEMPLATES["小吃"])

        num_dishes = random.randint(15, 20)
        selected = random.sample(templates, min(num_dishes, len(templates)))

        dishes = []
        for i, dish_name in enumerate(selected, 1):
            # 根据菜系和菜品类型设置价格
            if cuisine == "火锅":
                if "锅底" in dish_name:
                    # 锅底价格较高（30-50元）
                    price = random.uniform(30, 50)
                else:
                    # 配菜价格较低（5-20元）
                    price = random.uniform(5, 20)
            elif cuisine == "串串":
                if "锅底" in dish_name:
                    # 锅底价格（25-40元）
                    price = random.uniform(25, 40)
                else:
                    # 串串价格（3-15元）
                    price = random.uniform(3, 15)
            else:
                # 其他菜系：价格在餐厅均价上下浮动
                price = restaurant["avg_price"] * (0.5 + random.random() * 0.8)
                price = max(8, min(100, price))

            price = round(price, 1)

            dishes.append({
                "id": f"{restaurant['id']}_{i}",
                "name": dish_name,
                "price": price,
                "description": f"{restaurant['name']}的{dish_name}，{'招牌推荐' if i <= 3 else '人气热销'}",
                "tags": ["招牌" if i <= 3 else "热销" if i <= 8 else "推荐"],
                "spicy": get_spicy_level(dish_name, cuisine),
                "allergens": get_allergens(dish_name),
                "restaurant_id": restaurant["id"],
                "restaurant_name": restaurant["name"],
                "restaurant_rating": restaurant["rating"]
            })

        dishes_by_restaurant[restaurant["id"]] = dishes

    return dishes_by_restaurant


# 生成数据
DISHES_BY_RESTAURANT = generate_dishes()


# ========== 查询函数 ==========
def get_restaurant(restaurant_id: int) -> Optional[Dict]:
    """根据ID获取餐厅"""
    for r in RESTAURANTS:
        if r["id"] == restaurant_id:
            return r
    return None


def get_dishes_by_restaurant(restaurant_id: int) -> List[Dict]:
    """获取餐厅的菜品"""
    return DISHES_BY_RESTAURANT.get(restaurant_id, [])


def search_restaurants(cuisine: str = None, max_price: float = None, min_rating: float = None) -> List[Dict]:
    """搜索餐厅"""
    results = RESTAURANTS.copy()

    if cuisine and cuisine != "不限":
        results = [r for r in results if cuisine == r["cuisine"] or cuisine in r["tags"]]

    if max_price:
        results = [r for r in results if r["avg_price"] <= max_price]

    if min_rating:
        results = [r for r in results if r["rating"] >= min_rating]

    return sorted(results, key=lambda x: x["rating"], reverse=True)


def search_dishes(keyword: str = None, max_price: float = None, spicy: str = None,
                  restaurant_id: int = None, limit: int = 10) -> List[Dict]:
    """搜索菜品"""
    all_dishes = []
    for restaurant in RESTAURANTS:
        dishes = DISHES_BY_RESTAURANT.get(restaurant["id"], [])
        for dish in dishes:
            dish_copy = dish.copy()
            dish_copy["restaurant_info"] = restaurant
            all_dishes.append(dish_copy)

    results = all_dishes.copy()

    if keyword:
        results = [d for d in results if keyword in d["name"]]

    if max_price:
        results = [d for d in results if d["price"] <= max_price]

    if spicy and spicy != "不限":
        results = [d for d in results if d["spicy"] == spicy]

    if restaurant_id:
        results = [d for d in results if d["restaurant_id"] == restaurant_id]

    results.sort(key=lambda x: (-x["restaurant_rating"], x["price"]))

    return results[:limit]


def get_recommendations(user_prefs: dict, budget: float, keyword: str = None, limit: int = 5) -> List[Dict]:
    """根据用户偏好获取推荐"""
    spicy = user_prefs.get('spicy_level', '微辣')
    avoid_foods = user_prefs.get('avoid_foods', [])

    all_dishes = []
    for restaurant in RESTAURANTS:
        dishes = DISHES_BY_RESTAURANT.get(restaurant["id"], [])
        for dish in dishes:
            # 过滤忌口
            if any(a in dish.get("allergens", []) for a in avoid_foods):
                continue

            # 过滤预算
            if dish["price"] > budget * 1.2:
                continue

            # 辣度严格匹配
            dish_spicy = dish.get("spicy", "不辣")
            if dish_spicy != spicy:
                continue

            # 关键词匹配
            if keyword and keyword not in dish["name"]:
                continue

            all_dishes.append({
                "dish": dish,
                "restaurant": restaurant,
            })

    all_dishes.sort(key=lambda x: (-x["restaurant"]["rating"], x["dish"]["price"]))

    return all_dishes[:limit]
