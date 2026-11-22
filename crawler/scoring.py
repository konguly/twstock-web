"""計算邏輯：逐項對照 財報藏寶圖 v5 的公式（獲利矩陣 + 決策總覽）。

輸入  facts : fubon.fetch_fundamentals 的結果 + 股價(px) + 基本資料(code/name/industry/listed/is_fin)
輸出  analyze() 回傳 dict，供網頁顯示；summary() 回傳清單用的精簡欄位。
Excel 中的空白字串("")在這裡一律用 None 表示。
"""
import datetime as dt
import re

from .util import isnum, xl_round0

GRADE_A, GRADE_B1, GRADE_B2 = "A優等", "B1納入備取", "B2納入備取"
GRADE_C, GRADE_C1, GRADE_C2, GRADE_NEG = "C列入觀察", "C1不考慮", "C2不考慮", "ROE<=0不考慮"

DEFAULT_CFG = {
    "pe_low": 10, "pe_mid": 15, "pe_high": 18, "market_pe_adjust": 0, "risk_free_rate": 1.5,
    "buffett_indicator": None, "min_score_elite": 13,
    "thresholds": {"roe5_avg": 15, "roe_1y": 20, "op_margin": 10, "fcf5_avg": 0, "fcf_1y": 1,
                   "cfo_ni_pct": 50, "insider_hold_pct": 10, "pledge_pct_max": 10,
                   "listed_years": 5, "eps_min": 1, "roe_min": 10},
    "cyclical_industries": ["鋼鐵工業", "航運業", "塑膠工業", "水泥工業", "造紙工業", "玻璃陶瓷", "化學工業", "橡膠工業"],
}
FIN_ROE_A, FIN_ROE_B = 10, 7


# ------------------------------------------------------------------ 小工具
def _g(d, k, i):
    """d[k][i]，缺值或越界回傳 None。"""
    try:
        v = (d or {}).get(k)
        if v is None:
            return None
        return v[i] if isnum(v[i]) else None
    except (IndexError, TypeError):
        return None


def _nums(vals):
    return [v for v in vals if isnum(v)]


def _avg(vals):
    n = _nums(vals)
    return sum(n) / len(n) if n else None


def _sum4(d, k):
    """近 4 季合計；4 季不齊回傳 None。"""
    v = [_g(d, k, i) for i in range(4)]
    return sum(v) if all(isnum(x) for x in v) else None


def _div(a, b):
    return a / b if isnum(a) and isnum(b) and b != 0 else None


def grade(roe, fcf):
    if not isnum(roe) or not isnum(fcf):
        return None
    if roe >= 15:
        return GRADE_A if fcf > 0 else GRADE_B1
    if roe >= 10:
        return GRADE_B2 if fcf > 0 else GRADE_C
    if roe > 0:
        return GRADE_C1 if fcf > 0 else GRADE_C2
    return GRADE_NEG


def grade_fin(roe, bv_chg):
    if not isnum(roe) or not isnum(bv_chg):
        return None
    if roe >= FIN_ROE_A:
        return GRADE_A if bv_chg > 0 else GRADE_B1
    if roe >= FIN_ROE_B:
        return GRADE_B2 if bv_chg > 0 else GRADE_C
    if roe > 0:
        return GRADE_C1 if bv_chg > 0 else GRADE_C2
    return GRADE_NEG


def grade_pts(g):
    return 3 if g == GRADE_A else 2 if g == GRADE_B1 else 1 if g == GRADE_B2 else 0


def matrix_score(grades):
    """J 欄：近 5 欄(近4季 + 近4年)。A=3、B1=2、B2=1。"""
    return sum(grade_pts(g) for g in grades[:5])


