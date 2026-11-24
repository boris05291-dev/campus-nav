# ui/map_view.py
# 負責：地圖畫面（tkinter Canvas）。
# - 用灰線畫出所有道路（沿著 path 折線），在可選的地點畫上彩色圓點和名稱
# - 滑鼠移到地點上會顯示全名，點一下會交給 on_place_click 處理（填進起點或終點），左下角有圖例
# - 把找到的最短路線沿著道路畫出來，並標出起點、終點
# - 比較三種演算法時，播放搜尋過程的動畫：一步一步亮出演算法處理過的地點，最後畫出找到的路線
# 沒有用背景圖：綠地、湖、建築、樹（ui/scenery.py）和道路、地點都是程式自己畫的

import tkinter as tk

import config
from ui import scenery


class MapView(tk.Canvas):

    # 建立地圖畫布，算好縮放比例後畫出道路和地點
    # on_place_click 是點地點時要呼叫的函式，會傳入地點 id（由 app.py 傳進來）
    def __init__(self, parent, graph, on_place_click):
        super().__init__(
            parent,
            width=config.MAP_WIDTH,
            height=config.MAP_HEIGHT,
            bg=config.MAP_BG_COLOR,
            highlightthickness=0,
        )
        self.graph = graph
        self.on_place_click = on_place_click
        # 動畫下一步的排程編號（self.after 回傳的），沒有在播動畫時是 None
        self.animation_job = None
        self.compute_scale()
        scenery.draw_ground(self)
        self.draw_roads()
        self.draw_places()
        # 樹要等道路和名稱都畫好才種，才能避開它們
        scenery.draw_trees(self)
        self.draw_legend()

    # JSON 的座標範圍和畫布大小不同，算出要縮放多少、位移多少才會剛好置中放進畫布
    def compute_scale(self):
        # 地點和道路折線上的所有點都要放得進畫布
        xs = []
        ys = []
        for place in self.graph.places.values():
            xs.append(place["x"])
            ys.append(place["y"])
        for edge in self.graph.edges:
            for x, y in edge["path"]:
                xs.append(x)
                ys.append(y)

        # 沒有任何地點時，不用縮放
        if len(xs) == 0:
            self.scale = 1
            self.min_x = 0
            self.min_y = 0
            self.offset_x = 0
            self.offset_y = 0
            return

        self.min_x = min(xs)
        self.min_y = min(ys)
        # 用 max(…, 1) 避免所有點在同一條線上時除以 0
        span_x = max(max(xs) - self.min_x, 1)
        span_y = max(max(ys) - self.min_y, 1)

        # 扣掉四周留白後可以用的空間；寬高用同一個比例，地圖才不會變形
        usable_width = config.MAP_WIDTH - 2 * config.MAP_MARGIN
        usable_height = config.MAP_HEIGHT - 2 * config.MAP_MARGIN
        self.scale = min(usable_width / span_x, usable_height / span_y)

        # 讓地圖在畫布中間
        self.offset_x = (config.MAP_WIDTH - span_x * self.scale) / 2
        self.offset_y = (config.MAP_HEIGHT - span_y * self.scale) / 2

    # 把 JSON 裡的座標換算成畫布上的座標
    def to_canvas(self, x, y):
        canvas_x = self.offset_x + (x - self.min_x) * self.scale
        canvas_y = self.offset_y + (y - self.min_y) * self.scale
        return canvas_x, canvas_y

    # 把一串 [x, y] 點換算成 create_line 要的 [x1, y1, x2, y2, ...]
    def to_canvas_points(self, path):
        points = []
        for x, y in path:
            canvas_x, canvas_y = self.to_canvas(x, y)
            points.append(canvas_x)
            points.append(canvas_y)
        return points

    # 每條道路沿著 path 折線畫成白線；先畫全部的綠色邊線，再畫白色路面，路口才會接得乾淨
    # 樓梯在白色路面上再畫一條灰色虛線，看起來像一階一階的
    def draw_roads(self):
        for edge in self.graph.edges:
            self.create_line(
                self.to_canvas_points(edge["path"]),
                fill=config.ROAD_EDGE_COLOR,
                width=config.ROAD_EDGE_WIDTH,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                tags="road",    # 放名稱時用來檢查有沒有蓋到道路
            )
        for edge in self.graph.edges:
            self.create_line(
                self.to_canvas_points(edge["path"]),
                fill=config.ROAD_COLOR,
                width=config.ROAD_WIDTH,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
        for edge in self.graph.edges:
            if edge["stairs"]:
                self.create_line(
                    self.to_canvas_points(edge["path"]),
                    fill=config.STAIRS_COLOR,
                    width=config.ROAD_WIDTH,
                    dash=config.STAIRS_DASH,
                )

    # 在可以選的地點（不是路口）畫彩色圓點和名稱；滑鼠移上去會顯示全名
    def draw_places(self):
        r = config.PLACE_RADIUS
        # 第一輪先畫所有圓點，第二輪再放名稱，名稱才能避開所有圓點
        places = []
        for place_id, place in self.graph.places.items():
            if place["type"] != "junction":
                places.append((place_id, place))

        dots = {}
        for place_id, place in places:
            x, y = self.to_canvas(place["x"], place["y"])
            # 不認得的種類就當成設施來畫
            color = config.PLACE_COLORS.get(place["type"], config.PLACE_COLORS["facility"])
            # tags 裡的 "place"：畫路線時可以把路線放到地點下面；"dot"：放名稱時要避開
            dots[place_id] = self.create_oval(
                x - r, y - r, x + r, y + r,
                fill=color,
                outline=config.PLACE_OUTLINE,
                width=2,
                tags=("place", "dot"),
            )

        for place_id, place in places:
            x, y = self.to_canvas(place["x"], place["y"])
            # 地圖空間比較小，名稱再去掉「、」後面的部分，例如「J 圖書館、教學大樓」→「J 圖書館」
            # config.MAP_LABELS 有寫的地點，改用更短的名稱，比較不會擋到道路
            text = config.MAP_LABELS.get(place_id, self.graph.short_name(place_id).split("、")[0])
            label = self.place_label(x, y, text, config.LABEL_SIDES.get(place_id))
            # 滑鼠移到圓點或名稱上就顯示全名，移開就收起來
            # pid=place_id 是把「這一圈的 id」存進 lambda，不然每個地點都會變成最後一個 id
            for item in (dots[place_id], label):
                self.tag_bind(item, "<Enter>", lambda event, pid=place_id: self.show_info(pid))
                self.tag_bind(item, "<Leave>", lambda event: self.hide_info())
                self.tag_bind(item, "<Button-1>", lambda event, pid=place_id: self.on_place_click(pid))

    # 在圓點旁邊放名稱：試 8 個位置（下、右、左、上、右下、左下、右上、左上），
    # 每個位置算「重疊分數」，用分數最低的；分數 0（什麼都沒蓋到）就直接用，不用再試
    # side 是 config.LABEL_SIDES 指定的位置（例如 "上"）：先試它，只要沒蓋到別的名稱或圓點就用它（蓋到路沒關係），
    # 會蓋到的話，還是照上面的方法自動挑
    def place_label(self, x, y, text, side=None):
        r = config.PLACE_RADIUS
        # 每個位置是 (往右移多少, 往下移多少, 文字要對齊圓點的哪一邊)
        all_positions = {
            "下": (0, r + 2, tk.N),
            # 左右多留 5 像素：白底比字寬 2 像素，太靠近會被當成蓋到自己的圓點
            "右": (r + 5, 0, tk.W),
            "左": (-r - 5, 0, tk.E),
            "上": (0, -r - 2, tk.S),
            "右下": (r, r, tk.NW),
            "左下": (-r, r, tk.NE),
            "右上": (r, -r, tk.SW),
            "左上": (-r, -r, tk.SE),
        }
        positions = list(all_positions.values())
        if side in all_positions:
            # 把指定的位置移到第一個試
            positions.remove(all_positions[side])
            positions.insert(0, all_positions[side])
        best_label = None
        best_score = 0
        for i, (dx, dy, anchor) in enumerate(positions):
            label = self.create_text(
                x + dx, y + dy,
                text=text,
                anchor=anchor,
                fill=config.TEXT_COLOR,
                font=config.LABEL_FONT,
                tags=("place", "label"),
            )
            score = self.overlap_score(label)
            if best_label is None or score < best_score:
                # 比目前最好的還好：把舊的刪掉，留下這個
                if best_label is not None:
                    self.delete(best_label)
                best_label = label
                best_score = score
            else:
                self.delete(label)
            if best_score == 0:
                break
            # 第一個試的是指定的位置，分數不到 100（只蓋到路）就用它
            if i == 0 and side in all_positions and score < 100:
                break

        self.add_label_background(best_label)
        return best_label

    # 在名稱後面墊一塊白底，字才不會壓在綠地、樹或道路上看不清楚
    def add_label_background(self, label):
        left, top, right, bottom = self.bbox(label)
        background = self.create_rectangle(
            left - 2, top, right + 2, bottom,
            fill=config.LABEL_BG_COLOR,
            outline="",
            tags=("place", "labelbg"),
        )
        # 白底是後畫的，會蓋住字，所以把字移回上面
        self.tag_raise(label, background)

    # 算某個名稱的「重疊分數」：蓋到別的名稱或圓點一個算 100 分（一定要避開），
    # 蓋到一條道路算 1 分（盡量避開）；分數越低越好
    def overlap_score(self, item):
        left, top, right, bottom = self.bbox(item)
        score = 0
        # 白底比字左右各寬 2 像素，所以範圍也放寬 2 像素
        for other in self.find_overlapping(left - 2, top, right + 2, bottom):
            if other == item:
                continue
            tags = self.gettags(other)
            if "label" in tags or "labelbg" in tags or "dot" in tags:
                score = score + 100
            elif "road" in tags:
                score = score + 1
        return score

    # 在地點旁邊顯示一個白色小方框，寫出地點全名；游標變成手指，提示可以點
    def show_info(self, place_id):
        self.hide_info()
        self.config(cursor="hand2")
        place = self.graph.places[place_id]
        x, y = self.to_canvas(place["x"], place["y"])
        info = place["name"]
        # 有高度資料的話，順便顯示海拔
        if place["elevation"] is not None:
            info = info + "\n海拔 " + str(place["elevation"]) + " 公尺"
        text = self.create_text(
            x + 12, y - 12,
            text=info,
            anchor=tk.SW,
            fill=config.TEXT_COLOR,
            font=config.TEXT_FONT,
            tags="info",
            # disabled：滑鼠會穿過方框，不然方框蓋到地點時會一直進入/離開、畫面閃個不停像當機
            state="disabled",
        )
        # bbox 會回傳文字佔的範圍 (左, 上, 右, 下)，用它畫出剛好包住文字的方框
        left, top, right, bottom = self.bbox(text)
        box = self.create_rectangle(
            left - 6, top - 3, right + 6, bottom + 3,
            fill=config.INFO_BG_COLOR,
            outline=config.INFO_BORDER_COLOR,
            tags="info",
            state="disabled",
        )
        # 方框是後畫的會蓋住文字，所以把文字移回上面
        self.tag_raise(text, box)

        # 名稱很長、地點又在右邊或上面時，方框會超出畫布，把它推回來
        left, top, right, bottom = self.bbox("info")
        if right > config.MAP_WIDTH:
            self.move("info", config.MAP_WIDTH - right - 4, 0)
        if top < 0:
            self.move("info", 0, -top + 4)

    # 收起顯示全名的小方框，游標變回原本的樣子
    def hide_info(self):
        self.delete("info")
        self.config(cursor="")

    # 在左下角畫圖例，說明每種顏色代表什麼
    # 先把每一行畫出來，再量所有字佔多大，畫一個剛好包住的白框，字放大或縮小都不會超出框
    def draw_legend(self):
        r = config.PLACE_RADIUS
        # 每行的高度跟著字的大小走：量一個字有多高，再多留一點空隙
        row_height = self.text_height(config.LABEL_FONT) + 8
        rows = len(config.PLACE_COLORS) + 1
        x = 24
        y = config.MAP_HEIGHT - 24 - row_height * (rows - 1)

        for place_type, color in config.PLACE_COLORS.items():
            self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=config.PLACE_OUTLINE,
                             width=2, tags="legend")
            self.create_text(x + r + 8, y, text=config.PLACE_TYPE_NAMES[place_type], anchor=tk.W,
                             fill=config.TEXT_COLOR, font=config.LABEL_FONT, tags="legend")
            y = y + row_height
        # 最後一行說明紅線
        self.create_line(x - 8, y, x + 8, y, fill=config.ROUTE_COLOR, width=config.ROUTE_WIDTH,
                         capstyle=tk.ROUND, tags="legend")
        self.create_text(x + r + 8, y, text="找到的路線", anchor=tk.W, fill=config.TEXT_COLOR,
                         font=config.LABEL_FONT, tags="legend")

        left, top, right, bottom = self.bbox("legend")
        box = self.create_rectangle(left - 10, top - 8, right + 10, bottom + 8,
                                    fill=config.LEGEND_BG_COLOR, outline=config.INFO_BORDER_COLOR)
        # 白框是最後畫的，會蓋住圖例，所以把它移到圖例下面
        self.tag_lower(box, "legend")

    # 量某個字型一行字有多高（像素）：先畫一個字、量完再刪掉
    def text_height(self, font):
        item = self.create_text(0, 0, text="字", font=font)
        left, top, right, bottom = self.bbox(item)
        self.delete(item)
        return bottom - top

    # 把路線經過的每一段道路折線接起來，回傳 [[x, y], [x, y], ...]
    # 下一段的第一個點和上一段的最後一個點相同，所以跳過
    def route_points(self, path):
        points = []
        for i in range(len(path) - 1):
            segment = self.graph.edge_points(path[i], path[i + 1])
            if i > 0:
                segment = segment[1:]
            points = points + segment
        return points

    # 沿著道路畫一條路線（顏色、粗細可以指定），放在地點和名稱下面，名稱才不會被擋住
    def draw_line_on_roads(self, path, color, width):
        self.create_line(
            self.to_canvas_points(self.route_points(path)),
            fill=color,
            width=width,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
            tags="route",
        )
        self.tag_lower("route", "place")

    # 沿著道路的折線畫出整條路線，再在起點、終點畫上標記；舊的路線會先清掉
    def draw_route(self, path):
        self.clear_route()
        # create_line 至少要兩個點，起點等於終點時就不畫
        if len(path) < 2:
            return
        self.draw_line_on_roads(path, config.ROUTE_COLOR, config.ROUTE_WIDTH)
        # 起點、終點標記要在最上面，所以最後才畫
        self.draw_marker(path[0], config.START_COLOR)
        self.draw_marker(path[-1], config.END_COLOR)

    # 比較三種演算法時用：播放某一種演算法的搜尋過程（動畫）
    # name 演算法名稱、color 顏色、path 最後找到的路線、
    # steps 搜尋過程：[(這一步處理的地點清單, 到這一步為止檢查了幾次道路), ...]（見 core/pathfinder.py）
    # on_done：播完後要做的事（例如接著播下一種演算法），不用的話傳 None
    def play_search(self, name, color, path, steps, on_done):
        self.clear_route()
        # 把這次動畫要用的資料存起來，show_search_step 每一步都會用到
        self.search_name = name
        self.search_color = color
        self.search_path = path
        self.search_steps = steps
        self.search_done = on_done
        self.lit = set()   # 已經亮起來（處理過）的地點
        self.draw_marker(path[0], config.START_COLOR)
        self.draw_marker(path[-1], config.END_COLOR)
        self.show_search_step(0)

    # 動畫的第 i 步：把這一步處理的地點畫成彩色圓點，正在處理的地點加一圈外框，
    # 左上角寫出做到第幾步、檢查了幾次道路；然後用 self.after 排好下一步
    def show_search_step(self, i):
        places, checked = self.search_steps[i]
        color = self.search_color
        is_bellman = self.search_name == "Bellman-Ford"

        # 上一步的外框拿掉，只留這一步的
        self.delete("current")
        for place_id in places:
            x, y = self.to_canvas(self.graph.places[place_id]["x"], self.graph.places[place_id]["y"])
            if place_id not in self.lit:
                self.lit.add(place_id)
                r = config.SEARCH_DOT_RADIUS
                self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="white", width=1, tags="search")
            r = config.SEARCH_DOT_RADIUS + 5
            self.create_oval(x - r, y - r, x + r, y + r, outline=color, width=3, tags=("search", "current"))
        # 圓點放在名稱下面，名稱才不會被擋住（labelbg 是名稱的白底）
        self.tag_lower("search", "labelbg")

        # Bellman-Ford 每一輪都檢查全部道路：讓全部道路閃一下顏色，看得出它每輪都「掃全圖」
        if is_bellman:
            for edge in self.graph.edges:
                self.create_line(self.to_canvas_points(edge["path"]), fill=color, width=config.ROAD_WIDTH,
                                 capstyle=tk.ROUND, tags=("search", "sweep"))
            self.tag_lower("sweep", "dot")
            self.after(config.SWEEP_MS, lambda: self.delete("sweep"))

        # 左上角的說明
        if is_bellman:
            text = ("Bellman-Ford　第 " + str(i + 1) + " 輪：把全部道路檢查一遍\n"
                    + "這一輪有 " + str(len(places)) + " 個地點變近，累計檢查道路 " + str(checked) + " 次")
            delay = config.ROUND_MS
        else:
            text = (self.search_name + "　第 " + str(i + 1) + " 步：處理「" + self.place_short_name(places[0]) + "」\n"
                    + "已處理 " + str(len(self.lit)) + " 個地點，累計檢查道路 " + str(checked) + " 次")
            delay = config.STEP_MS
        self.show_status(text)
        self.tag_raise("marker")

        if i + 1 < len(self.search_steps):
            self.animation_job = self.after(delay, lambda: self.show_search_step(i + 1))
        else:
            self.animation_job = self.after(delay, self.finish_search)

    # 動畫最後：畫出找到的路線、寫出總結；有 on_done 的話，停一下再執行它
    def finish_search(self):
        self.delete("current")
        self.draw_line_on_roads(self.search_path, self.search_color, config.ROUTE_WIDTH)
        checked = self.search_steps[-1][1]
        if self.search_name == "Bellman-Ford":
            work = "跑了 " + str(len(self.search_steps)) + " 輪"
        else:
            work = "處理了 " + str(len(self.lit)) + " 個地點"
        self.show_status(self.search_name + "　完成！" + work + "\n總共檢查道路 " + str(checked) + " 次，畫出找到的路線")
        self.tag_raise("marker")
        self.animation_job = None
        if self.search_done is not None:
            self.animation_job = self.after(config.PAUSE_MS, self.search_done)

    # 動畫說明用的地點名稱：路口沒有名字，就寫「路口」
    def place_short_name(self, place_id):
        if self.graph.places[place_id]["type"] == "junction":
            return "路口"
        return self.graph.short_name(place_id)

    # 在地圖左上角顯示動畫的說明（白底方框），舊的說明會先清掉
    def show_status(self, text):
        self.delete("status")
        item = self.create_text(16, 14, text=text, anchor=tk.NW, fill=self.search_color,
                                font=config.BOLD_FONT, tags=("search", "status"))
        left, top, right, bottom = self.bbox(item)
        box = self.create_rectangle(left - 8, top - 5, right + 8, bottom + 5, fill=config.INFO_BG_COLOR,
                                    outline=self.search_color, width=2, tags=("search", "status"))
        # 方框後畫會蓋住字，把字移回上面；整個說明放在最上層
        self.tag_raise(item, box)
        self.tag_raise("status")

    # 在某個地點畫一個有白邊的大圓點，用來標示起點或終點
    def draw_marker(self, place_id, color):
        r = config.MARKER_RADIUS
        x, y = self.to_canvas(self.graph.places[place_id]["x"], self.graph.places[place_id]["y"])
        self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="white", width=3, tags=("route", "marker"))

    # 停止正在播的動畫（沒有在播就不用做什麼）
    def stop_animation(self):
        if self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None

    # 清掉畫面上的路線、起終點標記和動畫；正在播的動畫也會停下來
    def clear_route(self):
        self.stop_animation()
        self.delete("route")
        self.delete("search")
