# tests/test_data.py
# 負責：檢查「真正的」地圖資料 data/map_data.json 有沒有打錯。
# 其他測試用的是 4 個點的小地圖，只能確認程式邏輯；這裡確認的是資料本身，
# 以後改了 JSON（加路、改距離、改 id），跑一次測試就知道有沒有改壞。
# 也測試 main.py 的 load_error_reason（讀地圖失敗時顯示的中文原因）。

import json
import math
import unittest

import config
from core.graph import CampusGraph
from core.pathfinder import dijkstra
from main import load_error_reason
from ui.scenery import BUILDINGS

# 「公尺 ÷ 像素長度」的合理範圍。目前 124 條路都在 0.67 ~ 1.0 之間，
# 超出這個範圍，很可能是 distance_m 或 path 打錯了
MIN_METERS_PER_PIXEL = 0.5
MAX_METERS_PER_PIXEL = 1.2

# 道路坡度的上限（%）。目前最陡的是 B 宿舍旁邊那段（約 42%，可能是樓梯），超過 50% 就當作打錯
MAX_SLOPE = 50


# 用經緯度算兩個地點之間的直線距離（公尺），這是球面上兩點距離的公式（haversine）
def straight_distance(a, b):
    earth_radius = 6371000
    lat1 = math.radians(a["lat"])
    lat2 = math.radians(b["lat"])
    d_lat = lat2 - lat1
    d_lng = math.radians(b["lng"] - a["lng"])
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * earth_radius * math.asin(math.sqrt(h))


# 算一條折線的長度（像素）：把每一小段的長度加起來
def path_length(path):
    total = 0
    for i in range(len(path) - 1):
        total = total + math.dist(path[i], path[i + 1])
    return total


class TestMapData(unittest.TestCase):

    # 每個測試開始前，讀真正的地圖；經緯度 CampusGraph 沒有存，所以另外直接讀 JSON
    def setUp(self):
        self.graph = CampusGraph(config.MAP_DATA_PATH)
        with open(config.MAP_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.raw_nodes = {}
        for node in data["nodes"]:
            self.raw_nodes[node["id"]] = node

    # 每條路的「公尺 ÷ 像素長度」要在合理範圍內，太大或太小代表距離或折線打錯
    def test_distance_matches_drawn_path(self):
        for edge in self.graph.edges:
            ratio = edge["distance"] / path_length(edge["path"])
            # subTest：有錯時會告訴我們是哪一條路
            with self.subTest(road=edge["from"] + " - " + edge["to"]):
                self.assertGreaterEqual(ratio, MIN_METERS_PER_PIXEL)
                self.assertLessEqual(ratio, MAX_METERS_PER_PIXEL)

    # 沿著道路走，不可能比兩點之間的直線還短；經緯度本身有誤差，所以留 5% 的空間
    def test_road_not_shorter_than_straight_line(self):
        for edge in self.graph.edges:
            a = self.raw_nodes[edge["from"]]
            b = self.raw_nodes[edge["to"]]
            with self.subTest(road=edge["from"] + " - " + edge["to"]):
                self.assertGreaterEqual(edge["distance"], straight_distance(a, b) * 0.95)

    # 道路是雙向的，所以只要從一個地點走得到其他每個地點，任兩個地點之間就都走得到
    def test_all_places_reachable(self):
        places = []
        for place_id, place in self.graph.places.items():
            if place["type"] != "junction":
                places.append(place_id)
        first = places[0]
        for place_id in places[1:]:
            with self.subTest(place=place_id):
                path, total = dijkstra(self.graph, first, place_id)
                self.assertNotEqual(path, [])

    # 每個地點都要有海拔，而且在合理範圍（校區在內門山區，大約 50 ~ 250 公尺）
    def test_elevation_filled(self):
        for place_id, place in self.graph.places.items():
            with self.subTest(place=place_id):
                self.assertIsNotNone(place["elevation"])
                self.assertGreater(place["elevation"], 50)
                self.assertLess(place["elevation"], 250)

    # 每條路的坡度不能超過 MAX_SLOPE；超過的話很可能是海拔或距離打錯了
    def test_slope_reasonable(self):
        for edge in self.graph.edges:
            with self.subTest(road=edge["from"] + " - " + edge["to"]):
                self.assertLessEqual(abs(self.graph.slope_percent(edge["from"], edge["to"])), MAX_SLOPE)

    # scenery.py 的建築物是用地點 id 找位置，JSON 改了 id 卻忘了改這裡，程式一開就會當掉
    def test_building_ids_exist(self):
        for building in BUILDINGS:
            place_id = building[0]
            # 不用 assertIn：它失敗時會把整份地圖印出來，太長看不清楚
            self.assertTrue(place_id in self.graph.places, "JSON 裡找不到 scenery.py 用到的地點 id：" + place_id)


class TestLoadErrorReason(unittest.TestCase):

    # 每種讀地圖的錯誤，都要換成對應的中文原因
    def test_reasons(self):
        self.assertEqual(load_error_reason(FileNotFoundError()), "找不到地圖檔。")
        with self.assertRaises(json.JSONDecodeError) as caught:
            json.loads('{"nodes": [}')
        self.assertIn("第 1 行", load_error_reason(caught.exception))
        self.assertIn("nodes", load_error_reason(KeyError("nodes")))
        self.assertEqual(load_error_reason(ValueError("道路連到不存在的地點：X")), "道路連到不存在的地點：X")


if __name__ == "__main__":
    unittest.main()
