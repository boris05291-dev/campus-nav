# core/pathfinder.py
# 負責：最短路徑演算法。
# dijkstra(graph, start, end) 用 Dijkstra 演算法找出從 start 到 end 的最短路線，
# 回傳 (路線, 總距離)，路線是依序經過的地點清單。
# - 起點等於終點：回傳 ([起點], 0)
# - 走不到終點：回傳 ([], float("inf"))

import heapq


# 找出從 start 到 end 的最短路線，回傳 (路線, 總距離)
def dijkstra(graph, start, end):
    # 起點或終點打錯字時直接報錯，不要默默回傳「走不到」
    # 用 f-string，start 不是字串（例如數字）時也不會變成 TypeError
    if start not in graph.adjacency:
        raise KeyError(f"找不到起點：{start}")
    if end not in graph.adjacency:
        raise KeyError(f"找不到終點：{end}")

    # distances：目前找到「從起點走到每個地點」的最短距離
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

        # 已經確定終點的最短距離，可以提早結束
        if current == end:
            break

        # 看看經過 current 走到每個鄰居，會不會比原本知道的路更短
        for neighbor, distance in graph.neighbors(current):
            # 已經確定最短距離的鄰居直接跳過（結果和原本一樣，只是意思更清楚）
            if neighbor in visited:
                continue
            new_distance = current_distance + distance
            if neighbor not in distances or new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = current
                heapq.heappush(heap, (new_distance, neighbor))

    # 終點從來沒被走到過，代表走不到
    if end not in distances:
        return [], float("inf")

    # 從終點沿著 previous 一路往回走到起點，再反轉，就是路線
    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()

    return path, distances[end]
