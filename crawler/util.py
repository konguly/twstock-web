"""共用小工具:文字正規化、數字轉換、四捨五入(與 Excel ROUND 相同)。"""
import math
import re

_WS = re.compile(r"\s+")


def norm(s):
    """全形/不斷行空白、換行、Tab 一律換成半形空白並壓縮。"""
    if s is None:
        return ""
    s = str(s).replace("　", " ").replace("\xa0", " ")
    return _WS.sub(" ", s).strip()


def to_num(s):
    """'10,252' -> 10252.0；'N/A'、空字串、非數字 -> None。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return None if (isinstance(s, float) and math.isnan(s)) else float(s)
    t = str(s).replace(",", "").strip()
    if not t or t.upper() == "N/A" or t == "-":
        return None
    try:
        return float(t)
    except ValueError:
        return None


def to_pct(s):
    """'7.33%' -> 7.33；沒有 % 的數字原樣回傳。"""
    if s is None:
        return None
    return to_num(str(s).replace("%", ""))


def xl_round0(x):
    """Excel ROUND(x,0)：0.5 進位(遠離 0)。"""
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def isnum(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and not math.isnan(x)
