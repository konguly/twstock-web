"""美股收盤價更新：讀網站的 us/index.json，到 Yahoo Finance 抓最新收盤價，寫回「現價」與股價日期。

用法：python -m crawler.us_prices site/us/index.json
失敗時不改檔案（網站沿用上次的股價），不影響台股更新。
"""
import json, sys, time, datetime as dt, urllib.request, urllib.parse

URL = "https://query1.finance.yahoo.com/v7/finance/spark?range=1d&interval=1d&symbols="
UA = {"User-Agent": "Mozilla/5.0 (compatible; twstock-web)"}


def fetch(symbols):
    req = urllib.request.Request(URL + urllib.parse.quote(",".join(symbols), safe=","), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main(path):
    with open(path, encoding="utf-8") as f:
        D = json.load(f)
    cols = D["cols"]; ci = {c: i for i, c in enumerate(cols)}
    rows = D["rows"]; syms = [r[0] for r in rows]
    px, last_ts = {}, 0
    for i in range(0, len(syms), 20):
        part = syms[i:i + 20]
        for k in range(3):
            try:
                j = fetch(part); break
            except Exception as e:  # 網路不穩就重試
                print("retry", part[0], e); time.sleep(3)
        else:
            continue
        res = (j.get("spark") or {}).get("result") or []
        for x in res:
            for rsp in x.get("response") or []:
                m = rsp.get("meta") or {}
                p, ts = m.get("regularMarketPrice"), m.get("regularMarketTime") or 0
                if x.get("symbol") and isinstance(p, (int, float)) and p > 0:
                    px[x["symbol"]] = round(float(p), 2); last_ts = max(last_ts, ts)
        time.sleep(0.3)
    if len(px) < len(syms) * 0.8:
        print(f"只取得 {len(px)}/{len(syms)} 檔，保留原本股價"); return 0
    pi = ci["p"]
    for r in rows:
        if r[0] in px:
            while len(r) <= pi: r.append(None)
            r[pi] = px[r[0]]
    # 美東時間的交易日
    d = dt.datetime.fromtimestamp(last_ts, dt.timezone(dt.timedelta(hours=-5))).date()
    D["meta"]["price_date"] = d.isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, separators=(",", ":"))
    print(f"美股股價更新 {len(px)}/{len(syms)} 檔，日期 {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "site/us/index.json"))
