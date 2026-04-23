# data/mock_restaurants.py
import random
import json
from typing import List, Dict, Optional

# ========== 餐厅数据（扩展到50家） ==========
RESTAURANTS = [
    # 川菜 (8家)
    {"id": 1, "name": "川湘小馆", "cuisine": "川菜", "rating": 4.8, "avg_price": 35, "delivery_time": 35, "sales": 2300,
     "tags": ["麻辣", "正宗", "老字号"]},
    {"id": 2, "name": "蜀味轩", "cuisine": "川菜", "rating": 4.7, "avg_price": 32, "delivery_time": 32, "sales": 1850,
     "tags": ["麻辣", "性价比高"]},
    {"id": 3, "name": "麻辣诱惑", "cuisine": "川菜", "rating": 4.9, "avg_price": 40, "delivery_time": 38, "sales": 3100,
     "tags": ["麻辣", "网红店"]},
    {"id": 4, "name": "成都小吃", "cuisine": "川菜", "rating": 4.6, "avg_price": 25, "delivery_time": 28, "sales": 2900,
     "tags": ["小吃", "实惠"]},
    {"id": 5, "name": "巴国布衣", "cuisine": "川菜", "rating": 4.7, "avg_price": 38, "delivery_time": 35, "sales": 1650,
     "tags": ["传统", "川菜"]},
    {"id": 6, "name": "渝乡人家", "cuisine": "川菜", "rating": 4.5, "avg_price": 30, "delivery_time": 30, "sales": 1450,
     "tags": ["家常", "实惠"]},
    {"id": 7, "name": "川味观", "cuisine": "川菜", "rating": 4.8, "avg_price": 45, "delivery_time": 40, "sales": 1200,
     "tags": ["精致", "川菜"]},
    {"id": 8, "name": "辣府", "cuisine": "川菜", "rating": 4.6, "avg_price": 35, "delivery_time": 33, "sales": 1750,
     "tags": ["麻辣", "香锅"]},

    # 粤菜 (5家)
    {"id": 9, "name": "粤式茶餐厅", "cuisine": "粤菜", "rating": 4.7, "avg_price": 42, "delivery_time": 30,
     "sales": 1850, "tags": ["清淡", "广式"]},
    {"id": 10, "name": "港岛茶餐厅", "cuisine": "粤菜", "rating": 4.8, "avg_price": 45, "delivery_time": 32,
     "sales": 2100, "tags": ["港式", "茶餐厅"]},
    {"id": 11, "name": "点都德", "cuisine": "粤菜", "rating": 4.9, "avg_price": 50, "delivery_time": 35, "sales": 2800,
     "tags": ["点心", "老字号"]},
    {"id": 12, "name": "广州酒家", "cuisine": "粤菜", "rating": 4.7, "avg_price": 48, "delivery_time": 35,
     "sales": 1650, "tags": ["传统", "粤菜"]},
    {"id": 13, "name": "避风塘", "cuisine": "粤菜", "rating": 4.6, "avg_price": 40, "delivery_time": 30, "sales": 1950,
     "tags": ["海鲜", "港式"]},

    # 湘菜 (4家)
    {"id": 14, "name": "湘味轩", "cuisine": "湘菜", "rating": 4.8, "avg_price": 38, "delivery_time": 32, "sales": 1980,
     "tags": ["香辣", "下饭"]},
    {"id": 15, "name": "毛家饭店", "cuisine": "湘菜", "rating": 4.7, "avg_price": 42, "delivery_time": 35,
     "sales": 1750, "tags": ["传统", "湘菜"]},
    {"id": 16, "name": "湘鄂情", "cuisine": "湘菜", "rating": 4.6, "avg_price": 35, "delivery_time": 30, "sales": 1450,
     "tags": ["家常", "实惠"]},
    {"id": 17, "name": "辣妹子", "cuisine": "湘菜", "rating": 4.5, "avg_price": 32, "delivery_time": 28, "sales": 1650,
     "tags": ["香辣", "家常"]},

    # 东北菜 (3家)
    {"id": 18, "name": "东北饺子馆", "cuisine": "东北菜", "rating": 4.7, "avg_price": 30, "delivery_time": 30,
     "sales": 1780, "tags": ["饺子", "实惠"]},
    {"id": 19, "name": "雪乡人家", "cuisine": "东北菜", "rating": 4.6, "avg_price": 32, "delivery_time": 32,
     "sales": 1450, "tags": ["家常", "分量足"]},
    {"id": 20, "name": "刘老根", "cuisine": "东北菜", "rating": 4.5, "avg_price": 28, "delivery_time": 28,
     "sales": 1650, "tags": ["实惠", "家常"]},

    # 日料 (4家)
    {"id": 21, "name": "日式料理屋", "cuisine": "日料", "rating": 4.8, "avg_price": 55, "delivery_time": 32,
     "sales": 1240, "tags": ["寿司", "刺身"]},
    {"id": 22, "name": "元气寿司", "cuisine": "日料", "rating": 4.7, "avg_price": 48, "delivery_time": 30,
     "sales": 1560, "tags": ["寿司", "回转"]},
    {"id": 23, "name": "一兰拉面", "cuisine": "日料", "rating": 4.6, "avg_price": 42, "delivery_time": 28,
     "sales": 1340, "tags": ["拉面", "日式"]},
    {"id": 24, "name": "鸟贵族", "cuisine": "日料", "rating": 4.5, "avg_price": 45, "delivery_time": 30, "sales": 1120,
     "tags": ["烧鸟", "居酒屋"]},

    # 韩餐 (3家)
    {"id": 25, "name": "韩式炸鸡", "cuisine": "韩餐", "rating": 4.6, "avg_price": 32, "delivery_time": 28,
     "sales": 2100, "tags": ["炸鸡", "啤酒"]},
    {"id": 26, "name": "火炉火", "cuisine": "韩餐", "rating": 4.7, "avg_price": 45, "delivery_time": 35, "sales": 1450,
     "tags": ["烤肉", "韩式"]},
    {"id": 27, "name": "韩国馆", "cuisine": "韩餐", "rating": 4.5, "avg_price": 38, "delivery_time": 30, "sales": 1250,
     "tags": ["韩餐", "家常"]},

    # 西餐 (4家)
    {"id": 28, "name": "西式简餐", "cuisine": "西餐", "rating": 4.6, "avg_price": 45, "delivery_time": 35,
     "sales": 1320, "tags": ["牛排", "意面"]},
    {"id": 29, "name": "必胜客", "cuisine": "西餐", "rating": 4.5, "avg_price": 50, "delivery_time": 32, "sales": 2100,
     "tags": ["披萨", "连锁"]},
    {"id": 30, "name": "萨莉亚", "cuisine": "西餐", "rating": 4.4, "avg_price": 35, "delivery_time": 28, "sales": 2500,
     "tags": ["实惠", "意餐"]},
    {"id": 31, "name": "星巴克", "cuisine": "西餐", "rating": 4.5, "avg_price": 38, "delivery_time": 20, "sales": 3200,
     "tags": ["咖啡", "轻食"]},

    # 火锅 (3家)
    {"id": 32, "name": "重庆火锅", "cuisine": "火锅", "rating": 4.9, "avg_price": 65, "delivery_time": 45,
     "sales": 2450, "tags": ["麻辣", "火锅"]},
    {"id": 33, "name": "海底捞", "cuisine": "火锅", "rating": 4.9, "avg_price": 70, "delivery_time": 50, "sales": 3500,
     "tags": ["服务好", "火锅"]},
    {"id": 34, "name": "潮汕牛肉火锅", "cuisine": "火锅", "rating": 4.8, "avg_price": 58, "delivery_time": 40,
     "sales": 1430, "tags": ["牛肉", "鲜嫩"]},

    # 小吃 (5家)
    {"id": 35, "name": "张记麻辣烫", "cuisine": "小吃", "rating": 4.9, "avg_price": 28, "delivery_time": 35,
     "sales": 3200, "tags": ["麻辣", "自选"]},
    {"id": 36, "name": "杨国福", "cuisine": "小吃", "rating": 4.7, "avg_price": 30, "delivery_time": 30, "sales": 2800,
     "tags": ["麻辣烫", "连锁"]},
    {"id": 37, "name": "沙县小吃", "cuisine": "小吃", "rating": 4.4, "avg_price": 20, "delivery_time": 22,
     "sales": 4500, "tags": ["实惠", "国民"]},
    {"id": 38, "name": "兰州拉面", "cuisine": "小吃", "rating": 4.5, "avg_price": 22, "delivery_time": 22,
     "sales": 2890, "tags": ["拉面", "实惠"]},
    {"id": 39, "name": "桂林米粉", "cuisine": "小吃", "rating": 4.5, "avg_price": 25, "delivery_time": 25,
     "sales": 1650, "tags": ["米粉", "酸辣"]},

    # 轻食 (3家)
    {"id": 40, "name": "轻食主义沙拉", "cuisine": "轻食", "rating": 4.6, "avg_price": 38, "delivery_time": 25,
     "sales": 890, "tags": ["健康", "低卡"]},
    {"id": 41, "name": "wagas", "cuisine": "轻食", "rating": 4.7, "avg_price": 48, "delivery_time": 28, "sales": 760,
     "tags": ["轻食", "网红"]},
    {"id": 42, "name": "新元素", "cuisine": "轻食", "rating": 4.6, "avg_price": 52, "delivery_time": 30, "sales": 680,
     "tags": ["健康", "西式"]},

    # 甜品 (4家)
    {"id": 43, "name": "甜品工坊", "cuisine": "甜品", "rating": 4.7, "avg_price": 25, "delivery_time": 25,
     "sales": 1670, "tags": ["甜品", "蛋糕"]},
    {"id": 44, "name": "满记甜品", "cuisine": "甜品", "rating": 4.8, "avg_price": 32, "delivery_time": 28,
     "sales": 1890, "tags": ["甜品", "连锁"]},
    {"id": 45, "name": "鲜芋仙", "cuisine": "甜品", "rating": 4.6, "avg_price": 28, "delivery_time": 25, "sales": 2100,
     "tags": ["芋圆", "甜品"]},
    {"id": 46, "name": "哈根达斯", "cuisine": "甜品", "rating": 4.7, "avg_price": 45, "delivery_time": 25, "sales": 890,
     "tags": ["冰淇淋", "高端"]},

    # 海鲜 (2家)
    {"id": 47, "name": "海鲜大排档", "cuisine": "海鲜", "rating": 4.7, "avg_price": 55, "delivery_time": 42,
     "sales": 1340, "tags": ["海鲜", "实惠"]},
    {"id": 48, "name": "海鲜码头", "cuisine": "海鲜", "rating": 4.8, "avg_price": 68, "delivery_time": 45, "sales": 980,
     "tags": ["海鲜", "新鲜"]},

    # 素食 (2家)
    {"id": 49, "name": "素食主义", "cuisine": "素食", "rating": 4.6, "avg_price": 35, "delivery_time": 28, "sales": 760,
     "tags": ["素食", "健康"]},
    {"id": 50, "name": "素生活", "cuisine": "素食", "rating": 4.5, "avg_price": 32, "delivery_time": 25, "sales": 580,
     "tags": ["素食", "清净"]},
]

