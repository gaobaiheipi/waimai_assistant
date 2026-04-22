# data/mock_restaurants.py
"""30个餐厅，每个餐厅20个菜品的Mock数据集"""

import random
import json
from typing import List, Dict, Optional

# 餐厅数据
RESTAURANTS = [
    {"id": 1, "name": "川湘小馆", "cuisine": "川菜", "rating": 4.8, "avg_price": 35, "delivery_time": 35, "sales": 2300,
     "tags": ["麻辣", "正宗", "老字号"]},
    {"id": 2, "name": "粤式茶餐厅", "cuisine": "粤菜", "rating": 4.7, "avg_price": 42, "delivery_time": 30,
     "sales": 1850, "tags": ["清淡", "广式", "粥粉面"]},
    {"id": 3, "name": "张记麻辣烫", "cuisine": "小吃", "rating": 4.9, "avg_price": 28, "delivery_time": 35,
     "sales": 3200, "tags": ["麻辣", "可定制", "性价比高"]},
    {"id": 4, "name": "轻食主义沙拉", "cuisine": "轻食", "rating": 4.6, "avg_price": 38, "delivery_time": 25,
     "sales": 890, "tags": ["健康", "低卡", "减肥"]},
    {"id": 5, "name": "西北风味", "cuisine": "西北菜", "rating": 4.7, "avg_price": 40, "delivery_time": 40,
     "sales": 1560, "tags": ["面食", "羊肉", "分量足"]},
    {"id": 6, "name": "日式料理屋", "cuisine": "日料", "rating": 4.8, "avg_price": 55, "delivery_time": 32,
     "sales": 1240, "tags": ["寿司", "刺身", "精致"]},
    {"id": 7, "name": "韩式炸鸡", "cuisine": "韩餐", "rating": 4.6, "avg_price": 32, "delivery_time": 28, "sales": 2100,
     "tags": ["炸鸡", "啤酒", "外卖"]},
    {"id": 8, "name": "东北饺子馆", "cuisine": "东北菜", "rating": 4.7, "avg_price": 30, "delivery_time": 30,
     "sales": 1780, "tags": ["饺子", "实惠", "家常"]},
    {"id": 9, "name": "泰式风情", "cuisine": "东南亚", "rating": 4.5, "avg_price": 48, "delivery_time": 38,
     "sales": 950, "tags": ["酸辣", "咖喱", "异国"]},
    {"id": 10, "name": "西式简餐", "cuisine": "西餐", "rating": 4.6, "avg_price": 45, "delivery_time": 35,
     "sales": 1320, "tags": ["牛排", "意面", "汉堡"]},
    {"id": 11, "name": "湘味轩", "cuisine": "湘菜", "rating": 4.8, "avg_price": 38, "delivery_time": 32, "sales": 1980,
     "tags": ["香辣", "下饭", "火爆"]},
    {"id": 12, "name": "港式茶餐厅", "cuisine": "港式", "rating": 4.7, "avg_price": 40, "delivery_time": 30,
     "sales": 1670, "tags": ["奶茶", "菠萝包", "烧腊"]},
    {"id": 13, "name": "重庆火锅", "cuisine": "火锅", "rating": 4.9, "avg_price": 65, "delivery_time": 45,
     "sales": 2450, "tags": ["麻辣", "火锅", "聚会"]},
    {"id": 14, "name": "清真拉面", "cuisine": "清真", "rating": 4.6, "avg_price": 28, "delivery_time": 25,
     "sales": 1890, "tags": ["拉面", "牛肉", "清真"]},
    {"id": 15, "name": "潮汕牛肉火锅", "cuisine": "火锅", "rating": 4.8, "avg_price": 58, "delivery_time": 40,
     "sales": 1430, "tags": ["牛肉", "鲜嫩", "清淡"]},
    {"id": 16, "name": "新疆大盘鸡", "cuisine": "新疆菜", "rating": 4.7, "avg_price": 42, "delivery_time": 38,
     "sales": 1120, "tags": ["大盘鸡", "羊肉串", "分量大"]},
    {"id": 17, "name": "台湾小吃", "cuisine": "台湾菜", "rating": 4.5, "avg_price": 30, "delivery_time": 28,
     "sales": 980, "tags": ["卤肉饭", "蚵仔煎", "奶茶"]},
    {"id": 18, "name": "北京烤鸭店", "cuisine": "京菜", "rating": 4.8, "avg_price": 68, "delivery_time": 45,
     "sales": 870, "tags": ["烤鸭", "精品", "宴请"]},
    {"id": 19, "name": "素食主义", "cuisine": "素食", "rating": 4.6, "avg_price": 35, "delivery_time": 28, "sales": 760,
     "tags": ["素食", "健康", "环保"]},
    {"id": 20, "name": "海鲜大排档", "cuisine": "海鲜", "rating": 4.7, "avg_price": 55, "delivery_time": 42,
     "sales": 1340, "tags": ["海鲜", "新鲜", "实惠"]},
    {"id": 21, "name": "螺蛳粉", "cuisine": "小吃", "rating": 4.5, "avg_price": 25, "delivery_time": 25, "sales": 2100,
     "tags": ["螺蛳粉", "酸辣", "网红"]},
    {"id": 22, "name": "黄焖鸡米饭", "cuisine": "鲁菜", "rating": 4.6, "avg_price": 28, "delivery_time": 28,
     "sales": 3100, "tags": ["黄焖鸡", "米饭", "快餐"]},
    {"id": 23, "name": "沙县小吃", "cuisine": "小吃", "rating": 4.4, "avg_price": 20, "delivery_time": 22,
     "sales": 4500, "tags": ["实惠", "快餐", "国民"]},
    {"id": 24, "name": "酸菜鱼", "cuisine": "川菜", "rating": 4.8, "avg_price": 48, "delivery_time": 35, "sales": 1980,
     "tags": ["酸菜鱼", "酸辣", "下饭"]},
    {"id": 25, "name": "小龙虾", "cuisine": "小吃", "rating": 4.7, "avg_price": 58, "delivery_time": 40, "sales": 1650,
     "tags": ["小龙虾", "夜宵", "麻辣"]},
    {"id": 26, "name": "披萨先生", "cuisine": "西餐", "rating": 4.6, "avg_price": 48, "delivery_time": 32,
     "sales": 1420, "tags": ["披萨", "意面", "外卖"]},
    {"id": 27, "name": "寿司郎", "cuisine": "日料", "rating": 4.8, "avg_price": 52, "delivery_time": 30, "sales": 1180,
     "tags": ["寿司", "刺身", "回转"]},
    {"id": 28, "name": "兰州拉面", "cuisine": "清真", "rating": 4.5, "avg_price": 22, "delivery_time": 22,
     "sales": 2890, "tags": ["拉面", "牛肉", "实惠"]},
    {"id": 29, "name": "麻辣香锅", "cuisine": "川菜", "rating": 4.8, "avg_price": 38, "delivery_time": 32,
     "sales": 2350, "tags": ["麻辣", "香锅", "自选"]},
    {"id": 30, "name": "甜品工坊", "cuisine": "甜品", "rating": 4.7, "avg_price": 25, "delivery_time": 25,
     "sales": 1670, "tags": ["甜品", "蛋糕", "奶茶"]},
]


