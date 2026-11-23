"""用「葡萄王 1707」的富邦頁面驗證：頁面解析 + V6 五條件選股計算。

執行：  python -m unittest discover -s tests -v
"""
import datetime as dt
import os
import unittest

from crawler import fubon, scoring

FX = os.path.join(os.path.dirname(__file__), "fixtures", "1707")
TODAY = dt.date(2026, 11, 22)


def read(name):
    with open(os.path.join(FX, name + ".html"), encoding="utf8") as f:
        return f.read()


def load_facts():
    L = {k: fubon.parse_main_lines(read(k)) for k in ("isA", "isQ", "frA", "frQ")}
    return {"code": "1707", "name": "葡萄王", "industry": "生技醫療業", "market": "上市",
            "listed": "1982-12-20", "is_fin": False,
            "isA": fubon.x_is_annual(L["isA"]), "isQ": fubon.x_is_quarter(L["isQ"]),
            "frA": fubon.x_fr_annual(L["frA"]), "frQ": fubon.x_fr_quarter(L["frQ"]),
            "div": fubon.x_div(read("div")), "px": fubon.x_basic(read("basic"))}


class TestParse(unittest.TestCase):
    def test_ratio_rows(self):
        f = load_facts()
        self.assertEqual(f["frA"]["roe"][:5], [15.6, 18.54, 18.81, 20.12, 21.16])
        self.assertEqual(f["frQ"]["debt"][0], 22.65)
        self.assertEqual(f["frQ"]["bv"][0], 69.11)
        self.assertEqual(f["isQ"]["rev"][:8], [2414, 2278, 3002, 2428, 2569, 2252, 3155, 2899])


class TestScreen(unittest.TestCase):
    def setUp(self):
        self.f = load_facts()

    def run_with(self, price=None, yld=None):
        f = dict(self.f)
        f["px"] = dict(f["px"])
        if price is not None:
            f["px"]["price"] = price
        if yld is not None:
            f["px"]["yield_pct"] = yld
        return scoring.analyze(f, today=TODAY)

    def test_values(self):
        a = self.run_with(price=81.8, yld=5.0)
        c = {x["key"]: x for x in a["checks"]}
        self.assertAlmostEqual(c["roe"]["v"], 15.6)
        self.assertAlmostEqual(c["pb"]["v"], 81.8 / 69.11)
        self.assertAlmostEqual(c["rev"]["v"], ((2414 + 2278 + 3002 + 2428) / (2569 + 2252 + 3155 + 2899) - 1) * 100)
        self.assertAlmostEqual(c["debt"]["v"], 22.65)

    def test_fail_on_revenue(self):
        a = self.run_with(price=81.8, yld=5.0)        # 近四季營收衰退 → 不入選
        self.assertFalse(a["ok"])
        self.assertIn("營收沒有衰退", a["verdict"])
        self.assertEqual(scoring.summary(a)["f"], "11101")

    def test_pass_all(self):
        f = dict(self.f)
        f["isQ"] = dict(f["isQ"], rev=[3000] * 4 + [2500] * 4)
        f["px"] = dict(f["px"], price=80.0, yield_pct=4.5)
        a = scoring.analyze(f, today=TODAY)
        self.assertTrue(a["ok"])
        self.assertEqual(a["n_pass"], 5)

    def test_expensive(self):
        a = self.run_with(price=200, yld=5.0)
        self.assertFalse({x["key"]: x for x in a["checks"]}["pb"]["ok"])

    def test_missing_and_fin(self):
        a = scoring.analyze({"code": "0000", "name": "空", "industry": "", "px": {}}, today=TODAY)
        self.assertIsNone(a["ok"])
        self.assertEqual(scoring.summary(a)["f"], "-----")
        f = dict(self.f, is_fin=True)
        self.assertIsNone(scoring.analyze(f, today=TODAY)["ok"])

    def test_thresholds_from_config(self):
        a = scoring.analyze(dict(self.f, px=dict(self.f["px"], price=81.8, yield_pct=5)), {"roe_min": 16}, TODAY)
        self.assertFalse(a["checks"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