# ========== 菜品模板（每个菜系20-30个菜品） ==========
DISH_TEMPLATES = {
    "川菜": ["麻婆豆腐", "宫保鸡丁", "水煮鱼", "回锅肉", "鱼香肉丝", "辣子鸡", "毛血旺", "酸菜鱼", "夫妻肺片", "口水鸡",
             "干煸豆角", "水煮肉片", "酸辣土豆丝", "麻婆茄子", "川味香肠", "担担面", "酸辣粉", "红油抄手", "龙抄手",
             "钟水饺",
             "沸腾鱼", "香辣虾", "花椒鸡", "豆瓣鱼", "蒜泥白肉", "棒棒鸡", "灯影牛肉", "毛血旺", "水煮牛肉", "小炒肉"],

    "粤菜": ["叉烧饭", "烧鹅饭", "白切鸡", "豉汁蒸排骨", "虾饺", "肠粉", "凤爪", "奶黄包", "流沙包", "糯米鸡",
             "干炒牛河", "湿炒牛河", "云吞面", "牛腩面", "煲仔饭", "腊味饭", "菠萝包", "蛋挞", "杨枝甘露", "双皮奶",
             "烧卖", "叉烧酥", "萝卜糕", "马蹄糕", "虾肠", "牛肉肠", "艇仔粥", "皮蛋瘦肉粥", "及第粥", "状元及第粥"],

    "湘菜": ["剁椒鱼头", "小炒黄牛肉", "辣椒炒肉", "农家小炒肉", "湘西外婆菜", "臭豆腐", "口味虾", "口味蛇", "腊味合蒸",
             "毛氏红烧肉",
             "东安鸡", "血鸭", "永州血鸭", "衡阳鱼粉", "长沙米粉", "糖油粑粑", "葱油粑粑", "刮凉粉", "姊妹团子",
             "龙脂猪血",
             "土匪猪肝", "香辣蟹", "蒜香排骨", "干锅肥肠", "干锅花菜", "干锅千页豆腐", "酸豆角炒肉", "擂辣椒皮蛋",
             "湘西腊肉", "烟笋炒腊肉"],

    "东北菜": ["猪肉炖粉条", "小鸡炖蘑菇", "锅包肉", "地三鲜", "溜肉段", "酸菜炖排骨", "酱骨架", "东北大拉皮",
               "东北乱炖", "雪衣豆沙",
               "拔丝地瓜", "杀猪菜", "血肠", "粘豆包", "韭菜盒子", "酸菜饺子", "白菜猪肉饺", "芹菜猪肉饺", "三鲜饺",
               "玉米面饼",
               "红烧排骨", "溜肥肠", "酱猪蹄", "红烧肉", "铁锅炖", "大丰收", "老虎菜", "蘸酱菜", "皮冻", "焖子"],

    "日料": ["三文鱼刺身", "北极贝刺身", "甜虾刺身", "加州卷", "鳗鱼寿司", "三文鱼寿司", "天妇罗", "炸猪排", "日式拉面",
             "乌冬面",
             "照烧鸡排饭", "牛肉饭", "亲子丼", "咖喱猪排饭", "味增汤", "茶碗蒸", "日式煎饺", "章鱼小丸子", "大福",
             "抹茶蛋糕",
             "玉子烧", "关东煮", "荞麦面", "冷面", "寿喜锅", "日式火锅", "刺身拼盘", "寿司拼盘", "盐烤青花鱼",
             "烤鳗鱼"],

    "韩餐": ["原味炸鸡", "甜辣炸鸡", "蒜香炸鸡", "酱油炸鸡", "芝士炸鸡", "韩式年糕", "泡菜炒饭", "石锅拌饭", "韩式冷面",
             "泡菜汤",
             "大酱汤", "豆腐汤", "韩式烤肉", "烤五花肉", "烤牛肉", "韩式炸酱面", "海鲜饼", "泡菜饼", "炒年糕", "鱼饼汤",
             "部队火锅", "参鸡汤", "辣炒年糕", "韩式拌饭", "紫菜包饭", "辣白菜", "韩式炖鸡", "韩式猪蹄", "韩式炸鸡翅",
             "韩式鸡爪"],

    "西餐": ["牛排", "意面", "汉堡", "披萨", "沙拉", "薯条", "炸鸡", "烤鸡", "三明治", "热狗",
             "焗饭", "奶油蘑菇汤", "南瓜汤", "罗宋汤", "提拉米苏", "芝士蛋糕", "布朗尼", "马卡龙", "泡芙", "可颂",
             "凯撒沙拉", "蔬菜沙拉", "水果沙拉", "烤羊排", "烤三文鱼", "海鲜意面", "肉酱意面", "奶油意面", "夏威夷披萨",
             "海鲜披萨"],

    "火锅": ["麻辣锅底", "番茄锅底", "菌菇锅底", "清汤锅底", "肥牛卷", "肥羊卷", "虾滑", "毛肚", "鸭肠", "黄喉",
             "午餐肉", "蟹肉棒", "鱼丸", "牛肉丸", "羊肉丸", "蔬菜拼盘", "菌菇拼盘", "豆腐拼盘", "粉丝", "火锅面",
             "金针菇", "香菇", "娃娃菜", "茼蒿", "菠菜", "土豆片", "藕片", "山药", "豆皮", "腐竹"],

    "小吃": ["麻辣烫", "炸串", "烤冷面", "煎饼果子", "肉夹馍", "凉皮", "酸辣粉", "臭豆腐", "烤面筋", "烤鱿鱼",
             "章鱼烧", "炸鸡排", "盐酥鸡", "甘梅薯条", "地瓜球", "车轮饼", "鸡蛋仔", "格仔饼", "鱼蛋", "牛杂",
             "烤红薯", "糖炒栗子", "冰糖葫芦", "棉花糖", "爆米花", "关东煮", "烤肠", "手抓饼", "烧饼", "煎包"],

    "轻食": ["鸡胸肉沙拉", "牛油果沙拉", "三文鱼沙拉", "藜麦沙拉", "酸奶碗", "水果杯", "全麦三明治", "素食卷", "能量碗",
             "思慕雪",
             "羽衣甘蓝沙拉", "荞麦面沙拉", "虾仁沙拉", "金枪鱼沙拉", "鸡肉卷", "蔬菜卷", "水果沙拉", "酸奶麦片",
             "奇亚籽布丁", "燕麦杯",
             "波奇饭", "轻食套餐", "素食套餐", "减脂餐", "蛋白质碗", "绿色果汁", "冷压果汁", "果昔", "巴西莓碗",
             "椰奶碗"],

    "甜品": ["芒果慕斯", "巧克力蛋糕", "芝士蛋糕", "提拉米苏", "泡芙", "马卡龙", "布丁", "双皮奶", "杨枝甘露",
             "芒果班戟",
             "榴莲班戟", "千层蛋糕", "雪媚娘", "大福", "糯米糍", "冰淇淋", "奶茶", "水果茶", "奶盖茶", "果汁",
             "芋圆", "烧仙草", "豆花", "糖水", "西米露", "椰汁糕", "红豆沙", "绿豆沙", "芝麻糊", "杏仁茶"],

    "海鲜": ["清蒸鲈鱼", "蒜蓉扇贝", "椒盐皮皮虾", "香辣蟹", "白灼虾", "蒜蓉生蚝", "烤生蚝", "烤扇贝", "烤鱿鱼", "烤鱼",
             "海鲜炒饭", "海鲜面", "海鲜粥", "海鲜汤", "海鲜拼盘", "刺身拼盘", "寿司拼盘", "海鲜沙拉", "海鲜火锅",
             "海鲜大咖"],

    "素食": ["素菜包", "素饺子", "素春卷", "素烧鹅", "素鸡", "素鸭", "素火腿", "素肉", "素鱼", "素虾",
             "素什锦", "素炒面", "素炒饭", "素汤", "素火锅", "素汉堡", "素披萨", "素寿司", "素刺身", "素蛋糕"],
}