# 为每个餐厅生成20个菜品
def generate_dishes():
    """生成所有餐厅的菜品"""
    dishes_by_restaurant = {}

    dish_templates = {
        "川菜": ["麻婆豆腐", "宫保鸡丁", "水煮鱼", "回锅肉", "鱼香肉丝", "辣子鸡", "毛血旺", "酸菜鱼", "夫妻肺片",
                 "口水鸡",
                 "干煸豆角", "水煮肉片", "酸辣土豆丝", "麻婆茄子", "川味香肠", "担担面", "酸辣粉", "红油抄手", "龙抄手",
                 "钟水饺"],
        "粤菜": ["叉烧饭", "烧鹅饭", "白切鸡", "豉汁蒸排骨", "虾饺", "肠粉", "凤爪", "奶黄包", "流沙包", "糯米鸡",
                 "干炒牛河", "湿炒牛河", "云吞面", "牛腩面", "煲仔饭", "腊味饭", "菠萝包", "蛋挞", "杨枝甘露",
                 "双皮奶"],
        "小吃": ["麻辣烫", "炸串", "烤冷面", "煎饼果子", "肉夹馍", "凉皮", "酸辣粉", "臭豆腐", "烤面筋", "烤鱿鱼",
                 "章鱼烧", "炸鸡排", "盐酥鸡", "甘梅薯条", "地瓜球", "车轮饼", "鸡蛋仔", "格仔饼", "鱼蛋", "牛杂"],
        "轻食": ["鸡胸肉沙拉", "牛油果沙拉", "三文鱼沙拉", "藜麦沙拉", "酸奶碗", "水果杯", "全麦三明治", "素食卷",
                 "能量碗", "思慕雪",
                 "羽衣甘蓝沙拉", "荞麦面沙拉", "虾仁沙拉", "金枪鱼沙拉", "鸡肉卷", "蔬菜卷", "水果沙拉", "酸奶麦片",
                 "奇亚籽布丁", "燕麦杯"],
        "西北菜": ["羊肉泡馍", "肉夹馍", "凉皮", "油泼面", "biangbiang面", "臊子面", "裤带面", "羊肉串", "烤羊排",
                   "手抓羊肉",
                   "大盘鸡", "馕包肉", "烤包子", "羊肉抓饭", "酸奶", "甜醅子", "灰豆子", "酿皮", "浆水面", "牛肉面"],
        "日料": ["三文鱼刺身", "北极贝刺身", "甜虾刺身", "加州卷", "鳗鱼寿司", "三文鱼寿司", "天妇罗", "炸猪排",
                 "日式拉面", "乌冬面",
                 "照烧鸡排饭", "牛肉饭", "亲子丼", "咖喱猪排饭", "味增汤", "茶碗蒸", "日式煎饺", "章鱼小丸子", "大福",
                 "抹茶蛋糕"],
        "韩餐": ["原味炸鸡", "甜辣炸鸡", "蒜香炸鸡", "酱油炸鸡", "芝士炸鸡", "韩式年糕", "泡菜炒饭", "石锅拌饭",
                 "韩式冷面", "泡菜汤",
                 "大酱汤", "豆腐汤", "韩式烤肉", "烤五花肉", "烤牛肉", "韩式炸酱面", "海鲜饼", "泡菜饼", "炒年糕",
                 "鱼饼汤"],
        "东北菜": ["猪肉炖粉条", "小鸡炖蘑菇", "锅包肉", "地三鲜", "溜肉段", "酸菜炖排骨", "酱骨架", "东北大拉皮",
                   "东北乱炖", "雪衣豆沙",
                   "拔丝地瓜", "杀猪菜", "血肠", "粘豆包", "韭菜盒子", "酸菜饺子", "白菜猪肉饺", "芹菜猪肉饺", "三鲜饺",
                   "玉米面饼"],
        "东南亚": ["冬阴功汤", "绿咖喱鸡", "黄咖喱蟹", "红咖喱牛肉", "芒果糯米饭", "泰式炒河粉", "菠萝炒饭", "泰式奶茶",
                   "青木瓜沙拉", "泰式春卷",
                   "海南鸡饭", "肉骨茶", "叻沙", "椰浆饭", "沙爹串", "越南河粉", "越南春卷", "印尼炒饭", "巴东牛肉",
                   "摩摩喳喳"],
        "西餐": ["牛排", "意面", "汉堡", "披萨", "沙拉", "薯条", "炸鸡", "烤鸡", "三明治", "热狗",
                 "焗饭", "奶油蘑菇汤", "南瓜汤", "罗宋汤", "提拉米苏", "芝士蛋糕", "布朗尼", "马卡龙", "泡芙", "可颂"],
        "湘菜": ["剁椒鱼头", "小炒黄牛肉", "辣椒炒肉", "农家小炒肉", "湘西外婆菜", "臭豆腐", "口味虾", "口味蛇",
                 "腊味合蒸", "毛氏红烧肉",
                 "东安鸡", "血鸭", "永州血鸭", "衡阳鱼粉", "长沙米粉", "糖油粑粑", "葱油粑粑", "刮凉粉", "姊妹团子",
                 "龙脂猪血"],
        "港式": ["烧鹅饭", "叉烧饭", "烧肉饭", "烧鸭饭", "烧腩仔", "烧味拼盘", "干炒牛河", "湿炒牛河", "云吞面",
                 "牛腩面",
                 "虾饺", "烧卖", "凤爪", "排骨", "奶黄包", "流沙包", "叉烧包", "糯米鸡", "肠粉", "蛋挞"],
        "火锅": ["麻辣锅底", "番茄锅底", "菌菇锅底", "清汤锅底", "肥牛卷", "肥羊卷", "虾滑", "毛肚", "鸭肠", "黄喉",
                 "午餐肉", "蟹肉棒", "鱼丸", "牛肉丸", "羊肉丸", "蔬菜拼盘", "菌菇拼盘", "豆腐拼盘", "粉丝", "火锅面"],
        "清真": ["牛肉拉面", "羊肉拉面", "牛肉炒面", "羊肉炒面", "牛肉盖饭", "羊肉盖饭", "牛肉泡馍", "羊肉泡馍",
                 "牛肉饺子", "羊肉饺子",
                 "烤羊肉串", "烤牛肉串", "烤鸡翅", "烤馕", "手抓羊肉", "大盘鸡", "酸奶", "奶茶", "馕包肉", "馕炒肉"],
        "新疆菜": ["大盘鸡", "羊肉串", "手抓饭", "馕包肉", "烤羊排", "烤包子", "拉条子", "丁丁炒面", "过油肉拌面",
                   "新疆酸奶",
                   "奶茶", "馕", "烤全羊", "胡辣羊蹄", "椒麻鸡", "皮带面", "烤鱼", "烤鸽子", "烤鸡蛋", "格瓦斯"],
        "台湾菜": ["卤肉饭", "鸡肉饭", "控肉饭", "排骨饭", "鸡腿饭", "蚵仔煎", "蚵仔面线", "大肠包小肠", "盐酥鸡",
                   "甜不辣",
                   "棺材板", "担仔面", "牛肉面", "牛肉卷饼", "葱油饼", "芋圆", "烧仙草", "珍珠奶茶", "凤梨酥",
                   "太阳饼"],
        "京菜": ["北京烤鸭", "京酱肉丝", "宫保鸡丁", "老北京炸酱面", "爆肚", "卤煮火烧", "炒肝", "豆汁", "焦圈",
                 "豌豆黄",
                 "驴打滚", "艾窝窝", "糖火烧", "麻豆腐", "炸灌肠", "炒疙瘩", "糊塌子", "门钉肉饼", "褡裢火烧",
                 "芸豆卷"],
        "素食": ["素菜包", "素饺子", "素春卷", "素烧鹅", "素鸡", "素鸭", "素火腿", "素肉", "素鱼", "素虾",
                 "素什锦", "素炒面", "素炒饭", "素汤", "素火锅", "素汉堡", "素披萨", "素寿司", "素刺身", "素蛋糕"],
        "海鲜": ["清蒸鲈鱼", "蒜蓉扇贝", "椒盐皮皮虾", "香辣蟹", "白灼虾", "蒜蓉生蚝", "烤生蚝", "烤扇贝", "烤鱿鱼",
                 "烤鱼",
                 "海鲜炒饭", "海鲜面", "海鲜粥", "海鲜汤", "海鲜拼盘", "刺身拼盘", "寿司拼盘", "海鲜沙拉", "海鲜火锅",
                 "海鲜大咖"],
        "鲁菜": ["黄焖鸡", "葱烧海参", "九转大肠", "糖醋鲤鱼", "油爆双脆", "德州扒鸡", "奶汤蒲菜", "孔府菜", "泰山三美",
                 "周村烧饼"],
        "甜品": ["芒果慕斯", "巧克力蛋糕", "芝士蛋糕", "提拉米苏", "泡芙", "马卡龙", "布丁", "双皮奶", "杨枝甘露",
                 "芒果班戟",
                 "榴莲班戟", "千层蛋糕", "雪媚娘", "大福", "糯米糍", "冰淇淋", "奶茶", "水果茶", "奶盖茶", "果汁"],
    }

    for restaurant in RESTAURANTS:
        cuisine = restaurant["cuisine"]
        templates = dish_templates.get(cuisine, dish_templates["小吃"])

        # 随机选择20个菜品
        selected = random.sample(templates, min(20, len(templates)))

        dishes = []
        for i, dish_name in enumerate(selected, 1):
            # 生成菜品价格（餐厅均价上下浮动）
            base_price = restaurant["avg_price"]
            price = round(base_price * (0.6 + random.random() * 0.8), 1)
            price = max(12, min(98, price))

            dishes.append({
                "id": f"{restaurant['id']}_{i}",
                "name": dish_name,
                "price": price,
                "description": f"{restaurant['name']}的招牌{dish_name}，深受顾客喜爱",
                "tags": ["招牌" if i <= 3 else "热销" if i <= 8 else "推荐"],
                "spicy": "麻辣" if "辣" in dish_name or cuisine in ["川菜",
                                                                    "湘菜"] else "微辣" if random.random() > 0.7 else "不辣"
            })

        dishes_by_restaurant[restaurant["id"]] = dishes

    return dishes_by_restaurant


