#!/usr/bin/env python3
"""
build_estimate_xlsx.py — 明細JSON（extract_estimate_pdf.py の出力）を自社見積テンプレート
「表紙(工事)」に流し込み、レイアウトを崩さずに自社見積 Excel を作る。

使い方（例）:
    python3 build_estimate_xlsx.py --template 見積書.xlsx --lines lines.json --out 見積書_完成.xlsx \
        --customer "有限会社 原田製麵" --title "原田製麵　エアコン更新工事" --site "広島市中区江波栄町1-16" \
        --no 6330554 --date 2026-09-15 \
        --margin-pct 0 --markup-pct 100 --round-unit 1 --round-mode round

単価の決め方（3方式。いずれも表紙の設定セル N9:N11 に入り、数式で反映される）
    そのまま           : --margin-pct 0   --markup-pct 100
    粗利率 X% を確保   : --margin-pct X   （売価 = 原価 ÷ (1 − X/100)）
    掛率 Y% を掛ける   : --markup-pct Y   （売価 = 原価 × Y/100。115 なら 15% 上乗せ）
    端数処理           : --round-unit 10 / 100 / 1000（売単価をその単位で処理。1 = 処理なし）
                         --round-mode round(四捨五入) | up(切上げ) | down(切捨て)
    数式は  売価 = 端数処理( 原価 × 掛率 ÷ (100 − 粗利率) ÷ 単位 ) × 単位

レイアウト:
    明細が 16 行以内 → 表紙の明細欄に直接記入（テンプレートと同じ使い方）
    それ以上         → 表紙は区分ごとの集計行、明細は新設する「内訳(工事)」シートに全行記入
    （--layout cover|detail で強制可）

仕組み:
    xlsx を ZIP として開き、シートXMLのセルだけを書き換える。図形（社名テキストボックス・印影・OLE）、
    列幅・行高・罫線・印刷設定・フッターはテンプレートのまま。openpyxl 等は使わない（図形が消えるため）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Optional
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

COLS = [chr(ord("A") + i) for i in range(20)]  # A..T

# ------------------------------------------------------------------ テンプレート「表紙(工事)」の配置
COVER_SHEET = "表紙(工事)"
CELL_CUSTOMER, CELL_HONORIFIC, CELL_NO, CELL_DATE, CELL_AMOUNT = "A5", "G5", "K3", "J4", "B7"
CELL_TITLE, CELL_SITE, CELL_PERIOD, CELL_TERMS, CELL_VALIDITY = "D12", "D14", "D15", "D16", "D17"
HEADER_ROW = 19          # 項目 / 内容 / 数量 / 単位 / 単価 / 金額 / 備考
FIRST_ROW, LAST_FREE_ROW = 20, 38   # 明細欄（39〜40 は注記、41〜43 は空行、43 が枠の最下段）
NOTE_ROWS = (39, 43)
COVER_CAPACITY = 16      # 表紙に直接書ける明細行数（タイトル行・合計行を除く）
# 印刷範囲外（M〜T 列）の設定セル
SET_ROW_MARGIN, SET_ROW_MARKUP, SET_ROW_UNIT = 9, 10, 11
SET_COL_LABEL, SET_COL_VALUE = "M", "N"
INTERNAL_HEADERS = {"M": "粗利率(%)", "N": "数量", "O": "原価単価", "P": "掛率(%)", "Q": "粗利額", "R": "原価金額", "S": "備考"}
# 行の「型」→ テンプレートのどの行の書式を使うか
ARCHETYPE_ROW = {"title": 20, "section": 21, "item": 22, "total": 28, "blank": 41, "last": 43,
                 "header": 19, "spacer": 18}
ITEM_STYLE_OVERRIDE = {"B": 46, "C": 46, "D": 46, "E": 46, "F": 47, "L": 87, "P": 79}  # B〜F: 折返し無し / P: 整数表示
ROW_HEIGHT = {"title": 22.5, "section": 22.5, "item": 22.5, "total": 25.5, "blank": 22.5, "last": 22.5,
              "header": 22.5, "spacer": 12.6}
DETAIL_SHEET_DEFAULT = "内訳(工事)"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

NUM_PREFIX_RE = re.compile(r"^[\s　]*(?:\d{1,3}|[①-⑳]|[一二三四五六七八九十]{1,3}|[A-Za-z])[\s　]*[）)\.．、:：][\s　]*")
LABEL_PREFIX_RE = re.compile(r"^([^\s　（）()：:]{1,4})）")  # 「機器）…」→「機器：…」


# ------------------------------------------------------------------ 小道具


def esc(s: str) -> str:
    return escape(str(s))


def fmt_num(v) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if float(v).is_integer():
        return str(int(v))
    return f"{float(v):.15g}"


def excel_serial(d: dt.date) -> int:
    return (d - dt.date(1899, 12, 30)).days


def cell_xml(ref: str, s: int, spec) -> str:
    """spec: None | ("n", 数値) | ("s", 文字列) | ("f", 数式, キャッシュ数値) | ("fs", 数式, キャッシュ文字列)"""
    if spec is None or (spec[0] == "s" and spec[1] == ""):
        return f'<c r="{ref}" s="{s}"/>'
    k = spec[0]
    if k == "n":
        return f'<c r="{ref}" s="{s}"><v>{fmt_num(spec[1])}</v></c>'
    if k == "s":
        return f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{esc(spec[1])}</t></is></c>'
    if k == "f":
        return f'<c r="{ref}" s="{s}"><f>{esc(spec[1])}</f><v>{fmt_num(spec[2])}</v></c>'
    if k == "fs":
        return f'<c r="{ref}" s="{s}" t="str"><f>{esc(spec[1])}</f><v>{esc(spec[2])}</v></c>'
    raise ValueError(spec)


ROW_RE = r'<row r="{r}"(?:\s[^>]*?)?(?:/>|>.*?</row>)'
CELL_RE = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S)


class SheetXml:
    """シートXMLを文字列のまま扱う最小限のヘルパー（他の要素には触らない）"""

    def __init__(self, xml: str):
        self.xml = xml

    def _row(self, r: int):
        m = re.search(ROW_RE.format(r=r), self.xml, re.S)
        if not m:
            raise KeyError(f"row {r} がテンプレートにありません")
        return m

    def row_tag(self, r: int) -> str:
        m = self._row(r)
        return re.match(r"<row\b[^>]*?/?>", m.group(0)).group(0)

    def styles_of_row(self, r: int) -> dict[str, int]:
        m = self._row(r)
        out = {}
        for col, _, attrs, _ in CELL_RE.findall(m.group(0)):
            sm = re.search(r'\bs="(\d+)"', attrs)
            out[col] = int(sm.group(1)) if sm else 0
        return out

    def cell_style(self, ref: str) -> int:
        col, r = re.match(r"([A-Z]+)(\d+)", ref).groups()
        return self.styles_of_row(int(r)).get(col, 0)

    def replace_row(self, r: int, new_xml: str) -> None:
        m = self._row(r)
        self.xml = self.xml[: m.start()] + new_xml + self.xml[m.end():]

    def set_cell(self, ref: str, spec, style: Optional[int] = None) -> None:
        col, rs = re.match(r"([A-Z]+)(\d+)", ref).groups()
        r = int(rs)
        m = self._row(r)
        row = m.group(0)
        cm = re.search(r'<c r="%s%d"([^>]*?)(?:/>|>.*?</c>)' % (col, r), row, re.S)
        if cm:
            sm = re.search(r'\bs="(\d+)"', cm.group(1))
            s = style if style is not None else (int(sm.group(1)) if sm else 0)
            new_row = row[: cm.start()] + cell_xml(ref, s, spec) + row[cm.end():]
        else:
            s = style if style is not None else 0
            new_cell = cell_xml(ref, s, spec)
            # 列順を保って挿入
            cells = list(CELL_RE.finditer(row))
            pos = None
            for c in cells:
                if COLS.index(c.group(1)) > COLS.index(col):
                    pos = c.start()
                    break
            if pos is None:
                if row.endswith("/>"):
                    new_row = row[:-2] + ">" + new_cell + "</row>"
                else:
                    pos = row.rfind("</row>")
                    new_row = row[:pos] + new_cell + row[pos:]
            else:
                new_row = row[:pos] + new_cell + row[pos:]
        self.xml = self.xml[: m.start()] + new_row + self.xml[m.end():]


def make_row(r: int, styles: dict[str, int], values: dict, ht: float, tag: Optional[str] = None) -> str:
    """A〜T の全セルを持つ行XML。tag を渡すとその行タグ（属性）を使い ht だけ差し替える"""
    if tag is None:
        tag = f'<row r="{r}" spans="1:20" ht="{fmt_num(ht)}" customHeight="1">'
    else:
        tag = re.sub(r'\br="\d+"', f'r="{r}"', tag)
        tag = re.sub(r'\bht="[^"]*"', f'ht="{fmt_num(ht)}"', tag)
        if 'ht="' not in tag:
            tag = tag[:-1] + f' ht="{fmt_num(ht)}" customHeight="1">'
        if tag.endswith("/>"):
            tag = tag[:-2] + ">"
    cells = "".join(cell_xml(f"{c}{r}", styles.get(c, 0), values.get(c)) for c in COLS)
    return tag + cells + "</row>"


# ------------------------------------------------------------------ 単価計算


ROUNDING = {"round": ROUND_HALF_UP, "up": ROUND_UP, "down": ROUND_DOWN}
EXCEL_ROUND = {"round": "ROUND", "up": "ROUNDUP", "down": "ROUNDDOWN"}


@dataclass
class Pricing:
    margin_pct: float = 0.0    # 粗利率 %（0 = なし）      売価 = 原価 ÷ (1 − 粗利率/100)
    markup_pct: float = 100.0  # 掛率 %（100 = なし、115 = ×1.15）
    unit: int = 1              # 端数処理単位（円）
    mode: str = "round"

    def sell(self, cost) -> int | float:
        # 数式と同じ順序 原価×掛率÷(100−粗利率)÷単位 で計算する（.5 の端数が二進誤差で崩れないよう整数を優先）
        x = Decimal(str(cost)) * Decimal(str(self.markup_pct)) / (Decimal(100) - Decimal(str(self.margin_pct)))
        u = Decimal(self.unit)
        q = (x / u).quantize(Decimal("1"), rounding=ROUNDING[self.mode]) * u
        return int(q) if q == q.to_integral_value() else float(q)

    def formula(self, cost_ref: str, m_ref: str, p_ref: str, unit_ref: str) -> str:
        fn = EXCEL_ROUND[self.mode]
        return f"{fn}({cost_ref}*{p_ref}/(100-{m_ref})/{unit_ref},0)*{unit_ref}"


# ------------------------------------------------------------------ 明細の整形


@dataclass
class Line:
    kind: str                      # title / section / item
    text: str = ""                 # title / section の表示文字列（括弧付き）
    name: str = ""                 # item の名称（先頭の番号は除去、字下げは維持）
    qty: Optional[float] = None
    unit: str = ""
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    remarks: str = ""
    group_start: bool = False
    group_name: str = ""


def normalize_indent(name: str) -> str:
    """元見積の字下げ（全角スペース）を 0 / 1 / 2 個に丸める（階層は残しつつ見た目を整える）"""
    lead = re.match(r"^[\s　]*", name).group(0)
    body = name[len(lead):]
    n = lead.count("　") + lead.count(" ") // 2
    return "　" * (0 if n == 0 else 1 if n == 1 else 2) + body


def clean_item_name(name: str, keep_numbering: bool) -> str:
    name = name.rstrip(" 　")
    if keep_numbering:
        return normalize_indent(name)
    return NUM_PREFIX_RE.sub("", name, count=1) if NUM_PREFIX_RE.match(name) else normalize_indent(name)


def clean_header(text: str) -> str:
    t = text.strip(" 　")
    t = NUM_PREFIX_RE.sub("", t, count=1)
    t = LABEL_PREFIX_RE.sub(r"\1：", t)
    if t.startswith(("［", "[", "【", "〔")):
        return t
    return f"［{t}］"


def make_lines(data: dict, keep_numbering: bool) -> tuple[Optional[str], list[Line]]:
    """JSON の lines → 表示用 Line。タイトル文字列と、区分（group）の切れ目を決める"""
    title: Optional[str] = None
    out: list[Line] = []
    for raw in data["lines"]:
        k = raw["kind"]
        if k == "note":
            continue
        if k == "title":
            if title is None:
                title = raw["text"].strip(" 　")
            else:
                out.append(Line("section", text=clean_header(raw["text"]), group_start=True,
                                group_name=clean_header(raw["text"]).strip("［］")))
            continue
        if k == "header":
            h = clean_header(raw["text"])
            out.append(Line("section", text=h, group_start=True, group_name=h.strip("［］")))
            continue
        name = raw.get("name") or raw.get("spec") or ""
        cleaned = clean_item_name(name, keep_numbering)
        amt = raw.get("amount")
        starts = bool(NUM_PREFIX_RE.match(name)) or (amt is not None and amt < 0) or ("値引" in name) or not out
        spec = raw.get("spec") or ""
        if raw.get("name") and spec:
            cleaned = f"{cleaned}　{spec.strip()}"
        out.append(Line("item", name=cleaned, qty=raw.get("qty"), unit=raw.get("unit") or "",
                        unit_price=raw.get("unit_price"), amount=amt, remarks=raw.get("remarks") or "",
                        group_start=starts, group_name=cleaned.strip(" 　")))
    return title, out


@dataclass
class Group:
    name: str
    first: int  # Line index
    last: int


def make_groups(lines: list[Line]) -> list[Group]:
    groups: list[Group] = []
    for i, ln in enumerate(lines):
        if ln.group_start or not groups:
            groups.append(Group(ln.group_name or ln.name.strip(" 　") or ln.text, i, i))
        else:
            groups[-1].last = i
    return groups


# ------------------------------------------------------------------ 行の生成（表紙・内訳 共通）


@dataclass
class Ctx:
    pricing: Pricing
    set_prefix: str            # 設定セル参照の接頭辞: "" (同一シート) or "'表紙(工事)'!"
    styles: dict[str, dict[str, int]]  # archetype → {col: style}
    tags: dict[str, str]        # archetype → 表紙の行タグ（表紙の再生成時のみ使用）
    detail_numbering: bool = False   # True: 1,2,3（数値） / False: ①②③

    @property
    def unit_ref(self) -> str:
        return f"{self.set_prefix}${SET_COL_VALUE}${SET_ROW_UNIT}"


def item_row_values(ctx: Ctx, r: int, ln: Line, seq: int) -> tuple[dict, dict]:
    """明細行のセル値。戻り値: (values, computed{'sell','cost'})"""
    p = ctx.pricing
    qty = ln.qty
    cost_amt = ln.amount if ln.amount is not None else (qty or 0) * (ln.unit_price or 0)
    by_unit = ln.unit_price is not None and qty not in (None, 0)
    m_ref, p_ref = f"M{r}", f"P{r}"
    v: dict = {}
    v["A"] = ("n", seq) if ctx.detail_numbering else ("s", CIRCLED[seq - 1] if seq <= len(CIRCLED) else str(seq))
    v["B"] = ("s", ln.name)
    v["G"] = ("n", qty) if qty is not None else None
    v["H"] = ("s", ln.unit)
    v["M"] = ("f", f"{ctx.set_prefix}${SET_COL_VALUE}${SET_ROW_MARGIN}", p.margin_pct)
    v["N"] = ("f", f"G{r}", qty) if qty is not None else None
    v["P"] = ("f", f"{ctx.set_prefix}${SET_COL_VALUE}${SET_ROW_MARKUP}", p.markup_pct)
    v["R"] = ("n", cost_amt)
    v["S"] = ("s", ln.remarks) if ln.remarks else None
    if by_unit:
        sell_unit = p.sell(ln.unit_price)
        sell_amt = sell_unit * qty
        sell_amt = int(sell_amt) if float(sell_amt).is_integer() else sell_amt
        v["O"] = ("n", ln.unit_price)
        v["I"] = ("f", p.formula(f"O{r}", m_ref, p_ref, ctx.unit_ref), sell_unit)
        v["K"] = ("f", f"G{r}*I{r}", sell_amt)
    else:
        sell_amt = p.sell(cost_amt)
        if qty not in (None, 0) and float(cost_amt / qty).is_integer():
            v["O"] = ("n", int(cost_amt / qty))
        v["K"] = ("f", p.formula(f"R{r}", m_ref, p_ref, ctx.unit_ref), sell_amt)
    v["Q"] = ("f", f"K{r}-R{r}", sell_amt - cost_amt)
    return v, {"sell": sell_amt, "cost": cost_amt}


def total_row_values(r: int, first: int, last: int, sell: float, cost: float, label: str = "　合　　計",
                     sheet_prefix: str = "") -> dict:
    v = {"B": ("s", label),
         "K": ("f", f"SUM({sheet_prefix}K{first}:K{last})", sell),
         "R": ("f", f"SUM({sheet_prefix}R{first}:R{last})", cost),
         "Q": ("f", f"K{r}-R{r}", sell - cost),
         "M": ("f", f"IF(K{r}=0,0,(K{r}-R{r})/K{r}*100)", 0 if not sell else (sell - cost) / sell * 100)}
    return v


def render_lines_rows(ctx: Ctx, lines: list[Line], start_row: int, seq_start: int = 1):
    """lines を start_row から並べる。戻り値: (rows[(r, archetype, values)], line_row{index: r}, totals)"""
    rows = []
    line_row: dict[int, int] = {}
    seq = seq_start
    sell_total = cost_total = 0
    r = start_row
    for i, ln in enumerate(lines):
        if ln.kind == "section":
            rows.append((r, "section", {"B": ("s", ln.text)}))
        elif ln.kind == "title":
            rows.append((r, "title", {"B": ("s", ln.text)}))
        else:
            v, c = item_row_values(ctx, r, ln, seq)
            seq += 1
            sell_total += c["sell"]
            cost_total += c["cost"]
            rows.append((r, "item", v))
        line_row[i] = r
        r += 1
    return rows, line_row, {"sell": sell_total, "cost": cost_total}


# ------------------------------------------------------------------ 表紙


def apply_header_info(sh: SheetXml, a: argparse.Namespace) -> None:
    if a.customer:
        sh.set_cell(CELL_CUSTOMER, ("s", a.customer))
    if a.no:
        sh.set_cell(CELL_NO, ("n", int(a.no)) if str(a.no).isdigit() else ("s", str(a.no)))
    if a.date:
        d = dt.date.fromisoformat(a.date)
        sh.set_cell(CELL_DATE, ("n", excel_serial(d)))
    if a.title:
        sh.set_cell(CELL_TITLE, ("s", a.title))
    if a.site:
        sh.set_cell(CELL_SITE, ("s", a.site))
    if a.period:
        sh.set_cell(CELL_PERIOD, ("s", a.period))
    if a.terms:
        sh.set_cell(CELL_TERMS, ("s", a.terms))
    if a.validity:
        sh.set_cell(CELL_VALIDITY, ("s", a.validity))


def apply_settings_block(sh: SheetXml, p: Pricing, styles_input: dict[str, int]) -> None:
    """表紙の印刷範囲外（M6:T18 の枠内）に単価設定セルを置く"""
    label_style = sh.cell_style("M7")  # 左罫線付き HGSｺﾞｼｯｸM 10
    rows = {
        8: ("【単価設定】※印刷されません", None, None),
        SET_ROW_MARGIN: ("粗利率(%)", ("n", p.margin_pct), styles_input["int"]),
        SET_ROW_MARKUP: ("掛率(%)", ("n", p.markup_pct), styles_input["int"]),
        SET_ROW_UNIT: ("端数処理(円)", ("n", p.unit), styles_input["num"]),
        12: ("例) 粗利率 20 → 原価÷0.8 ／ 掛率 115 → 原価×1.15（両方入れると掛け合わせ）", None, None),
        13: ("端数処理: 売単価をこの単位で" + {"round": "四捨五入", "up": "切上げ", "down": "切捨て"}[p.mode] + "（1 = 処理なし）", None, None),
        14: ("行ごとに変えたい場合は各明細行の M列(粗利率)・P列(掛率) を直接入力", None, None),
        15: ("そのままの金額にする場合: 粗利率 0 ／ 掛率 100 ／ 端数 1", None, None),
    }
    for r, (label, val, st) in rows.items():
        sh.set_cell(f"{SET_COL_LABEL}{r}", ("s", label), style=label_style)
        if val is not None:
            sh.set_cell(f"{SET_COL_VALUE}{r}", val, style=st)


def build_cover(sh: SheetXml, ctx: Ctx, title_text: str, body_rows, total_row_vals: dict, total_row: int,
                ref_rows: bool, cost_total: float) -> None:
    """表紙 20〜38 行を作り直す。body_rows: [(r, archetype, values)]"""
    st, tags = ctx.styles, ctx.tags
    new_rows: dict[int, str] = {}
    new_rows[FIRST_ROW] = make_row(FIRST_ROW, st["title"], {"B": ("s", title_text)}, ROW_HEIGHT["title"], tags["title"])
    for r, arch, vals in body_rows:
        new_rows[r] = make_row(r, st[arch], vals, ROW_HEIGHT[arch], tags[arch])
    new_rows[total_row] = make_row(total_row, st["total"], total_row_vals, ROW_HEIGHT["total"], tags["total"])
    # 合計の下: 空行（余白があれば粗利の参考値を R/S 列に）
    refs = [(0.9, "粗利10％"), (0.85, "粗利15％"), (0.8, "粗利20％"), (0.75, "粗利25％")]
    r = total_row + 1
    while r <= LAST_FREE_ROW:
        vals = {}
        if ref_rows and refs and r >= total_row + 2:
            div, label = refs.pop(0)
            vals = {"R": ("f", f"R{total_row}/{div}", cost_total / div), "S": ("s", label)}
        new_rows[r] = make_row(r, st["blank"], vals, ROW_HEIGHT["blank"], tags["blank"])
        r += 1
    for r, xml in new_rows.items():
        sh.replace_row(r, xml)
    # 注記行〜枠最下段: A〜L はそのまま、M〜T の残骸を消す
    for r in range(NOTE_ROWS[0], NOTE_ROWS[1] + 1):
        for col in COLS[12:]:
            sh.set_cell(f"{col}{r}", None)
    # 内部列の見出し（印刷範囲外）
    for col, label in INTERNAL_HEADERS.items():
        sh.set_cell(f"{col}{HEADER_ROW}", ("s", label))
    # 金額欄 = 合計
    sh.set_cell(CELL_AMOUNT, ("f", f"K{total_row}", total_row_vals["K"][2]))
    # 22行目だけにあった B:F 結合を外す（明細行は結合なしで統一）
    sh.xml = re.sub(r'<mergeCell ref="B22:F22"/>', "", sh.xml)
    sh.xml = re.sub(r'<mergeCells count="(\d+)">',
                    lambda m: f'<mergeCells count="{len(re.findall(r"<mergeCell ", sh.xml))}">', sh.xml, count=1)


# ------------------------------------------------------------------ 内訳シート


def build_detail_sheet(ctx: Ctx, cover_xml: str, sheet_name: str, title_text: str, lines: list[Line],
                       customer: str, no_value, work_title: str):
    """内訳(工事) シートの XML を組み立てる。戻り値: (xml, line_row, total_row, totals)"""
    st = ctx.styles
    cols_xml = re.search(r"<cols>.*?</cols>", cover_xml, re.S).group(0)
    margins = re.search(r"<pageMargins[^>]*/>", cover_xml).group(0)
    footer = re.search(r"<headerFooter>.*?</headerFooter>", cover_xml, re.S)
    footer_xml = footer.group(0) if footer else ""
    cov = f"'{COVER_SHEET}'!"

    rows_xml: list[str] = []
    merges = ["A1:L2", "K3:L3", "A4:B4", "A5:B5"]
    s112 = 112  # 表紙タイトルと同じ書式
    rows_xml.append(make_row(1, {c: s112 for c in COLS[:12]}, {"A": ("s", "内　訳　明　細　書")}, 19.5))
    rows_xml.append(make_row(2, {c: s112 for c in COLS[:12]}, {}, 19.5))
    rows_xml.append(make_row(3, {"J": 3, "K": 118, "L": 118},
                             {"J": ("s", "No."), "K": ("f", f"{cov}{CELL_NO}", no_value) if isinstance(no_value, (int, float))
                              else ("fs", f"{cov}{CELL_NO}", str(no_value or ""))}, 19.5))
    rows_xml.append(make_row(4, {"A": 116, "B": 116, "C": 28, "D": 28, "E": 28, "F": 28},
                             {"A": ("s", "工事名"), "D": ("fs", f"{cov}{CELL_TITLE}", work_title)}, 20.25))
    rows_xml.append(make_row(5, {"A": 116, "B": 116, "C": 28, "D": 28, "E": 28, "F": 28},
                             {"A": ("s", "宛　名"), "D": ("fs", f'{cov}{CELL_CUSTOMER}&"　"&{cov}{CELL_HONORIFIC}',
                                                       f"{customer}　御中")}, 20.25))
    rows_xml.append(make_row(6, st["spacer"], {}, ROW_HEIGHT["spacer"]))
    hdr_vals = {"A": ("s", "項　目"), "B": ("s", "内　　　容"), "G": ("s", "数 量"), "H": ("s", "単位"),
                "I": ("s", "単  価"), "K": ("s", "金　　額"), "L": ("s", "備　考")}
    hdr_vals.update({c: ("s", l) for c, l in INTERNAL_HEADERS.items()})
    rows_xml.append(make_row(7, st["header"], hdr_vals, ROW_HEIGHT["header"]))
    merges += ["B7:F7", "I7:J7", "S7:T7"]

    first = 8
    rows_xml.append(make_row(first, st["title"], {"B": ("s", title_text)}, ROW_HEIGHT["title"]))
    merges += [f"I{first}:J{first}", f"S{first}:T{first}"]
    body, line_row, totals = render_lines_rows(ctx, lines, first + 1)
    for r, arch, vals in body:
        rows_xml.append(make_row(r, st[arch], vals, ROW_HEIGHT[arch]))
        merges += [f"I{r}:J{r}", f"S{r}:T{r}"]
    total_row = first + 1 + len(body)
    tv = total_row_values(total_row, first, total_row - 1, totals["sell"], totals["cost"])
    rows_xml.append(make_row(total_row, st["last"], tv, ROW_HEIGHT["total"]))
    merges += [f"I{total_row}:J{total_row}", f"S{total_row}:T{total_row}"]

    merge_xml = "".join(f'<mergeCell ref="{m}"/>' for m in merges)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<dimension ref="A1:T{total_row}"/>'
        '<sheetViews><sheetView view="pageBreakPreview" zoomScale="85" zoomScaleNormal="85" '
        'zoomScaleSheetLayoutView="85" workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultColWidth="6.7109375" defaultRowHeight="12" customHeight="1"/>'
        f"{cols_xml}<sheetData>{''.join(rows_xml)}</sheetData>"
        f'<mergeCells count="{len(merges)}">{merge_xml}</mergeCells><phoneticPr fontId="3"/>'
        f'{margins}<pageSetup paperSize="9" scale="89" fitToWidth="1" fitToHeight="0" orientation="portrait"/>'
        f"{footer_xml}</worksheet>"
    )
    return xml, line_row, total_row, totals


# ------------------------------------------------------------------ ブック側の登録


def add_input_styles(styles_xml: str) -> tuple[str, dict[str, int]]:
    """入力セル用の書式（黄色塗り・細罫線）を2つ追加して、その style id を返す"""
    fills_m = re.search(r'<fills count="(\d+)">(.*?)</fills>', styles_xml, re.S)
    n_fill = int(fills_m.group(1))
    fill = '<fill><patternFill patternType="solid"><fgColor rgb="FFFFFF99"/><bgColor indexed="64"/></patternFill></fill>'
    styles_xml = styles_xml[: fills_m.end() - len("</fills>")] + fill + styles_xml[fills_m.end() - len("</fills>"):]
    styles_xml = styles_xml.replace(f'<fills count="{n_fill}">', f'<fills count="{n_fill + 1}">', 1)
    borders_m = re.search(r'<borders count="(\d+)">(.*?)</borders>', styles_xml, re.S)
    n_border = int(borders_m.group(1))
    border = ('<border><left style="thin"><color indexed="64"/></left><right style="thin"><color indexed="64"/></right>'
              '<top style="thin"><color indexed="64"/></top><bottom style="thin"><color indexed="64"/></bottom><diagonal/></border>')
    styles_xml = styles_xml[: borders_m.end() - len("</borders>")] + border + styles_xml[borders_m.end() - len("</borders>"):]
    styles_xml = styles_xml.replace(f'<borders count="{n_border}">', f'<borders count="{n_border + 1}">', 1)
    xfs_m = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', styles_xml, re.S)
    n_xf = int(xfs_m.group(1))
    # numFmt: 182 = 0_);[Red](0)（テンプレート内の定義を流用）  3 = #,##0（組込み）
    def xf(numfmt):
        return (f'<xf numFmtId="{numfmt}" fontId="7" fillId="{n_fill}" borderId="{n_border}" xfId="0" '
                'applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
                '<alignment horizontal="right" vertical="center"/></xf>')
    new = xf(182) + xf(3)
    styles_xml = styles_xml[: xfs_m.end() - len("</cellXfs>")] + new + styles_xml[xfs_m.end() - len("</cellXfs>"):]
    styles_xml = styles_xml.replace(f'<cellXfs count="{n_xf}">', f'<cellXfs count="{n_xf + 2}">', 1)
    return styles_xml, {"int": n_xf, "num": n_xf + 1}


def register_detail_sheet(parts: dict[str, bytes], sheet_name: str, sheet_xml: str, last_row: int) -> None:
    """workbook.xml / rels / [Content_Types] / app.xml に内訳シートを登録する"""
    wb = parts["xl/workbook.xml"].decode("utf-8")
    rels = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    ct = parts["[Content_Types].xml"].decode("utf-8")
    rid_nums = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels)]
    rid = f"rId{max(rid_nums) + 1}"
    n = 2
    while f"xl/worksheets/sheet{n}.xml" in parts:
        n += 1
    part = f"xl/worksheets/sheet{n}.xml"
    parts[part] = sheet_xml.encode("utf-8")
    rels = rels.replace("</Relationships>",
                        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                        f'Target="worksheets/sheet{n}.xml"/></Relationships>')
    ct = ct.replace("</Types>",
                    f'<Override PartName="/{part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    sheet_ids = [int(x) for x in re.findall(r'<sheet [^>]*sheetId="(\d+)"', wb)]
    idx = len(re.findall(r"<sheet ", wb))
    wb = wb.replace("</sheets>", f'<sheet name="{esc(sheet_name)}" sheetId="{max(sheet_ids) + 1}" r:id="{rid}"/></sheets>')
    q = sheet_name.replace("'", "''")
    dn = (f'<definedName name="_xlnm.Print_Area" localSheetId="{idx}">\'{esc(q)}\'!$A$1:$L${last_row}</definedName>'
          f'<definedName name="_xlnm.Print_Titles" localSheetId="{idx}">\'{esc(q)}\'!$7:$7</definedName>')
    if "<definedNames>" in wb:
        wb = wb.replace("</definedNames>", dn + "</definedNames>")
    else:
        wb = wb.replace("</sheets>", "</sheets><definedNames>" + dn + "</definedNames>")
    parts["xl/workbook.xml"] = wb.encode("utf-8")
    parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
    parts["[Content_Types].xml"] = ct.encode("utf-8")
    # docProps/app.xml のシート一覧（任意項目だが整合させる）
    if "docProps/app.xml" in parts:
        app = parts["docProps/app.xml"].decode("utf-8")
        names = [sheet_name]
        app = re.sub(r"<vt:i4>\d+</vt:i4>", lambda m, c=[0]: (c.__setitem__(0, c[0] + 1) or f"<vt:i4>{idx + 1 if c[0] == 1 else len(re.findall('Print_', app)) + 2}</vt:i4>"), app)
        tp = re.search(r'<TitlesOfParts><vt:vector size="(\d+)" baseType="lpstr">(.*?)</vt:vector></TitlesOfParts>', app, re.S)
        if tp:
            items = re.findall(r"<vt:lpstr>(.*?)</vt:lpstr>", tp.group(2))
            sheets = [x for x in items if "!" not in x] + names
            ranges = [x for x in items if "!" in x] + [f"'{esc(q)}'!Print_Area", f"'{esc(q)}'!Print_Titles"]
            all_items = sheets + ranges
            new_tp = ('<TitlesOfParts><vt:vector size="%d" baseType="lpstr">%s</vt:vector></TitlesOfParts>'
                      % (len(all_items), "".join(f"<vt:lpstr>{x}</vt:lpstr>" for x in all_items)))
            app = app[: tp.start()] + new_tp + app[tp.end():]
            app = re.sub(r"(<vt:lpstr>ワークシート</vt:lpstr></vt:variant><vt:variant><vt:i4>)\d+(</vt:i4>)",
                         lambda m: f"{m.group(1)}{len(sheets)}{m.group(2)}", app)
            app = re.sub(r"(<vt:lpstr>名前付き一覧</vt:lpstr></vt:variant><vt:variant><vt:i4>)\d+(</vt:i4>)",
                         lambda m: f"{m.group(1)}{len(ranges)}{m.group(2)}", app)
        parts["docProps/app.xml"] = app.encode("utf-8")


def drop_calc_chain(parts: dict[str, bytes]) -> None:
    """calcChain を捨て、開いたときに全再計算させる（数式セルの位置が変わるため）"""
    parts.pop("xl/calcChain.xml", None)
    rels = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    rels = re.sub(r'<Relationship [^>]*Target="calcChain.xml"[^>]*/>', "", rels)
    parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
    ct = parts["[Content_Types].xml"].decode("utf-8")
    ct = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", ct)
    parts["[Content_Types].xml"] = ct.encode("utf-8")
    wb = parts["xl/workbook.xml"].decode("utf-8")
    if "fullCalcOnLoad" not in wb:
        wb = re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', wb, count=1)
    parts["xl/workbook.xml"] = wb.encode("utf-8")


def find_cover_part(parts: dict[str, bytes]) -> str:
    wb = parts["xl/workbook.xml"].decode("utf-8")
    rels = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    m = re.search(r'<sheet name="%s"[^>]*r:id="(rId\d+)"' % re.escape(COVER_SHEET), wb)
    if not m:
        raise SystemExit(f"テンプレートにシート「{COVER_SHEET}」がありません")
    t = re.search(r'<Relationship Id="%s"[^>]*Target="([^"]+)"' % m.group(1), rels)
    target = t.group(1)
    return target if target.startswith("xl/") else "xl/" + target.lstrip("/")


# ------------------------------------------------------------------ メイン


def main() -> None:
    ap = argparse.ArgumentParser(description="明細JSON → 自社見積Excel（テンプレート流し込み）")
    ap.add_argument("--template", required=True)
    ap.add_argument("--lines", required=True, help="extract_estimate_pdf.py の出力JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--customer", help="宛名（A5）例: 有限会社 原田製麵")
    ap.add_argument("--title", help="工事名（D12）")
    ap.add_argument("--site", help="施工場所（D14）")
    ap.add_argument("--no", help="見積No.（K3）")
    ap.add_argument("--date", help="見積日 YYYY-MM-DD（J4）。省略時はテンプレートのまま")
    ap.add_argument("--period", help="工事期限（D15）")
    ap.add_argument("--terms", help="御支払条件（D16）")
    ap.add_argument("--validity", help="有効期限（D17）")
    ap.add_argument("--cover-title", help="明細欄1行目の【 】見出し。省略時は PDF のタイトル or 工事名")
    ap.add_argument("--margin-pct", type=float, default=0.0, help="粗利率 %%（売価 = 原価 ÷ (1−率)）。0 = なし")
    ap.add_argument("--markup-pct", type=float, default=100.0, help="掛率 %%（売価 = 原価 × 率/100）。100 = なし")
    ap.add_argument("--round-unit", type=int, default=1, help="売単価の端数処理単位（円）。1 = なし")
    ap.add_argument("--round-mode", choices=["round", "up", "down"], default="round")
    ap.add_argument("--layout", choices=["auto", "cover", "detail"], default="auto")
    ap.add_argument("--detail-sheet-name", default=DETAIL_SHEET_DEFAULT)
    ap.add_argument("--keep-numbering", action="store_true", help="元見積の「1）」等の番号を名称に残す")
    a = ap.parse_args()

    pricing = Pricing(a.margin_pct, a.markup_pct, max(1, a.round_unit), a.round_mode)
    data = json.load(open(a.lines, encoding="utf-8"))
    pdf_title, lines = make_lines(data, a.keep_numbering)
    if not lines:
        raise SystemExit("明細がありません")
    work_title = a.title or pdf_title or ""
    cover_title = a.cover_title or (f"【{pdf_title}】" if pdf_title else (f"【{work_title}】" if work_title else "【見積内訳】"))
    customer = a.customer or (data.get("meta") or {}).get("customer") or ""

    with zipfile.ZipFile(a.template) as z:
        order = [i.filename for i in z.infolist()]
        parts = {n: z.read(n) for n in order}
    cover_part = find_cover_part(parts)
    cover = SheetXml(parts[cover_part].decode("utf-8"))
    if 't="shared"' in cover.xml:
        pass  # 明細欄の再生成で共有数式は丸ごと消える。残っていないか最後に検査する
    styles_xml, input_styles = add_input_styles(parts["xl/styles.xml"].decode("utf-8"))
    parts["xl/styles.xml"] = styles_xml.encode("utf-8")

    styles = {k: cover.styles_of_row(r) for k, r in ARCHETYPE_ROW.items()}
    styles["item"] = {**styles["item"], **ITEM_STYLE_OVERRIDE}
    tags = {k: cover.row_tag(r) for k, r in ARCHETYPE_ROW.items()}

    layout = a.layout
    if layout == "auto":
        layout = "cover" if len(lines) <= COVER_CAPACITY else "detail"

    apply_header_info(cover, a)
    if not a.customer and customer:
        cover.set_cell(CELL_CUSTOMER, ("s", customer))
    apply_settings_block(cover, pricing, input_styles)
    no_value = int(a.no) if (a.no and str(a.no).isdigit()) else (a.no or "")

    summary = {"layout": layout, "lines": len(lines), "groups": None}
    if layout == "cover":
        ctx = Ctx(pricing, "", styles, tags, detail_numbering=False)
        body, _, totals = render_lines_rows(ctx, lines, FIRST_ROW + 1)
        total_row = FIRST_ROW + 1 + len(body)
        if total_row > LAST_FREE_ROW:
            raise SystemExit(f"明細 {len(lines)} 行は表紙に収まりません。--layout detail を指定してください")
        tv = total_row_values(total_row, FIRST_ROW, total_row - 1, totals["sell"], totals["cost"])
        build_cover(cover, ctx, cover_title, body, tv, total_row, ref_rows=(total_row + 5 <= LAST_FREE_ROW),
                    cost_total=totals["cost"])
        parts[cover_part] = cover.xml.encode("utf-8")
    else:
        dctx = Ctx(pricing, f"'{COVER_SHEET}'!", styles, tags, detail_numbering=True)
        sheet_xml, line_row, dtotal_row, totals = build_detail_sheet(
            dctx, cover.xml, a.detail_sheet_name, cover_title, lines, customer, no_value, work_title)
        groups = make_groups(lines)
        max_groups = LAST_FREE_ROW - FIRST_ROW - 1  # タイトル行と合計行を除いた行数
        if len(groups) > max_groups:
            keep = groups[: max_groups - 1]
            rest = groups[max_groups - 1 :]
            keep.append(Group("その他（内訳明細参照）", rest[0].first, rest[-1].last))
            groups = keep
        dq = f"'{a.detail_sheet_name.replace(chr(39), chr(39) * 2)}'!"
        body = []
        sell_total = cost_total = 0
        for gi, g in enumerate(groups):
            r = FIRST_ROW + 1 + gi
            d1, d2 = line_row[g.first], line_row[g.last]
            g_sell = 0
            g_cost = 0
            for li in range(g.first, g.last + 1):
                ln = lines[li]
                if ln.kind != "item":
                    continue
                v, c = item_row_values(dctx, line_row[li], ln, 1)
                g_sell += c["sell"]
                g_cost += c["cost"]
            sell_total += g_sell
            cost_total += g_cost
            vals = {
                "A": ("s", CIRCLED[gi] if gi < len(CIRCLED) else str(gi + 1)),
                "B": ("s", g.name),
                "G": ("n", 1), "H": ("s", "式"),
                "K": ("f", f"SUM({dq}K{d1}:K{d2})", g_sell),
                "R": ("f", f"SUM({dq}R{d1}:R{d2})", g_cost),
                "Q": ("f", f"K{r}-R{r}", g_sell - g_cost),
                "M": ("f", f"IF(K{r}=0,0,(K{r}-R{r})/K{r}*100)", 0 if not g_sell else (g_sell - g_cost) / g_sell * 100),
            }
            body.append((r, "item", vals))
        total_row = FIRST_ROW + 1 + len(body)
        tv = total_row_values(total_row, FIRST_ROW, total_row - 1, sell_total, cost_total)
        cctx = Ctx(pricing, "", styles, tags)
        build_cover(cover, cctx, cover_title, body, tv, total_row, ref_rows=(total_row + 5 <= LAST_FREE_ROW),
                    cost_total=cost_total)
        parts[cover_part] = cover.xml.encode("utf-8")
        register_detail_sheet(parts, a.detail_sheet_name, sheet_xml, dtotal_row)
        summary["groups"] = len(groups)
        summary["detail_rows"] = dtotal_row
        totals = {"sell": sell_total, "cost": cost_total}

    drop_calc_chain(parts)

    # 検査: 共有数式の残骸が無いか、XML が整形式か
    cov_final = parts[cover_part].decode("utf-8")
    if 't="shared"' in cov_final:
        raise SystemExit("内部エラー: 表紙に共有数式が残っています（テンプレートの想定と違う配置です）")
    for name, blob in parts.items():
        if name.endswith((".xml", ".rels")):
            try:
                ET.fromstring(blob)
            except ET.ParseError as e:
                raise SystemExit(f"内部エラー: {name} が整形式ではありません: {e}")

    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order:
            if n in parts:
                z.writestr(n, parts[n])
        for n in parts:
            if n not in order:
                z.writestr(n, parts[n])

    summary.update({
        "out": a.out, "sell_total": totals["sell"], "cost_total": totals["cost"],
        "margin_pct": pricing.margin_pct, "markup_pct": pricing.markup_pct, "round_unit": pricing.unit, "round_mode": pricing.mode,
        "customer": customer, "title": work_title, "cover_title": cover_title, "cover_total_row": total_row,
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
