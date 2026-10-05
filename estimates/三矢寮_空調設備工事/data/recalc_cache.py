# -*- coding: utf-8 -*-
"""数式セルにキャッシュ値 <v> を埋め込む簡易再計算（LibreOffice Calc が無い環境向け）。
対応: 四則, &, 比較(=,<>,<,>,<=,>=), ROUND/ROUNDUP/ROUNDDOWN/FLOOR/SUM/IF/OR/AND/TEXT, 定義名, 他シート参照, "" 文字列。
使い方: python3 recalc_cache.py book.xlsx  → 同ファイルを上書き。主要セルの値を表示。"""
import sys, re, zipfile, shutil, math, datetime
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries, get_column_letter

path = sys.argv[1]
wb = load_workbook(path)
names = {k: v.attr_text for k, v in wb.defined_names.items()}
cache = {}


def xl_round(x, n=0):
    if x == "":
        return ""
    m = 10 ** n
    return math.floor(abs(x) * m + 0.5) / m * (1 if x >= 0 else -1) if n < 0 else round(x + 0.0, n) if False else \
        (math.floor(abs(x) * m + 0.5) / m) * (1 if x >= 0 else -1)


def xl_roundup(x, n=0):
    m = 10 ** n
    return math.ceil(abs(x) * m - 1e-9) / m * (1 if x >= 0 else -1)


def xl_rounddown(x, n=0):
    m = 10 ** n
    return math.floor(abs(x) * m + 1e-9) / m * (1 if x >= 0 else -1)


def xl_floor(x, s):
    return math.floor(x / s + 1e-12) * s


def xl_text(v, fmt):
    if fmt == "#,##0":
        return f"{int(round(v)):,}"
    if fmt == "0%":
        return f"{int(round(v * 100))}%"
    return str(v)


def xl_if(c, a, b=0):
    return a if c else b


def num(v):
    return 0 if v in (None, "") else v


class Rng:
    def __init__(self, vals):
        self.vals = vals


def SUM(*args):
    t = 0
    for a in args:
        if isinstance(a, Rng):
            t += sum(v for v in a.vals if isinstance(v, (int, float)))
        elif isinstance(a, (int, float)):
            t += a
    return t


def cell_value(sheet, ref):
    ref = ref.replace("$", "")
    key = (sheet, ref)
    if key in cache:
        return cache[key]
    c = wb[sheet][ref]
    v = c.value
    if isinstance(v, str) and v.startswith("="):
        cache[key] = 0  # 循環防止
        v = evaluate(sheet, v[1:])
    elif isinstance(v, datetime.datetime):
        v = (v - datetime.datetime(1899, 12, 30)).days
    elif v is None:
        v = ""
    cache[key] = v
    return v


def rng_values(sheet, rng):
    c1, r1, c2, r2 = range_boundaries(rng.replace("$", ""))
    out = []
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            out.append(cell_value(sheet, f"{get_column_letter(c)}{r}"))
    return Rng(out)


SHEET_RE = r"(?:'([^']+)'|([A-Za-z0-9_　-鿿＀-￯（）().]+))!"


def evaluate(sheet, expr):
    e = expr
    # 定義名 → 参照
    for n, ref in names.items():
        e = re.sub(r"\b" + n + r"\b", ref, e)
    # 範囲
    def rng_repl(m):
        sh = m.group(1) or m.group(2) or sheet
        return f"__RNG__({sh!r},{m.group(3)!r})"
    e = re.sub("(?:" + SHEET_RE + ")?" + r"(\$?[A-Z]{1,3}\$?\d+:\$?[A-Z]{1,3}\$?\d+)", rng_repl, e)
    # 単一セル
    def ref_repl(m):
        sh = m.group(1) or m.group(2) or sheet
        return f"__CELL__({sh!r},{m.group(3)!r})"
    e = re.sub("(?<![:\w'$])(?:" + SHEET_RE + ")?" + r"(\$?[A-Z]{1,3}\$?\d+)(?![\w(:])", ref_repl, e)
    # 文字列リテラル "..." → '...'
    e = re.sub(r'"([^"]*)"', lambda m: repr(m.group(1)), e)
    # 比較演算子
    e = e.replace("<>", "!=")
    e = re.sub(r"(?<![<>!=])=(?!=)", "==", e)
    e = e.replace("&", "+")
    e = re.sub(r"\bROUNDUP\(", "xl_roundup(", e)
    e = re.sub(r"\bROUNDDOWN\(", "xl_rounddown(", e)
    e = re.sub(r"\bROUND\(", "xl_round(", e)
    e = re.sub(r"\bFLOOR\(", "xl_floor(", e)
    e = re.sub(r"\bIF\(", "xl_if(", e)
    e = re.sub(r"\bTEXT\(", "xl_text(", e)
    e = re.sub(r"\bOR\(", "xl_or(", e)
    e = re.sub(r"\bAND\(", "xl_and(", e)
    env = dict(__RNG__=lambda sh, r: rng_values(sh, r), __CELL__=lambda sh, r: cell_value(sh, r),
               SUM=SUM, xl_round=xl_round, xl_roundup=xl_roundup, xl_rounddown=xl_rounddown,
               xl_floor=xl_floor, xl_if=xl_if, xl_text=xl_text,
               xl_or=lambda *a: any(a), xl_and=lambda *a: all(a))

    class N:  # 数値と "" の混在演算
        pass
    try:
        return _eval_num(e, env)
    except Exception as ex:
        raise RuntimeError(f"{sheet}!{expr}: {ex}")


def _eval_num(e, env):
    # "" を 0 として扱う必要がある算術は、Python で '' が出ると TypeError になるため、
    # 文字列演算('+'連結)以外は数値変換して再評価する
    try:
        return eval(e, {"__builtins__": {}}, env)
    except TypeError:
        env2 = dict(env)
        env2["__CELL__"] = lambda sh, r: num(cell_value(sh, r))
        return eval(e, {"__builtins__": {}}, env2)


values = {}
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("="):
                values[(ws.title, c.coordinate)] = cell_value(ws.title, c.coordinate)

sheet_files = {ws.title: f"xl/worksheets/sheet{i+1}.xml" for i, ws in enumerate(wb.worksheets)}
tmp = path + ".tmp"
with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        for title, fn in sheet_files.items():
            if item.filename == fn:
                xml = data.decode("utf-8")

                def patch(m):
                    ref = m.group(1)
                    v = values.get((title, ref))
                    if v is None:
                        return m.group(0)
                    if isinstance(v, str):
                        from xml.sax.saxutils import escape
                        return f'<c r="{ref}"{m.group(2)} t="str"><f>{m.group(3)}</f><v>{escape(v)}</v></c>'
                    if isinstance(v, bool):
                        v = int(v)
                    if isinstance(v, float) and v.is_integer():
                        v = int(v)
                    return f'<c r="{ref}"{m.group(2)}><f>{m.group(3)}</f><v>{v}</v></c>'
                xml = re.sub(r'<c r="([A-Z]+\d+)"([^>]*)><f>([^<]*)</f>(?:<v\s*/>|<v></v>)?</c>', patch, xml)
                data = xml.encode("utf-8")
        zout.writestr(item, data)
shutil.move(tmp, path)
print("patched", len(values), "formula cells")
import json
out = {f"{k[0]}!{k[1]}": v for k, v in values.items()}
json.dump(out, open(path + ".values.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
