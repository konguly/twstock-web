"""選股計算(V6 新版)：五條件基本面篩選。

依 2015~2025 年(11 年)上市櫃回測得到的條件，每次財報更新後重新篩選：
  1. 近 5 年 ROE(稅後)每年都 >= 5%
  2. 股價淨值比 PB(現價 / 最新一季每股淨值) <= 1.5
  3. 現金殖利率 >= 4%
  4. 近四季營收 對 前四季營收 沒有衰退(成長率 >= 0%)
  5. 負債比率(最新一季) <= 50%
五項全部通過才列入選股名單。金融保險業不適用(負債結構不同，回測也排除)。
"""
import datetime as dt

DEFAULT_CFG = {
    "roe_min": 5.0,          # 近 5 年 ROE 每年最低標準(%)
    "roe_years": 5,
    "pb_max": 1.5,           # 股價淨值比上限(倍)
    "yield_min": 4.0,        # 現金殖利率下限(%)
    "rev_growth_min": 0.0,   # 近四季營收年增率下限(%)
    "debt_max": 50.0,        # 負債比率上限(%)
    "fund_ttl_days": 7,
    "nodata_ttl_days": 30,
    "request_delay_sec": 0.7,
}

CHECKS = [
    ("roe", "近5年ROE每年都夠", "近 5 年 ROE 最低值"),
    ("pb", "股價便宜", "股價淨值比 PB"),
    ("yld", "有穩定發錢", "現金殖利率"),
    ("rev", "營收沒有衰退", "近四季營收年增率"),
    ("debt", "負債不高", "負債比率"),
]


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else None


