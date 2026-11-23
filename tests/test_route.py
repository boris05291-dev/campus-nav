# tests/test_route.py
# 負責：用 unittest 測試 core/route.py 的 build_stops、route_via、plan_route，
# 確認路口會被跳過、路口那幾段的距離會加到下一站、轉彎判斷正確。

import os
import unittest

from core.graph import CampusGraph
from core.pathfinder import dijkstra
from core.route import build_stops, plan_route, route_via

# 測試地圖放在這個測試檔旁邊（和其他測試共用）
TEST_MAP = os.path.join(os.path.dirname(__file__), "test_map.json")


class TestBuildStops(unittest.TestCase):

    # 每個測試開始前重新讀測試地圖，再加一個路口 J1，讓「體育館 → J1 → 宿舍」走得通
    # J1 在體育館正下方（畫面座標 y 往下變大），從餐廳往右走到體育館再往 J1，是右轉
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)
        self.graph.places["J1"] = {"name": "路口", "type": "junction", "x": 20, "y": 10}
        self.graph.adjacency["J1"] = []
        self.graph.add_road("GYM", "J1", 5)
        self.graph.add_road("J1", "DORM", 6)

    # 沒有路口：每一站都列出來，距離就是每一段道路的長度
    # 圖書館→餐廳那條路是彎的（經過 (5, 5)），到餐廳時是往右上走，接著往右走，所以是右轉
    # 如果只看地點連成的直線（三個地點都在 y=0），會誤判成直走
    def test_no_junction(self):
        stops = build_stops(self.graph, ["LIB", "EAT", "GYM"])
        self.assertEqual(stops, [("LIB", 0, None), ("EAT", 4, None), ("GYM", 3, "右轉")])

    # 路口要跳過，路口前後兩段的距離（5 + 6）加到下一站
    def test_junction_skipped(self):
        stops = build_stops(self.graph, ["GYM", "J1", "DORM"])
        self.assertEqual(stops, [("GYM", 0, None), ("DORM", 11, None)])

    # 轉彎要看「離開上一站的那條路」：從體育館往下走到 J1，是右轉
    def test_turn_after_stop(self):
        stops = build_stops(self.graph, ["EAT", "GYM", "J1", "DORM"])
        self.assertEqual(stops, [("EAT", 0, None), ("GYM", 3, None), ("DORM", 11, "右轉")])

    # 只有起點（起點等於終點）：只有一站，距離 0
    def test_single_place(self):
        self.assertEqual(build_stops(self.graph, ["LIB"]), [("LIB", 0, None)])


class TestRouteVia(unittest.TestCase):

    # 每個測試開始前，都重新讀一次測試地圖
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)

    # 餐廳 → 圖書館（4）→ 體育館（圖書館→餐廳→體育館 7），共 11；餐廳會經過兩次
    def test_via_detour(self):
        path, total = route_via(self.graph, "EAT", "LIB", "GYM")
        self.assertEqual(path, ["EAT", "LIB", "EAT", "GYM"])
        self.assertEqual(total, 11)

    # 途經點本來就在最短路線上：結果和直接走一樣，途經點只出現一次
    def test_via_on_the_way(self):
        self.assertEqual(route_via(self.graph, "LIB", "EAT", "GYM"), (["LIB", "EAT", "GYM"], 7))

    # 途經點和起點或終點一樣：等於沒有途經點
    def test_via_same_as_start_or_end(self):
        expected = dijkstra(self.graph, "LIB", "GYM")
        self.assertEqual(route_via(self.graph, "LIB", "LIB", "GYM"), expected)
        self.assertEqual(route_via(self.graph, "LIB", "GYM", "GYM"), expected)

    # 起點到途經點、或途經點到終點走不到（宿舍沒有道路）：回傳走不到
    def test_via_unreachable(self):
        self.assertEqual(route_via(self.graph, "LIB", "DORM", "GYM"), ([], float("inf")))
        self.assertEqual(route_via(self.graph, "DORM", "LIB", "GYM"), ([], float("inf")))


class TestPlanRoute(unittest.TestCase):

    # 每個測試開始前，都重新讀一次測試地圖
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)

    # 一般情況：沒有錯誤，結果和 dijkstra 一樣
    def test_ok(self):
        self.assertEqual(plan_route(self.graph, "LIB", "GYM", False, None), (["LIB", "EAT", "GYM"], 7, None))

    # 起點或終點找不到：錯誤訊息要說是哪一個
    def test_missing_start_or_end(self):
        self.assertIn("起點", plan_route(self.graph, None, "GYM", False, None)[2])
        self.assertIn("終點", plan_route(self.graph, "LIB", None, False, None)[2])

    # 途經點沒填：當作沒有途經點；有填卻找不到：要報錯，不能當作沒填
    def test_via_empty_or_not_found(self):
        self.assertIsNone(plan_route(self.graph, "LIB", "GYM", False, None)[2])
        self.assertIn("途經點", plan_route(self.graph, "LIB", "GYM", True, None)[2])

    # 起點等於終點：沒有途經點要報錯；有不同的途經點就可以（去了再回來）
    def test_same_start_and_end(self):
        self.assertIn("同一個", plan_route(self.graph, "LIB", "LIB", False, None)[2])
        self.assertIn("同一個", plan_route(self.graph, "LIB", "LIB", True, "LIB")[2])
        self.assertEqual(plan_route(self.graph, "LIB", "LIB", True, "EAT"), (["LIB", "EAT", "LIB"], 8, None))

    # 走不到（宿舍沒有道路）：要報錯
    def test_unreachable(self):
        self.assertEqual(plan_route(self.graph, "LIB", "DORM", False, None)[0], [])
        self.assertIn("沒有道路", plan_route(self.graph, "LIB", "DORM", False, None)[2])


if __name__ == "__main__":
    unittest.main()
