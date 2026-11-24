# tools/split_roads.py
# 負責：把 data/map_data.json 的每一條道路，切成大約 10 公尺一小段，
# 存成另一個檔案 data/road_pieces.json，方便人工檢查：
# - 道路畫得對不對：每一小段都有編號和像素座標，可以對照地圖找到它
# - 坡度和樓梯：每一小段都有頭尾海拔、上升幾公尺、坡度 %
#
# 這個檔案只給人看，導航程式不會讀它；map_data.json 也不會被改到。
# 執行方式（在專案資料夾裡）：python3 tools/split_roads.py
#
# 海拔怎麼來：
# 1. 先用地圖上「有經緯度的地點」，算出「像素座標 → 經緯度」的換算公式
# 2. 把每個切點換成經緯度。地形資料（Open-Meteo，和 map_data.json 用的是同一份）一格約 90 公尺，
#    直接查會一格一格跳（10 公尺內突然差好幾公尺），而且一個一個查太多次會被網站擋。
#    所以改成：只查校園範圍內「每 3 秒經緯度（約 90 公尺）一個格子點」的海拔，
#    格子點中間的海拔，用旁邊 4 個格子點照距離比例算（雙線性內插），這樣海拔會平順變化
# 3. 每個切點再取周圍約 45 公尺的 8 個點，9 個點一起平均（和 map_data.json 的地點做法一樣）
# 4. 最後微調，讓道路頭尾的海拔和 map_data.json 裡兩端地點的海拔一樣
# 如果連不上網路，就改用「兩端地點的海拔照距離平均分配」（這時整條路每一小段坡度都一樣）

import json
import math
import os
import time
import urllib.request

# 專案資料夾（這個檔案在 tools/ 裡，所以往上一層）
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_PATH = os.path.join(PROJECT_DIR, "data", "map_data.json")
OUTPUT_PATH = os.path.join(PROJECT_DIR, "data", "road_pieces.json")

PIECE_LENGTH = 10        # 每一小段大約幾公尺
STEEP_SLOPE = 15         # 坡度超過這個 %，在檔案裡標「很陡」
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
POINTS_PER_REQUEST = 100  # Open-Meteo 一次最多查 100 個點
AROUND_RADIUS = 45        # 平滑海拔時，周圍的點離切點幾公尺
GRID = 1 / 1200           # 格子點的間隔（度），1/1200 度 = 3 秒，約 90 公尺，和地形資料一樣


# 兩個像素點之間的距離
def pixel_distance(p, q):
    return math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2)


# 算一條折線總共多長（像素）
def polyline_length(path):
    total = 0
    for i in range(len(path) - 1):
        total += pixel_distance(path[i], path[i + 1])
    return total


# 在折線上，從起點沿著線走 target 像素，回傳那個位置 [x, y]
def point_on_polyline(path, target):
    walked = 0
    for i in range(len(path) - 1):
        step = pixel_distance(path[i], path[i + 1])
        if walked + step >= target and step > 0:
            ratio = (target - walked) / step
            x = path[i][0] + (path[i + 1][0] - path[i][0]) * ratio
            y = path[i][1] + (path[i + 1][1] - path[i][1]) * ratio
            return [round(x, 1), round(y, 1)]
        walked += step
    return [path[-1][0], path[-1][1]]


# 取出折線上 start 到 end 像素之間的那一段（包含中間的轉折點），用來畫出這一小段
def cut_polyline(path, start, end):
    result = [point_on_polyline(path, start)]
    walked = 0
    for i in range(1, len(path) - 1):
        walked += pixel_distance(path[i - 1], path[i])
        if start < walked < end:
            result.append([path[i][0], path[i][1]])
    result.append(point_on_polyline(path, end))
    return result


# 解 3 元一次聯立方程式（高斯消去法），給下面算換算公式用
def solve_3x3(matrix, answer):
    m = [matrix[i][:] + [answer[i]] for i in range(3)]
    for col in range(3):
        # 找這一欄絕對值最大的那一列換上來，避免除以很小的數
        best = col
        for row in range(col + 1, 3):
            if abs(m[row][col]) > abs(m[best][col]):
                best = row
        m[col], m[best] = m[best], m[col]
        for row in range(3):
            if row != col:
                times = m[row][col] / m[col][col]
                for k in range(4):
                    m[row][k] -= times * m[col][k]
    return [m[i][3] / m[i][i] for i in range(3)]


# 用所有有經緯度的地點，找出「像素 (x, y) → 經緯度」的換算公式
# 公式長這樣：lat = a*x + b*y + c，lng = d*x + e*y + f（最小平方法：讓所有地點的誤差加起來最小）
def fit_pixel_to_latlng(nodes):
    sums = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    lat_right = [0, 0, 0]
    lng_right = [0, 0, 0]
    for node in nodes:
        if "lat" not in node or "lng" not in node:
            continue
        row = [node["x"], node["y"], 1]
        for i in range(3):
            for j in range(3):
                sums[i][j] += row[i] * row[j]
            lat_right[i] += row[i] * node["lat"]
            lng_right[i] += row[i] * node["lng"]
    lat_formula = solve_3x3(sums, lat_right)
    lng_formula = solve_3x3(sums, lng_right)
    return lat_formula, lng_formula


