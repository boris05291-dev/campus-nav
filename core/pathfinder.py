# core/pathfinder.py
# 負責：最短路徑演算法，共三種，用法都一樣：
#   dijkstra(graph, start, end)      Dijkstra：每次處理目前離起點最近的地點
#   a_star(graph, start, end)        A*：Dijkstra 再加上「離終點還有多遠」的估計，比較快找到終點
#   bellman_ford(graph, start, end)  Bellman-Ford：把所有道路一輪一輪重複檢查，直到不再變短
# 三個函式都回傳 (路線, 總花費)，路線是依序經過的地點清單。
# - 起點等於終點：回傳 ([起點], 0)
# - 走不到終點：回傳 ([], float("inf"))
#
# 兩個可以不填的參數：
# - use_slope：False（預設）＝ 找最短距離；True ＝ 找最省力的路，上坡會被當成比較遠
#              （每段路的花費由 graph.step_cost 計算，見 core/graph.py）
# - counter：要比較三種演算法時傳一個空的字典進來，函式會把「做了多少工作」記在裡面：
#              counter["visited"]：處理了幾個地點（Bellman-Ford 記的是跑了幾輪）
#              counter["checked"]：檢查了幾次道路（三種演算法都用這個比較）
#              counter["steps"]：搜尋過程，畫動畫用；每一步是 (這一步處理的地點清單, 到這一步為止檢查了幾次道路)
#                                Dijkstra、A* 每一步處理一個地點；Bellman-Ford 每一步是一輪，記這一輪變近的地點

import heapq


# 檢查起點和終點存不存在，打錯字時直接報錯，不要默默回傳「走不到」
# 用 f-string，start 不是字串（例如數字）時也不會變成 TypeError
def check_places(graph, start, end):
    if start not in graph.adjacency:
        raise KeyError(f"找不到起點：{start}")
    if end not in graph.adjacency:
        raise KeyError(f"找不到終點：{end}")


# 從終點沿著 previous 一路往回走到起點，再反轉，就是路線；終點沒被走到過就回傳 ([], 無限大)
def build_path(previous, distances, start, end):
    if end not in distances:
        return [], float("inf")
    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path, distances[end]


# 把 counter 裡的計數設成 0；沒有傳 counter 時用一個用完就丟的字典，下面的程式就不用一直判斷
def start_counter(counter):
    if counter is None:
        counter = {}
    counter["visited"] = 0
    counter["checked"] = 0
    counter["steps"] = []
    return counter


# 在 counter["steps"] 記下一步：這一步處理了哪些地點、到目前為止檢查了幾次道路
# 只是記錄給畫面播動畫用，不會影響演算法的結果
def record_step(counter, places):
    counter["steps"].append((places, counter["checked"]))


# Dijkstra：找出從 start 到 end 花費最小的路線，回傳 (路線, 總花費)
def dijkstra(graph, start, end, use_slope=False, counter=None):
    check_places(graph, start, end)
    counter = start_counter(counter)

    # distances：目前找到「從起點走到每個地點」的最小花費
    distances = {start: 0}
    # previous：記錄最短路線上，每個地點是從哪個地點走過來的
    previous = {}
    # visited：已經確定最短距離的地點，不用再處理
    visited = set()
    # heap：待處理的地點，每次 heappop 都會拿出「目前距離最短」的那一個
    heap = [(0, start)]

    while heap:
        current_distance, current = heapq.heappop(heap)

        # 同一個地點可能被放進 heap 好幾次，只處理第一次（最短的那次）
        if current in visited:
            continue
        visited.add(current)
        counter["visited"] = counter["visited"] + 1

        # 已經確定終點的最短距離，可以提早結束
        if current == end:
            record_step(counter, [current])
            break

        # 看看經過 current 走到每個鄰居，會不會比原本知道的路更短
        for neighbor, distance in graph.neighbors(current):
            # 已經確定最短距離的鄰居直接跳過（結果和原本一樣，只是意思更清楚）
            if neighbor in visited:
                continue
            counter["checked"] = counter["checked"] + 1
            new_distance = current_distance + graph.step_cost(current, neighbor, distance, use_slope)
            if neighbor not in distances or new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = current
                heapq.heappush(heap, (new_distance, neighbor))
        record_step(counter, [current])

    return build_path(previous, distances, start, end)


# A*：和 Dijkstra 幾乎一樣，差別在 heap 排序用的是「已經走的花費 + 估計離終點還多遠」
# 估計值用 graph.straight_distance（兩點的直線距離再打折，見 core/graph.py），
# 打折是因為經緯度有誤差、下坡花費也會比距離少；打完折的估計值不會比真正的花費大，
# 所以 A* 找到的路線一定和 Dijkstra 一樣短，只是會比較少去看「離終點反方向」的地點
# （tests/test_data.py 會檢查每條路的估計值都沒有超過真正的花費）
def a_star(graph, start, end, use_slope=False, counter=None):
    check_places(graph, start, end)
    counter = start_counter(counter)

    distances = {start: 0}
    previous = {}
    visited = set()
    # heap 裡放 (已走花費 + 估計剩下的距離, 地點)
    heap = [(graph.straight_distance(start, end), start)]

    while heap:
        guess, current = heapq.heappop(heap)
        if current in visited:
            continue
        visited.add(current)
        counter["visited"] = counter["visited"] + 1

        if current == end:
            record_step(counter, [current])
            break

        for neighbor, distance in graph.neighbors(current):
            if neighbor in visited:
                continue
            counter["checked"] = counter["checked"] + 1
            new_distance = distances[current] + graph.step_cost(current, neighbor, distance, use_slope)
            if neighbor not in distances or new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = current
                heapq.heappush(heap, (new_distance + graph.straight_distance(neighbor, end), neighbor))
        record_step(counter, [current])

    return build_path(previous, distances, start, end)


# Bellman-Ford：不用 heap，每一輪把「所有道路」都檢查一次，看能不能讓某個地點變近
# 最多跑（地點數 - 1）輪就一定找到答案；某一輪什麼都沒變，代表已經是答案，可以提早結束
# 它可以處理負的距離（Dijkstra 不行），但要檢查的道路次數多很多，所以比較慢
def bellman_ford(graph, start, end, use_slope=False, counter=None):
    check_places(graph, start, end)
    counter = start_counter(counter)

    distances = {start: 0}
    previous = {}

    for round_number in range(len(graph.adjacency) - 1):
        counter["visited"] = counter["visited"] + 1   # 記錄跑了幾輪
        changed = False
        changed_places = []   # 這一輪變近的地點，畫動畫用
        # 道路是雙向的，鄰接表裡兩個方向都有，所以照鄰接表走一遍就是兩個方向都檢查到
        for current in graph.adjacency:
            if current not in distances:
                continue   # 還沒走到的地點，不能從它出發
            for neighbor, distance in graph.neighbors(current):
                counter["checked"] = counter["checked"] + 1
                new_distance = distances[current] + graph.step_cost(current, neighbor, distance, use_slope)
                if neighbor not in distances or new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
                    previous[neighbor] = current
                    changed = True
                    if neighbor not in changed_places:
                        changed_places.append(neighbor)
        # 最後一輪什麼都沒變，也要記下來：它還是把全部道路檢查了一遍
        record_step(counter, changed_places)
        if not changed:
            break

    return build_path(previous, distances, start, end)