# ------------------------------------------------------------------ 獲利矩陣
def build_matrix(f):
    """回傳 8 欄(近4季 + 7 個年度)的 {label, roe, fcf, grade}。"""
    is_fin = f.get("is_fin")
    isA, isQ, bsA, bsQ = f.get("isA"), f.get("isQ"), f.get("bsA"), f.get("bsQ")
    cfA, cfQ, frA, frQ = f.get("cfA"), f.get("cfQ"), f.get("frA"), f.get("frQ")
    cols = []
    # 近 4 季
    per_q = (isQ or {}).get("per") or []
    c = {"label": (per_q[0] + "+後3季") if per_q and per_q[0] else None, "roe": None, "fcf": None, "grade": None}
    ni4 = _sum4(isQ, "ni")
    eq0 = _g(bsQ, "eq", 0)
    if isnum(ni4) and isnum(eq0) and eq0 != 0:
        c["roe"] = ni4 / eq0 * 100
    if is_fin:
        a, b = _g(frQ, "bv", 0), _g(frQ, "bv", 4)
        if isnum(a) and isnum(b):
            c["fcf"] = a - b
    else:
        cfo4, cfi4, cap = _sum4(cfQ, "cfo"), _sum4(cfQ, "cfi"), _g(bsQ, "cap", 0)
        if isnum(cfo4) and isnum(cfi4) and isnum(cap) and cap != 0:
            c["fcf"] = (cfo4 + cfi4) / cap * 10
    c["grade"] = (grade_fin if is_fin else grade)(c["roe"], c["fcf"])
    cols.append(c)
    # 7 個年度
    per_a = (isA or {}).get("per") or []
    for j in range(7):
        p = per_a[j] if j < len(per_a) else None
        c = {"label": f"{p}年" if p else None, "roe": None, "fcf": None, "grade": None}
        if p:
            ni, e0, e1 = _g(isA, "ni", j), _g(bsA, "eq", j), _g(bsA, "eq", j + 1)
            if isnum(ni) and isnum(e0) and isnum(e1):
                avg = xl_round0((e0 + e1) / 2)
                if avg != 0:
                    c["roe"] = ni / avg * 100
            if is_fin:
                a, b = _g(frA, "bv", j), _g(frA, "bv", j + 1)
                if isnum(a) and isnum(b):
                    c["fcf"] = a - b
            else:
                op, inv, sh = _g(cfA, "cfo", j), _g(cfA, "cfi", j), _g(isA, "sh", j)
                if isnum(op) and isnum(inv) and isnum(sh) and sh != 0:
                    c["fcf"] = (op + inv) / sh
            c["grade"] = (grade_fin if is_fin else grade)(c["roe"], c["fcf"])
        cols.append(c)
    return cols


# ------------------------------------------------------------------ 決策總覽
def _status(v, std, higher=True, strict=True):
    if v is None:
        return None
    return (v > std) if higher else (v < std)


