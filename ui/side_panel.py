# ui/side_panel.py
# 負責：右邊的控制面板（寬度見 config.PANEL_WIDTH）。
# - 讓使用者輸入起點和終點，打字時會自動推薦地點
# - 「最省力路線（避開上坡）」勾選框
# - 提供「找路線」和「比較三種演算法」按鈕
# - 顯示結果：經過的地點、總距離、上下坡、預估步行時間；或三種演算法的比較

import tkinter as tk

import config
from core.route import direction_text


class SearchBox:

    # 建立一組「文字標籤 + 輸入框 + 推薦清單」
    # on_enter 是選好地點（或按 Enter）之後要做的下一步，由 SidePanel 決定
    def __init__(self, panel, graph, label_text, on_enter):
        self.panel = panel
        self.graph = graph
        self.on_enter = on_enter
        # 推薦清單裡每一行對應的地點 id，順序和清單一樣
        self.suggestions = []
        # 推薦清單現在有沒有顯示出來
        self.shown = False

        label = tk.Label(
            panel,
            text=label_text,
            font=config.TEXT_FONT,
            bg=config.PANEL_BG_COLOR,
            fg=config.TEXT_COLOR,
            anchor="w",
        )
        label.pack(fill=tk.X, padx=16, pady=(8, 2))

        self.entry = tk.Entry(panel, font=config.TEXT_FONT, relief=tk.SOLID, bd=1)
        self.entry.pack(fill=tk.X, padx=16, ipady=3)

        # 推薦清單平常藏起來，要用的時候才用 place 疊在輸入框正下方
        # exportselection=False：選清單時不會把另一個輸入框選好的字弄掉
        self.listbox = tk.Listbox(
            panel,
            font=config.TEXT_FONT,
            height=config.SUGGEST_ROWS,
            relief=tk.SOLID,
            bd=1,
            activestyle="none",
            selectbackground=config.SUGGEST_SELECT_COLOR,
            exportselection=False,
        )

        self.entry.bind("<KeyRelease>", self.on_key_release)
        self.entry.bind("<FocusIn>", lambda event: self.update_suggestions())
        self.entry.bind("<FocusOut>", lambda event: self.panel.after(200, self.hide_if_unfocused))
        self.entry.bind("<Down>", lambda event: self.move(1))
        self.entry.bind("<Up>", lambda event: self.move(-1))
        self.entry.bind("<Return>", lambda event: self.choose_and_next())
        self.entry.bind("<Escape>", lambda event: self.hide())
        # 用滑鼠點清單裡的一筆，也算選好了
        self.listbox.bind("<ButtonRelease-1>", lambda event: self.choose_and_next())

    # 每打一個字就重新推薦；上下鍵、Enter、Esc 是在操作清單，不用重新推薦
    def on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        self.update_suggestions()

    # 依照輸入框的字重新產生推薦清單，預設選第一筆（最像的）
    def update_suggestions(self):
        self.suggestions = self.graph.suggest(self.entry.get())
        self.listbox.delete(0, tk.END)
        for place_id in self.suggestions:
            self.listbox.insert(tk.END, self.graph.places[place_id]["name"])

        if len(self.suggestions) == 0:
            self.hide()
            return
        # 筆數少的時候清單就矮一點，最多 SUGGEST_ROWS 行，更多的可以捲
        self.listbox.config(height=min(len(self.suggestions), config.SUGGEST_ROWS))
        self.listbox.selection_set(0)
        self.show()

    # 把推薦清單顯示在輸入框正下方，並放到最上層，才不會被下面的元件擋住
    def show(self):
        self.listbox.place(in_=self.entry, x=0, rely=1.0, relwidth=1.0)
        self.listbox.lift()
        self.shown = True

    # 把推薦清單藏起來
    def hide(self):
        self.listbox.place_forget()
        self.shown = False

    # 焦點離開輸入框時呼叫；如果焦點是跑到推薦清單（滑鼠在點清單），就先不要藏
    def hide_if_unfocused(self):
        focused = self.panel.focus_get()
        if focused is not self.entry and focused is not self.listbox:
            self.hide()

    # 用上下鍵在推薦清單裡移動；step 是 1（往下）或 -1（往上）
    def move(self, step):
        if not self.shown:
            self.update_suggestions()
            return
        selected = self.listbox.curselection()
        if len(selected) == 0:
            index = 0
        else:
            index = selected[0] + step
        # 不要超出清單範圍
        index = max(0, min(index, len(self.suggestions) - 1))
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        # 選到的那一筆如果在畫面外，自動捲過去
        self.listbox.see(index)

    # 把清單裡選到的地點填進輸入框，收起清單，然後做下一步
    def choose_and_next(self):
        if self.shown:
            selected = self.listbox.curselection()
            if len(selected) > 0:
                place_id = self.suggestions[selected[0]]
                self.entry.delete(0, tk.END)
                self.entry.insert(0, self.graph.places[place_id]["name"])
            self.hide()
        self.on_enter()

    # 回傳輸入框裡的地點 id；找不到、或打的字符合好幾個地點，就回傳 None
    def get_place_id(self):
        return self.graph.find_place(self.entry.get())

    # 把輸入框換成指定的文字（例如交換起終點、點地圖時用）
    def set_text(self, text):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, text)
        self.hide()