# ========== 忌口检测函数 ==========
def get_allergens(dish_name: str) -> list:
    """根据菜品名称返回忌口标签"""
    allergens = []

    # 香菜
    if "香菜" in dish_name or "芫荽" in dish_name:
        allergens.append("香菜")

    # 蒜
    if "蒜" in dish_name or "大蒜" in dish_name or "蒜蓉" in dish_name or "蒜泥" in dish_name:
        allergens.append("蒜")

    # 花生
    if "花生" in dish_name or "花生米" in dish_name or "花生碎" in dish_name or "花生酱" in dish_name:
        allergens.append("花生")

    # 乳制品
    dairy_keywords = ["奶", "乳", "芝士", "奶酪", "黄油", "奶油", "酸奶", "双皮奶", "奶茶", "乳酪", "奶盖", "冰淇淋"]
    for kw in dairy_keywords:
        if kw in dish_name:
            allergens.append("乳制品")
            break

    return allergens


SPICY_LEVELS = ["不辣", "微辣", "中辣", "特辣"]


def get_spicy_level(dish_name: str, cuisine: str) -> str:
    """根据菜品名称和菜系返回辣度等级"""

    # 明确的不辣关键词
    if any(kw in dish_name for kw in ["清蒸", "白灼", "清淡", "不辣", "原味", "清汤"]):
        return "不辣"

    # 特辣关键词
    if any(kw in dish_name for kw in ["特辣", "变态辣", "魔鬼辣", "猛辣"]):
        return "特辣"

    # 中辣关键词
    if any(kw in dish_name for kw in ["中辣", "香辣", "香辣", "麻辣"]):
        return "中辣"

    # 微辣关键词
    if any(kw in dish_name for kw in ["微辣", "酸辣", "酸辣", "泡椒"]):
        return "微辣"

    # 根据菜系判断
    if cuisine in ["川菜", "湘菜"]:
        if "辣" in dish_name:
            return random.choice(["微辣", "中辣", "特辣"])
        return random.choice(["不辣", "微辣", "中辣"])
    elif cuisine in ["火锅", "小吃", "西北菜", "新疆菜"]:
        return random.choice(["不辣", "微辣", "中辣"])
    elif cuisine in ["粤菜", "港式", "京菜"]:
        return random.choice(["不辣", "微辣"])
    elif cuisine in ["日料", "韩餐", "西餐", "轻食", "甜品"]:
        return "不辣"  # 这些菜系默认不辣
    else:
        return random.choice(["不辣", "微辣"])


