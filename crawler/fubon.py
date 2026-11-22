"""富邦 eBroker DJ 財報頁面:下載、解析、抽出計算所需的數據。

解析方式與 Excel 版(財報藏寶圖 v3~v5、UpdateProfitMatrix 巨集)相同:
  * 財報類頁面只取 id="oMainTable" 的表格，每一列拼成一行文字，
    「科目名稱 + 最後 8 個數字」就是一列資料(最新期在最左邊)。
  * 基本資料(zca)、股利(zcc)、董監持股(zck)、月營收(zch)頁面沒有固定表格 id，
    改為掃描所有列，用列首文字辨認。
"""
import os
import random
import re
import time

import requests
from lxml import html as LH

from .util import norm, to_num, to_pct

BASE = os.environ.get("TWSTOCK_FUBON_BASE", "https://fubon-ebrokerdj.fbs.com.tw/z/zc/")  # 測試時可改指向本機
PATHS = {
    "isA": "zcq/zcqa/zcqa_{c}.djhtm",   # 綜合損益表(年)
    "isQ": "zcq/zcq_{c}.djhtm",         # 綜合損益表(季)
    "bsA": "zcp/zcpb/zcpb_{c}.djhtm",   # 資產負債表(年)
    "bsQ": "zcp/zcpa/zcpa_{c}.djhtm",   # 資產負債表(季)
    "cfA": "zc3/zc3a_{c}.djhtm",        # 現金流量表(年)
    "cfQ": "zc3/zc3_{c}.djhtm",         # 現金流量表(季)
    "frA": "zcr/zcra/zcra_{c}.djhtm",   # 財務比率表(年)
    "frQ": "zcr/zcr_{c}.djhtm",         # 財務比率表(季)
    "basic": "zca/zca_{c}.djhtm",       # 基本資料(股價、歷史本益比、殖利率)
    "div": "zcc/zcc_{c}.djhtm",         # 股利政策
    "bm": "zck/zck_{c}.djhtm",          # 董監事持股
    "rev": "zch/zch_{c}.djhtm",         # 月營收
}
NODATA_TEXT = "查無"


class Fetcher:
    def __init__(self, delay=0.7, retries=3, timeout=25, ua=None):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": ua or "Mozilla/5.0 (compatible; twstock-web personal research bot)",
            "Accept-Language": "zh-TW,zh;q=0.9",
        })
        self.delay, self.retries, self.timeout = delay, retries, timeout
        self._last = 0.0
        self.n_ok = 0
        self.n_fail = 0

    def _wait(self):
        gap = self.delay * (0.7 + 0.6 * random.random())
        dt = time.time() - self._last
        if dt < gap:
            time.sleep(gap - dt)
        self._last = time.time()

    @staticmethod
    def decode(raw):
        for enc in ("utf-8", "big5hkscs", "cp950"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("big5hkscs", errors="replace")

    def get_url(self, url):
        """成功回傳 HTML 文字；失敗回傳 None。"""
        for k in range(self.retries):
            self._wait()
            try:
                r = self.s.get(url, timeout=self.timeout)
                if r.status_code == 200 and len(r.content) > 200:
                    self.n_ok += 1
                    return self.decode(r.content)
                if r.status_code in (404, 410):
                    break
            except requests.RequestException:
                pass
            time.sleep(1.5 * (k + 1))
        self.n_fail += 1
        return None

    def get(self, key, code):
        return self.get_url(BASE + PATHS[key].format(c=code))


# ---------------------------------------------------------------- HTML -> 列

def _leaf_rows(tree):
    rows = []
    for tr in tree.iter("tr"):
        if tr.xpath(".//tr") or tr.xpath('.//div[contains(@class,"table-row")]'):
            continue                   # 外層列(含巢狀表格/新版 div 列)略過
        cells = [norm(td.text_content()) for td in tr.xpath("./td|./th")]
        if any(cells):
            rows.append(cells)
    # 富邦新版版面：<div class="table-row"><span class="table-cell">…</span>…</div>
    for dv in tree.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," table-row ")]'):
        cells = [norm(c.text_content()) for c in
                 dv.xpath('./*[contains(@class,"table-cell")]')]
        if any(cells):
            rows.append(cells)
    return rows