def analyze(f, cfg=None, today=None):
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    th = {**DEFAULT_CFG["thresholds"], **cfg.get("thresholds", {})}
    today = today or dt.date.today()
    is_fin = bool(f.get("is_fin"))
    px = f.get("px") or {}
    price = px.get("price") if isnum(px.get("price")) else None

    M = build_matrix(f)
    grades = [c["grade"] for c in M]
    score = matrix_score(grades)
    out = {"code": f.get("code"), "name": f.get("name"), "industry": f.get("industry"),
           "market": f.get("market"), "is_fin": is_fin, "matrix": M, "score": score,
           "price": price, "price_date": px.get("date")}
    if is_fin:
        out["matrix_note"] = "金融保險業：第二指標用「每股淨值年增」，ROE 門檻 A≥10%、B≥7%"

    isA, isQ, cfA, cfQ, frA, frQ = (f.get(k) for k in ("isA", "isQ", "cfA", "cfQ", "frA", "frQ"))
    ann_roe = [M[i]["roe"] for i in range(1, 6)]    # C15:G15
    ann_fcf = [M[i]["fcf"] for i in range(1, 6)]    # C16:G16
    ttm_roe, y1_roe = M[0]["roe"], M[1]["roe"]

    # ---- 輔助：營業利益率、營業現金/淨利、EPS、股利 ----
    rev4, op4 = _sum4(isQ, "rev"), _sum4(isQ, "opinc")
    opm_ttm = _div(op4, rev4)
    opm_ttm = opm_ttm * 100 if opm_ttm is not None else None
    opm_y1 = _div(_g(isA, "opinc", 0), _g(isA, "rev", 0))
    opm_y1 = opm_y1 * 100 if opm_y1 is not None else None
    ni4 = _sum4(isQ, "ni")
    cfo4 = _sum4(cfQ, "cfo")
    q_ttm = _div(cfo4, ni4)
    q_y1 = _div(_g(cfA, "cfo", 0), _g(isA, "ni", 0))
    eps_y = [_g(frA, "eps", i) for i in range(8)]
    eps_ttm = _sum4(frQ, "eps")
    per_fr = (frA or {}).get("per") or []
    divs = f.get("div") or {}

    def div_of(i):
        p = per_fr[i] if i < len(per_fr) else None
        return divs.get(str(p)) if p else None

    div_y = [div_of(i) for i in range(8)]                    # 現金股利(FR 年度對應)
    payout = [(_div(div_y[i], eps_y[i]) * 100 if _div(div_y[i], eps_y[i]) is not None and eps_y[i] > 0 else None)
              for i in range(8)]
    bm = f.get("bm") or {}

    # listed years
    listed_years = None
    if f.get("listed"):
        try:
            d0 = dt.date.fromisoformat(f["listed"][:10])
            listed_years = today.year - d0.year - ((today.month, today.day) < (d0.month, d0.day))
        except ValueError:
            pass

    # ---- 9 大指標 ----
    avg_roe5 = _avg(ann_roe)
    avg_fcf5 = _avg(ann_fcf)
    v_roe1 = ttm_roe if isnum(ttm_roe) else y1_roe
    v_opm = opm_ttm if opm_ttm is not None else opm_y1
    v_fcf1 = M[0]["fcf"] if isnum(M[0]["fcf"]) else M[1]["fcf"]
    qv = q_ttm if q_ttm is not None else q_y1
    v_q = qv * 100 if qv is not None else None
    hold, pledge = bm.get("hold_pct"), bm.get("pledge_pct")
    items = [
        (1, "ROE 近5年平均(%)", th["roe5_avg"], avg_roe5, True, "書：近5年平均 >15%（獲利能力）"),
        (2, "ROE 近1年(%)", th["roe_1y"], v_roe1, True, "書：避免 5 年前很高、之後下滑的公司"),
        (3, "營業利益率 近1年(%)", th["op_margin"], v_opm, True, "書：過濾出高獲利能力型"),
        (4, "每股自由現金流 近5年平均(元)", th["fcf5_avg"], avg_fcf5, True, "書：近5年平均 >0"),
        (5, "每股自由現金流 近1年(元)", th["fcf_1y"], v_fcf1, True, "書：近1年 >1 元"),
        (6, "營業現金對淨利比 近1年(%)", th["cfo_ni_pct"], v_q, True, "盈餘品質"),
        (7, "董監持股比例(%)", th["insider_hold_pct"], hold, True, "利害關係與股東一致"),
        (8, "董監持股質押比例(%)", th["pledge_pct_max"], pledge, False, "質押越低越好"),
        (9, "上市櫃年數(年)", th["listed_years"], listed_years, True, "經得起景氣循環考驗"),
    ]
    ind = []
    for n, name, std, val, higher, note in items:
        ok = None if val is None else ((val > std) if higher else (val < std))
        ind.append({"n": n, "name": name, "std": std, "val": val, "ok": ok, "higher": higher, "note": note})
    n_pass = sum(1 for i in ind if i["ok"] is True)
    fails = " ".join(str(i["n"]) for i in ind if i["ok"] is False)
    out["ind9"] = ind
    out["pass9"] = n_pass
    out["fail9"] = "無" if n_pass == 9 else fails
    out["pass9_label"] = ("全數通過" if n_pass == 9 else "差一項" if n_pass >= 8 else
                          "部分通過" if n_pass >= 6 else "多項未過")
    eps_min = min(_nums(eps_y[0:5])) if len(_nums(eps_y[0:5])) == 5 else None
    roe_min = min(_nums(ann_roe)) if len(_nums(ann_roe)) == 5 else None
    out["extra"] = [
        {"name": "近5年 EPS 最低值(元)", "std": th["eps_min"], "val": eps_min,
         "ok": None if eps_min is None else eps_min >= th["eps_min"], "note": "書 p.62：連續5年最少獲利1元"},
        {"name": "近5年 ROE 最低值(%)", "std": th["roe_min"], "val": roe_min,
         "ok": None if roe_min is None else roe_min >= th["roe_min"], "note": "書 p.64–66：ROE 最低標準 10%"},
    ]

    # ---- 5 年綜合級別 ----
    all_fcf_pos = ("資料不足" if len(_nums(ann_fcf)) < 5 else ("是" if all(v > 0 for v in _nums(ann_fcf)) else "否"))
    fcf_sum5 = sum(_nums(ann_fcf)) if len(_nums(ann_fcf)) == 5 else None
    all_div = "是" if sum(1 for i in range(0, 5) if isnum(div_y[i]) and div_y[i] > 0) == 5 else "否"
    roe_keep = ("資料不足" if not (isnum(avg_roe5) and isnum(v_roe1)) else ("是" if v_roe1 >= avg_roe5 else "否"))
    if avg_roe5 is None or all_fcf_pos == "資料不足":
        g5 = "資料不足"
    elif avg_roe5 >= 15:
        if all_fcf_pos == "是":
            g5 = "A" if roe_keep == "是" else "A-（ROE下滑）"
        else:
            g5 = "B1" if (fcf_sum5 or 0) > 0 else "C（自由現金不足）"
    elif avg_roe5 >= 10:
        g5 = "B2" if (all_fcf_pos == "是" and all_div == "是") else "C（條件不足）"
    else:
        g5 = "不合格（ROE<10%）"

    # 級別趨勢(近2期 vs 前4期)；ROE<=0 的欄位在 Excel 版是 FALSE，不算有資料
    have = sum(1 for g in grades[:6] if g and g != GRADE_NEG)
    recent = (grade_pts(grades[0]) + grade_pts(grades[1])) / 2
    prior = sum(grade_pts(g) for g in grades[2:6]) / 4
    if have < 6:
        trend, trend_note = "資料不足", ""
    else:
        diff = recent - prior
        trend = "升級中" if diff >= 0.5 else "降級中" if diff <= -0.5 else "持平"
        trend_note = f"近2期平均 {recent:.1f} 分 vs 前4期 {prior:.1f} 分（A=3、B1=2、B2=1）"

    k263 = sum(_nums(div_y[0:5])) if len(_nums(div_y[0:5])) == 5 else None
    k265 = (k263 / fcf_sum5 * 100) if (k263 is not None and fcf_sum5) else None
    c265 = (div_y[0] / M[1]["fcf"] * 100) if (isnum(div_y[0]) and isnum(M[1]["fcf"]) and M[1]["fcf"] != 0) else None
    if len(_nums(ann_fcf)) < 5:
        neg2 = "資料不足"
    else:
        a = ann_fcf
        neg2 = "是（書：剔除）" if any(a[i] <= 0 and a[i + 1] <= 0 for i in range(4)) else "否"
    out["grade5"] = {"grade": g5, "all_fcf_pos": all_fcf_pos, "fcf_sum5": fcf_sum5, "all_div": all_div,
                     "roe_keep": roe_keep, "trend": trend, "trend_note": trend_note,
                     "fcf_payout5": k265, "fcf_payout1": c265, "neg2": neg2}

    # ---- 估價 ----
    adj = cfg["market_pe_adjust"]
    pe_l, pe_m, pe_h = cfg["pe_low"] + adj, cfg["pe_mid"] + adj, cfg["pe_high"] + adj
    eps_last = _g(frA, "eps", 0)
    g_cons = _div(_g(isA, "rev", 0), _g(isA, "rev", 1))
    g_cons = (g_cons - 1) * 100 if g_cons is not None else None
    revs = f.get("rev") or []
    cumyoy = revs[0]["cum_yoy"] if revs and isnum(revs[0].get("cum_yoy")) else None
    g_trend = cumyoy
    margin_cons = _div(_g(isA, "ni", 0), _g(isA, "rev", 0))
    margin_cons = margin_cons * 100 if margin_cons is not None else None
    rev4s, ni4s = _sum4(isQ, "rev"), _sum4(isQ, "ni")
    margin_trend = _div(ni4s, rev4s)
    margin_trend = margin_trend * 100 if margin_trend is not None else None
    g_mix = _avg([g_cons, g_trend]) if (g_cons is not None and g_trend is not None) else None
    m_mix = _avg([margin_cons, margin_trend]) if (margin_cons is not None and margin_trend is not None) else None
    e_cons = eps_last * (1 + g_cons / 100) if (eps_last is not None and g_cons is not None) else None
    e_trend = None
    if eps_last is not None and g_trend is not None and margin_cons is not None and margin_trend is not None \
            and margin_cons != 0:
        e_trend = eps_last * (1 + g_trend / 100) * (margin_trend / margin_cons)
    e_mix = _avg([e_cons, e_trend]) if (e_cons is not None and e_trend is not None) else None
    eps_est = [e_cons, e_trend, e_mix]

    def bands(e):
        if e is None or e <= 0:
            return [None, None, None]
        return [e * pe_l, e * pe_m, e * pe_h]

    B = [bands(e) for e in eps_est]
    pe_now = [(price / e if (price and e and e > 0) else None) for e in eps_est]

    def zone(i):
        e = eps_est[i]
        if price is None or e is None:
            return None
        if e <= 0:
            return "虧損，不適用"
        lo, mid, hi = B[i]
        return ("低估區" if price <= lo else "合理偏低" if price <= (lo + mid) / 2 else
                "合理區" if price <= mid else "偏貴" if price <= hi else "過熱")

    zones = [zone(i) for i in range(3)]
    hist_pe = [v for v in ((f.get("px") or {}).get("pe") or {}).get("lo", []) if isnum(v) and v > 0]
    hist_pe_hi = [v for v in ((f.get("px") or {}).get("pe") or {}).get("hi", []) if isnum(v) and v > 0]
    out["valuation"] = {
        "pe": {"low": pe_l, "mid": pe_m, "high": pe_h},
        "eps_last": eps_last, "eps_ttm": eps_ttm,
        "growth": [g_cons, g_trend, g_mix], "margin": [margin_cons, margin_trend, m_mix],
        "eps_est": eps_est, "pe_now": pe_now, "bands": B, "zones": zones,
        "hist_pe_min": min(hist_pe) if hist_pe else None,
        "hist_pe_max": max(hist_pe_hi) if hist_pe_hi else None,
    }

    # ---- 高登公式（前瞻版）----
    bv0 = _g(frA, "bv", 0)
    pay_last = payout[0]
    gordon = []
    for i in range(3):
        e = eps_est[i]
        d = {"payout": pay_last}
        d["div_est"] = e * pay_last / 100 if (e is not None and pay_last is not None) else None
        d["Y"] = d["div_est"] / price * 100 if (d["div_est"] is not None and price) else None
        d["bv_est"] = bv0 - div_y[0] + e if (isnum(bv0) and isnum(div_y[0]) and e is not None) else None
        d["roe_est"] = e / ((bv0 + d["bv_est"]) / 2) * 100 if (d["bv_est"] is not None and e is not None
                                                              and (bv0 + d["bv_est"]) != 0) else None
        d["G"] = d["roe_est"] * (1 - pay_last / 100) if (d["roe_est"] is not None and pay_last is not None) else None
        d["ret"] = d["Y"] + d["G"] if (d["Y"] is not None and d["G"] is not None) else None
        d["lynch"] = d["ret"] / pe_now[i] if (d["ret"] is not None and pe_now[i]) else None
        grade_ok = not (g5.startswith("C") or g5.startswith("不合") or g5 == "資料不足")
        if d["ret"] is None:
            d["fit"] = ""
        elif not grade_ok:
            d["fit"] = "不適用（級別不足）"
        elif d["ret"] < 10:
            d["fit"] = "不適用（<10%）"
        elif d["G"] > d["Y"]:
            d["fit"] = "適用：75%~120%" if (d["ret"] >= 15 and g5.startswith("A")) else "適用：75%~100%"
        else:
            d["fit"] = "適用：50%~75%"
        if d["fit"].startswith("適用"):
            d["lo_f"] = 0.5 if d["fit"][3:6] == "50%" else 0.75
            d["hi_f"] = 1.2 if "120%" in d["fit"] else 1.0 if "100%" in d["fit"] else 0.75
        else:
            d["lo_f"] = d["hi_f"] = None
        d["gp"] = d["ret"] * e if (d["ret"] is not None and e is not None) else None
        d["hot"] = d["gp"] * 1.2 if d["gp"] is not None else None
        d["mid"] = d["gp"] * 0.75 if d["gp"] is not None else None
        d["cheap"] = d["gp"] * 0.5 if d["gp"] is not None else None
        d["range"] = ([d["gp"] * d["lo_f"], d["gp"] * d["hi_f"]]
                      if (d["lo_f"] is not None and d["gp"] is not None) else None)
        if price is None or d["gp"] is None:
            d["judge"] = ""
        elif d["lo_f"] is None:
            d["judge"] = "不適用"
        elif price <= d["cheap"]:
            d["judge"] = "低估價以下"
        elif price <= d["range"][0]:
            d["judge"] = "區間下緣以下"
        elif price <= d["range"][1]:
            d["judge"] = "在建議區間內"
        else:
            d["judge"] = "高於建議區間"
        gordon.append(d)
    out["gordon"] = gordon

    # ---- 綜合判斷 ----
    ey = (eps_ttm / price * 100) if (eps_ttm is not None and price) else None
    div_yield = px.get("yield_pct")
    up_pe = ((B[2][1] / price - 1) * 100) if (B[2][1] is not None and price) else None
    g2 = gordon[2]
    up_g = ((g2["gp"] * g2["lo_f"] / price - 1) * 100) if (g2["lo_f"] is not None and price) else None

    if neg2.startswith("是"):
        quality = "未通過"
    elif g5.startswith("A") or g5 == "B1":
        quality = "通過" if n_pass >= 8 else "未通過"
    elif g5 == "B2":
        quality = "通過" if sum(1 for i in ind[3:9] if i["ok"] is True) >= 5 else "未通過"
    else:
        quality = "未通過"
    # 營收近12月年增率(以最近一季季底月份為起點)
    rev12 = None
    per_q0 = ((isQ or {}).get("per") or [None])[0]
    m = re.match(r"(\d{4})\.(\d)Q", per_q0 or "")
    if m and revs:
        ym = f"{int(m.group(1)) - 1911:03d}/{int(m.group(2)) * 3:02d}"
        idx = next((k for k, r in enumerate(revs) if r["ym"] == ym), None)
        if idx is not None and idx + 12 <= len(revs):
            w = revs[idx:idx + 12]
            if all(isnum(r["rev"]) and isnum(r["ly"]) for r in w):
                ly = sum(r["ly"] for r in w)
                rev12 = (sum(r["rev"] for r in w) / ly - 1) * 100 if ly else None
    weak = (roe_keep == "否") + (trend == "降級中") + (1 if (rev12 is not None and rev12 < 0) else 0) \
        + (1 if (v_q is not None and v_q < 100) else 0)
    warn = []
    if n_pass < 9 and (g5.startswith("A") or g5 == "B1"):
        warn.append(f"9大指標未全過：{out['fail9']}")
    if roe_keep == "否":
        warn.append("ROE近1年低於5年平均")
    if trend == "降級中":
        warn.append("級別降級中")
    if v_q is not None and v_q < 100:
        warn.append("盈餘品質<100%")
    if rev12 is not None and rev12 < 0:
        warn.append("近12月營收衰退")
    if eps_ttm is not None and eps_ttm <= 0:
        warn.append("近4季虧損")
    if f.get("industry") in cfg["cyclical_industries"]:
        warn.append("景氣循環股：本益比需反向解讀")
    if neg2.startswith("是"):
        warn.append("連續2年自由現金為負")
    if k265 is not None and k265 < 0:
        warn.append("5年自由現金發放率為負")

    z = zones[2]
    # 資料健全性：股價/近4季EPS < 3 倍幾乎必為股票分割、減資等造成的 EPS 未還原
    anom = bool(price and eps_ttm and eps_ttm > 0 and price / eps_ttm < 3)
    if anom:
        up_pe = up_g = None
        warn.append("股價與EPS不一致(疑似股票分割/減資，EPS未還原)")
    if anom:
        sig = "資料異常：股價與EPS不一致(疑似股票分割/減資)，請人工確認"
    elif price is None or e_mix is None:
        sig = "資料不足"
    elif e_mix <= 0:
        sig = "虧損：本益比不適用，不建議"
    elif quality == "未通過":
        sig = f"品質不足（9大指標 {n_pass}/9、級別 {g5}）：不建議"
    elif z in ("過熱", "偏貴"):
        sig = f"{z}：等待回檔"
    else:
        sig = z + ("，但體質轉弱：觀察／分批" if weak > 0 else
                   "：符合買點條件" if z == "低估區" else "：可分批布局" if z == "合理偏低" else
                   "：宜保守，等待更好價格")
    if sig == "資料不足" or anom:
        cat = "na"
    elif "不建議" in sig:
        cat = "avoid"
    elif "符合買點" in sig or "可分批" in sig:
        cat = "buy"
    else:
        cat = "watch"
    out["verdict"] = {"quality": quality, "weak": weak, "warnings": warn, "signal": sig, "cat": cat,
                      "earn_yield": ey, "div_yield": div_yield, "upside_pe": up_pe, "upside_gordon": up_g,
                      "rev12": rev12, "rf": cfg["risk_free_rate"],
                      "ey_ok": (None if ey is None else ey >= 2 * cfg["risk_free_rate"]),
                      "buffett": cfg.get("buffett_indicator")}
    if is_fin:
        out["verdict"]["note"] = "金融保險業：現金流量表不適用，9大指標中的自由現金流項目與估價僅供參考。"
    return out


def summary(a):
    """清單頁用的精簡欄位(短鍵名，節省流量)。"""
    v, g5 = a["verdict"], a["grade5"]
    z = a["valuation"]["zones"][2]
    return {"c": a["code"], "n": a["name"], "i": a["industry"], "p": a["price"], "d": a["price_date"],
            "s": a["score"], "g": g5["grade"], "k": a["pass9"], "q": v["quality"], "z": z,
            "sig": v["signal"], "cat": v["cat"], "up": v["upside_pe"], "ug": v["upside_gordon"],
            "y": v["div_yield"], "f": 1 if a["is_fin"] else 0,
            "gr": [(c["grade"] or "")[:2] for c in a["matrix"][:6]]}
