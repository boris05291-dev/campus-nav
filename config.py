# config.py
# 負責：存放整個程式共用的常數，例如畫面顏色、字型、視窗大小、走路速度等。
# 其他檔案需要這些數值時，從這裡 import，以後要調整只改這一個地方。

import os

# 地圖資料檔的位置（用 config.py 所在的資料夾來找，從哪裡執行程式都找得到）
MAP_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "map_data.json")

# ===== 視窗大小 =====
WINDOW_TITLE = "校園最短路徑導航"
PANEL_WIDTH = 400     # 右邊控制面板的寬（字放大了，面板也跟著加寬）

# 左邊地圖畫布的長寬比例；實際寬度由 app.py 的 fit_screen 依螢幕大小決定，地圖會自動縮放、置中
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
STAIRS_COLOR = "#8D8D8D"      # 樓梯：在白色路面上畫灰色虛線，看起來像一階一階
STAIRS_DASH = (2, 3)          # 虛線樣式：畫 2 像素、空 3 像素
LEGEND_BG_COLOR = "#FFFFFF"   # 圖例的底色
PLACE_OUTLINE = "#FFFFFF"     # 地點圓點的外框（白邊，疊在道路上比較清楚）
PLACE_RADIUS = 7             # 地點圓點的半徑（像素）

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
MARKER_RADIUS = 11            # 起點、終點標記的半徑

LABEL_BG_COLOR = "#FFFFFF"    # 地圖上地點名稱的白底，名稱才不會和綠地、樹混在一起
# 地圖上名稱太長、容易擋到道路的地點，改顯示短名稱（下拉選單和滑鼠移過去還是全名）
MAP_LABELS = {
    "A": "A 研究室",
    "C": "C 行政＆教學",
    "I": "I 教學大樓",
    "P16": "16 停車場",
}
# 自動挑的名稱位置不好看時，在這裡指定放在圓點的哪一邊：下、右、左、上、右下、左下、右上、左上
# 指定的位置會蓋到別的名稱或圓點時，還是會自動換位置
LABEL_SIDES = {
    "A": "左",
    "B": "上",
    "P7": "右",
    "P13": "右上",
    "M": "右",
    "H": "右",
    "P8": "左",
    "P10": "右",     # 下面是往 9 網球場的路，名稱放下面會擋住路線
}
# 比較三種演算法時，三條路線各用一種顏色（Dijkstra 紅、A* 藍、Bellman-Ford 橘）
COMPARE_COLORS = ["#E53935", "#1E63C8", "#F29D0E"]
# 播放搜尋過程動畫時用
SEARCH_DOT_RADIUS = 6         # 處理過的地點畫成的小圓點半徑
STEP_MS = 250                 # Dijkstra、A*：每處理一個地點停多久（毫秒）
ROUND_MS = 700                # Bellman-Ford：每一輪停多久（毫秒），每輪要檢查全部道路，所以停久一點
SWEEP_MS = 350                # Bellman-Ford 每一輪「全部道路閃一下」持續多久（毫秒）
PAUSE_MS = 1500               # 依序播放時，播完一種演算法後，停多久再播下一種（毫秒）

# ===== 步行 =====
WALK_SPEED = 70               # 走路速度：每分鐘 70 公尺（約時速 4.2 公里），比 Google 的 80 慢一點，算進等人的時間

# ===== 坡度 =====
# 下面這些數字由 core/graph.py 的 step_cost 使用：「最省力路線」用它算花費，步行時間也用它算
# 上坡每爬 1 公尺，當作平地多走幾公尺（奈史密斯規則：爬 600 公尺 ≈ 走 5 公里，約 8 倍）
CLIMB_FACTOR = 8
# 越陡越慢：坡度每多 1%，爬坡多花的部分再多幾 %（5 代表坡度 10% 時爬坡要多花 1.5 倍）
STEEP_EXTRA = 5
# 陡度加成最多幾倍；坡度 10% 以上都算 1.5 倍，免得樓梯（坡度 40% 左右）被算得太慢
STEEP_BONUS_MAX = 1.5
# 緩下坡比較快：每下降 1 公尺，當作少走幾公尺
DOWNHILL_FACTOR = 2
# 下坡最多快多少（0.1 ＝ 最多少算 10% 的距離）
# A* 的直線距離估計會跟著這個數字自動打折（見 core/graph.py 的 straight_distance），改了也不會算錯
DOWNHILL_MAX = 0.1
# 坡度超過這個百分比，結果區會標示「陡」；陡下坡要小心走，不會變快
STEEP_SLOPE = 8

# ===== 樓梯 =====
# JSON 裡標了 "stairs": true 的道路是樓梯。樓梯的海拔資料不準（地形資料解析度 90 公尺，量不出幾公尺長的樓梯），
# 所以樓梯不看坡度，直接用固定倍數：走 1 公尺樓梯，當作平地走幾公尺
STAIRS_UP_FACTOR = 2          # 上樓梯
STAIRS_DOWN_FACTOR = 1.5      # 下樓梯（要看腳下，也比平地慢）

# ===== 字型 =====
# 依序找電腦裡有沒有這些字型，用第一個找到的（app.py 的 choose_font 會處理）
# 微軟正黑體是 Windows 內建；Mac 用蘋方；Linux 常見的是 Noto Sans CJK 或文泉驛
FONT_CHOICES = ["Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC",
                "Noto Sans CJK TC", "Noto Sans TC", "WenQuanYi Zen Hei"]
# 字型大小（點）；原本 9、10 在投影機和高解析度螢幕上太小，放大一些
TITLE_SIZE = 20
LABEL_SIZE = 13
TEXT_SIZE = 14
# 下面三個是預設值，程式啟動時 choose_font 會換成上面找到的字型
TITLE_FONT = ("Microsoft JhengHei", TITLE_SIZE, "bold")
LABEL_FONT = ("Microsoft JhengHei", LABEL_SIZE)
TEXT_FONT = ("Microsoft JhengHei", TEXT_SIZE)
BOLD_FONT = ("Microsoft JhengHei", TEXT_SIZE, "bold")
