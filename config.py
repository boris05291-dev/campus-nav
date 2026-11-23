# config.py
# 負責：存放整個程式共用的常數，例如畫面顏色、字型、視窗大小、走路速度等。
# 其他檔案需要這些數值時，從這裡 import，以後要調整只改這一個地方。

import os

# 地圖資料檔的位置（用 config.py 所在的資料夾來找，從哪裡執行程式都找得到）
MAP_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "map_data.json")

# ===== 視窗大小 =====
WINDOW_TITLE = "校園最短路徑導航"
PANEL_WIDTH = 280     # 右邊控制面板的寬

# 左邊地圖畫布的大小；地圖會自動縮放、置中放進這個範圍
MAP_WIDTH = 1170
MAP_HEIGHT = 630
MAP_MARGIN = 30       # 地圖四周留白，避免地點貼在邊框上

# ===== 顏色 =====
MAP_BG_COLOR = "#F4F6EF"      # 地圖背景（校園外面）
LAND_COLOR = "#A9C48A"        # 校園綠地
LAKE_COLOR = "#5DB8A8"        # 湖水
LAKE_EDGE_COLOR = "#3E9886"   # 湖的邊
SHADOW_COLOR = "#7E9A66"      # 建築物和樹的影子
PANEL_BG_COLOR = "#FFFFFF"    # 控制面板背景
TEXT_COLOR = "#222222"        # 一般文字
ROAD_COLOR = "#FFFFFF"        # 道路（白色）
ROAD_WIDTH = 5                # 道路線條粗細
ROAD_EDGE_COLOR = "#8CA872"   # 道路兩旁的邊線
ROAD_EDGE_WIDTH = 8           # 邊線要比道路粗，才會露出來
LEGEND_BG_COLOR = "#FFFFFF"   # 圖例的底色
PLACE_OUTLINE = "#FFFFFF"     # 地點圓點的外框（白邊，疊在道路上比較清楚）
PLACE_RADIUS = 6              # 地點圓點的半徑（像素）

# 不同種類的地點用不同顏色：building 建築、facility 設施、gate 出入口
PLACE_COLORS = {
    "building": "#2F6FB0",
    "facility": "#3A9D5D",
    "gate": "#D9822B",
}
# 圖例上每種顏色要寫的說明
PLACE_TYPE_NAMES = {
    "building": "建築（教學大樓、宿舍）",
    "facility": "設施（球場、停車場、湖）",
    "gate": "出入口",
}

# 輸入框下面的推薦清單
SUGGEST_ROWS = 8                 # 一次顯示幾筆，更多的可以往下捲
SUGGEST_SELECT_COLOR = "#2F6FB0" # 目前選到的那一筆的底色

# 滑鼠移到地點上時，顯示全名的小方框
INFO_BG_COLOR = "#FFFFFF"
INFO_BORDER_COLOR = "#999999"
ROUTE_COLOR = "#E53935"       # 找到的路線
ROUTE_WIDTH = 6               # 路線線條粗細
START_COLOR = "#2E7D32"       # 起點標記（綠）
END_COLOR = "#C62828"         # 終點標記（紅）
MARKER_RADIUS = 9             # 起點、終點標記的半徑

# ===== 步行 =====
WALK_SPEED = 70               # 走路速度：每分鐘 70 公尺（約時速 4.2 公里），比 Google 的 80 慢一點，算進爬坡、等人的時間

# ===== 字型（微軟正黑體，Windows 內建，中文顯示比較清楚）=====
TITLE_FONT = ("Microsoft JhengHei", 14, "bold")
LABEL_FONT = ("Microsoft JhengHei", 9)
TEXT_FONT = ("Microsoft JhengHei", 10)
