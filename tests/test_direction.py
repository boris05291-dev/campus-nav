# tests/test_direction.py
# 測試 direction_text：兩點之間的方向箭頭對不對
# 測試 turn_text：走到路口時該左轉、右轉、直走還是迴轉

import unittest

from core.route import direction_text, turn_text


class TestDirection(unittest.TestCase):

    # 測試八個方向（畫面座標 y 往下變大）
    def test_eight_directions(self):
        self.assertEqual(direction_text(0, 0, 100, 0), "→ 往右")
        self.assertEqual(direction_text(0, 0, -100, 10), "← 往左")
        self.assertEqual(direction_text(0, 0, 0, -100), "↑ 往上")
        self.assertEqual(direction_text(0, 0, 10, 100), "↓ 往下")
        self.assertEqual(direction_text(0, 0, 100, -100), "↗ 往右上")
        self.assertEqual(direction_text(0, 0, -100, -80), "↖ 往左上")
        self.assertEqual(direction_text(0, 0, 60, 100), "↘ 往右下")
        self.assertEqual(direction_text(0, 0, -100, 100), "↙ 往左下")

    # 往右走到 (100, 0) 之後，再往不同方向走（畫面座標 y 往下變大，往下走是右轉）
    def test_turns(self):
        self.assertEqual(turn_text(0, 0, 100, 0, 200, 10), "直走")
        self.assertEqual(turn_text(0, 0, 100, 0, 100, 100), "右轉")
        self.assertEqual(turn_text(0, 0, 100, 0, 100, -100), "左轉")
        self.assertEqual(turn_text(0, 0, 100, 0, 0, 5), "迴轉")

    # 角度相減會跨過 180 度的情況：往左走（180 度）再往左下（-135 度附近）應該是左轉
    def test_turn_across_180(self):
        self.assertEqual(turn_text(100, 0, 0, 0, -100, 100), "左轉")
        self.assertEqual(turn_text(100, 0, 0, 0, -100, -100), "右轉")


if __name__ == "__main__":
    unittest.main()
