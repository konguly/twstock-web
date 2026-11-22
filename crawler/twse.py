"""證交所 ISIN 公告：取得「股票」清單(代號、名稱、上市日、市場別、產業別)。
上市 strMode=2、上櫃 strMode=4；只取 CFICode 以 ESV 開頭(普通股)的列，排除 ETF、特別股、受益憑證等。"""
import re

from lxml import html as LH

from .fubon import Fetcher
from .util import norm

URL_ISIN = "https://isin.twse.com.tw/isin/C_public.jsp?strMode={m}"


def parse_isin(html_text):
    out = []
    if not html_text:
        return out
    tree = LH.fromstring(html_text)
    for tr in tree.iter("tr"):
        tds = [norm(td.text_content()) for td in tr.xpath("./td")]
        if len(tds) >= 6 and tds[5].startswith("ESV"):
            first = tds[0]
            m = re.match(r"^(\S+?)[\s　]+(.+)$", first)
            if not m:
                continue
            code, name = m.group(1).strip(), m.group(2).strip()
            listed = tds[2].replace("/", "-")[:10] if tds[2] else None
            out.append({"code": code, "name": name, "listed": listed, "market": tds[3], "industry": tds[4]})
    return out


def fetch_universe(fx: Fetcher):
    """回傳 (list, error)。只保留 4 碼數字且不以 0 開頭的普通股代號。"""
    allrows, seen = [], set()
    for m in (2, 4):
        h = fx.get_url(URL_ISIN.format(m=m))
        rows = parse_isin(h)
        if not rows:
            return None, f"無法取得或解析證交所清單(strMode={m})"
        for r in rows:
            if r["code"] in seen:
                continue
            seen.add(r["code"])
            allrows.append(r)
    allrows = [r for r in allrows if re.fullmatch(r"[1-9]\d{3}", r["code"])]
    if len(allrows) < 1000:
        return None, f"股票筆數異常({len(allrows)})"
    allrows.sort(key=lambda r: r["code"])
    return allrows, None
