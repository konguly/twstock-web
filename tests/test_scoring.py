"""用「葡萄王 1707」的真實數據(取自 v5 Excel)驗證：頁面解析 + 計算結果與 Excel 一致。

執行：  python -m unittest discover -s tests -v
"""
import datetime as dt
import json
import os
import unittest

from crawler import fubon, scoring

FX = os.path.join(os.path.dirname(__file__), "fixtures", "1707")
TODAY = dt.date(2026, 11, 22)          # Excel 檔案存檔時的日期附近；只影響「上市年數」


def read(name):
    with open(os.path.join(FX, name + ".html"), encoding="utf8") as f:
        return f.read()


def load_facts():
    L = {k: fubon.parse_main_lines(read(k)) for k in
         ("isA", "isQ", "bsA", "bsQ", "cfA", "cfQ", "frA", "frQ")}
    f = {"code": "1707", "name": "葡萄王", "industry": "生技醫療業", "market": "上市",
         "listed": "1982-12-20", "is_fin": False,
         "isA": fubon.x_is_annual(L["isA"]), "isQ": fubon.x_is_quarter(L["isQ"]),
         "bsA": fubon.x_bs_annual(L["bsA"]), "bsQ": fubon.x_bs_quarter(L["bsQ"]),
         "cfA": fubon.x_cf(L["cfA"]), "cfQ": fubon.x_cf(L["cfQ"]),
         "frA": fubon.x_fr_annual(L["frA"]), "frQ": fubon.x_fr_quarter(L["frQ"]),
         "div": fubon.x_div(read("div")), "bm": fubon.x_bm(read("bm")),
         "rev": fubon.x_rev(read("rev")), "px": fubon.x_basic(read("basic"))}
    return f


class TestAgainstExcel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = load_facts()
        cls.a = scoring.analyze(cls.f, today=TODAY)
        with open(os.path.join(FX, "expected.json"), encoding="utf8") as fh:
            cls.e = json.load(fh)

    def close(self, got, want, tol=1e-6, msg=""):
        self.assertIsNotNone(got, msg)
        self.assertAlmostEqual(got, float(want), delta=tol * max(1.0, abs(float(want))), msg=msg)

    # ---------- 解析 ----------
    def test_parse_basics(self):
        px = self.f["px"]
        self.assertEqual(px["price"], 81.8)
        self.assertEqual(px["date"], "11/04")
        self.assertAlmostEqual(px["yield_pct"], 7.33)
        self.assertEqual(self.f["div"]["2025"], 6.0)
        self.assertAlmostEqual(self.f["bm"]["hold_pct"], float(self.e["C12"]), places=1)
        self.assertEqual(self.f["frA"]["per"][0], "2025")
        self.assertEqual(self.f["isQ"]["per"][0], "2026.2Q")

    # ---------- 獲利矩陣 ----------
    def test_matrix(self):
        m = self.e["matrix_rows"]
        for i, c in enumerate(self.a["matrix"]):
            self.assertEqual(c["grade"], m["grade"][i], f"grade col {i}")
            if m["roe"][i] is not None:
                self.close(c["roe"], m["roe"][i], 1e-9, f"roe col {i}")
            if m["fcf"][i] is not None:
                self.close(c["fcf"], m["fcf"][i], 1e-9, f"fcf col {i}")
        self.assertEqual(self.a["score"], self.e["J17"])

    # ---------- 9 大指標 ----------
    def test_nine_indicators(self):
        for i, row in enumerate(range(6, 15)):
            it = self.a["ind9"][i]
            self.close(it["val"], self.e[f"C{row}"], 1e-9, f"指標{i + 1} 實際值")
            self.assertEqual("✔" if it["ok"] else "✘", self.e[f"D{row}"], f"指標{i + 1} 判定")
        self.assertEqual(self.a["pass9"], self.e["C15"])
        self.assertEqual(self.a["pass9_label"], self.e["D15"])
        self.assertEqual(self.a["fail9"], self.e["C16"])
        self.close(self.a["extra"][0]["val"], self.e["C17"])
        self.close(self.a["extra"][1]["val"], self.e["C18"])

    # ---------- 5 年級別 ----------
    def test_grade5(self):
        g = self.a["grade5"]
        self.assertEqual(g["all_fcf_pos"], self.e["B21"])
        self.close(g["fcf_sum5"], self.e["B22"])
        self.assertEqual(g["all_div"], self.e["B23"])
        self.assertEqual(g["roe_keep"], self.e["B24"])
        self.assertEqual(g["grade"], self.e["B25"])
        self.assertEqual(g["trend"], self.e["B26"])
        self.close(g["fcf_payout5"], self.e["B28"])
        self.close(g["fcf_payout1"], self.e["B29"])
        self.assertEqual(g["neg2"], self.e["B30"])

    # ---------- 估價 ----------
    def test_valuation(self):
        v = self.a["valuation"]
        for i, col in enumerate("BCD"):
            self.close(v["eps_est"][i], self.e[f"{col}44"], 1e-9, f"預估EPS {col}")
            self.close(v["pe_now"][i], self.e[f"{col}46"], 1e-9, f"預估PE {col}")
            for j, r in enumerate((49, 50, 51)):
                self.close(v["bands"][i][j], self.e[f"{col}{r}"], 1e-9, f"價格帶 {col}{r}")
            self.assertEqual(v["zones"][i], self.e[f"{col}52"], f"區間 {col}")
        self.close(v["growth"][0], self.e["B42"], 1e-9)
        self.close(v["growth"][1], self.e["C42"], 1e-6)
        self.close(v["margin"][1], self.e["C43"], 1e-9)
        self.close(v["hist_pe_min"], self.e["B53"])
        self.close(v["hist_pe_max"], self.e["C53"])

    def test_gordon(self):
        for i, col in enumerate("BCD"):
            g = self.a["gordon"][i]
            for key, r in (("payout", 56), ("div_est", 57), ("Y", 58), ("bv_est", 59), ("roe_est", 60),
                           ("G", 61), ("ret", 62), ("lynch", 63), ("gp", 67)):
                self.close(g[key], self.e[f"{col}{r}"], 1e-9, f"高登 {key} {col}")
            self.assertEqual(g["fit"], self.e[f"{col}64"], f"適用性 {col}")
            self.assertEqual(g["judge"], self.e[f"{col}72"], f"高登判斷 {col}")

    # ---------- 綜合 ----------
    def test_verdict(self):
        v = self.a["verdict"]
        self.assertEqual(v["quality"], self.e["B79"])
        self.assertEqual(v["weak"], self.e["B80"])
        self.assertEqual(v["signal"], self.e["B82"])
        self.close(v["earn_yield"], self.e["B75"], 1e-9)
        self.close(v["upside_pe"], self.e["B77"], 1e-9)
        want = self.e["B81"]
        got = "".join(f"【{w}】" for w in v["warnings"]) or "無警示"
        self.assertEqual(got, want)


