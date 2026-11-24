# tools/view_pieces.py
# 負責：檢查用的畫面，把 data/road_pieces.json（tools/split_roads.py 產生的）畫在地圖上。
# - 每一小段依坡度上色：綠色平、黃色緩坡、橘色有點陡、紅色很陡；樓梯再加黑色虛線
# - 每一小段中間寫它是第幾段，路口和地點寫它的 id，兩個合起來就是編號（例如 jD-jR15-03）
# - 滑鼠移到某一小段上，右邊會顯示它的完整資料；點一下會用藍色標起來
# - 右邊可以輸入編號找某一小段
# - 滾輪放大縮小，按住滑鼠左鍵拖曳可以移動地圖
#
# 這個畫面只給人檢查用，和導航程式無關，也不會改任何資料檔。
# 執行方式（在專案資料夾裡）：python3 tools/view_pieces.py
# 如果還沒有 data/road_pieces.json，要先執行：python3 tools/split_roads.py

import json
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

# 讓這個檔案找得到上一層的 config.py、core、ui（因為它放在 tools/ 資料夾裡）
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

import config
from core.graph import CampusGraph
from ui import scenery

PIECES_PATH = os.path.join(PROJECT_DIR, "data", "road_pieces.json")

CANVAS_WIDTH = 1170
CANVAS_HEIGHT = 630
MARGIN = 30
PIECE_WIDTH = 5          # 每一小段的線條粗細
SELECT_COLOR = "#1E63D6" # 點選或找到的那一小段（藍色）
ZOOM_STEP = 1.25         # 滾輪轉一格放大或縮小幾倍

# 坡度（取絕對值）的分級：(小於多少 %, 顏色, 說明)；最後一級是「其他全部」
SLOPE_LEVELS = [
    (5, "#43A047", "平路（坡度 5% 以下）"),
    (10, "#FBC02D", "緩坡（5% ~ 10%）"),
    (15, "#FB8C00", "有點陡（10% ~ 15%）"),
    (None, "#E53935", "很陡（15% 以上）"),
]


# 依坡度決定這一小段要畫什麼顏色
def slope_color(slope):
    for limit, color, text in SLOPE_LEVELS:
        if limit is None or abs(slope) < limit:
            return color
    return SLOPE_LEVELS[-1][1]


