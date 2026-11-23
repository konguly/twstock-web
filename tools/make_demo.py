"""產生網頁的「示範資料」(docs/demo)：以葡萄王(1707)的測試數據做幾個變化版本，
只用來在第一次真實更新之前預覽網頁。真實資料出現後(data/index.json)，網頁就不會再讀示範資料。
用法：python tools/make_demo.py
"""
import copy
import datetime as dt
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from crawler import build, scoring            # noqa: E402
from test_scoring import load_facts           # noqa: E402

OUT = os.path.join(ROOT, "docs", "demo")
base = load_facts()
today = dt.date.today()
now = build.iso()


def variant(code, name, industry, price=None, yld=None, rev_up=False, fin=False):
    f = copy.deepcopy(base)
    f.update({"code": code, "name": name, "industry": industry, "is_fin": fin})
    if price is not None:
        f["px"]["price"] = price
    if yld is not None:
        f["px"]["yield_pct"] = yld
    if rev_up:
        f["isQ"]["rev"] = [3000] * 4 + [2600] * 4 + f["isQ"]["rev"][8:]
    return f


demo = [
    base,
    variant("9001", "示範・五項通過A", "電子零組件業", price=78, yld=5.2, rev_up=True),
    variant("9002", "示範・五項通過B", "食品工業", price=95, yld=4.4, rev_up=True),
    variant("9003", "示範・太貴", "半導體業", price=180, yld=2.1, rev_up=True),
    variant("9004", "示範・殖利率不足", "生技醫療業", price=90, yld=3.0, rev_up=True),
]
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
rows = []
for f in demo:
    a = scoring.analyze(f, None, today)
    a["hl"] = "示範資料" if f["code"] != "1707" else "保健食品、益生菌"
    a["links"] = {"profile": build.PROFILE_URL.format(c=f["code"]),
                  "report": build.REPORT_URL.format(c=f["code"], p=build.report_period(today))}
    a["fund_at"] = a["px_at"] = now
    a["fund_q"] = f["frQ"]["per"][0]
    build.save_json(os.path.join(OUT, "stocks", f["code"] + ".json"), a)
    s = scoring.summary(a)
    s["hl"] = a["hl"]
    rows.append(s)
rows.sort(key=scoring.sort_key)
meta = {"updated_at": now, "n_stocks": len(rows), "n_universe": len(rows), "n_pick": sum(1 for s in rows if s["ok"]),
        "config": {k: scoring.DEFAULT_CFG[k] for k in ("roe_min", "roe_years", "pb_max", "yield_min",
                                                        "rev_growth_min", "debt_max")}}
build.save_json(os.path.join(OUT, "index.json"), {"meta": meta, "stocks": rows})
print("示範資料：", len(rows), "檔 →", OUT)