# 用換算公式把像素點換成經緯度
def to_latlng(point, lat_formula, lng_formula):
    lat = lat_formula[0] * point[0] + lat_formula[1] * point[1] + lat_formula[2]
    lng = lng_formula[0] * point[0] + lng_formula[1] * point[1] + lng_formula[2]
    return round(lat, 6), round(lng, 6)


# 向 Open-Meteo 查一堆經緯度的海拔，回傳海拔清單；連不上就回傳 None
# 網站每分鐘有查詢次數上限，所以每查一批就休息一下；被擋（HTTP 429）就等一分鐘再試
def fetch_elevations(latlngs):
    result = []
    for i in range(0, len(latlngs), POINTS_PER_REQUEST):
        group = latlngs[i:i + POINTS_PER_REQUEST]
        lats = ",".join(str(p[0]) for p in group)
        lngs = ",".join(str(p[1]) for p in group)
        url = ELEVATION_URL + "?latitude=" + lats + "&longitude=" + lngs
        data = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except Exception as error:
                print("查海拔失敗（第", attempt + 1, "次）：", error)
                if attempt < 2:
                    print("等 61 秒再試……")
                    time.sleep(61)
        if data is None:
            print("一直查不到，改用兩端地點平均分配")
            return None
        result += data["elevation"]
        print("已查", len(result), "/", len(latlngs), "個格子點")
        time.sleep(2)
    return result


# 先查好所有需要的格子點海拔，存成字典：(第幾列, 第幾行) -> 海拔
# latlngs 是之後要算海拔的所有點；每個點要用到它周圍的 4 個格子點
def fetch_grid(latlngs):
    needed = set()
    for lat, lng in latlngs:
        row = math.floor(lat / GRID)
        col = math.floor(lng / GRID)
        for r in [row, row + 1]:
            for c in [col, col + 1]:
                needed.add((r, c))
    keys = sorted(needed)
    points = []
    for r, c in keys:
        points.append((round(r * GRID, 6), round(c * GRID, 6)))
    print("需要查", len(points), "個格子點的海拔")
    elevations = fetch_elevations(points)
    if elevations is None:
        return None
    grid = {}
    for i in range(len(keys)):
        grid[keys[i]] = elevations[i]
    return grid


# 用旁邊 4 個格子點，照距離比例算出某個經緯度的海拔（雙線性內插）
def grid_elevation(grid, lat, lng):
    row = math.floor(lat / GRID)
    col = math.floor(lng / GRID)
    # 這個點在格子裡的位置，0 是左下角、1 是右上角
    up = lat / GRID - row
    right = lng / GRID - col
    bottom = grid[(row, col)] * (1 - right) + grid[(row, col + 1)] * right
    top = grid[(row + 1, col)] * (1 - right) + grid[(row + 1, col + 1)] * right
    return bottom * (1 - up) + top * up


# 回傳一個經緯度周圍 8 個方向、各約 AROUND_RADIUS 公尺的點（再加上自己，共 9 個點）
def points_around(lat, lng):
    # 緯度 1 度約 111000 公尺；經度 1 度的長度要乘上 cos(緯度)
    lat_step = AROUND_RADIUS / 111000
    lng_step = AROUND_RADIUS / (111000 * math.cos(math.radians(lat)))
    result = [(lat, lng)]
    for angle in range(0, 360, 45):
        a = math.radians(angle)
        result.append((round(lat + lat_step * math.sin(a), 6), round(lng + lng_step * math.cos(a), 6)))
    return result


# 把一條路上切點的平滑海拔，微調成讓頭尾等於兩端地點的海拔（中間的點照位置比例補上差距）
def fit_to_ends(smooth, start_elevation, end_elevation):
    count = len(smooth)
    start_diff = start_elevation - smooth[0]
    end_diff = end_elevation - smooth[-1]
    result = []
    for i in range(count):
        ratio = i / (count - 1)
        result.append(round(smooth[i] + start_diff + (end_diff - start_diff) * ratio, 1))
    return result


# 只有兩端海拔時：照距離平均分配（每一小段上升一樣多）
def straight_elevations(count, start_elevation, end_elevation):
    result = []
    for i in range(count):
        ratio = i / (count - 1)
        result.append(round(start_elevation + (end_elevation - start_elevation) * ratio, 1))
    return result