def _get(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def merged_cfg(cfg=None):
    c = dict(DEFAULT_CFG)
    for k, v in (cfg or {}).items():
        if k in DEFAULT_CFG and _num(v) is not None:
            c[k] = float(v)
    return c


def latest_yield(f, price, today):
    """現金殖利率(%)：優先用富邦基本資料頁的殖利率；沒有時用最近一個完整年度的現金股利 / 現價。"""
    y = _num(_get(f, "px", "yield_pct"))
    if y is not None:
        return y, "富邦基本資料頁"
    div = f.get("div") or {}
    if price and div:
        for yy in sorted((int(k) for k in div if str(k).isdigit()), reverse=True):
            v = _num(div.get(str(yy)))
            if v is not None and yy <= today.year:
                return v / price * 100, f"{yy} 年現金股利 ÷ 現價"
    return None, None


def analyze(f, cfg=None, today=None):
    cfg = merged_cfg(cfg)
    today = today or dt.date.today()
    px = f.get("px") or {}
    price = _num(px.get("price"))
    out = {
        "code": f.get("code"), "name": f.get("name"), "industry": f.get("industry"),
        "market": f.get("market"), "listed": f.get("listed"), "is_fin": bool(f.get("is_fin")),
        "price": price, "price_date": px.get("date"),
        "cfg": {k: cfg[k] for k in ("roe_min", "roe_years", "pb_max", "yield_min", "rev_growth_min", "debt_max")},
    }

    # 1. 近 5 年 ROE
    per_a = _get(f, "frA", "per") or []
    roe_a = _get(f, "frA", "roe") or []
    n = int(cfg["roe_years"])
    m = min(8, max(len(per_a), len(roe_a)))
    roe_hist = [{"y": per_a[i] if i < len(per_a) else None, "v": _num(roe_a[i]) if i < len(roe_a) else None}
                for i in range(m)]
    last_n = [r["v"] for r in roe_hist[:n]]
    roe_min = min(last_n) if len(last_n) == n and all(v is not None for v in last_n) else None
    out["roe_hist"] = roe_hist

    # 2. PB
    per_q = _get(f, "frQ", "per") or []
    bv = _num((_get(f, "frQ", "bv") or [None])[0])
    pb = price / bv if (price and bv and bv > 0) else None
    out.update({"bv": bv, "bv_per": per_q[0] if per_q else None, "pb": pb})

    # 3. 殖利率
    yld, ysrc = latest_yield(f, price, today)
    out.update({"yld": yld, "yld_src": ysrc})

    # 4. 近四季營收成長
    rq = _get(f, "isQ", "rev") or []
    per_iq = _get(f, "isQ", "per") or []
    rg = None
    if len(rq) >= 8 and all(_num(v) is not None for v in rq[:8]):
        a, b = sum(rq[:4]), sum(rq[4:8])
        rg = (a / b - 1) * 100 if b > 0 else None
        out["rev4"], out["rev4_prev"] = a, b
    out.update({"rev_g": rg, "rev_q": per_iq[:8], "rev_vals": rq[:8]})

    # 5. 負債比率(最新一季；沒有季資料用年度)
    debt = _num((_get(f, "frQ", "debt") or [None])[0])
    debt_per = per_q[0] if per_q else None
    if debt is None:
        debt = _num((_get(f, "frA", "debt") or [None])[0])
        debt_per = per_a[0] if per_a else None
    out.update({"debt": debt, "debt_per": debt_per})

    vals = {"roe": roe_min, "pb": pb, "yld": yld, "rev": rg, "debt": debt}
    std = {"roe": ("≥", cfg["roe_min"], "%"), "pb": ("≤", cfg["pb_max"], "倍"), "yld": ("≥", cfg["yield_min"], "%"),
           "rev": ("≥", cfg["rev_growth_min"], "%"), "debt": ("≤", cfg["debt_max"], "%")}
    checks = []
    for key, title, label in CHECKS:
        v = vals[key]
        op, th, unit = std[key]
        ok = None if v is None else (v >= th if op == "≥" else v <= th)
        if key == "pb" and pb is None and bv is not None and bv <= 0:
            ok = False          # 淨值為負：直接不通過
        checks.append({"key": key, "t": title, "label": label, "v": v, "op": op, "th": th, "u": unit, "ok": ok})
    out["checks"] = checks
    out["growth"] = growth(f)
    n_pass = sum(1 for c in checks if c["ok"] is True)
    out["n_pass"] = n_pass

    if out["is_fin"]:
        out["ok"], out["verdict"] = None, "金融保險業不適用本選股法"
    elif price is None:
        out["ok"], out["verdict"] = None, "沒有股價資料"
    elif n_pass == 5:
        out["ok"], out["verdict"] = True, "五項全部通過：列入選股名單"
    else:
        fails = [c["t"] for c in checks if c["ok"] is False]
        nas = [c["t"] for c in checks if c["ok"] is None]
        msg = ("未通過：" + "、".join(fails)) if fails else ""
        if nas:
            msg += ("；" if msg else "") + "資料不足：" + "、".join(nas)
        out["ok"], out["verdict"] = False, msg
    return out


def growth(f, years=7):
    """成長力道圖：近 7 個年度 + 今年已公布各季累計的 營業毛利、營業費用、營業利益(百萬元)與三個比率(%)。"""
    ia, iq = f.get("isA") or {}, f.get("isQ") or {}
    out = {"labels": [], "gp": [], "opex": [], "opinc": [], "gm": [], "exr": [], "om": []}

    def add(label, rev, gp, opex, opinc):
        if rev is None or rev <= 0 or (gp is None and opinc is None):
            return
        pct = lambda v: round(v / rev * 100, 2) if v is not None else None
        out["labels"].append(label)
        for k, v in (("gp", gp), ("opex", opex), ("opinc", opinc)):
            out[k].append(v)
        out["gm"].append(pct(gp))
        out["exr"].append(pct(opex))
        out["om"].append(pct(opinc))

    per = ia.get("per") or []
    col = lambda d, k, i: _num((d.get(k) or [None] * 99)[i]) if i < len(d.get(k) or []) else None
    for i in reversed(range(min(years, len(per)))):
        add(f"{per[i]}年", col(ia, "rev", i), col(ia, "gp", i), col(ia, "opex", i), col(ia, "opinc", i))
    # 今年(最新一季所屬年度)若尚未有年報：加上「前 N 季」累計
    qper = iq.get("per") or []
    if qper and "." in str(qper[0]):
        y = str(qper[0]).split(".")[0]
        if not per or str(per[0]) < y:
            idx = [i for i, p in enumerate(qper) if str(p).startswith(y + ".")]
            sums = {}
            for k in ("rev", "gp", "opex", "opinc"):
                vals = [col(iq, k, i) for i in idx]
                sums[k] = sum(vals) if vals and all(v is not None for v in vals) else None
            add(f"{y}前{len(idx)}季", sums["rev"], sums["gp"], sums["opex"], sums["opinc"])
    return out if out["labels"] else None


def summary(an):
    """index.json 每檔的精簡資料。f = 五項結果字串(1 通過 / 0 未過 / - 資料不足)。"""
    flags = "".join("1" if c["ok"] is True else "0" if c["ok"] is False else "-" for c in an["checks"])
    return {
        "c": an["code"], "n": an["name"], "i": an["industry"], "m": an["market"],
        "p": an["price"], "d": an["price_date"],
        "rm": an["checks"][0]["v"], "pb": an["pb"], "y": an["yld"], "rg": an["rev_g"], "db": an["debt"],
        "k": an["n_pass"], "f": flags, "ok": an["ok"], "fin": an["is_fin"],
    }


def sort_key(s):
    """選股名單在前，再依殖利率高到低。"""
    return (0 if s["ok"] else 1, -s["k"], -(s["y"] if s["y"] is not None else -1))
