# core/route.py
# 負責：把 dijkstra 找到的路線整理成「給人看的導航步驟」。
# - route_via：先到途經點、再到終點的路線
# - plan_route：檢查使用者的選擇（找不到地點、起終點相同…），沒問題才找路線
# - build_stops：跳過路口，算出每一站離上一站幾公尺、要怎麼轉
# - direction_text：兩個地點之間是往哪個方向走
# - turn_text：走到某個地點時要左轉、右轉、直走還是迴轉
# - route_summary：整條路線的實際距離、總共上坡幾公尺、下坡幾公尺
# - walk_minutes：整條路線的步行時間（上坡越陡越慢、緩下坡稍微快）
# - stairs_count：路線上有幾段樓梯
# - compare_algorithms：同一段路用 Dijkstra、A*、Bellman-Ford 各找一次，比較它們的差別（含搜尋過程，給動畫用）
# 這裡只做計算，不碰 tkinter，所以可以直接用 unittest 測試。

import math
import time

import config
from core.pathfinder import a_star, bellman_ford, dijkstra

# 要比較的三種演算法：(顯示的名稱, 函式)
ALGORITHMS = [
    ("Dijkstra", dijkstra),
    ("A*", a_star),
    ("Bellman-Ford", bellman_ford),
]


# 找出「start → via → end」的路線，回傳 (路線, 總距離)，格式和 dijkstra 一樣
# 做法：跑兩次 dijkstra（start → via、via → end），再把兩段接起來
# 任何一段走不到，就回傳 ([], float("inf"))
# via 和 start 或 end 一樣也沒關係：dijkstra 會回傳 ([via], 0)，接起來就等於沒有途經點
# use_slope、algorithm、counter 都可以不填：預設用 dijkstra 找最短距離（見 core/pathfinder.py）
# 有傳 counter 時，兩段的工作量會加起來
def route_via(graph, start, via, end, use_slope=False, algorithm=dijkstra, counter=None):
    counter1 = {}
    counter2 = {}
    path1, distance1 = algorithm(graph, start, via, use_slope, counter1)
    path2, distance2 = algorithm(graph, via, end, use_slope, counter2)
    if counter is not None:
        counter["visited"] = counter1["visited"] + counter2["visited"]
        counter["checked"] = counter1["checked"] + counter2["checked"]
        # 搜尋過程接起來；第二段的「檢查了幾次道路」要加上第一段已經檢查的次數
        counter["steps"] = list(counter1["steps"])
        for places, checked in counter2["steps"]:
            counter["steps"].append((places, checked + counter1["checked"]))
    if len(path1) == 0 or len(path2) == 0:
        return [], float("inf")
    # path2 的第一個點就是 via，已經在 path1 的最後面了，所以跳過，不然 via 會出現兩次
    return path1 + path2[1:], distance1 + distance2


# 按下「找路線」時用：先檢查使用者的選擇有沒有問題，沒問題才找路線
# start、end、via 是地點 id，輸入框的字找不到地點時是 None
# has_via：途經點輸入框有沒有填字（沒填是正常的；有填卻找不到，要提醒使用者，不能當作沒填）
# use_slope：True 時找最省力的路（上坡算比較遠），這時「總距離」其實是「花費」，
#            真正走多少公尺要用 route_summary 算
# 回傳 (路線, 總距離, 錯誤訊息)；成功時錯誤訊息是 None，失敗時路線是 []、總距離是 None
def plan_route(graph, start, end, has_via, via, use_slope=False):
    if start is None:
        return [], None, "找不到起點。\n請從推薦清單選一個地點。"
    if end is None:
        return [], None, "找不到終點。\n請從推薦清單選一個地點。"
    if not has_via:
        via = None
    elif via is None:
        return [], None, "找不到途經點。\n請從推薦清單選一個地點，或把它清空。"
    # 有不同的途經點時，起點等於終點是合理的（例如宿舍 → 7-11 → 宿舍）
    if start == end and (via is None or via == start):
        return [], None, "起點和終點是同一個地方。"

    if via is None:
        path, total = dijkstra(graph, start, end, use_slope)
    else:
        path, total = route_via(graph, start, via, end, use_slope)

    if len(path) == 0:
        return [], None, "這兩個地點之間沒有道路可以走到。"
    return path, total, None


# 把 dijkstra 回傳的路線（地點 id 清單）整理成導航步驟
# 只列出建築和設施，路口跳過比較好讀；路口那幾段的距離加到下一站
# 回傳 [(地點 id, 離上一站幾公尺, 離開上一站時怎麼轉), ...]
# 第一站是起點：距離 0；起點前面沒有路，第一段也不用轉，所以「怎麼轉」是 None
def build_stops(graph, path):
    stops = [(path[0], 0, None)]
    walked = 0
    last_stop_index = 0   # 上一站在 path 裡的位置
    for i in range(len(path) - 1):
        walked = walked + graph.distance_between(path[i], path[i + 1])
        next_place = path[i + 1]
        if graph.places[next_place]["type"] != "junction":
            turn = None
            if last_stop_index > 0:
                # 用「走進上一站的那條路」和「離開上一站的那條路」判斷轉彎
                # 道路可能是彎的，所以要看折線上最靠近上一站的那一小段，不是兩個地點連成的直線
                here_id = path[last_stop_index]
                road_in = graph.edge_points(path[last_stop_index - 1], here_id)
                road_out = graph.edge_points(here_id, path[last_stop_index + 1])
                before = road_in[-2]   # 走進來那條路，到達上一站前的最後一個點
                after = road_out[1]    # 離開那條路，出發後的第一個點
                here = graph.places[here_id]
                turn = turn_text(before[0], before[1], here["x"], here["y"], after[0], after[1])
            stops.append((next_place, walked, turn))
            walked = 0
            last_stop_index = i + 1
    return stops


