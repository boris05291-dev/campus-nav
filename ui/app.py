# ui/app.py
# 負責：建立 tkinter 主視窗，把地圖區（map_view）和側邊欄（side_panel）組合起來，
# 並在使用者按下「找路線」後，呼叫最短路徑演算法、把結果交給畫面顯示。
# 排版：左邊地圖畫布（大小見 config.MAP_WIDTH、MAP_HEIGHT），右邊控制面板（寬度見 config.PANEL_WIDTH）。

import tkinter as tk

import config
from core.route import build_stops, plan_route
from ui.map_view import MapView
from ui.side_panel import SidePanel


class App(tk.Tk):

    # 建立主視窗，左邊放地圖、右邊放控制面板
    def __init__(self, graph):
        super().__init__()
        self.title(config.WINDOW_TITLE)
        # 大小固定，排版才不會被拉亂
        self.resizable(False, False)
        self.graph = graph

        # 螢幕太小時（例如 1366 寬的筆電、投影機），把地圖縮到放得下，不然右邊面板會跑出螢幕
        # 地圖會自動縮放（map_view.compute_scale），所以只要改畫布大小；20、100 是留給視窗邊框和工作列
        config.MAP_WIDTH = min(config.MAP_WIDTH, self.winfo_screenwidth() - config.PANEL_WIDTH - 20)
        config.MAP_HEIGHT = min(config.MAP_HEIGHT, self.winfo_screenheight() - 100)

        # 點地圖上的地點時，交給面板決定填進起點還是終點
        # （self.side_panel 在下面才建立，但使用者點地圖時一定已經建好了）
        self.map_view = MapView(self, graph, lambda place_id: self.side_panel.fill_from_map(place_id, self.map_view.clear_route))
        self.map_view.pack(side=tk.LEFT)

        # 把 self.find_route 交給面板，按鈕按下去就會執行它
        self.side_panel = SidePanel(self, graph, self.find_route)
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y)

    # 按下「找路線」時執行：檢查選擇並找路線（core/route.py 的 plan_route）→ 畫路線、顯示每一段
    # 檢查的規則放在 core，不在這裡，才能用 unittest 測試
    def find_route(self):
        path, total, error = plan_route(
            self.graph,
            self.side_panel.get_start(),
            self.side_panel.get_end(),
            self.side_panel.has_via(),
            self.side_panel.get_via(),
        )
        if error is not None:
            self.map_view.clear_route()
            self.side_panel.show_message(error)
            return

        # 把路線整理成導航步驟（跳過路口、算每段距離和轉彎），細節見 core/route.py
        stops = build_stops(self.graph, path)

        minutes = total / config.WALK_SPEED
        self.map_view.draw_route(path)
        self.side_panel.show_result(stops, total, minutes)