# 主程式：讀地圖 → 切路 → 查海拔 → 存檔
def main():
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    places = {}
    for node in data["nodes"]:
        places[node["id"]] = node
    lat_formula, lng_formula = fit_pixel_to_latlng(data["nodes"])

    # 第一步：把每條路切成小段，先記下切點的像素座標
    roads = []
    all_latlngs = []
    for edge in data["edges"]:
        path = edge.get("path")
        if not path:
            a = places[edge["from"]]
            b = places[edge["to"]]
            path = [[a["x"], a["y"]], [b["x"], b["y"]]]
        distance = edge["distance_m"]
        count = max(1, round(distance / PIECE_LENGTH))
        pixel_total = polyline_length(path)
        # 切點：第 0 個是起點，第 count 個是終點
        cut_points = []
        for i in range(count + 1):
            cut_points.append(point_on_polyline(path, pixel_total * i / count))
        # 頭尾直接用 path 的端點，不要有誤差
        cut_points[0] = path[0]
        cut_points[-1] = path[-1]
        # 每個切點要查 9 個點的海拔（自己和周圍 8 個）
        for point in cut_points:
            lat, lng = to_latlng(point, lat_formula, lng_formula)
            all_latlngs += points_around(lat, lng)
        roads.append({"edge": edge, "path": path, "count": count, "cut_points": cut_points})

    # 第二步：查格子點海拔，算出每個點的海拔，再每 9 個一組平均，變成每個切點的平滑海拔
    grid = fetch_grid(all_latlngs)
    raw_all = None
    if grid is not None:
        raw_all = []
        for i in range(0, len(all_latlngs), 9):
            total = 0
            for lat, lng in all_latlngs[i:i + 9]:
                total += grid_elevation(grid, lat, lng)
            raw_all.append(total / 9)
    source = "Open-Meteo 地形資料（平滑後，頭尾對齊地點海拔）"
    if raw_all is None:
        source = "兩端地點海拔照距離平均分配"

    # 第三步：組出每一小段的資料
    output_roads = []
    position = 0
    steep_count = 0
    piece_total = 0
    for road in roads:
        edge = road["edge"]
        count = road["count"]
        path = road["path"]
        cut_points = road["cut_points"]
        start_elevation = places[edge["from"]].get("elevation")
        end_elevation = places[edge["to"]].get("elevation")
        # 兩端有一邊沒填海拔，就當作和另一邊一樣高；都沒填就當 0（平路）
        if start_elevation is None:
            start_elevation = end_elevation if end_elevation is not None else 0
        if end_elevation is None:
            end_elevation = start_elevation

        if raw_all is None:
            elevations = straight_elevations(count + 1, start_elevation, end_elevation)
        else:
            smooth = raw_all[position:position + count + 1]
            elevations = fit_to_ends(smooth, start_elevation, end_elevation)
        position += count + 1

        piece_length = edge["distance_m"] / count
        pixel_total = polyline_length(path)
        pieces = []
        for i in range(count):
            rise = round(elevations[i + 1] - elevations[i], 1)
            slope = round(rise / piece_length * 100, 1) if piece_length > 0 else 0
            note = ""
            if abs(slope) >= STEEP_SLOPE:
                note = "很陡"
                steep_count += 1
            pieces.append({
                "id": edge["from"] + "-" + edge["to"] + "-" + str(i + 1).zfill(2),
                "第幾段": str(i + 1) + "/" + str(count),
                "length_m": round(piece_length, 1),
                "start": cut_points[i],
                "end": cut_points[i + 1],
                "path": cut_polyline(path, pixel_total * i / count, pixel_total * (i + 1) / count),
                "elevation_start": elevations[i],
                "elevation_end": elevations[i + 1],
                "rise_m": rise,
                "slope_percent": slope,
                "提示": note,
                "備註": "",
            })
            piece_total += 1

        output_roads.append({
            "from": edge["from"],
            "to": edge["to"],
            "from_name": places[edge["from"]]["name"],
            "to_name": places[edge["to"]]["name"],
            "distance_m": edge["distance_m"],
            "stairs": edge.get("stairs", False),
            "pieces": pieces,
        })

    result = {
        "說明": "由 tools/split_roads.py 從 map_data.json 產生，只給人檢查用，導航程式不會讀這個檔案。"
              "每條道路切成約 " + str(PIECE_LENGTH) + " 公尺一小段，編號是「起點-終點-第幾段」，"
              "方向都是從 from 走到 to。start、end、path 是像素座標（和 map_data.json 一樣，對照 1560×839 的地圖）。"
              "rise_m 是這一小段上升幾公尺（負的是下坡），slope_percent 是坡度 %，"
              "坡度超過 " + str(STEEP_SLOPE) + "% 的在「提示」寫「很陡」。"
              "海拔來源：" + source + "。地形資料一格約 90 公尺，10 公尺一段的坡度只是估計，"
              "請以實地走過的感覺為準。檢查後有問題可以寫在「備註」；"
              "注意重新執行 split_roads.py 會覆蓋這個檔案，備註會不見。",
        "piece_length_m": PIECE_LENGTH,
        "road_count": len(output_roads),
        "piece_count": piece_total,
        "steep_piece_count": steep_count,
        "roads": output_roads,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("完成：", len(output_roads), "條路，切成", piece_total, "小段，其中", steep_count, "段很陡")
    print("海拔來源：", source)
    print("存到：", OUTPUT_PATH)


if __name__ == "__main__":
    main()
