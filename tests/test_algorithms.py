# tests/test_algorithms.py
# 負責：測試三種演算法（Dijkstra、A*、Bellman-Ford）和坡度功能。
# - 三種演算法在測試地圖和真正的校園地圖上，找到的距離都要一樣（都是最短）
# - counter 有記錄工作量；A* 檢查的道路不會比 Dijkstra 多
# - 坡度：上坡會被當成比較遠，「最省力路線」會繞開陡坡；route_summary 算對上下坡

import os
import unittest

import config
from core.graph import CampusGraph
from core.pathfinder import a_star, bellman_ford, dijkstra
from core.route import compare_algorithms, plan_route, route_summary

TEST_MAP = os.path.join(os.path.dirname(__file__), "test_map.json")
ALL = [dijkstra, a_star, bellman_ford]


class TestThreeAlgorithms(unittest.TestCase):

    # 每個測試開始前，都重新讀一次測試地圖
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)

    # 測試地圖上三種演算法的答案都和 Dijkstra 一樣，包含走不到、起點等於終點
    def test_same_answer_on_test_map(self):
        for algorithm in ALL:
            with self.subTest(algorithm=algorithm.__name__):
                self.assertEqual(algorithm(self.graph, "LIB", "GYM"), (["LIB", "EAT", "GYM"], 7))
                self.assertEqual(algorithm(self.graph, "LIB", "DORM"), ([], float("inf")))
                self.assertEqual(algorithm(self.graph, "EAT", "EAT"), (["EAT"], 0))

    # 起點或終點打錯字都要報錯
    def test_unknown_place_raises(self):
        for algorithm in ALL:
            with self.subTest(algorithm=algorithm.__name__):
                with self.assertRaisesRegex(KeyError, "起點"):
                    algorithm(self.graph, "不存在", "LIB")

    # 傳 counter 進去，要記下處理了幾個地點、檢查幾次道路
    def test_counter(self):
        counter = {}
        dijkstra(self.graph, "LIB", "GYM", False, counter)
        self.assertGreater(counter["visited"], 0)
        self.assertGreater(counter["checked"], 0)

    # counter["steps"] 記下搜尋過程：Dijkstra、A* 每一步一個地點，第一步是起點、最後一步是終點；
    # Bellman-Ford 每一輪一步。最後一步記的檢查次數，要等於總共檢查的次數
    def test_steps(self):
        for algorithm in [dijkstra, a_star]:
            with self.subTest(algorithm=algorithm.__name__):
                counter = {}
                algorithm(self.graph, "LIB", "GYM", False, counter)
                self.assertEqual(len(counter["steps"]), counter["visited"])
                self.assertEqual(counter["steps"][0][0], ["LIB"])
                self.assertEqual(counter["steps"][-1][0], ["GYM"])
                self.assertEqual(counter["steps"][-1][1], counter["checked"])
        counter = {}
        bellman_ford(self.graph, "LIB", "GYM", False, counter)
        self.assertEqual(len(counter["steps"]), counter["visited"])
        self.assertEqual(counter["steps"][-1][1], counter["checked"])
        # 最後一輪什麼都沒變（所以才停下來），這一步沒有地點
        self.assertEqual(counter["steps"][-1][0], [])


class TestRealMap(unittest.TestCase):

    # 讀真正的校園地圖，挑出所有可以選的地點（不是路口）
    def setUp(self):
        self.graph = CampusGraph(config.MAP_DATA_PATH)
        self.places = []
        for place_id, place in self.graph.places.items():
            if place["type"] != "junction":
                self.places.append(place_id)

    # 任兩個地點，三種演算法找到的距離都要一樣；A* 檢查的道路不能比 Dijkstra 多
    # （路線本身可能不同：有兩條一樣短的路時，選哪一條都對）
    def test_all_pairs_same_distance(self):
        for start in self.places:
            for end in self.places:
                dijkstra_counter = {}
                a_star_counter = {}
                path, best = dijkstra(self.graph, start, end, False, dijkstra_counter)
                with self.subTest(start=start, end=end):
                    self.assertEqual(a_star(self.graph, start, end, False, a_star_counter)[1], best)
                    self.assertEqual(bellman_ford(self.graph, start, end)[1], best)
                    self.assertLessEqual(a_star_counter["checked"], dijkstra_counter["checked"])

    # compare_algorithms 回傳三筆結果，路線長度都一樣
    def test_compare_algorithms(self):
        results = compare_algorithms(self.graph, self.places[0], self.places[-1], repeat=3)
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result["distance"], results[0]["distance"])
            self.assertGreater(result["checked"], 0)


class TestSlope(unittest.TestCase):

    # 測試地圖：圖書館→餐廳→體育館 7 公尺（短），圖書館→體育館 10 公尺（長）
    # 把餐廳設成在山上（高 5 公尺），走短的路要爬 5 公尺，等於多走 5 × 8 = 40 公尺
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)
        self.graph.places["LIB"]["elevation"] = 0
        self.graph.places["EAT"]["elevation"] = 5
        self.graph.places["GYM"]["elevation"] = 0

    # 爬升高度、坡度：往上是正的、往下是負的
    def test_climb_and_slope(self):
        self.assertEqual(self.graph.climb("LIB", "EAT"), 5)
        self.assertEqual(self.graph.climb("EAT", "LIB"), -5)
        self.assertEqual(self.graph.slope_percent("LIB", "EAT"), 125)   # 5 ÷ 4 × 100

    # 沒有高度的地點當作平路
    def test_no_elevation_is_flat(self):
        self.assertEqual(self.graph.climb("GYM", "DORM"), 0)

    # 上坡的花費 = 距離 + 爬升 × CLIMB_FACTOR；下坡不加
    def test_step_cost(self):
        self.assertEqual(self.graph.step_cost("LIB", "EAT", 4, True), 4 + 5 * config.CLIMB_FACTOR)
        self.assertEqual(self.graph.step_cost("EAT", "GYM", 3, True), 3)
        self.assertEqual(self.graph.step_cost("LIB", "EAT", 4, False), 4)

    # 不管坡度：走短的 7 公尺；最省力：改走平的 10 公尺那條，三種演算法都一樣
    def test_avoid_uphill(self):
        for algorithm in ALL:
            with self.subTest(algorithm=algorithm.__name__):
                self.assertEqual(algorithm(self.graph, "LIB", "GYM")[0], ["LIB", "EAT", "GYM"])
                self.assertEqual(algorithm(self.graph, "LIB", "GYM", True), (["LIB", "GYM"], 10))

    # plan_route 也可以找最省力路線
    def test_plan_route_with_slope(self):
        self.assertEqual(plan_route(self.graph, "LIB", "GYM", False, None, True), (["LIB", "GYM"], 10, None))

    # route_summary：實際距離、上坡、下坡
    def test_route_summary(self):
        self.assertEqual(route_summary(self.graph, ["LIB", "EAT", "GYM"]), (7, 5, 5))
        self.assertEqual(route_summary(self.graph, ["LIB"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