def parse_rows(html_text):
    """所有表格的所有列(每列 = 儲存格文字清單，保留空儲存格)。"""
    if not html_text:
        return []
    try:
        tree = LH.fromstring(html_text)
    except Exception:
        return []
    return _leaf_rows(tree)


def parse_main_lines(html_text):
    """oMainTable 的每一列 -> 一行正規化文字。找不到表格回傳 []。"""
    if not html_text:
        return []
    try:
        tree = LH.fromstring(html_text)
    except Exception:
        return []
    tb = tree.xpath('//*[@id="oMainTable"]')
    if not tb:
        return []
    out = []
    for cells in _leaf_rows(tb[0]):
        line = norm(" ".join(c for c in cells if c))
        if line:
            out.append(line)
    return out


def find_vals(lines, label):
    """找「科目名稱 + 8 期數字」那一列，回傳 8 個字串；找不到回傳 None。
    (與 VBA FindVals 相同：最後 8 個 token 是數值，其餘 token 去掉空白後與 label 比對)"""
    for ln in lines:
        t = ln.split(" ")
        if len(t) >= 9 and "".join(t[:-8]) == label:
            return t[-8:]
    return None


def fvals(lines, label):
    v = find_vals(lines, label)
    return None if v is None else [to_num(x) for x in v]


def period_vals(lines):
    v = find_vals(lines, "期別")
    return None if v is None else [x if x not in ("N/A", "") else None for x in v]


def has_nodata(html_text):
    return bool(html_text) and NODATA_TEXT in html_text and "oMainTable" not in html_text


# ---------------------------------------------------------------- 各頁面抽取

def x_is_annual(lines):
    return {"per": period_vals(lines), "rev": fvals(lines, "營業收入淨額"),
            "opinc": fvals(lines, "營業利益"), "ni": fvals(lines, "常續性稅後淨利"),
            "sh": fvals(lines, "加權平均股數")}


def x_is_quarter(lines):
    return {"per": period_vals(lines), "rev": fvals(lines, "營業收入淨額"),
            "opinc": fvals(lines, "營業利益"), "ni": fvals(lines, "常續性稅後淨利")}


def x_bs_annual(lines):
    return {"eq": fvals(lines, "股東權益總額")}


def x_bs_quarter(lines):
    return {"eq": fvals(lines, "股東權益總額"), "cap": fvals(lines, "普通股股本"),
            "per": period_vals(lines)}


def x_cf(lines):
    return {"cfo": fvals(lines, "來自營運之現金流量"), "cfi": fvals(lines, "投資活動之現金流量")}


def x_fr_annual(lines):
    return {"per": period_vals(lines), "eps": fvals(lines, "每股盈餘"),
            "bv": fvals(lines, "每股淨值(F)(TSE公告數)")}


def x_fr_quarter(lines):
    return {"per": period_vals(lines), "eps": fvals(lines, "每股盈餘"),
            "bv": fvals(lines, "每股淨值(F)(TSE公告數)")}


def _next_num(cells, i):
    for c in cells[i + 1:]:
        if c:
            return c
    return None


def x_basic(html_text):
    rows = parse_rows(html_text)
    out = {"price": None, "date": None, "yield_pct": None, "pe": {"years": [], "hi": [], "lo": []}}
    m = re.search(r"最近交易日\s*[:：]\s*(\d{1,2}/\d{1,2})", html_text or "")
    if m:
        out["date"] = m.group(1)
    for cells in rows:
        for i, c in enumerate(cells):
            if c == "收盤價" and out["price"] is None:
                out["price"] = to_num(_next_num(cells, i))
            elif c == "殖利率" and out["yield_pct"] is None:
                out["yield_pct"] = to_pct(_next_num(cells, i))
        first = next((c for c in cells if c), "")
        vals = [c for c in cells if c][1:]
        if first == "年度" and not out["pe"]["years"]:
            out["pe"]["years"] = [to_num(v) for v in vals]
        elif first == "最高本益比" and not out["pe"]["hi"]:
            out["pe"]["hi"] = [to_num(v) for v in vals]
        elif first == "最低本益比" and not out["pe"]["lo"]:
            out["pe"]["lo"] = [to_num(v) for v in vals]
    return out


