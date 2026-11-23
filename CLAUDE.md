專案：校園地圖最短路徑導航（大一程式設計期末專題）
規則
一律用繁體中文回答，我看不懂英文
程式註解全部用繁體中文，每個函式上面說明它在做什麼
只用 Python 3 內建功能（tkinter、json、heapq、unittest），不要安裝其他套件
程式要寫得像大一學生看得懂的程度，不要用太進階的寫法
pathfinder.py 的 Dijkstra 已依我的要求由 Claude 撰寫（2026-11-16），之後要修改前先問我
每次改完程式，用條列告訴我改了哪些檔案、為什麼
架構
data/map_data.json：地點與道路資料（x、y、path 是像素座標，當初對照 1560×839 的校園地圖描出來；程式不使用背景圖，風景由 ui/scenery.py 自己畫）
config.py：顏色、字型、走路速度等常數
core/graph.py：CampusGraph 類別，讀 JSON、建鄰接表、算權重
core/pathfinder.py：dijkstra(graph, start, end) 回傳 (路線, 總距離)
ui/app.py、ui/map_view.py、ui/side_panel.py：tkinter 視窗
main.py：程式入口
tests/：unittest 測試
