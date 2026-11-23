# tests/test_pathfinder.py
# 負責：用 unittest 測試 core/pathfinder.py，
# 確認 dijkstra 找到的路線和總距離正確，也包含起點等於終點、走不到等特殊情況。
# 執行方式（在 campus_nav 資料夾）：python -m unittest discover -s tests

import os
import unittest

from core.graph import CampusGraph
from core.pathfinder import dijkstra

# 測試地圖放在這個測試檔旁邊
TEST_MAP = os.path.join(os.path.dirname(__file__), "test_map.json")


class TestDijkstra(unittest.TestCase):

    # 每個測試開始前，都重新讀一次測試地圖
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)

    # 一般路線：繞路（4 + 3 = 7）比直接走（10）短，要選繞路
    def test_normal_route(self):
        path, total = dijkstra(self.graph, "LIB", "GYM")
        self.assertEqual(path, ["LIB", "EAT", "GYM"])
        self.assertEqual(total, 7)

    # 走不到：宿舍沒有任何道路
    def test_unreachable(self):
        path, total = dijkstra(self.graph, "LIB", "DORM")
        self.assertEqual(path, [])
        self.assertEqual(total, float("inf"))

    # 起點等於終點：路線只有自己，距離是 0
    def test_start_equals_end(self):
        path, total = dijkstra(self.graph, "EAT", "EAT")
        self.assertEqual(path, ["EAT"])
        self.assertEqual(total, 0)

    # 起點或終點打錯字：要報錯，不能默默回傳「走不到」
    # 用 assertRaisesRegex 確認錯誤訊息有寫「起點」或「終點」，才知道是哪一個打錯
    def test_unknown_place_raises(self):
        with self.assertRaisesRegex(KeyError, "起點"):
            dijkstra(self.graph, "不存在", "LIB")
        with self.assertRaisesRegex(KeyError, "終點"):
            dijkstra(self.graph, "LIB", "不存在")


if __name__ == "__main__":
    unittest.main()