# ========== 生成菜品 ==========
def generate_dishes():
    """生成所有餐厅的菜品"""
    dishes_by_restaurant = {}

    for restaurant in RESTAURANTS:
        cuisine = restaurant["cuisine"]
        templates = DISH_TEMPLATES.get(cuisine, DISH_TEMPLATES["小吃"])

        # 随机选择20-25个菜品（同一店内以主菜系为主）
        num_dishes = random.randint(20, 25)
        selected = random.sample(templates, min(num_dishes, len(templates)))

        # 再添加2-3个其他菜系的菜品作为特色
        other_cuisines = [c for c in DISH_TEMPLATES.keys() if c != cuisine]
        other_cuisine = random.choice(other_cuisines)
        other_templates = DISH_TEMPLATES.get(other_cuisine, DISH_TEMPLATES["小吃"])
        other_dishes = random.sample(other_templates, min(3, len(other_templates)))
        selected.extend(other_dishes)

        dishes = []
        for i, dish_name in enumerate(selected, 1):
            # 菜品价格在餐厅均价上下浮动
            price = round(restaurant["avg_price"] * (0.5 + random.random() * 1.0), 1)
            price = max(10, min(120, price))

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
        results = [r for r in results if cuisine in r["cuisine"] or cuisine in r["tags"]]

    if max_price:
        results = [r for r in results if r["avg_price"] <= max_price]

    if min_rating:
        results = [r for r in results if r["rating"] >= min_rating]

    return sorted(results, key=lambda x: x["rating"], reverse=True)


