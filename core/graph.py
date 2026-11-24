# core/graph.py
# 負責：定義 CampusGraph 類別。
# - 讀取 data/map_data.json 的地點與道路資料
# - 把資料整理成「鄰接表」（每個地點連到哪些地點、距離多少）
# - 道路的權重就是 JSON 裡的距離（公尺）
#
# map_data.json 的格式：
# {
#   "nodes": [ {"id": "J", "name": "J 圖書館…", "type": "building", "x": 190, "y": 215}, ... ],
#   "edges": [ {"from": "A", "to": "J", "distance_m": 45, "path": [[x, y], [x, y], ...]}, ... ]
# }
# 道路可以加 "stairs": true，表示這段是樓梯（沒填就是一般道路）
# 程式裡一律用 id 代表地點，name 只拿來顯示。
# x、y 和 path 都是地圖上的像素座標；path 是沿著道路畫的折線（從 from 畫到 to）。
# 地點還可以有這些欄位（可以不填）：
# - "elevation"：海拔高度（公尺），用來算坡度；沒填的地點當作和旁邊一樣高（平路）
# - "lat"、"lng"：經緯度，A* 演算法用它估計「離終點的直線距離」；沒填的話估計值當作 0

import json
import math

import config


# 把讀地圖時發生的錯誤，換成一句看得懂的中文原因（main.py 跳出錯誤視窗時用）
# 放在這裡而不是 main.py：main.py 會載入 tkinter，測試只想測這個函式時不必連 tkinter 一起載入
# 注意順序：JSONDecodeError 也是一種 ValueError，所以要先檢查它
def load_error_reason(error):
    if isinstance(error, FileNotFoundError):
        return "找不到地圖檔。"
    if isinstance(error, json.JSONDecodeError):
        return "JSON 格式有錯：第 " + str(error.lineno) + " 行、第 " + str(error.colno) + " 個字附近。"
    if isinstance(error, KeyError):
        return "資料缺少欄位：" + str(error)
    if isinstance(error, ValueError):
        # CampusGraph 自己丟出的錯誤（例如道路連到不存在的地點），訊息本來就是中文
        return str(error)
    if isinstance(error, TypeError):
        # 上面沒檢查到的型別錯誤，例如某個地點寫成字串而不是 { }
        return "資料的格式不對（某個欄位的型別錯了）：" + str(error)
    return "檔案打不開：" + str(error)


