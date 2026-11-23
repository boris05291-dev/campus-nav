# ui/scenery.py
# 負責：畫地圖的「風景」——綠色校園地面、湖、操場、停車場、建築物、樹。
# 這些只是裝飾，和找路線無關。座標都跟 map_data.json 一樣（同一套像素座標），
# 畫的時候用 map_view.to_canvas() 換算成畫布座標，所以會跟道路對齊。

import random

import config

# 校園綠地的外框（順時針一圈的點），畫的時候用 smooth 變成圓滑的山丘形狀
LAND = [
    (380, 250), (420, 180), (500, 130), (600, 95), (700, 60), (780, 55),
    (860, 70), (960, 80), (1060, 120), (1150, 150), (1260, 160), (1360, 175),
    (1480, 180), (1600, 185), (1600, 640), (1450, 630), (1300, 640),
    (1150, 650), (1050, 690), (950, 740), (860, 770), (720, 775), (690, 700),
    (680, 600), (640, 520), (560, 470), (470, 460), (400, 430), (370, 340),
]

# 兩個湖的外框
LAKES = [
    # 影清湖
    [(430, 400), (470, 383), (520, 392), (575, 385), (610, 402), (585, 428),
     (530, 432), (485, 450), (440, 432)],
    # 靜月湖
    [(1195, 375), (1220, 352), (1265, 350), (1305, 362), (1300, 395),
     (1260, 410), (1215, 402)],
]

# 方形的場地：(左, 上, 右, 下, 顏色)
FIELDS = [
    (850, 600, 920, 650, "#D9C3BE"),    # 14 學生停車場
    (690, 600, 738, 700, "#D9C3BE"),    # 15 學生停車場
    (1010, 194, 1062, 232, "#D9C3BE"),  # 13 學生停車場
    (955, 298, 985, 328, "#D9C3BE"),    # 16 教職員停車場
    (940, 418, 966, 442, "#B5574A"),    # 2 球場（左半）
    (972, 418, 998, 442, "#B5574A"),    # 2 球場（右半）
    (903, 226, 931, 240, "#4E8FB5"),    # 9 網球場
]

# 建築物：(地點 id, 往右偏移, 往下偏移, 寬, 高, 屋頂顏色)
# 位置直接用 map_data.json 裡那個地點的 x、y，在 JSON 移動地點，建築物就會跟著移動，不用改兩個地方
# 偏移通常是 0；M、N 的圓點在建築物上緣，所以建築物往下畫一點
BUILDINGS = [
    ("J", 0, 0, 50, 30, "#8FD3CF"),     # J 圖書館
    ("A", 0, 0, 30, 24, "#F2C9A8"),     # A 教授研究室
    ("B", 0, 0, 60, 40, "#EBA58F"),     # B1/B2 學生宿舍
    ("P7", 0, 0, 30, 24, "#D9B3E0"),    # 7 演講廳
    ("K", 0, 0, 40, 30, "#F4E7C5"),     # K 行政大樓
    ("I", 0, 0, 70, 26, "#E6EFD0"),     # I 教學大樓
    ("H", 0, 0, 60, 30, "#9C8CC7"),     # H 學生宿舍
    ("D", 0, 0, 44, 28, "#8FD3CF"),     # D 教學大樓
    ("C", 0, 0, 60, 22, "#EBA58F"),     # C 行政＆教學大樓
    ("F", 0, 0, 40, 24, "#EBA58F"),     # F 教學大樓
    ("P6", 0, 0, 50, 30, "#8FB8DE"),    # 6 體育館
    ("M", 0, 17, 50, 30, "#F4EED8"),    # M 學生宿舍
    ("Nd", 7, 15, 50, 30, "#F4EED8"),   # N 學生宿舍
    ("L", 0, 0, 30, 24, "#B9D9A0"),     # L 無人機足球
]

# 樹葉的幾種綠色，隨機挑一種，看起來比較自然
TREE_COLORS = ["#4F7A3A", "#5E8C45", "#6B9A4E", "#46703A"]


# 畫一個方塊，座標是 JSON 的像素座標
def draw_box(map_view, left, top, right, bottom, color, outline):
    x1, y1 = map_view.to_canvas(left, top)
    x2, y2 = map_view.to_canvas(right, bottom)
    map_view.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline, tags="scenery")


# 畫在道路下面的東西：綠地、湖、操場、場地、建築物
def draw_ground(map_view):
    map_view.create_polygon(map_view.to_canvas_points(LAND), smooth=True,
                            fill=config.LAND_COLOR, outline="", tags=("scenery", "land"))

    for lake in LAKES:
        map_view.create_polygon(map_view.to_canvas_points(lake), smooth=True,
                                fill=config.LAKE_COLOR, outline=config.LAKE_EDGE_COLOR,
                                width=2, tags="scenery")

    # 1 操場：外圈紅色跑道、裡面綠色草地
    x1, y1 = map_view.to_canvas(950, 480)
    x2, y2 = map_view.to_canvas(1070, 555)
    map_view.create_oval(x1, y1, x2, y2, fill="#C8624F", outline="#A84F3F", tags="scenery")
    map_view.create_oval(x1 + 9, y1 + 9, x2 - 9, y2 - 9, fill="#8FBF6A", outline="#F0F0F0", tags="scenery")

    # 5 西班牙廣場：圓形廣場
    x1, y1 = map_view.to_canvas(660, 298)
    x2, y2 = map_view.to_canvas(705, 340)
    map_view.create_oval(x1, y1, x2, y2, fill="#E3D3C3", outline="#C9B5A3", tags="scenery")

    for left, top, right, bottom, color in FIELDS:
        draw_box(map_view, left, top, right, bottom, color, "#B8A39C")

    # 建築物：先畫往右下偏一點的深色影子，再畫屋頂，看起來比較立體
    for place_id, dx, dy, w, h, color in BUILDINGS:
        place = map_view.graph.places[place_id]
        cx = place["x"] + dx
        cy = place["y"] + dy
        draw_box(map_view, cx - w / 2 + 3, cy - h / 2 + 3, cx + w / 2 + 3, cy + h / 2 + 3,
                 config.SHADOW_COLOR, "")
        draw_box(map_view, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, color, "#7A7A7A")


# 在綠地的空位隨機種樹：只要那個位置除了綠地以外什麼都沒有（道路、湖、建築、名稱、別棵樹），就種一棵
# 道路和名稱都要先畫好再呼叫這個函式，樹才會避開它們
def draw_trees(map_view):
    # 固定亂數種子，每次開程式樹的位置都一樣
    rng = random.Random(7)
    for i in range(1500):
        x = rng.uniform(0, config.MAP_WIDTH)
        y = rng.uniform(0, config.MAP_HEIGHT)
        r = rng.uniform(4, 7)

        # 檢查樹（多留 2 像素空隙）會不會蓋到東西
        items = map_view.find_overlapping(x - r - 2, y - r - 2, x + r + 2, y + r + 2)
        if len(items) == 0:
            continue    # 在綠地外面
        only_land = True
        for item in items:
            if "land" not in map_view.gettags(item):
                only_land = False
        if not only_land:
            continue

        color = rng.choice(TREE_COLORS)
        # 影子、樹冠、左上角一點亮光
        map_view.create_oval(x - r + 2, y - r + 2, x + r + 2, y + r + 2,
                             fill=config.SHADOW_COLOR, outline="", tags="tree")
        map_view.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="", tags="tree")
        map_view.create_oval(x - r / 2, y - r / 2, x, y, fill="#8DB86A", outline="", tags="tree")