def search_dishes(keyword: str = None, max_price: float = None, spicy: str = None,
                  restaurant_id: int = None, limit: int = 10) -> List[Dict]:
    """搜索菜品，按评分和价格排序（评分高优先，同评分价格低优先）"""
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
        if spicy == "不辣":
            results = [d for d in results if d["spicy"] == "不辣"]
        elif spicy == "微辣":
            results = [d for d in results if d["spicy"] in ["不辣", "微辣"]]
        elif spicy == "中辣":
            results = [d for d in results if d["spicy"] in ["微辣", "中辣"]]
        else:
            results = [d for d in results if d["spicy"] in ["中辣", "特辣", "麻辣"]]

    if restaurant_id:
        results = [d for d in results if d["restaurant_id"] == restaurant_id]

    # 评分高优先，同评分价格低优先
    results.sort(key=lambda x: (-x["restaurant_rating"], x["price"]))

    return results[:limit]


def get_recommendations(user_prefs: dict, budget: float, keyword: str = None, limit: int = 5) -> List[Dict]:
    """
    根据用户偏好获取推荐
    返回：菜品列表，每个菜品包含餐厅信息
    排序：评分高优先，同评分价格低优先
    """
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

            # 辣度匹配
            dish_spicy = dish.get("spicy", "微辣")
            if spicy == "不辣" and dish_spicy != "不辣":
                continue
            elif spicy == "微辣" and dish_spicy not in ["不辣", "微辣"]:
                continue
            elif spicy == "中辣" and dish_spicy not in ["微辣", "中辣"]:
                continue
            elif spicy == "特辣" and dish_spicy not in ["中辣", "特辣", "麻辣"]:
                continue

            # 关键词匹配
            if keyword and keyword not in dish["name"]:
                continue

            all_dishes.append({
                "dish": dish,
                "restaurant": restaurant,
                "score": restaurant["rating"] * 10 - dish["price"] * 0.1  # 综合评分
            })

    # 按餐厅评分降序，价格升序
    all_dishes.sort(key=lambda x: (-x["restaurant"]["rating"], x["dish"]["price"]))

    return all_dishes[:limit]
