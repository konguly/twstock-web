"""主程式：更新股票清單 → 更新股價 → 輪流更新財報 → 計算 → 輸出網站用的 JSON。

用法(在專案根目錄)：
  python -m crawler.build --state state --out site/data                # 正式更新(GitHub Actions 每天跑)
  python -m crawler.build --state state --out site/data --codes 1707,2330   # 小量測試
  python -m crawler.build --state state --out site/data --budget-min 60    # 限制時間
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

from . import fubon, scoring, twse

TZ = ZoneInfo("Asia/Taipei")
PRICE_FRESH_H = 16          # 股價超過這麼多小時才重抓
PROFILE_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zc/zca/zca_{c}.djhtm"
REPORT_URL = "https://doc.twse.com.tw/server-java/t57sb01?step=1&colorchg=1&co_id={c}&year={y}&seamon=&mtype=A&"


def report_year(d):
    """最新一期已公告財報所屬年度(民國年)，給公開資訊觀測站電子書列表用。"""
    return int(report_period(d)[:4]) - 1911


def now():
    return dt.datetime.now(TZ)


def iso(t=None):
    return (t or now()).isoformat(timespec="seconds")


def age_hours(s):
    if not s:
        return 1e9
    try:
        return (now() - dt.datetime.fromisoformat(s)).total_seconds() / 3600
    except ValueError:
        return 1e9


def report_period(d):
    """依法定申報期限推估已公告的最新一期財報檔名期別(與 Excel 版相同)。"""
    md = d.month * 100 + d.day
    y = d.year
    if md >= 1115:
        return f"{y}03"
    if md >= 815:
        return f"{y}02"
    if md >= 516:
        return f"{y}01"
    if md >= 401:
        return f"{y - 1}04"
    return f"{y - 1}03"


def load_json(path, default=None):
    try:
        with open(path, encoding="utf8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj, compact=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8") as f:
        json.dump(_round(obj), f, ensure_ascii=False, allow_nan=False,
                  separators=(",", ":") if compact else None, indent=None if compact else 1)


def _round(o):
    if isinstance(o, float):
        return round(o, 4)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    return o


class Guard:
    """連續失敗太多代表被擋或網站改版：提早中止，避免用壞資料覆蓋網站。"""

    def __init__(self, fx, first_n=25):
        self.fx, self.first_n = fx, first_n

    def check(self):
        if self.fx.n_ok == 0 and self.fx.n_fail >= self.first_n:
            raise SystemExit("前 %d 個請求全部失敗：可能被來源網站阻擋或網址改版，已中止(不會覆蓋網站資料)。"
                             % self.first_n)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="state")
    ap.add_argument("--out", default="site/data")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--refs", default="data_ref/highlights.json")
    ap.add_argument("--codes", default="")
    ap.add_argument("--budget-min", type=float, default=300)
    ap.add_argument("--skip-universe", action="store_true")
    ap.add_argument("--prices-only", action="store_true")
    ap.add_argument("--force-fund", action="store_true")
    a = ap.parse_args(argv)

    cfg = scoring.merged_cfg(load_json(a.config, {}) or {})
    refs = load_json(a.refs, {}) or {}
    fx = fubon.Fetcher(delay=float(cfg.get("request_delay_sec", 0.7)))
    guard = Guard(fx)
    t0 = time.time()
    deadline = t0 + a.budget_min * 60
    fdir = os.path.join(a.state, "facts")
    os.makedirs(fdir, exist_ok=True)

    # ---------- 1. 股票清單 ----------
    uni_path = os.path.join(a.state, "universe.json")
    universe = load_json(uni_path)
    if not a.skip_universe:
        rows, err = twse.fetch_universe(fx)
        if rows:
            universe = rows
            save_json(uni_path, universe)
        else:
            print("[警告] 股票清單更新失敗：", err, "→ 沿用上次清單", file=sys.stderr)
    guard.check()
    if not universe:
        raise SystemExit("沒有股票清單可用(證交所頁面無法取得，且沒有上次的備份)。")
    if a.codes:
        want = {c.strip() for c in a.codes.split(",") if c.strip()}
        universe = [r for r in universe if r["code"] in want]
        if not universe:
            raise SystemExit("--codes 指定的代號不在股票清單中。")
    info = {r["code"]: r for r in universe}

    def fpath(c):
        return os.path.join(fdir, c + ".json")

    facts = {c: load_json(fpath(c)) for c in info}

    # ---------- 2. 股價(每天) ----------
    n_price = 0
    for c, r in info.items():
        f = facts.get(c)
        if not f or f.get("status") != "ok":
            continue
        if age_hours(f.get("px_at")) < PRICE_FRESH_H:
            continue
        if time.time() > deadline - 60:
            break
        px = fubon.fetch_price(fx, c)
        guard.check()
        if px and px.get("price") is not None:
            f["px"], f["px_at"] = px, iso()
            save_json(fpath(c), f)
            n_price += 1
    print(f"股價更新：{n_price} 檔 ({time.time() - t0:.0f}s)")

    # ---------- 2b. 補抓 ROE 與負債比率(V6 新選股法需要；舊資料沒有這兩欄) ----------
    n_fix = 0
    if not a.prices_only:
        for c, f in list(facts.items()):
            if not f or f.get("status") != "ok" or f.get("fr_v") == 6 or c not in info:
                continue
            if time.time() > deadline - 60:
                break
            part = fubon.fetch_ratios(fx, c)
            guard.check()
            if not part:
                continue
            f.update(part)
            f["fr_v"] = 6
            save_json(fpath(c), f)
            n_fix += 1
        print(f"補抓財務比率(ROE/負債比率)：{n_fix} 檔")

    # ---------- 2c. 補抓損益表(成長力道圖需要營業毛利、營業費用) ----------
    n_fix = 0
    if not a.prices_only:
        for c, f in list(facts.items()):
            if not f or f.get("status") != "ok" or f.get("is_v") == 7 or c not in info:
                continue
            if time.time() > deadline - 60:
                break
            part = fubon.fetch_income(fx, c)
            guard.check()
            if not part:
                continue
            f.update(part)
            f["is_v"] = 7
            save_json(fpath(c), f)
            n_fix += 1
        print(f"補抓損益表(營業毛利/營業費用)：{n_fix} 檔")

    # ---------- 3. 財報(輪流) ----------
    n_fund = n_nodata = 0
    failures = []
    if not a.prices_only:
        ttl_h = float(cfg.get("fund_ttl_days", 7)) * 24
        nd_h = float(cfg.get("nodata_ttl_days", 30)) * 24
        todo = []
        for c in info:
            f = facts.get(c)
            if f is None:
                todo.append((1e12, c))
            elif f.get("status") == "nodata":
                if age_hours(f.get("fund_at")) > nd_h:
                    todo.append((age_hours(f.get("fund_at")), c))
            elif a.force_fund or age_hours(f.get("fund_at")) > ttl_h:
                todo.append((age_hours(f.get("fund_at")), c))
        todo.sort(reverse=True)
        print(f"待更新財報：{len(todo)} 檔")
        for _, c in todo:
            if time.time() > deadline - 30:
                print("已達時間上限，其餘留到下次。")
                break
            r = info[c]
            is_fin = r["industry"] == "金融保險業"
            part, status = fubon.fetch_fundamentals(fx, c, is_fin)
            guard.check()
            base = {"code": c, "name": r["name"], "industry": r["industry"], "market": r["market"],
                    "listed": r["listed"], "is_fin": is_fin}
            if status == "ok":
                px = fubon.fetch_price(fx, c) or ((facts.get(c) or {}).get("px")) or {}
                f = {**base, **part, "px": px, "px_at": iso(), "fund_at": iso(), "status": "ok", "fr_v": 6, "is_v": 7}
                facts[c] = f
                save_json(fpath(c), f)
                n_fund += 1
            elif status == "nodata":
                f = {**base, "status": "nodata", "fund_at": iso()}
                facts[c] = f
                save_json(fpath(c), f)
                n_nodata += 1
            else:
                failures.append(c)
    print(f"財報更新：成功 {n_fund}、查無資料 {n_nodata}、失敗 {len(failures)} ({time.time() - t0:.0f}s)")

    # ---------- 4. 計算與輸出 ----------
    today = now().date()
    rows, n_stale = [], 0
    for c, r in info.items():
        f = facts.get(c)
        if not f or f.get("status") != "ok":
            continue
        # 清單資料(名稱/產業/上市日)以最新的證交所清單為準
        f.update({"name": r["name"], "industry": r["industry"], "market": r["market"], "listed": r["listed"],
                  "is_fin": r["industry"] == "金融保險業"})
        an = scoring.analyze(f, cfg, today)
        if age_hours(f.get("fund_at")) > 24 * 14:
            n_stale += 1
        ref = refs.get(c, {})
        an["hl"] = ref.get("hl")
        an["fund_q"] = (f.get("frQ") or {}).get("per", [None])[0]
        an["links"] = {"profile": ref.get("url") or PROFILE_URL.format(c=c),
                       "report": REPORT_URL.format(c=c, y=report_year(today))}
        an["fund_at"], an["px_at"] = f.get("fund_at"), f.get("px_at")
        save_json(os.path.join(a.out, "stocks", c + ".json"), an)
        s = scoring.summary(an)
        s["hl"] = an["hl"]
        rows.append(s)
    rows.sort(key=scoring.sort_key)

    if not a.codes and len(rows) < 100 and os.path.exists(os.path.join(a.out, "index.json")):
        raise SystemExit("可分析的股票太少(%d)，疑似來源異常；不覆蓋既有資料。" % len(rows))

    meta = {"updated_at": iso(), "n_stocks": len(rows), "n_universe": len(info), "n_stale_14d": n_stale,
            "n_price_updated": n_price, "n_fund_updated": n_fund, "n_nodata": n_nodata,
            "failures": failures[:60], "requests_ok": fx.n_ok, "requests_fail": fx.n_fail,
            "minutes": round((time.time() - t0) / 60, 1),
            "n_pick": sum(1 for s in rows if s["ok"]),
            "config": {k: cfg.get(k) for k in ("roe_min", "roe_years", "pb_max", "yield_min",
                                               "rev_growth_min", "debt_max")}}
    save_json(os.path.join(a.out, "index.json"), {"meta": meta, "stocks": rows})
    print(f"輸出完成：{len(rows)} 檔 → {a.out}")

    # 小量測試時，把結果印成表格(也寫進 GitHub 的 Job Summary)
    if a.codes:
        def r1(v):
            return "—" if v is None else round(v, 2)
        lines = ["| 代號 | 名稱 | 現價 | ROE5年最低 | PB | 殖利率 | 營收成長 | 負債比 | 通過 | 結果 |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for s in rows:
            lines.append(f"| {s['c']} | {s['n']} | {s['p']} | {r1(s['rm'])} | {r1(s['pb'])} | {r1(s['y'])} | "
                         f"{r1(s['rg'])} | {r1(s['db'])} | {s['k']}/5 | {'入選' if s['ok'] else '—'} |")
        txt = "\n".join(lines)
        print(txt)
        sm = os.environ.get("GITHUB_STEP_SUMMARY")
        if sm:
            with open(sm, "a", encoding="utf8") as fh:
                fh.write("### 測試結果\n" + txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
