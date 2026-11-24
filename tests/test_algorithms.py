# tests/test_algorithms.py
# 負責：測試三種演算法（Dijkstra、A*、Bellman-Ford）和坡度功能。
# - 三種演算法在測試地圖和真正的校園地圖上，找到的距離都要一樣（都是最短）
# - counter 有記錄工作量；A* 檢查的道路不會比 Dijkstra 多
# - 坡度：上坡會被當成比較遠，「最省力路線」會繞開陡坡；route_summary 算對上下坡
# - 樓梯：標了 stairs 的道路不看坡度，用固定倍數算花費

import os
import unittest

import config
from core.graph import CampusGraph
from core.pathfinder import a_star, bellman_ford, dijkstra
from core.route import compare_algorithms, plan_route, route_summary, stairs_count, walk_minutes

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
    # 把餐廳設成在山上（高 5 公尺），走短的路要爬 5 公尺，而且很陡，花費比繞遠路大很多
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

    # 上坡的花費 = 距離 + 爬升 × CLIMB_FACTOR × 陡度加成；不考慮坡度時花費就是距離
    # 這裡直接傳距離進去，用 LIB→EAT 的高度差（爬 5 公尺）試不同坡度
    def test_step_cost_uphill(self):
        steep_bonus = 1 + 5 * config.STEEP_EXTRA / 100        # 100 公尺爬 5 公尺，坡度 5%
        self.assertAlmostEqual(self.graph.step_cost("LIB", "EAT", 100, True), 100 + 5 * config.CLIMB_FACTOR * steep_bonus)
        self.assertEqual(self.graph.step_cost("LIB", "EAT", 4, False), 4)

    # 越陡越慢：一樣爬 5 公尺，路越短（越陡），爬坡多花的部分越多
    def test_steeper_is_slower(self):
        gentle_extra = self.graph.step_cost("LIB", "EAT", 100, True) - 100    # 坡度 5%
        steep_extra = self.graph.step_cost("LIB", "EAT", 50, True) - 50       # 坡度 10%
        self.assertGreater(steep_extra, gentle_extra)

    # 陡度加成最多 STEEP_BONUS_MAX 倍：4 公尺爬 5 公尺（坡度 125%，像樓梯）也只乘 1.5 倍
    def test_steep_bonus_limit(self):
        self.assertAlmostEqual(self.graph.step_cost("LIB", "EAT", 4, True), 4 + 5 * config.CLIMB_FACTOR * config.STEEP_BONUS_MAX)

    # 緩下坡比較快：100 公尺下降 3 公尺（坡度 3%），少算 3 × DOWNHILL_FACTOR 公尺
    def test_gentle_downhill_faster(self):
        self.graph.places["EAT"]["elevation"] = 3
        self.assertEqual(self.graph.step_cost("EAT", "LIB", 100, True), 100 - 3 * config.DOWNHILL_FACTOR)

    # 下坡最多只快 DOWNHILL_MAX（10%）：100 公尺下降 5 公尺（坡度 5%）本來要少算 10 公尺，剛好碰到上限
    # 70 公尺下降 5 公尺（坡度約 7%）要少算 10 公尺，超過上限，只少算 7 公尺
    def test_downhill_limit(self):
        self.assertAlmostEqual(self.graph.step_cost("EAT", "LIB", 70, True), 70 * (1 - config.DOWNHILL_MAX))

    # 陡下坡要小心走，不會變快：3 公尺下降 5 公尺，花費就是距離
    def test_steep_downhill_not_faster(self):
        self.assertEqual(self.graph.step_cost("EAT", "GYM", 3, True), 3)

    # 步行時間：平路就是距離 ÷ 走路速度；有上坡會比較久
    def test_walk_minutes(self):
        self.assertAlmostEqual(walk_minutes(self.graph, ["LIB", "GYM"]), 10 / config.WALK_SPEED)
        self.assertGreater(walk_minutes(self.graph, ["LIB", "EAT", "GYM"]), 7 / config.WALK_SPEED)
        self.assertEqual(walk_minutes(self.graph, ["LIB"]), 0)

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

    # 把 LIB→EAT 改成樓梯：上樓梯花費 = 距離 × STAIRS_UP_FACTOR，下樓梯 = 距離 × STAIRS_DOWN_FACTOR，
    # 不再用坡度的規則；不考慮坡度時花費還是距離
    def test_stairs_cost(self):
        self.graph.find_edge("LIB", "EAT")["stairs"] = True
        self.assertTrue(self.graph.is_stairs("EAT", "LIB"))
        self.assertFalse(self.graph.is_stairs("EAT", "GYM"))
        self.assertEqual(self.graph.step_cost("LIB", "EAT", 4, True), 4 * config.STAIRS_UP_FACTOR)
        self.assertEqual(self.graph.step_cost("EAT", "LIB", 4, True), 4 * config.STAIRS_DOWN_FACTOR)
        self.assertEqual(self.graph.step_cost("LIB", "EAT", 4, False), 4)

    # 兩邊一樣高（不知道哪邊高）的樓梯，兩個方向都當作上樓梯
    def test_flat_stairs_count_as_up(self):
        self.graph.places["EAT"]["elevation"] = 0
        self.graph.find_edge("LIB", "EAT")["stairs"] = True
        self.assertEqual(self.graph.step_cost("EAT", "LIB", 4, True), 4 * config.STAIRS_UP_FACTOR)

    # stairs_count：路線上有幾段樓梯
    def test_stairs_count(self):
        self.assertEqual(stairs_count(self.graph, ["LIB", "EAT", "GYM"]), 0)
        self.graph.find_edge("LIB", "EAT")["stairs"] = True
        self.assertEqual(stairs_count(self.graph, ["LIB", "EAT", "GYM"]), 1)
        self.assertEqual(stairs_count(self.graph, ["LIB"]), 0)


if __name__ == "__main__":
    unittest.main()
