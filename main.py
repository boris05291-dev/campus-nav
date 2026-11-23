# main.py
# 負責：程式入口。執行 python main.py 時從這裡開始，
# 讀取地圖資料、建立主視窗（ui/app.py）並啟動程式。

import json
import tkinter as tk
from tkinter import messagebox

import config
from core.graph import CampusGraph
from ui.app import App


# 把讀地圖時發生的錯誤，換成一句看得懂的中文原因
# 注意順序：JSONDecodeError 也是一種 ValueError，所以要先檢查它
def load_error_reason(error):
    if isinstance(error, FileNotFoundError):
        return "找不到地圖檔。"
    if isinstance(error, json.JSONDecodeError):
        return "JSON 格式有錯：第 " + str(error.lineno) + " 行、第 " + str(error.colno) + " 個字附近。"
    if isinstance(error, KeyError):
        return "資料缺少欄位：" + str(error)
    if isinstance(error, ValueError):
        # graph.py 自己丟出的錯誤（例如道路連到不存在的地點），訊息本來就是中文
        return str(error)
    return "檔案打不開：" + str(error)


# 告訴 Windows「這個程式自己會處理螢幕縮放」
# 不加的話，螢幕縮放設成 125%、150% 時，Windows 會把整個視窗當圖片放大，字就會糊糊的
# 只有 Windows 有 ctypes.windll，其他系統會出錯，所以用 try 包起來，出錯就跳過
def make_text_sharp():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass


# 讀地圖、開視窗，然後進入 tkinter 的事件迴圈（視窗關掉才會結束）
# 地圖檔不見或格式錯誤時，跳出視窗說明原因；不然直接雙擊執行的人只會看到視窗閃一下就不見
def main():
    # 一定要在建立任何 tkinter 視窗之前呼叫才有用
    make_text_sharp()
    try:
        graph = CampusGraph(config.MAP_DATA_PATH)
    except (OSError, ValueError, KeyError) as error:
        root = tk.Tk()
        root.withdraw()   # 藏起空白的主視窗，只顯示錯誤訊息框
        messagebox.showerror(
            "地圖資料有問題",
            "讀不到地圖資料：\n" + config.MAP_DATA_PATH + "\n\n原因：" + load_error_reason(error),
        )
        root.destroy()
        return

    app = App(graph)
    app.mainloop()


if __name__ == "__main__":
    main()