class TestEdgeCases(unittest.TestCase):
    def test_empty_facts_do_not_crash(self):
        a = scoring.analyze({"code": "0000", "name": "空", "industry": "", "px": {}}, today=dt.date(2026, 11, 22))
        self.assertEqual(a["verdict"]["signal"], "資料不足")
        self.assertEqual(a["score"], 0)

    def test_loss_making(self):
        f = load_facts()
        f["frA"]["eps"][0] = -1.0
        f["isA"]["rev"] = [100.0, 100.0] + [100.0] * 6
        a = scoring.analyze(f, today=dt.date(2026, 11, 22))
        self.assertTrue(a["verdict"]["signal"].startswith("虧損"), a["verdict"]["signal"])
        self.assertEqual(a["verdict"]["cat"], "avoid")

    def test_grade_functions(self):
        g = scoring.grade
        self.assertEqual(g(16, 1), "A優等")
        self.assertEqual(g(16, -1), "B1納入備取")
        self.assertEqual(g(12, 1), "B2納入備取")
        self.assertEqual(g(12, -1), "C列入觀察")
        self.assertEqual(g(5, 1), "C1不考慮")
        self.assertEqual(g(5, -1), "C2不考慮")
        self.assertEqual(g(-3, 1), "ROE<=0不考慮")
        self.assertIsNone(g(None, 1))
        self.assertEqual(scoring.matrix_score(["A優等"] * 5 + ["A優等"]), 15)
        self.assertEqual(scoring.matrix_score(["A優等", "B1納入備取", "B2納入備取", "C列入觀察", None]), 6)
        self.assertEqual(scoring.grade_fin(11, 2), "A優等")
        self.assertEqual(scoring.grade_fin(8, 2), "B2納入備取")


if __name__ == "__main__":
    unittest.main()
