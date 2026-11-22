"""產生網頁的「示範資料」(docs/demo)：以葡萄王(1707)的測試數據做幾個變化版本，
只用來在第一次真實更新之前預覽網頁。真實資料出現後(data/index.json)，網頁就不會再讀示範資料。
用法：python tools/make_demo.py
"""
import copy
import datetime as dt
import json
import os
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


def variant(code, name, industry, price_x=1.0, ni_x=1.0, cfo_x=1.0, eps_x=1.0, fin=False):
    f = copy.deepcopy(base)
    f.update({"code": code, "name": name, "industry": industry, "is_fin": fin})
    f["isA"]["ni"] = [v * ni_x if v is not None else None for v in f["isA"]["ni"]]
    f["isQ"]["ni"] = [v * ni_x if v is not None else None for v in f["isQ"]["ni"]]
    f["cfA"]["cfo"] = [v * cfo_x if v is not None else None for v in f["cfA"]["cfo"]]
    f["cfQ"]["cfo"] = [v * cfo_x if v is not None else None for v in f["cfQ"]["cfo"]]
    f["frA"]["eps"] = [v * eps_x if v is not None else None for v in f["frA"]["eps"]]
    f["frQ"]["eps"] = [v * eps_x if v is not None else None for v in f["frQ"]["eps"]]
    f["px"]["price"] = round(base["px"]["price"] * price_x, 2)
    return f


demo = [
    base,
    variant("9001", "示範・低價優等", "電子零組件業", price_x=0.62),
    variant("9002", "示範・合理價", "半導體業", price_x=1.3),
    variant("9003", "示範・偏貴", "食品工業", price_x=1.6),
    variant("9004", "示範・過熱", "生技醫療業", price_x=2.4),
    variant("9005", "示範・獲利下滑", "電子零組件業", ni_x=0.55, price_x=0.9),
    variant("9006", "示範・現金流不足", "鋼鐵工業", cfo_x=0.25, price_x=0.8),
    variant("9007", "示範・低ROE", "建材營造業", ni_x=0.35, price_x=0.7),
]
rows = []
for f in demo:
    f = copy.deepcopy(f)
    f.setdefault("name", "葡萄王")
    a = scoring.analyze(f, None, today)
    a["hl"] = "示範資料" if f["code"] != "1707" else "保健食品、益生菌"
    a["links"] = {"profile": build.PROFILE_URL.format(c=f["code"]),
                  "report": build.REPORT_URL.format(c=f["code"], p=build.report_period(today))}
    a["fund_at"] = a["px_at"] = now
    build.save_json(os.path.join(OUT, "stocks", f["code"] + ".json"), a)
    s = scoring.summary(a)
    s["hl"] = a["hl"]
    rows.append(s)
rows.sort(key=lambda s: (-s["s"], -(s["up"] if s["up"] is not None else -999)))
meta = {"updated_at": now, "n_stocks": len(rows), "n_universe": len(rows), "n_stale_14d": 0,
        "n_price_updated": 0, "n_fund_updated": 0, "n_nodata": 0, "failures": [],
        "config": {"pe_low": 10, "pe_mid": 15, "pe_high": 18, "min_score_elite": 13}}
build.save_json(os.path.join(OUT, "index.json"), {"meta": meta, "stocks": rows})
for s in rows:
    print(s["c"], s["n"], s["s"], s["g"], s["k"], s["z"], "|", s["sig"])
