# ui/app.py
# 負責：建立 tkinter 主視窗，把地圖區（map_view）和側邊欄（side_panel）組合起來，
# 並在使用者按下「找路線」或「比較三種演算法」後，呼叫演算法、把結果交給畫面顯示，
# 比較時還會在地圖上播放三種演算法的搜尋過程動畫。
# 排版：左邊地圖畫布（大小見 config.MAP_WIDTH、MAP_HEIGHT），右邊控制面板（寬度見 config.PANEL_WIDTH）。

import tkinter as tk
from tkinter import font as tkfont

import config
from core.route import build_stops, compare_algorithms, plan_route, route_summary, stairs_count, walk_minutes
from ui.map_view import MapView
from ui.side_panel import SidePanel


class App(tk.Tk):

    # 建立主視窗，左邊放地圖、右邊放控制面板
    def __init__(self, graph):
        super().__init__()
        self.title(config.WINDOW_TITLE)
        # 大小固定，排版才不會被拉亂
        self.resizable(False, False)
        # 視窗變大了，放在螢幕左上角，下面才不會被工作列擋住
        self.geometry("+0+0")
        self.graph = graph

        # 這兩步要在建立地圖和面板之前做，它們才會用到調整後的字型和大小
        self.choose_font()
        self.fit_screen()

        # 點地圖上的地點時，交給面板決定填進起點還是終點
        # （self.side_panel 在下面才建立，但使用者點地圖時一定已經建好了）
        self.map_view = MapView(self, graph, lambda place_id: self.side_panel.fill_from_map(place_id, self.map_view.clear_route))
        self.map_view.pack(side=tk.LEFT)

        # 把 self.find_route、self.compare 交給面板，按鈕按下去就會執行它們
        self.side_panel = SidePanel(self, graph, self.find_route, self.compare, self.has_elevation())
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y)

    # 從 config.FONT_CHOICES 裡挑第一個這台電腦有的字型，換掉 config 裡的字型設定
    # 不然在沒有微軟正黑體的電腦（例如 Mac）上，tkinter 會用很醜的預設字型
    def choose_font(self):
        installed = tkfont.families(self)
        family = None
        for name in config.FONT_CHOICES:
            if name in installed:
                family = name
                break
        if family is None:
            return   # 都沒有的話，就用 config 裡原本的設定
        config.TITLE_FONT = (family, config.TITLE_SIZE, "bold")
        config.LABEL_FONT = (family, config.LABEL_SIZE)
        config.TEXT_FONT = (family, config.TEXT_SIZE)
        config.BOLD_FONT = (family, config.TEXT_SIZE, "bold")

    # 依照螢幕調整畫面大小
    # 1. 螢幕縮放（125%、150%）：字型用「點」當單位會自動變大，但畫布、線條用「像素」不會，
    #    所以把像素大小也乘上同樣的倍數，不然字變大了，面板和圓點卻還是一樣小，會擠在一起
    # 2. 地圖畫布跟著螢幕大小走：大螢幕放大、小螢幕（筆電、投影機）縮小，右邊面板才不會跑出螢幕
    def fit_screen(self):
        # 一般螢幕 1 英吋是 96 像素；縮放 150% 的螢幕是 144，倍數就是 1.5
        ratio = self.winfo_fpixels("1i") / 96
        if ratio > 1:
            config.PANEL_WIDTH = int(config.PANEL_WIDTH * ratio)
            config.ROAD_WIDTH = round(config.ROAD_WIDTH * ratio)
            config.ROAD_EDGE_WIDTH = round(config.ROAD_EDGE_WIDTH * ratio)
            config.ROUTE_WIDTH = round(config.ROUTE_WIDTH * ratio)
            config.PLACE_RADIUS = round(config.PLACE_RADIUS * ratio)
            config.MARKER_RADIUS = round(config.MARKER_RADIUS * ratio)

        # 地圖會自動縮放（map_view.compute_scale），所以只要改畫布大小；20、100 是留給視窗邊框和工作列
        # 寬度用滿螢幕剩下的空間，高度照 config 原本的長寬比例算，地圖上下才不會空一大塊
        shape = config.MAP_HEIGHT / config.MAP_WIDTH
        config.MAP_WIDTH = self.winfo_screenwidth() - config.PANEL_WIDTH - 20
        config.MAP_HEIGHT = min(int(config.MAP_WIDTH * shape), self.winfo_screenheight() - 100)

    # 地圖資料裡有沒有任何地點填了高度；沒有的話，坡度功能沒有作用，面板會提醒
    def has_elevation(self):
        for place in self.graph.places.values():
            if place["elevation"] is not None:
                return True
        return False

    # 檢查使用者的選擇並找路線（core/route.py 的 plan_route）
    # 有錯誤時清掉地圖上的路線、顯示錯誤訊息，回傳 None；沒問題就回傳路線
    def plan(self):
        path, total, error = plan_route(
            self.graph,
            self.side_panel.get_start(),
            self.side_panel.get_end(),
            self.side_panel.has_via(),
            self.side_panel.get_via(),
            self.side_panel.use_slope(),
        )
        if error is not None:
            self.map_view.clear_route()
            self.side_panel.show_message(error)
            return None
        return path

    # 按下「找路線」時執行：找路線 → 畫路線、顯示每一段
    # 檢查的規則放在 core，不在這裡，才能用 unittest 測試
    def find_route(self):
        path = self.plan()
        if path is None:
            return

        # 把路線整理成導航步驟（跳過路口、算每段距離和轉彎），細節見 core/route.py
        stops = build_stops(self.graph, path)
        # 「最省力路線」時 plan_route 回傳的是花費，所以實際距離和上下坡另外算
        distance, up, down = route_summary(self.graph, path)
        # 步行時間：每段路依坡度換算（上坡越陡越慢、緩下坡稍微快），細節見 core/graph.py 的 step_cost
        minutes = walk_minutes(self.graph, path)
        # 路線上有幾段樓梯，結果區會提醒（推行李、推輪椅的人會想知道）
        stairs = stairs_count(self.graph, path)

        self.map_view.draw_route(path)
        self.side_panel.show_result(stops, distance, minutes, up, down, stairs)

    # 按下「比較三種演算法」時執行：同一段路用 Dijkstra、A*、Bellman-Ford 各找一次，
    # 結果區用長條圖比較工作量和時間，地圖上依序播放三種演算法的搜尋過程動畫
    def compare(self):
        path = self.plan()
        if path is None:
            return
        via = None
        if self.side_panel.has_via():
            via = self.side_panel.get_via()
        # 存起來，按「播放」按鈕時要用
        self.compare_results = compare_algorithms(self.graph, path[0], path[-1], via, self.side_panel.use_slope())
        self.side_panel.show_comparison(self.compare_results, len(self.graph.places), len(self.graph.edges), self.play)
        self.play([0, 1, 2])

    # 在地圖上播放搜尋過程動畫；indices 是要播的演算法編號（0 Dijkstra、1 A*、2 Bellman-Ford）
    # 播完第一個後，再用同樣的方法播剩下的，所以 [0, 1, 2] 會三種依序播放
    def play(self, indices):
        index = indices[0]
        rest = indices[1:]
        result = self.compare_results[index]
        on_done = None
        if len(rest) > 0:
            on_done = lambda: self.play(rest)
        self.map_view.play_search(result["name"], config.COMPARE_COLORS[index], result["path"], result["steps"], on_done)