def x_div(html_text):
    """年度現金股利(小計)：只取列首為 4 位數年度的列(不含 2025/2H 這類半年列)。
    富邦此頁 HTML 缺 <tr> 開頭標籤，用 lxml 會整頁被併成一列，所以直接掃 <td> 序列。"""
    out = {}
    if not html_text:
        return out
    toks = [norm(re.sub(r"<[^>]+>", "", t))
            for t in re.findall(r"<td[^>]*>(.*?)</td>", html_text, flags=re.S | re.I)]
    for i, t in enumerate(toks):
        if re.fullmatch(r"\d{4}", t) and i + 3 < len(toks) and t not in out:
            if to_num(toks[i + 1]) is None or to_num(toks[i + 2]) is None:
                continue
            v = to_num(toks[i + 3])
            if v is not None:
                out[t] = v
    return out


def x_bm(html_text):
    """董監(董事+監察人)持股比例%、質押比例%。職稱含「董事」或「監察人」的列合計。"""
    hold = shares = pledged = 0.0
    seen = False
    for cells in parse_rows(html_text):
        if len(cells) >= 5 and ("董事" in cells[0] or "監察人" in cells[0]):
            sh, ratio, pl = to_num(cells[2]), to_pct(cells[3]), to_num(cells[4])
            if sh is None and ratio is None:
                continue
            seen = True
            hold += ratio or 0.0
            shares += sh or 0.0
            pledged += pl or 0.0
    if not seen:
        return {"hold_pct": None, "pledge_pct": None}
    return {"hold_pct": round(hold, 4),
            "pledge_pct": (round(pledged / shares * 100, 4) if shares else None)}


def x_rev(html_text, keep=30):
    out = []
    for cells in parse_rows(html_text):
        if len(cells) >= 7 and re.fullmatch(r"\d{2,3}/\d{2}", cells[0]):
            out.append({"ym": cells[0], "rev": to_num(cells[1]), "ly": to_num(cells[3]),
                        "yoy": to_pct(cells[4]), "cum_yoy": to_pct(cells[6])})
            if len(out) >= keep:
                break
    return out


# ---------------------------------------------------------------- 一檔股票

def fetch_price(fx, code):
    """只抓基本資料頁(每天更新股價用)。失敗回傳 None。"""
    h = fx.get("basic", code)
    if h is None:
        return None
    return x_basic(h)


def fetch_fundamentals(fx, code, is_fin):
    """抓財報類 11 頁。回傳 (facts_part, status)；status: ok / nodata / fail"""
    pages = {}
    keys = ["isA", "isQ", "bsA", "bsQ", "frA", "frQ", "div", "bm", "rev"]
    if not is_fin:
        keys += ["cfA", "cfQ"]
    for k in keys:
        pages[k] = fx.get(k, code)
        if k == "isA":
            if pages[k] is None:
                return None, "fail"
            lines = parse_main_lines(pages[k])
            if not lines or find_vals(lines, "常續性稅後淨利") is None:
                return None, "nodata"
    if any(pages[k] is None for k in ("isQ", "bsA", "bsQ", "frA", "frQ")):
        return None, "fail"
    L = {k: parse_main_lines(pages[k]) for k in pages if k in
         ("isA", "isQ", "bsA", "bsQ", "cfA", "cfQ", "frA", "frQ")}
    f = {
        "isA": x_is_annual(L["isA"]), "isQ": x_is_quarter(L["isQ"]),
        "bsA": x_bs_annual(L["bsA"]), "bsQ": x_bs_quarter(L["bsQ"]),
        "frA": x_fr_annual(L["frA"]), "frQ": x_fr_quarter(L["frQ"]),
        "div": x_div(pages["div"]) if pages.get("div") else {},
        "bm": x_bm(pages["bm"]) if pages.get("bm") else {"hold_pct": None, "pledge_pct": None},
        "rev": x_rev(pages["rev"]) if pages.get("rev") else [],
    }
    if not is_fin:
        if pages.get("cfA") is None or pages.get("cfQ") is None:
            return None, "fail"
        f["cfA"], f["cfQ"] = x_cf(L["cfA"]), x_cf(L["cfQ"])
    return f, "ok"