class SidePanel(tk.Frame):

    # 建立面板：標題、起點終點輸入框、按鈕、結果區
    # on_search 是按下「找路線」時要呼叫的函式，on_compare 是按下「比較三種演算法」時要呼叫的函式
    # has_elevation：地圖資料有沒有高度，沒有的話在勾選框旁邊提醒（都由 app.py 傳進來）
    def __init__(self, parent, graph, on_search, on_compare, has_elevation):
        super().__init__(
            parent,
            width=config.PANEL_WIDTH,
            bg=config.PANEL_BG_COLOR,
        )
        # 讓面板維持固定寬度，不會因為裡面的元件變大變小（高度跟著地圖）
        self.pack_propagate(False)
        self.graph = graph
        self.on_search = on_search
        self.has_elevation = has_elevation

        title = tk.Label(
            self,
            text=config.WINDOW_TITLE,
            font=config.TITLE_FONT,
            bg=config.PANEL_BG_COLOR,
            fg=config.TEXT_COLOR,
        )
        title.pack(pady=(20, 10))

        # 起點選好後，游標自動跳到終點；終點選好後，直接找路線
        # 途經點可以不填，所以起點選好後不跳到途經點；要用的話自己點進去，選好後跳到終點
        self.start = SearchBox(self, graph, "起點", lambda: self.end.entry.focus_set())
        self.via = SearchBox(self, graph, "途經點（可不填）", lambda: self.end.entry.focus_set())
        self.end = SearchBox(self, graph, "終點", on_search)

        hint = tk.Label(
            self,
            text="點輸入框或打幾個字，就會推薦地點\n例如：j、圖書、停車　↑↓ 選擇，Enter 確定\n也可以直接點地圖：第一下起點、第二下終點",
            font=config.LABEL_FONT,
            bg=config.PANEL_BG_COLOR,
            fg=config.TEXT_COLOR,
            justify=tk.LEFT,
            anchor="w",
        )
        hint.pack(fill=tk.X, padx=16, pady=(6, 0))

        # 勾起來就找「最省力」的路：上坡會被當成比較遠（見 core/graph.py 的 step_cost）
        slope_text = "最省力路線（避開上坡）"
        if not has_elevation:
            slope_text = slope_text + "\n※ 地圖還沒有高度資料，目前都當平路"
        self.slope_choice = tk.BooleanVar(value=False)
        slope_box = tk.Checkbutton(
            self,
            text=slope_text,
            variable=self.slope_choice,
            font=config.TEXT_FONT,
            bg=config.PANEL_BG_COLOR,
            fg=config.TEXT_COLOR,
            justify=tk.LEFT,
            anchor="w",
        )
        slope_box.pack(fill=tk.X, padx=12, pady=(10, 0))

        swap_button = tk.Button(self, text="⇅ 交換起點和終點", font=config.TEXT_FONT, command=self.swap)
        swap_button.pack(fill=tk.X, padx=16, pady=(8, 0))

        search_button = tk.Button(self, text="找路線", font=config.BOLD_FONT, command=on_search)
        search_button.pack(fill=tk.X, padx=16, pady=(8, 0))

        compare_button = tk.Button(self, text="比較三種演算法", font=config.TEXT_FONT, command=on_compare)
        compare_button.pack(fill=tk.X, padx=16, pady=(8, 8))

        # 路線很長時結果會超出面板，加一條捲軸
        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 16))

        # 結果區用 Text，名稱太長時會自動換行；state="disabled" 讓使用者不能打字進去
        self.result_text = tk.Text(
            self,
            font=config.TEXT_FONT,
            bg=config.PANEL_BG_COLOR,
            fg=config.TEXT_COLOR,
            wrap="char",
            relief=tk.FLAT,
            state="disabled",
            yscrollcommand=scrollbar.set,
            spacing1=2,    # 每行上面多留 2 像素，行距大一點比較好讀
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=(16, 0), pady=(0, 16))
        scrollbar.config(command=self.result_text.yview)
        # 比較演算法時，三種演算法的名稱用和地圖上路線一樣的顏色、粗體
        for i in range(len(config.COMPARE_COLORS)):
            self.result_text.tag_config("color" + str(i), foreground=config.COMPARE_COLORS[i], font=config.BOLD_FONT)
        self.result_text.tag_config("bold", font=config.BOLD_FONT)

    # 回傳起點 id；找不到、或打的字符合好幾個地點，就回傳 None
    def get_start(self):
        return self.start.get_place_id()

    # 回傳終點 id；找不到、或打的字符合好幾個地點，就回傳 None
    def get_end(self):
        return self.end.get_place_id()

    # 「最省力路線」有沒有勾起來
    def use_slope(self):
        return self.slope_choice.get()

    # 途經點輸入框有沒有填東西（空白不算）
    def has_via(self):
        return self.via.entry.get().strip() != ""

    # 回傳途經點 id；找不到、或打的字符合好幾個地點，就回傳 None
    def get_via(self):
        return self.via.get_place_id()

    # 按下「交換」時執行：把起點和終點的文字對調；兩個都是有效地點的話，直接找回程路線
    # 途經點不動，回程一樣會經過它
    def swap(self):
        start_text = self.start.entry.get()
        end_text = self.end.entry.get()
        self.start.set_text(end_text)
        self.end.set_text(start_text)
        if self.get_start() is not None and self.get_end() is not None:
            self.on_search()

    # 在地圖上點了某個地點時執行
    # 起點還空著、或起終點都已經填好（要重新開始）→ 填進起點並清掉終點
    # 只有起點填好 → 填進終點，然後直接找路線
    def fill_from_map(self, place_id, clear_route):
        name = self.graph.places[place_id]["name"]
        start_empty = self.start.entry.get().strip() == ""
        end_empty = self.end.entry.get().strip() == ""
        if start_empty or not end_empty:
            self.start.set_text(name)
            self.end.set_text("")
            clear_route()
            self.show_message("已選起點，請再點一個地點當終點。")
        else:
            self.end.set_text(name)
            self.on_search()

    # 在結果區顯示一段文字（會先清掉舊的內容）
    def show_message(self, message):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, message)
        self.result_text.config(state="disabled")

    # 把路線結果整理成文字顯示出來
    # stops 是 [(地點 id, 離上一站幾公尺, 離開上一站時怎麼轉), ...]，只有建築和設施，路口已經跳過
    # 「怎麼轉」是 turn_text 的結果，例如「右轉」；第一段沒有轉彎，是 None
    # distance 是實際總距離，minutes 是步行分鐘數，up、down 是總共上坡、下坡幾公尺
    def show_result(self, stops, distance, minutes, up, down):
        # 總距離和步行時間放最上面，路線很長時也不用往下捲才看得到
        lines = []
        if self.use_slope():
            lines.append("【最省力路線】")
        lines.append("總距離：" + str(distance) + " 公尺")
        if self.has_elevation:
            lines.append("上坡 " + str(round(up, 1)) + " 公尺、下坡 " + str(round(down, 1)) + " 公尺")
        lines.append("步行時間：約 " + str(round(minutes, 1)) + " 分鐘")
        lines.append("")
        number = 1
        previous = None
        for place_id, step_distance, turn in stops:
            # 第一站是起點，沒有「離上一站」的距離；轉彎和方向寫在兩站之間
            if previous is not None:
                a = self.graph.places[previous]
                b = self.graph.places[place_id]
                arrow = direction_text(a["x"], a["y"], b["x"], b["y"])
                step = arrow + " 走 " + str(step_distance) + " 公尺" + self.slope_note(previous, place_id, step_distance)
                if turn is None:
                    lines.append("    " + step)
                else:
                    lines.append("    " + turn + "，" + step)
            lines.append(str(number) + ". " + self.graph.short_name(place_id))
            previous = place_id
            number = number + 1
        self.show_message("\n".join(lines))

    # 兩站之間的坡度說明，例如「（上坡 4%）」、「（下坡 9%，陡）」；沒有高度資料或幾乎平的就回傳空字串
    # 用兩站的高度差 ÷ 兩站之間的距離，是這一段的平均坡度
    def slope_note(self, a, b, distance):
        if distance == 0:
            return ""
        percent = self.graph.climb(a, b) / distance * 100
        if abs(percent) < 1:
            return ""
        if percent > 0:
            note = "上坡 " + str(round(percent)) + "%"
        else:
            note = "下坡 " + str(round(-percent)) + "%"
        if abs(percent) >= config.STEEP_SLOPE:
            note = note + "，陡"
        return "（" + note + "）"

    # 顯示三種演算法的比較結果
    # results 是 core/route.py compare_algorithms 回傳的清單；place_count、road_count 是地圖有幾個地點、幾條路
    def show_comparison(self, results, place_count, road_count):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)

        self.result_text.insert(tk.END, "三種演算法比較\n", "bold")
        self.result_text.insert(tk.END, "地圖共 " + str(place_count) + " 個地點、" + str(road_count) + " 條路\n")
        if self.use_slope():
            self.result_text.insert(tk.END, "（目前比較的是「最省力路線」）\n")
        self.result_text.insert(tk.END, "\n")

        for i in range(len(results)):
            result = results[i]
            # 名稱用地圖上路線的顏色
            self.result_text.insert(tk.END, "■ " + result["name"] + "\n", "color" + str(i))
            lines = []
            lines.append("  路線長度：" + str(result["distance"]) + " 公尺")
            if result["name"] == "Bellman-Ford":
                lines.append("  跑了 " + str(result["visited"]) + " 輪")
            else:
                lines.append("  處理了 " + str(result["visited"]) + " 個地點")
            lines.append("  檢查道路 " + str(result["checked"]) + " 次")
            lines.append("  平均每次 " + str(round(result["ms"], 3)) + " 毫秒")
            self.result_text.insert(tk.END, "\n".join(lines) + "\n\n")

        self.result_text.insert(tk.END, "結論\n", "bold")
        self.result_text.insert(tk.END, self.comparison_summary(results))
        self.result_text.config(state="disabled")

    # 依照比較結果寫幾句結論：路線一不一樣、誰檢查最少道路、誰最快
    def comparison_summary(self, results):
        lines = []
        same = True
        for result in results:
            if result["distance"] != results[0]["distance"]:
                same = False
        if same:
            lines.append("三種演算法找到的路線一樣長，都是最短路線；地圖上三色條紋疊在一起。")
        else:
            lines.append("路線長度不一樣，請檢查程式！（正確的話三種應該一樣長）")

        least = results[0]
        fastest = results[0]
        for result in results:
            if result["checked"] < least["checked"]:
                least = result
            if result["ms"] < fastest["ms"]:
                fastest = result
        most = results[0]
        for result in results:
            if result["checked"] > most["checked"]:
                most = result
        lines.append("檢查道路最少的是 " + least["name"] + "（" + str(least["checked"]) + " 次），最多的是 "
                     + most["name"] + "（" + str(most["checked"]) + " 次）。")
        lines.append("跑最快的是 " + fastest["name"] + "。")
        lines.append("")
        lines.append("‧ Dijkstra：每次從離起點最近的地點往外擴，到終點就停。")
        lines.append("‧ A*：多參考「離終點的直線距離」，往終點方向優先找，通常檢查得最少。")
        lines.append("‧ Bellman-Ford：每一輪都把全部道路檢查一遍，工作量最大，但能處理負的距離。")
        return "\n".join(lines)