class PieceViewer(tk.Tk):

    # 建立視窗：讀資料、畫地圖、做右邊的面板
    def __init__(self, graph, pieces_data):
        super().__init__()
        self.title("道路小段檢查")
        # scenery.draw_ground 會用到 self.graph.places（建築物的位置）
        self.graph = graph
        self.roads = pieces_data["roads"]
        # 編號 -> (這一小段的資料, 它屬於哪條路)，查詢時用
        self.pieces = {}
        # 目前選到的那一小段的編號；沒選就是 None
        self.selected = None
        self.choose_font()

        self.canvas = tk.Canvas(self, width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
                                bg=config.MAP_BG_COLOR, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        # scenery 的函式是用「map_view.create_polygon」來畫，所以把畫布的畫圖函式借給自己用
        self.create_polygon = self.canvas.create_polygon
        self.create_rectangle = self.canvas.create_rectangle
        self.create_oval = self.canvas.create_oval

        self.compute_scale()
        scenery.draw_ground(self)
        self.draw_pieces()
        self.draw_places()
        self.make_panel()
        self.bind_mouse()

    # 找電腦裡有的中文字型（和 ui/app.py 一樣的做法）
    def choose_font(self):
        installed = tkfont.families(self)
        family = "Microsoft JhengHei"
        for name in config.FONT_CHOICES:
            if name in installed:
                family = name
                break
        self.font = (family, 12)
        self.small_font = (family, 9)
        self.bold_font = (family, 13, "bold")

    # 算出縮放比例和位移，讓所有道路剛好放進畫布中間（和 ui/map_view.py 的做法一樣）
    def compute_scale(self):
        xs = []
        ys = []
        for road in self.roads:
            for piece in road["pieces"]:
                for x, y in piece["path"]:
                    xs.append(x)
                    ys.append(y)
        self.min_x = min(xs)
        self.min_y = min(ys)
        span_x = max(max(xs) - self.min_x, 1)
        span_y = max(max(ys) - self.min_y, 1)
        self.scale = min((CANVAS_WIDTH - 2 * MARGIN) / span_x, (CANVAS_HEIGHT - 2 * MARGIN) / span_y)
        self.offset_x = (CANVAS_WIDTH - span_x * self.scale) / 2
        self.offset_y = (CANVAS_HEIGHT - span_y * self.scale) / 2

    # 把 JSON 的像素座標換成畫布座標
    def to_canvas(self, x, y):
        return (self.offset_x + (x - self.min_x) * self.scale,
                self.offset_y + (y - self.min_y) * self.scale)

    # 把一串 [x, y] 換成 create_line 要的 [x1, y1, x2, y2, ...]
    def to_canvas_points(self, path):
        points = []
        for x, y in path:
            canvas_x, canvas_y = self.to_canvas(x, y)
            points.append(canvas_x)
            points.append(canvas_y)
        return points

    # 畫每一小段：依坡度上色，樓梯加虛線，段和段之間畫白色小點當分隔，中間寫第幾段
    def draw_pieces(self):
        for road in self.roads:
            for piece in road["pieces"]:
                self.pieces[piece["id"]] = (piece, road)
                points = self.to_canvas_points(piece["path"])
                # tags 放兩個名字：「piece」代表所有小段，編號代表這一段，之後可以用編號找到它
                self.canvas.create_line(points, fill=slope_color(piece["slope_percent"]),
                                        width=PIECE_WIDTH, capstyle="round",
                                        tags=("piece", piece["id"]))
                if road["stairs"]:
                    self.canvas.create_line(points, fill="#222222", width=2, dash=(3, 3),
                                            tags=("stairs", piece["id"]))

        # 分隔點畫在所有線上面，才看得出一段一段
        for road in self.roads:
            for piece in road["pieces"][1:]:
                x, y = self.to_canvas(piece["start"][0], piece["start"][1])
                self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="white", outline="",
                                        tags="divider")

        # 第幾段的數字，寫在每一小段折線的正中間
        for road in self.roads:
            for piece in road["pieces"]:
                path = piece["path"]
                middle = path[len(path) // 2] if len(path) % 2 == 1 else None
                if middle is None:
                    a = path[len(path) // 2 - 1]
                    b = path[len(path) // 2]
                    middle = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
                x, y = self.to_canvas(middle[0], middle[1])
                number = piece["id"].split("-")[-1]
                self.canvas.create_text(x, y - 8, text=number, font=self.small_font,
                                        fill="#1A1A1A", tags=("number", piece["id"]))

    # 畫地點和路口：小圓點加上 id（小段的編號就是用這些 id 組成的）
    def draw_places(self):
        for place_id, place in self.graph.places.items():
            x, y = self.to_canvas(place["x"], place["y"])
            if place["type"] == "junction":
                self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#555555", outline="white",
                                        tags="place")
                color = "#555555"
            else:
                self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                                        fill=config.PLACE_COLORS.get(place["type"], "#2F6FB0"),
                                        outline="white", tags="place")
                color = "#0D3C78"
            self.canvas.create_text(x + 6, y + 6, text=place_id, anchor="nw", font=self.small_font,
                                    fill=color, tags="place_id")

    # 做右邊的面板：顯示開關、找編號、這一小段的資料、顏色說明
    def make_panel(self):
        # 面板的寬度由裡面最寬的字決定（資料框限制 300 像素就換行），高度由內容決定，字才不會被切掉
        panel = tk.Frame(self, bg="white", padx=12, pady=12)
        panel.pack(side="right", fill="y")

        tk.Label(panel, text="道路小段檢查", font=self.bold_font, bg="white").pack(anchor="w")
        tk.Label(panel, text="滾輪：放大縮小　拖曳：移動地圖\n滑鼠移到線上看資料，點一下標成藍色",
                 font=self.font, bg="white", justify="left", fg="#555555").pack(anchor="w", pady=(4, 10))

        # 顯示開關：勾掉就把那一類東西藏起來，地圖比較不擠
        self.show_numbers = tk.BooleanVar(value=True)
        self.show_place_ids = tk.BooleanVar(value=True)
        tk.Checkbutton(panel, text="顯示第幾段的數字", variable=self.show_numbers, font=self.font,
                       bg="white", command=self.update_visible).pack(anchor="w")
        tk.Checkbutton(panel, text="顯示地點／路口的 id", variable=self.show_place_ids, font=self.font,
                       bg="white", command=self.update_visible).pack(anchor="w")

        # 找編號
        tk.Label(panel, text="輸入編號（例如 jD-jR15-03）：", font=self.font, bg="white").pack(anchor="w", pady=(12, 0))
        search_row = tk.Frame(panel, bg="white")
        search_row.pack(anchor="w", fill="x")
        self.search_entry = tk.Entry(search_row, font=self.font, width=18)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda event: self.search())
        tk.Button(search_row, text="找", font=self.font, command=self.search).pack(side="left", padx=6)
        tk.Button(panel, text="回到整張地圖", font=self.font, command=self.reset_view).pack(anchor="w", pady=(6, 0))

        # 顏色說明
        tk.Label(panel, text="顏色說明（坡度）", font=self.bold_font, bg="white").pack(anchor="w", pady=(12, 0))
        for limit, color, text in SLOPE_LEVELS:
            row = tk.Frame(panel, bg="white")
            row.pack(anchor="w", pady=1)
            tk.Label(row, bg=color, width=3).pack(side="left")
            tk.Label(row, text=" " + text, font=self.font, bg="white").pack(side="left")
        row = tk.Frame(panel, bg="white")
        row.pack(anchor="w", pady=1)
        tk.Label(row, text="- - -", font=self.font, bg="white").pack(side="left")
        tk.Label(row, text=" 樓梯（map_data.json 標了 stairs）", font=self.font, bg="white").pack(side="left")
        row = tk.Frame(panel, bg="white")
        row.pack(anchor="w", pady=1)
        tk.Label(row, text=" ● ", font=self.font, bg="white", fg="#888888").pack(side="left")
        tk.Label(row, text="白色小點：小段和小段的分界", font=self.font, bg="white").pack(side="left")

        # 這一小段的資料
        self.info_label = tk.Label(panel, text="（把滑鼠移到道路上）", font=self.font, bg="#F5F5F5",
                                   justify="left", anchor="nw", wraplength=300, padx=8, pady=8)
        self.info_label.pack(anchor="w", fill="x", pady=(12, 0))

    # 依勾選的開關，顯示或藏起數字和 id
    def update_visible(self):
        state = "normal" if self.show_numbers.get() else "hidden"
        self.canvas.itemconfigure("number", state=state)
        state = "normal" if self.show_place_ids.get() else "hidden"
        self.canvas.itemconfigure("place_id", state=state)

    # 設定滑鼠：移到小段上顯示資料、點選、滾輪縮放、拖曳移動
    def bind_mouse(self):
        self.canvas.tag_bind("piece", "<Enter>", self.on_enter_piece)
        self.canvas.tag_bind("piece", "<Button-1>", self.on_click_piece)
        # Windows、Mac 的滾輪是 MouseWheel；Linux 是 Button-4（往上）和 Button-5（往下）
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", lambda event: self.zoom(event.x, event.y, ZOOM_STEP))
        self.canvas.bind("<Button-5>", lambda event: self.zoom(event.x, event.y, 1 / ZOOM_STEP))
        self.canvas.bind("<ButtonPress-1>", lambda event: self.canvas.scan_mark(event.x, event.y))
        self.canvas.bind("<B1-Motion>", lambda event: self.canvas.scan_dragto(event.x, event.y, gain=1))

    # 找出滑鼠目前指著的那一小段的編號
    def piece_under_mouse(self):
        item = self.canvas.find_withtag("current")
        if not item:
            return None
        for tag in self.canvas.gettags(item[0]):
            if tag in self.pieces:
                return tag
        return None

    # 滑鼠移到某一小段上：右邊顯示它的資料
    def on_enter_piece(self, event):
        piece_id = self.piece_under_mouse()
        if piece_id is not None:
            self.show_info(piece_id)

    # 點某一小段：標成藍色，並顯示資料
    def on_click_piece(self, event):
        piece_id = self.piece_under_mouse()
        if piece_id is not None:
            self.select(piece_id)

    # 把一小段的資料寫在右邊面板
    def show_info(self, piece_id):
        piece, road = self.pieces[piece_id]
        if piece["rise_m"] > 0:
            direction = "上坡"
        elif piece["rise_m"] < 0:
            direction = "下坡"
        else:
            direction = "平"
        lines = [
            "編號：" + piece_id,
            "第 " + piece["第幾段"] + " 段（從 " + road["from"] + " 往 " + road["to"] + "）",
            "從：" + road["from_name"],
            "到：" + road["to_name"],
            "長度：" + str(piece["length_m"]) + " 公尺（整條路 " + str(road["distance_m"]) + " 公尺）",
            "海拔：" + str(piece["elevation_start"]) + " → " + str(piece["elevation_end"]) + " 公尺",
            "上升：" + str(piece["rise_m"]) + " 公尺（" + direction + "）",
            "坡度：" + str(piece["slope_percent"]) + "%",
            "樓梯：" + ("是" if road["stairs"] else "不是"),
        ]
        if piece["提示"]:
            lines.append("提示：" + piece["提示"])
        if piece["備註"]:
            lines.append("備註：" + piece["備註"])
        self.info_label.config(text="\n".join(lines))

    # 把某一小段標成藍色（之前標的那段恢復原本的坡度顏色）
    def select(self, piece_id):
        if self.selected is not None:
            old_piece = self.pieces[self.selected][0]
            self.canvas.itemconfigure(self.line_of(self.selected), fill=slope_color(old_piece["slope_percent"]),
                                      width=PIECE_WIDTH)
            self.canvas.itemconfigure(self.number_of(self.selected), fill="#1A1A1A", font=self.small_font)
        self.selected = piece_id
        line = self.line_of(piece_id)
        self.canvas.itemconfigure(line, fill=SELECT_COLOR, width=PIECE_WIDTH + 4)
        self.canvas.tag_raise(line)
        self.canvas.tag_raise("stairs")
        self.canvas.tag_raise("divider")
        self.canvas.tag_raise("number")
        # 選到的那段的數字改成藍色粗體，放在最上面，才不會和旁邊的數字混在一起
        number = self.number_of(piece_id)
        self.canvas.itemconfigure(number, fill=SELECT_COLOR, font=self.bold_font)
        self.canvas.tag_raise(number)
        self.show_info(piece_id)

    # 找到某一小段那條彩色線的畫布物件（同一個編號還有數字、虛線，要挑有「piece」標籤的）
    def line_of(self, piece_id):
        for item in self.canvas.find_withtag(piece_id):
            if "piece" in self.canvas.gettags(item):
                return item
        return None

    # 找到某一小段的「第幾段」數字的畫布物件
    def number_of(self, piece_id):
        for item in self.canvas.find_withtag(piece_id):
            if "number" in self.canvas.gettags(item):
                return item
        return None

    # 用編號找某一小段：標成藍色，並把地圖移到它在畫面中間
    def search(self):
        piece_id = self.search_entry.get().strip()
        if piece_id not in self.pieces:
            messagebox.showinfo("找不到", "沒有這個編號：" + piece_id + "\n格式是「起點-終點-第幾段」，例如 jD-jR15-03")
            return
        self.select(piece_id)
        # 算出這一小段目前在畫布上的中心（縮放、拖曳過後位置會變，所以直接問畫布）
        x1, y1, x2, y2 = self.canvas.bbox(self.line_of(piece_id))
        center_x = self.canvas.canvasx(self.canvas.winfo_width() / 2)
        center_y = self.canvas.canvasy(self.canvas.winfo_height() / 2)
        self.canvas.move("all", center_x - (x1 + x2) / 2, center_y - (y1 + y2) / 2)

    # 滾輪（Windows、Mac）：往上轉放大、往下轉縮小
    def on_wheel(self, event):
        if event.delta > 0:
            self.zoom(event.x, event.y, ZOOM_STEP)
        else:
            self.zoom(event.x, event.y, 1 / ZOOM_STEP)

    # 以滑鼠所在的位置為中心放大或縮小整張地圖（文字大小不變，所以放大後數字比較不會擠在一起）
    def zoom(self, x, y, factor):
        canvas_x = self.canvas.canvasx(x)
        canvas_y = self.canvas.canvasy(y)
        self.canvas.scale("all", canvas_x, canvas_y, factor, factor)

    # 回到一開始整張地圖的樣子：全部清掉重畫
    def reset_view(self):
        self.canvas.delete("all")
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.selected = None
        scenery.draw_ground(self)
        self.draw_pieces()
        self.draw_places()
        self.update_visible()


# 程式從這裡開始：讀兩個資料檔，打開視窗
def main():
    if not os.path.exists(PIECES_PATH):
        print("找不到 data/road_pieces.json，請先執行：python3 tools/split_roads.py")
        return
    graph = CampusGraph(config.MAP_DATA_PATH)
    with open(PIECES_PATH, "r", encoding="utf-8") as f:
        pieces_data = json.load(f)
    app = PieceViewer(graph, pieces_data)
    app.mainloop()


if __name__ == "__main__":
    main()