# 全局数据
DISHES_BY_RESTAURANT = generate_dishes()


def get_all_dishes() -> List[Dict]:
    """获取所有菜品"""
    all_dishes = []
    for dishes in DISHES_BY_RESTAURANT.values():
        all_dishes.extend(dishes)
    return all_dishes


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


def search_dishes(keyword: str = None, max_price: float = None, spicy: str = None) -> List[Dict]:
    """搜索菜品"""
    all_dishes = get_all_dishes()
    results = all_dishes.copy()

    if keyword:
        results = [d for d in results if keyword in d["name"] or keyword in d["description"]]

    if max_price:
        results = [d for d in results if d["price"] <= max_price]

    if spicy and spicy != "不限":
        if spicy == "不辣":
            results = [d for d in results if d["spicy"] == "不辣"]
        elif spicy == "微辣":
            results = [d for d in results if d["spicy"] in ["微辣", "不辣"]]
        else:
            results = [d for d in results if d["spicy"] == spicy]

    return results


def get_recommendations(user_prefs: dict, budget: float, keyword: str = None, limit: int = 5) -> List[Dict]:
    """
    根据用户偏好获取推荐
    返回：菜品列表，每个菜品包含餐厅信息
    """
    spicy = user_prefs.get('spicy_level', '微辣')
    avoid_foods = user_prefs.get('avoid_foods', [])

    # 搜索符合预算的餐厅
    restaurants = search_restaurants(max_price=budget * 1.2)

    recommendations = []

    for restaurant in restaurants[:10]:  # 最多考虑10家餐厅
        dishes = get_dishes_by_restaurant(restaurant["id"])

        for dish in dishes:
            # 过滤忌口
            if any(avoid in dish["name"] for avoid in avoid_foods):
                continue

            # 过滤价格
            if dish["price"] > budget * 1.2:
                continue

            # 辣度匹配
            if spicy == "不辣" and dish["spicy"] not in ["不辣"]:
                continue
            elif spicy == "微辣" and dish["spicy"] not in ["不辣", "微辣"]:
                continue

            # 关键词匹配
            if keyword and keyword not in dish["name"] and keyword not in restaurant["name"]:
                continue

            recommendations.append({
                "dish": dish,
                "restaurant": restaurant,
                "score": restaurant["rating"] * 10 + (100 - dish["price"]) * 0.5
            })

    # 按分数排序
    recommendations.sort(key=lambda x: x["score"], reverse=True)

    return recommendations[:limit]