class CampusGraph:

    # 建立物件時呼叫：準備好空的資料，然後讀取 JSON 檔
    def __init__(self, file_path):
        # 地點 id -> {"name": 名稱, "type": 種類, "x": 座標x, "y": 座標y}
        self.places = {}
        # 鄰接表：地點 id -> [(相鄰地點 id, 距離), (相鄰地點 id, 距離), ...]
        self.adjacency = {}
        # 所有道路，每條只記一次：[{"from": a, "to": b, "distance": 距離, "path": 折線, "stairs": 是不是樓梯}, ...]
        self.edges = []
        # 用 (a, b) 直接查道路：(地點 id, 地點 id) -> 道路，兩個方向都會記
        self.edge_lookup = {}
        self.load(file_path)

    # 讀取 JSON 檔，先存所有地點，再把每條道路加進鄰接表
    def load(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 最外層要是 { "nodes": [...], "edges": [...] }；如果是 [ ] 或數字，下面的 data["nodes"] 會出現看不懂的錯誤
        if not isinstance(data, dict):
            raise ValueError("地圖檔最外層要用 { } 包起來，裡面放 nodes 和 edges。")

        # 第一步：登記所有地點，每個地點一開始沒有鄰居
        # 用 data["nodes"] 而不是 data.get，格式不對時會直接報錯，不會默默變成空地圖
        for node in data["nodes"]:
            place_id = node["id"]
            self.places[place_id] = {
                "name": node["name"],
                "type": node["type"],
                "x": node["x"],
                "y": node["y"],
                # 沒填的欄位存 None，代表「不知道」
                "elevation": node.get("elevation"),
                "lat": node.get("lat"),
                "lng": node.get("lng"),
                # 各樓層有哪些單位，例如 {"2F": ["出納", "註冊"], ...}；沒填就是空的 {}
                "floors": node.get("floors", {}),
            }
            self.adjacency[place_id] = []

        # 第二步：把每條道路加進去
        for edge in data["edges"]:
            self.add_road(edge["from"], edge["to"], edge["distance_m"], edge.get("path"), edge.get("stairs", False))

    # 加入一條雙向道路：a 可以走到 b，b 也可以走到 a
    # path 是沿著道路的折線；沒有給的話，就用兩個地點連成的直線
    # stairs 是 True 代表這段是樓梯
    def add_road(self, a, b, distance, path=None, stairs=False):
        # 檢查道路兩端的地點都存在，避免 JSON 打錯字卻沒發現
        if a not in self.adjacency:
            raise ValueError("道路連到不存在的地點：" + a)
        if b not in self.adjacency:
            raise ValueError("道路連到不存在的地點：" + b)
        # 距離要是數字；JSON 裡寫成 "10"（有引號）會變成字串，下面比大小時會當掉
        if not isinstance(distance, (int, float)):
            raise ValueError("道路距離要是數字（不要加引號）：" + a + " - " + b)
        # Dijkstra 不能處理負的距離，所以在這裡擋掉
        if distance < 0:
            raise ValueError("道路距離不能是負數：" + a + " - " + b)

        if path is None:
            path = [
                [self.places[a]["x"], self.places[a]["y"]],
                [self.places[b]["x"], self.places[b]["y"]],
            ]

        self.adjacency[a].append((b, distance))
        self.adjacency[b].append((a, distance))
        edge = {"from": a, "to": b, "distance": distance, "path": path, "stairs": stairs}
        self.edges.append(edge)
        # 兩個方向都記進字典，查的時候不用管方向；同兩點有好幾條路時只留最短的
        for key in [(a, b), (b, a)]:
            if key not in self.edge_lookup or distance < self.edge_lookup[key]["distance"]:
                self.edge_lookup[key] = edge

    # 找出直接連接 a、b 的道路（兩個方向都算；有好幾條時取最短的），找不到就報錯
    # 用字典直接查，不用每次把全部道路掃一遍
    def find_edge(self, a, b):
        if (a, b) not in self.edge_lookup:
            raise ValueError("兩個地點之間沒有直接相連的道路：" + a + " - " + b)
        return self.edge_lookup[(a, b)]

    # 回傳兩個直接相連的地點之間的道路距離
    def distance_between(self, a, b):
        return self.find_edge(a, b)["distance"]

    # 回傳「從 a 走到 b」的道路折線點；JSON 裡的 path 是從 from 畫到 to，反方向走就要倒過來
    def edge_points(self, a, b):
        edge = self.find_edge(a, b)
        if edge["from"] == a:
            return edge["path"]
        return list(reversed(edge["path"]))

    # a、b 之間的道路是不是樓梯（兩個方向都一樣）；沒有直接相連的道路就回傳 False
    def is_stairs(self, a, b):
        if (a, b) not in self.edge_lookup:
            return False
        return self.edge_lookup[(a, b)]["stairs"]

    # 從 a 走到 b 要爬升幾公尺：往上是正的、往下是負的
    # 只要有一邊沒填高度，就不知道坡度，當作平路（0）
    # 用 .get 是因為測試會自己手動加地點，那些地點沒有 elevation 這個欄位
    def climb(self, a, b):
        height_a = self.places[a].get("elevation")
        height_b = self.places[b].get("elevation")
        if height_a is None or height_b is None:
            return 0
        return height_b - height_a

    # 從 a 走到 b 的坡度（百分比）：爬升高度 ÷ 道路長度 × 100，例如 5 代表每走 100 公尺爬高 5 公尺
    def slope_percent(self, a, b):
        distance = self.distance_between(a, b)
        if distance == 0:
            return 0
        return self.climb(a, b) / distance * 100

    # 走一段路（從 a 到 b，長度 distance）的「花費」，演算法用它當權重，單位是「等於平地走幾公尺」
    # use_slope 是 False：花費就是距離
    # use_slope 是 True：
    # - 上坡：每爬 1 公尺，當作多走 config.CLIMB_FACTOR 公尺（奈史密斯規則：爬高 1 公尺大約和平地走 8 公尺一樣累）
    #         再乘上「陡度加成」：坡度每多 1%，爬坡多花 config.STEEP_EXTRA%，所以越陡越慢
    #         例：100 公尺爬 5 公尺（坡度 5%），加成 1.25 倍，花費 = 100 + 5 × 8 × 1.25 = 150
    #         加成最多 config.STEEP_BONUS_MAX（1.5 倍），樓梯這種很陡的路才不會算得太慢
    # - 緩下坡：走起來比較快，每下降 1 公尺少算 config.DOWNHILL_FACTOR 公尺，
    #           但最多只少算 config.DOWNHILL_MAX（10%）
    #           例：100 公尺下降 3 公尺，花費 = 100 - 3 × 2 = 94
    # - 陡下坡（坡度達 config.STEEP_SLOPE）：要小心走，不會變快，花費就是距離
    # - 樓梯（JSON 標了 "stairs": true）：不看坡度，上樓梯花費 = 距離 × config.STAIRS_UP_FACTOR，
    #   下樓梯 = 距離 × config.STAIRS_DOWN_FACTOR；兩邊一樣高（不知道哪邊高）時當作上樓梯
    #   例：10 公尺的樓梯，往上走花費 = 10 × 2 = 20，往下走 = 10 × 1.5 = 15
    # 花費最少是距離的 9 成；A* 估計用的直線距離有把這 1 成和經緯度誤差都扣掉（見 straight_distance），
    # 所以估計值不會比真正的花費大，A* 的答案還是對的
    def step_cost(self, a, b, distance, use_slope):
        if not use_slope or distance == 0:
            return distance
        up = self.climb(a, b)

        if self.is_stairs(a, b):
            if up >= 0:
                return distance * config.STAIRS_UP_FACTOR
            return distance * config.STAIRS_DOWN_FACTOR

        percent = up / distance * 100

        if up > 0:
            steep_bonus = 1 + percent * config.STEEP_EXTRA / 100
            if steep_bonus > config.STEEP_BONUS_MAX:
                steep_bonus = config.STEEP_BONUS_MAX
            return distance + up * config.CLIMB_FACTOR * steep_bonus

        if up < 0 and -percent < config.STEEP_SLOPE:
            saved = -up * config.DOWNHILL_FACTOR
            if saved > distance * config.DOWNHILL_MAX:
                saved = distance * config.DOWNHILL_MAX
            return distance - saved

        return distance

    # 用經緯度算 a、b 兩個地點的直線距離（公尺），公式是球面上兩點距離的 haversine 公式
    # 任何一個地點沒有經緯度，就回傳 0（A* 會變得和 Dijkstra 一樣，但答案還是對的）
    def straight_distance(self, a, b):
        place_a = self.places[a]
        place_b = self.places[b]
        if place_a.get("lat") is None or place_b.get("lat") is None:
            return 0
        earth_radius = 6371000
        lat1 = math.radians(place_a["lat"])
        lat2 = math.radians(place_b["lat"])
        d_lat = lat2 - lat1
        d_lng = math.radians(place_b["lng"] - place_a["lng"])
        h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
        # A* 的估計值不能比「真正的花費」大，所以要打兩次折：
        # 1. 經緯度有誤差，實測有的道路比直線還短一點（最多約 4%），乘 0.9 留空間
        # 2. 找最省力的路時，下坡花費最少只有距離的 (1 - DOWNHILL_MAX)，也就是 9 成，所以再乘這個數
        # 0.9 × 0.9 = 0.81；tests/test_data.py 會檢查每條路都符合這個條件
        safe = 0.9 * (1 - config.DOWNHILL_MAX)
        return 2 * earth_radius * math.asin(math.sqrt(h)) * safe

    # 用使用者打的文字找地點（路口不算），大小寫不分
    # 找的順序：完整名稱或代號（例如 J、6、B1/B2）完全一樣 → 推薦清單（suggest）剛好只有一個
    # 用 suggest 的規則，推薦清單看得到的地點就一定找得到（例如「教授 宿舍」）
    # 找到就回傳 id；找不到、或符合的不只一個，就回傳 None
    def find_place(self, text):
        text = text.strip().lower()
        if text == "":
            return None

        for place_id, place in self.places.items():
            if place["type"] == "junction":
                continue
            name = place["name"].lower()
            # 代號是名稱第一個空白前的部分，例如「J 圖書館…」的代號是「j」
            code = name.split(" ")[0]
            if text == name or text == code:
                return place_id

        ids = self.suggest(text)
        if len(ids) == 1:
            return ids[0]
        return None

    # 依照使用者打的文字推薦地點（路口不算），回傳排好順序的 id 清單，最像的排最前面
    # 排序：代號完全一樣 → 代號或名稱開頭一樣 → 名稱裡有打的字 → 同一級再照名稱排
    # 可以用空白分開好幾個字，例如「學生 停車」會找到名稱同時有「學生」和「停車」的地點
    # 什麼都沒打的時候回傳全部地點，讓使用者直接用選的
    def suggest(self, text):
        text = text.strip().lower()
        words = text.split()
        results = []
        for place_id, place in self.places.items():
            if place["type"] == "junction":
                continue
            name = place["name"].lower()
            code = name.split(" ")[0]

            if text == "" or text == code:
                score = 0
            elif code.startswith(text) or name.startswith(text):
                score = 1
            else:
                # 每一個字都要出現在名稱或樓層單位裡才算符合（例如打「出納」會找到 C 棟）
                search_text = name + " " + self.rooms_text(place_id)
                all_found = True
                for word in words:
                    if word not in search_text:
                        all_found = False
                if not all_found:
                    continue
                score = 2
            results.append((score, place["name"], place_id))

        # tuple 排序會先比分數，分數一樣再比名稱
        results.sort()
        ids = []
        for score, name, place_id in results:
            ids.append(place_id)
        return ids

    # 把某個地點所有樓層的單位接成一個字串（小寫），給 suggest 搜尋用
    # 例如 C 棟會得到「營繕 僑生資源 … 應英 動畫」；沒有樓層資料就回傳空字串
    def rooms_text(self, place_id):
        rooms = []
        for floor, names in self.places[place_id]["floors"].items():
            for room in names:
                rooms.append(room)
        return " ".join(rooms).lower()

    # 找出使用者打的字是在哪一樓的哪個單位，回傳像「2F 出納」的字串，給推薦清單顯示
    # 打的字直接出現在地點名稱裡（例如「圖書」），就不用另外說明，回傳空字串；找不到也回傳空字串
    # 有好幾個字（用空白分開）的話，只要其中一個字是單位名稱就算
    def room_hint(self, place_id, text):
        text = text.strip().lower()
        if text == "":
            return ""
        name = self.places[place_id]["name"].lower()
        found = []
        for word in text.split():
            if word in name:
                continue
            for floor, names in self.places[place_id]["floors"].items():
                for room in names:
                    if word in room.lower():
                        found.append(floor + " " + room)
        return "、".join(found)

    # 回傳某個地點的樓層說明，一行一層，由高樓層往低樓層排（和看建築物的順序一樣）
    # 例如 ["4F：應英、動畫", "3F：應中、應日、…"]；沒有樓層資料就回傳空清單
    def floor_lines(self, place_id):
        lines = []
        for floor, names in self.places[place_id]["floors"].items():
            lines.append(floor + "：" + "、".join(names))
        lines.reverse()
        return lines

    # 回傳比較短的地點名稱：去掉括號裡的長說明
    # 例如「C 行政＆教學大樓（視覺特效…）」→「C 行政＆教學大樓」；地圖和結果區都用這個
    def short_name(self, place_id):
        return self.places[place_id]["name"].split("（")[0]

    # 回傳某個地點的所有鄰居，格式是 [(相鄰地點 id, 距離), ...]
    def neighbors(self, place):
        if place not in self.adjacency:
            raise KeyError("找不到地點：" + place)
        # 回傳一份複製的清單，外面的程式改到它也不會弄壞鄰接表
        return list(self.adjacency[place])