# 依照兩個地點在地圖上的位置，回傳「箭頭 + 往哪個方向」，例如「↗ 往右上」
# 地圖的上方當作北邊；畫面座標的 y 往下變大，所以 dy 小於 0 代表往上
# 一個方向比另一個大兩倍以上就只算那個方向，不然算斜的
def direction_text(x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) > 2 * abs(dy):
        if dx > 0:
            return "→ 往右"
        return "← 往左"
    if abs(dy) > 2 * abs(dx):
        if dy < 0:
            return "↑ 往上"
        return "↓ 往下"
    if dx > 0 and dy < 0:
        return "↗ 往右上"
    if dx < 0 and dy < 0:
        return "↖ 往左上"
    if dx > 0:
        return "↘ 往右下"
    return "↙ 往左下"


# 從 (x1, y1) 走到 (x2, y2)，接著要走到 (x3, y3)：在 (x2, y2) 要怎麼轉？
# 回傳「直走」、「左轉」、「右轉」或「迴轉」
# 做法：用 atan2 算出前後兩段路各朝哪個角度，相減就是轉了幾度
# 畫面座標的 y 往下變大，所以角度變大是順時針，也就是右轉
def turn_text(x1, y1, x2, y2, x3, y3):
    angle_in = math.degrees(math.atan2(y2 - y1, x2 - x1))
    angle_out = math.degrees(math.atan2(y3 - y2, x3 - x2))
    turn = angle_out - angle_in
    # 把角度換到 -180 ~ 180 之間，例如轉 270 度其實是往另一邊轉 90 度
    while turn > 180:
        turn = turn - 360
    while turn <= -180:
        turn = turn + 360

    # 轉不到 30 度算直走，超過 150 度算往回走
    if abs(turn) < 30:
        return "直走"
    if abs(turn) > 150:
        return "迴轉"
    if turn > 0:
        return "右轉"
    return "左轉"


# 算出整條路線的 (實際距離, 總共上坡幾公尺, 總共下坡幾公尺)
# 找「最省力」的路時，演算法回傳的是花費，不是距離，所以要另外沿著路線加一次
def route_summary(graph, path):
    distance = 0
    up = 0
    down = 0
    for i in range(len(path) - 1):
        distance = distance + graph.distance_between(path[i], path[i + 1])
        climb = graph.climb(path[i], path[i + 1])
        if climb > 0:
            up = up + climb
        else:
            down = down - climb
    return distance, up, down


# 算出整條路線的步行時間（分鐘）
# 每一段都用 graph.step_cost（考慮坡度）換算成「等於平地走幾公尺」，加起來再除以走路速度
# 所以上坡越陡越慢、緩下坡稍微快一點（規則見 core/graph.py 的 step_cost）
def walk_minutes(graph, path):
    total = 0
    for i in range(len(path) - 1):
        distance = graph.distance_between(path[i], path[i + 1])
        total = total + graph.step_cost(path[i], path[i + 1], distance, True)
    return total / config.WALK_SPEED


# 算出路線上有幾段樓梯（JSON 標了 "stairs": true 的道路），結果區會提醒使用者
def stairs_count(graph, path):
    count = 0
    for i in range(len(path) - 1):
        if graph.is_stairs(path[i], path[i + 1]):
            count = count + 1
    return count


# 用三種演算法各找一次同一段路（start → via → end，via 可以是 None），比較它們的差別
# repeat：每種演算法重複跑幾次再算平均時間；只跑一次太快了，時間會是 0 或忽大忽小
# 回傳一個清單，每種演算法一筆字典：
#   name 名稱、path 路線、distance 實際距離、cost 演算法算出的總花費（最省力模式下含坡度，用來比較三種有沒有一樣好）、visited 處理幾個地點（Bellman-Ford 是幾輪）、
#   checked 檢查幾次道路、ms 平均每次花幾毫秒、steps 搜尋過程（地圖播動畫用，格式見 core/pathfinder.py）
def compare_algorithms(graph, start, end, via=None, use_slope=False, repeat=200):
    results = []
    for name, algorithm in ALGORITHMS:
        counter = {}
        begin = time.perf_counter()
        for i in range(repeat):
            if via is None:
                path, total = algorithm(graph, start, end, use_slope, counter)
            else:
                path, total = route_via(graph, start, via, end, use_slope, algorithm, counter)
        seconds = time.perf_counter() - begin

        distance, up, down = route_summary(graph, path)
        results.append({
            "name": name,
            "path": path,
            "distance": distance,
            "cost": total,
            "visited": counter["visited"],
            "checked": counter["checked"],
            "ms": seconds / repeat * 1000,
            "steps": counter["steps"],
        })
    return results
