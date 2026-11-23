專案：校園地圖最短路徑導航（大一程式設計期末專題）
規則
一律用繁體中文回答，我看不懂英文
程式註解全部用繁體中文，每個函式上面說明它在做什麼
只用 Python 3 內建功能（tkinter、json、heapq、unittest），不要安裝其他套件
程式要寫得像大一學生看得懂的程度，不要用太進階的寫法
pathfinder.py 的 Dijkstra 已依我的要求由 Claude 撰寫（2026-11-16）；2026-11-23 經我同意加入 A*、Bellman-Ford 和坡度。之後要修改前先問我
每次改完程式，用條列告訴我改了哪些檔案、為什麼
架構
data/map_data.json：地點與道路資料（elevation 是海拔公尺、可不填，用來算坡度；x、y、path 是像素座標，當初對照 1560×839 的校園地圖描出來；程式不使用背景圖，風景由 ui/scenery.py 自己畫）
config.py：顏色、字型、走路速度、坡度係數（CLIMB_FACTOR）等常數
core/graph.py：CampusGraph 類別，讀 JSON、建鄰接表、算權重（含坡度 step_cost、A* 用的直線距離）
core/pathfinder.py：dijkstra、a_star、bellman_ford(graph, start, end, use_slope=False, counter=None) 回傳 (路線, 總花費)
core/route.py：plan_route 檢查輸入再找路線、route_via 途經點、build_stops 導航步驟、route_summary 距離與上下坡、compare_algorithms 比較三種演算法
ui/app.py、ui/map_view.py、ui/side_panel.py：tkinter 視窗
main.py：程式入口
tests/：unittest 測試（test_algorithms.py 測三種演算法與坡度）
