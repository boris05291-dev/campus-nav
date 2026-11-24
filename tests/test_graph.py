# tests/test_graph.py
# 負責：用 unittest 測試 core/graph.py，
# 確認 CampusGraph 能正確讀取 JSON、建立鄰接表、算出權重。

import os
import tempfile
import unittest

from core.graph import CampusGraph

# 測試地圖放在這個測試檔旁邊（和 test_pathfinder.py 共用）
TEST_MAP = os.path.join(os.path.dirname(__file__), "test_map.json")


class TestCampusGraph(unittest.TestCase):

    # 每個測試開始前，都重新讀一次測試地圖
    def setUp(self):
        self.graph = CampusGraph(TEST_MAP)

    # 鄰接表是雙向的：餐廳的鄰居有圖書館和體育館
    def test_neighbors(self):
        self.assertEqual(sorted(self.graph.neighbors("EAT")), [("GYM", 3), ("LIB", 4)])

    # 道路連到不存在的地點（例如 JSON 打錯字）要報錯，兩端都要檢查
    def test_add_road_unknown_place(self):
        with self.assertRaises(ValueError):
            self.graph.add_road("LIB", "不存在", 5)
        with self.assertRaises(ValueError):
            self.graph.add_road("不存在", "LIB", 5)

    # 距離是負數要報錯（Dijkstra 不能處理負的距離）；0 公尺是可以的
    def test_add_road_negative_distance(self):
        with self.assertRaises(ValueError):
            self.graph.add_road("LIB", "DORM", -1)
        self.graph.add_road("LIB", "DORM", 0)
        self.assertEqual(self.graph.distance_between("LIB", "DORM"), 0)

    # 距離不是數字（JSON 裡寫成 "10"）要報中文的 ValueError，不是讓程式當掉
    def test_add_road_distance_not_number(self):
        with self.assertRaises(ValueError):
            self.graph.add_road("LIB", "DORM", "10")

    # 地圖檔最外層不是 { }（例如寫成 [ ]）要報 ValueError
    def test_load_root_not_dict(self):
        folder = tempfile.mkdtemp()
        bad_map = os.path.join(folder, "bad_map.json")
        with open(bad_map, "w", encoding="utf-8") as f:
            f.write("[]")
        with self.assertRaises(ValueError):
            CampusGraph(bad_map)
        os.remove(bad_map)
        os.rmdir(folder)

    # 兩個直接相連的地點，要回傳道路距離（兩個方向都一樣）
    def test_distance_between(self):
        self.assertEqual(self.graph.distance_between("LIB", "EAT"), 4)
        self.assertEqual(self.graph.distance_between("EAT", "LIB"), 4)

    # 沒有直接相連的道路要報錯
    def test_distance_between_not_connected(self):
        with self.assertRaises(ValueError):
            self.graph.distance_between("LIB", "DORM")

    # 照 JSON 的方向走，折線不變；反方向走，折線要倒過來
    def test_edge_points_direction(self):
        self.assertEqual(self.graph.edge_points("LIB", "EAT"), [[0, 0], [5, 5], [10, 0]])
        self.assertEqual(self.graph.edge_points("EAT", "LIB"), [[10, 0], [5, 5], [0, 0]])

    # JSON 沒給 path 的道路，用兩個地點連成直線
    def test_edge_points_default_straight(self):
        self.assertEqual(self.graph.edge_points("EAT", "GYM"), [[10, 0], [20, 0]])

    # 打完整名稱、代號（大小寫都可以）、或只有一個地點符合的部分文字，都找得到
    def test_find_place_found(self):
        self.assertEqual(self.graph.find_place("J 圖書館"), "LIB")
        self.assertEqual(self.graph.find_place("j"), "LIB")
        self.assertEqual(self.graph.find_place("圖書"), "LIB")
        self.assertEqual(self.graph.find_place("  餐廳  "), "EAT")

    # 用空白分開好幾個字：推薦清單只有一個地點時，find_place 也要找得到（兩邊規則要一樣）
    def test_find_place_multiple_words(self):
        self.assertEqual(self.graph.suggest("j 館"), ["LIB"])
        self.assertEqual(self.graph.find_place("j 館"), "LIB")

    # 同兩個地點有好幾條路：取最短的，後來加的長路不能蓋掉它
    def test_find_edge_keeps_shortest(self):
        self.graph.add_road("LIB", "GYM", 2)
        self.graph.add_road("GYM", "LIB", 99)
        self.assertEqual(self.graph.distance_between("LIB", "GYM"), 2)
        self.assertEqual(self.graph.distance_between("GYM", "LIB"), 2)

    # 短名稱：去掉括號裡的說明；沒有括號就是原本的名稱
    def test_short_name(self):
        self.graph.places["EAT"]["name"] = "餐廳（體育館旁）"
        self.assertEqual(self.graph.short_name("EAT"), "餐廳")
        self.assertEqual(self.graph.short_name("LIB"), "J 圖書館")

    # 空白、找不到、或符合好幾個地點（圖書館和體育館都有「館」），回傳 None
    def test_find_place_not_found(self):
        self.assertIsNone(self.graph.find_place(""))
        self.assertIsNone(self.graph.find_place("教室"))
        self.assertIsNone(self.graph.find_place("館"))

    # 什麼都沒打：推薦全部地點（照名稱排）
    def test_suggest_empty_shows_all(self):
        self.assertEqual(self.graph.suggest(""), ["LIB", "DORM", "EAT", "GYM"])

    # 打代號、部分名稱、用空白分開的好幾個字，都推薦得出來；找不到就是空清單
    def test_suggest_matches(self):
        self.assertEqual(self.graph.suggest("j")[0], "LIB")
        self.assertEqual(self.graph.suggest("館"), ["LIB", "GYM"])
        self.assertEqual(self.graph.suggest("j 館"), ["LIB"])
        self.assertEqual(self.graph.suggest("教室"), [])

    # 名稱開頭就一樣的，要排在「名稱中間才有」的前面
    def test_suggest_startswith_first(self):
        # 只照名稱排的話「餐」會排在「體」前面，所以這個測試能確認是先比「像不像」
        self.graph.places["EAT"]["name"] = "餐廳（體育館旁）"
        self.assertEqual(self.graph.suggest("體育"), ["GYM", "EAT"])

    # 打樓層裡的單位名稱（例如「出納」），也要找得到那棟建築；名稱和單位可以混著打
    def test_suggest_matches_rooms(self):
        self.assertEqual(self.graph.suggest("出納"), ["EAT"])
        self.assertEqual(self.graph.find_place("出納"), "EAT")
        self.assertEqual(self.graph.suggest("餐廳 會計"), ["EAT"])
        self.assertEqual(self.graph.suggest("圖書 出納"), [])

    # 推薦清單的樓層提示：打的是單位就說在幾樓；打的是名稱本身、或沒有樓層資料，就是空字串
    def test_room_hint(self):
        self.assertEqual(self.graph.room_hint("EAT", "出納"), "2F 出納")
        self.assertEqual(self.graph.room_hint("EAT", "餐廳"), "")
        self.assertEqual(self.graph.room_hint("EAT", ""), "")
        self.assertEqual(self.graph.room_hint("LIB", "出納"), "")

    # 樓層說明：高樓層排前面；沒有樓層資料的地點回傳空清單
    def test_floor_lines(self):
        self.assertEqual(self.graph.floor_lines("EAT"), ["2F：出納、會計", "1F：學餐"])
        self.assertEqual(self.graph.floor_lines("LIB"), [])


if __name__ == "__main__":
    unittest.main()
