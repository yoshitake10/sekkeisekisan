#!/usr/bin/env python3
"""
extract_estimate_pdf.py — 見積書PDF（テキストPDF）から明細行を抽出して JSON にする。

使い方:
    python3 extract_estimate_pdf.py 元見積.pdf -o lines.json [--debug] [--backend auto|pdfplumber|pypdfium2]

出力 JSON の形:
    {
      "source_pdf": "...", "pages": 2,
      "meta": {"date_text", "date_iso", "customer", "vendor", "title",
               "totals": {"合計金額": 2450000, ...}, "page_subtotals": [...], "items_total": ..., "text_lines": [...]},
      "lines": [
        {"page": 1, "kind": "title",  "text": "エアコン更新工事"},
        {"page": 1, "kind": "header", "text": "機器）三菱電機製　ビル用マルチエアコン"},
        {"page": 1, "kind": "item",   "name": "　　室外機　PUHY-SGRP280DM", "qty": 1, "unit": "台",
                                      "unit_price": null, "amount": 907500, "remarks": ""},
        {"page": 1, "kind": "note",   "text": "ありがとうございます"},
        ...
      ],
      "warnings": ["..."]
    }

仕組み:
  1. ページ内の文字列チャンクを座標付きで取得（pdfplumber または pypdfium2）
  2. y 座標で行にまとめ、「内容 / 数量 / 単位 / 単価 / 金額 / 備考」の見出し行を探す
  3. 表の縦罫線（あれば）または見出しの位置から列境界を決め、見出し行より下の行を列ごとに振り分ける
  4. 数量「1台」→ 1 / 台、金額「▲120,830」→ -120830 のように数値化する
  5. 見出し行より上（宛名・発行者・合計欄）と表の外の文はメタ情報として拾う
スキャンPDF（文字情報なし）は対象外。抽出結果は必ず元PDFと目視照合すること。
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- 文字列ユーティリティ

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９．，－", "0123456789.,-")


def norm_key(s: str) -> str:
    """見出し照合用: 空白を除去して比較する"""
    return re.sub(r"[\s　]+", "", s)


NUM_RE = re.compile(
    r"^[¥￥\\]?\s*(?P<neg>[-−－▲△(])?\s*[¥￥\\]?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*\)?\s*(?:円)?\s*[-−－]?$"
)


def parse_number(s: str) -> Optional[float]:
    """'907,500' '¥2,450,000' '-120,830' '▲120,830' '(1,000)' などを数値にする。数値でなければ None"""
    t = s.strip().translate(FULLWIDTH_DIGITS).replace("　", " ").strip()
    m = NUM_RE.match(t)
    if not m:
        return None
    v = float(m.group("num").replace(",", ""))
    if m.group("neg"):
        v = -v
    return v


QTY_RE = re.compile(r"^(?P<num>[-−－]?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>[^\d\s].*)?$")


def parse_qty(s: str) -> tuple[Optional[float], str]:
    """'1台' → (1, '台')、'6カ所' → (6, 'カ所')、'式' → (None, '式')、'2.5' → (2.5, '')"""
    t = s.strip().translate(FULLWIDTH_DIGITS).replace("　", " ").strip()
    if not t:
        return None, ""
    m = QTY_RE.match(t)
    if not m:
        return None, t
    q = float(m.group("num").replace(",", ""))
    return q, (m.group("unit") or "").strip()


def as_int_if_whole(v: Optional[float]):
    if v is None:
        return None
    return int(v) if float(v).is_integer() else v


# ---------------------------------------------------------------- チャンク取得（バックエンド）


@dataclass
class Chunk:
    x0: float
    x1: float
    top: float
    bottom: float
    text: str

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def h(self) -> float:
        return self.bottom - self.top


@dataclass
class VLine:
    x: float
    top: float
    bottom: float


@dataclass
class PageData:
    width: float
    height: float
    chunks: list[Chunk]
    vlines: list[VLine]


def chunks_pdfplumber(path: str) -> list[PageData]:
    import pdfplumber  # type: ignore

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                keep_blank_chars=True, x_tolerance=2.0, y_tolerance=2.5, use_text_flow=False
            )
            chunks = [
                Chunk(float(w["x0"]), float(w["x1"]), float(w["top"]), float(w["bottom"]), w["text"])
                for w in words
                if w["text"].strip(" 　")
            ]
            vlines = []
            for e in page.edges:
                if e.get("orientation") == "v" and (e["bottom"] - e["top"]) >= 4:
                    vlines.append(VLine(float(e["x0"]), float(e["top"]), float(e["bottom"])))
            pages.append(PageData(float(page.width), float(page.height), chunks, vlines))
    return pages


def chunks_pypdfium2(path: str) -> list[PageData]:
    import pypdfium2 as pdfium  # type: ignore
    import pypdfium2.raw as pdfium_c  # type: ignore

    pages = []
    pdf = pdfium.PdfDocument(path)
    for i in range(len(pdf)):
        page = pdf[i]
        w, h = page.get_size()
        tp = page.get_textpage()
        chunks = []
        for k in range(tp.count_rects()):
            l, b, r, t = tp.get_rect(k)
            txt = tp.get_text_bounded(left=l, bottom=b, right=r, top=t)
            txt = txt.replace("\r", "").replace("\n", "")
            if txt.strip(" 　"):
                chunks.append(Chunk(l, r, h - t, h - b, txt))
        vlines = []
        try:
            for obj in page.get_objects(max_depth=3):
                if obj.type != pdfium_c.FPDF_PAGEOBJ_PATH:
                    continue
                getter = getattr(obj, "get_bounds", None) or getattr(obj, "get_pos")
                l, b, r, t = getter()
                if (t - b) < 4:
                    continue  # 横線・極小
                if (r - l) <= 2.5:
                    vlines.append(VLine((l + r) / 2, h - t, h - b))
                else:  # 矩形（セル枠）→ 左右の辺
                    vlines.append(VLine(l, h - t, h - b))
                    vlines.append(VLine(r, h - t, h - b))
        except Exception:  # noqa: BLE001
            pass
        pages.append(PageData(float(w), float(h), chunks, vlines))
    return pages


def load_chunks(path: str, backend: str) -> tuple[str, list[PageData]]:
    errors = []
    order = ["pdfplumber", "pypdfium2"] if backend == "auto" else [backend]
    for name in order:
        try:
            fn = chunks_pdfplumber if name == "pdfplumber" else chunks_pypdfium2
            pages = fn(path)
            if any(p.chunks for p in pages):
                return name, pages
            errors.append(f"{name}: 文字情報が取得できませんでした（スキャンPDF？）")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {type(e).__name__}: {e}")
    raise SystemExit("PDF からテキストを取得できませんでした:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------- 行・列の構造化

HEADER_KEYWORDS = {
    "name": ["内容", "品名", "名称", "摘要", "品目", "項目", "工事名称", "名称・規格", "名称規格", "工事内容", "内訳", "工種"],
    "spec": ["規格", "仕様", "形式", "型式", "規格・寸法"],
    "qty": ["数量"],
    "unit": ["単位"],
    "unit_price": ["単価"],
    "amount": ["金額"],
    "remarks": ["備考", "摘要欄"],
    "date": ["日付"],
    "no": ["No", "No.", "番号", "No．", "NO", "NO."],
}

TOTAL_KEYWORDS = [
    "合計金額", "御見積金額", "お見積金額", "今回ご見積額", "見積金額", "税込合計", "税抜合計",
    "消費税額", "消費税", "値引き額", "値引額", "合計", "小計", "総合計", "総計",
]
SUBTOTAL_NAMES = {"小計", "計", "合計", "総計", "頁計", "ページ計", "小計金額", "総合計"}


@dataclass
class Row:
    cy: float
    chunks: list[Chunk] = field(default_factory=list)


def cluster_rows(chunks: list[Chunk]) -> list[Row]:
    if not chunks:
        return []
    med_h = statistics.median(c.h for c in chunks) or 8.0
    tol = max(2.0, med_h * 0.45)
    rows: list[Row] = []
    for c in sorted(chunks, key=lambda c: (c.cy, c.x0)):
        placed = False
        for r in rows[::-1][:5]:
            if abs(r.cy - c.cy) <= tol:
                r.chunks.append(c)
                n = len(r.chunks)
                r.cy = (r.cy * (n - 1) + c.cy) / n
                placed = True
                break
        if not placed:
            rows.append(Row(c.cy, [c]))
    for r in rows:
        r.chunks.sort(key=lambda c: c.x0)
    rows.sort(key=lambda r: r.cy)
    return rows


def match_header(row: Row) -> dict[str, Chunk]:
    found: dict[str, Chunk] = {}
    for c in row.chunks:
        key = norm_key(c.text)
        for col, kws in HEADER_KEYWORDS.items():
            if key in kws and col not in found:
                found[col] = c
    return found


@dataclass
class Columns:
    """列名 → (左境界, 右境界)。表の左右端 (x_min, x_max) と、下端 y_max（不明なら None）"""
    bounds: dict[str, tuple[float, float]]
    x_min: float
    x_max: float
    y_max: Optional[float]
    from_lines: bool
    name_left_edge: float = 0.0  # 罫線なし時: 内容列とみなす左端（直前の見出し文字列の右端）

    def assign(self, c: Chunk) -> Optional[str]:
        """チャンクの列名。表の外なら None"""
        if self.from_lines:
            if c.cx < self.x_min - 2 or c.cx > self.x_max + 2:
                return None
            for col, (l, r) in self.bounds.items():
                if l <= c.cx < r:
                    return col
            return min(self.bounds, key=lambda k: min(abs(c.cx - self.bounds[k][0]), abs(c.cx - self.bounds[k][1])))
        # 罫線なし: 直前の見出し右端〜内容列右境界に左端がある非数値文字列は内容列とみなす
        # （見出し「内容」は幅広い列の中央にあるため、中点境界だけでは左寄せの名称が前の列に落ちる）
        if "name" in self.bounds:
            l, r = self.bounds["name"]
            if self.name_left_edge <= c.x0 < r and parse_number(c.text) is None:
                return "name"
        for col, (l, r) in self.bounds.items():
            if l <= c.cx < r:
                return col
        return min(self.bounds, key=lambda k: min(abs(c.cx - self.bounds[k][0]), abs(c.cx - self.bounds[k][1])))


def _cluster_xs(xs: list[float], tol: float = 1.5) -> list[float]:
    out: list[float] = []
    for x in sorted(xs):
        if out and abs(out[-1] - x) <= tol:
            out[-1] = (out[-1] + x) / 2
        else:
            out.append(x)
    return out


def build_columns(found: dict[str, Chunk], page: PageData, header: Row) -> Columns:
    """縦罫線があればそれを列境界にし、無ければ見出し中心の中点を境界にする"""
    hdr_top = min(c.top for c in header.chunks)
    hdr_bot = max(c.bottom for c in header.chunks)
    cand = [v for v in page.vlines if v.top <= hdr_bot + 1 and v.bottom >= hdr_top - 1]
    xs = _cluster_xs([v.x for v in cand])
    if len(xs) >= 3:
        intervals = list(zip(xs[:-1], xs[1:]))
        bounds: dict[str, tuple[float, float]] = {}
        for col, c in found.items():
            for l, r in intervals:
                if l <= c.cx < r:
                    bounds[col] = (l, r)
                    break
        if "name" in bounds and ("amount" in bounds or "unit_price" in bounds or "qty" in bounds):
            # 表の下端: 境界 x 上にある縦線の最下端
            y_max = None
            ys = [v.bottom for v in page.vlines if any(abs(v.x - x) <= 1.5 for x in xs)]
            if ys:
                y_max = max(ys)
            return Columns(bounds, xs[0], xs[-1], y_max, True)
    anchors = sorted(((c.cx, col) for col, c in found.items()), key=lambda t: t[0])
    bounds = {}
    name_left_edge = 0.0
    for i, (cx, col) in enumerate(anchors):
        left = 0.0 if i == 0 else (anchors[i - 1][0] + cx) / 2
        right = page.width if i == len(anchors) - 1 else (cx + anchors[i + 1][0]) / 2
        bounds[col] = (left, right)
        if col == "name" and i > 0:
            name_left_edge = found[anchors[i - 1][1]].x1 + 1.0
    return Columns(bounds, 0.0, page.width, None, False, name_left_edge)


def row_text(row: Row) -> str:
    return " ".join(c.text.strip() for c in row.chunks)


# ---------------------------------------------------------------- メタ情報

ERA = {"令和": 2018, "平成": 1988, "昭和": 1925, "R": 2018, "H": 1988, "S": 1925}
DATE_RE = re.compile(
    r"(?P<era>令和|平成|昭和|R|H|S)?\s*(?P<y>\d{1,4}|元)\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"
)
DATE_SLASH_RE = re.compile(r"(?P<y>\d{4})[/.\-](?P<m>\d{1,2})[/.\-](?P<d>\d{1,2})")


def parse_date(text: str) -> Optional[tuple[str, str]]:
    t = text.translate(FULLWIDTH_DIGITS)
    m = DATE_RE.search(t)
    if m:
        y = 1 if m.group("y") == "元" else int(m.group("y"))
        if m.group("era"):
            y += ERA[m.group("era")]
        return m.group(0), f"{y:04d}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"
    m = DATE_SLASH_RE.search(t)
    if m:
        return m.group(0), f"{int(m.group('y')):04d}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"
    return None


COMPANY_RE = re.compile(r"(株式会社|有限会社|合同会社|合資会社|㈱|㈲|\(株\)|\(有\)|工務店|建設|工業|商事|商店|製作所|設備)")


def extract_meta(meta_rows: list[Row], page_w: float) -> dict:
    meta: dict = {"date_text": None, "date_iso": None, "customer": None, "vendor": None,
                  "totals": {}, "text_lines": [row_text(r) for r in meta_rows]}
    # 日付
    for r in meta_rows:
        d = parse_date(row_text(r))
        if d:
            meta["date_text"], meta["date_iso"] = d
            break
    # 宛名（御中 / 様）
    for r in meta_rows:
        texts = [c.text.strip(" 　") for c in r.chunks]
        for i, t in enumerate(texts):
            if re.search(r"(御中|様)$", t):
                name = re.sub(r"\s*(御中|様)$", "", t).strip(" 　")
                if not name:
                    name = " ".join(x for x in texts[:i] if x)
                if name:
                    meta["customer"] = name
                    break
        if meta["customer"]:
            break
    # 発行者: 右半分にある会社名らしい行（文字が大きいものを優先）
    cand = []
    for r in meta_rows:
        right = [c for c in r.chunks if c.x0 >= page_w * 0.45]
        if not right:
            continue
        t = " ".join(c.text.strip(" 　") for c in right).strip()
        if COMPANY_RE.search(t) and not t.endswith(("御中", "様")) and t != meta["customer"]:
            cand.append((-max(c.h for c in right), r.cy, t))
    if cand:
        cand.sort()
        meta["vendor"] = cand[0][2]
    # 合計欄: 見出し語を2つ以上含む行 → 同じ行 or 直下の数値を近い見出しに対応付ける
    for idx, r in enumerate(meta_rows):
        labels = [(c, norm_key(c.text)) for c in r.chunks if norm_key(c.text) in TOTAL_KEYWORDS]
        if len(labels) < 2:
            continue
        nums = [(c, parse_number(c.text)) for c in r.chunks if parse_number(c.text) is not None]
        if not nums and idx + 1 < len(meta_rows):
            nxt = meta_rows[idx + 1]
            nums = [(c, parse_number(c.text)) for c in nxt.chunks if parse_number(c.text) is not None]
        for c, v in nums:
            lab = min(labels, key=lambda lc: abs(lc[0].cx - c.cx))[1]
            meta["totals"][lab] = as_int_if_whole(v)
        if meta["totals"]:
            break
    return meta


# ---------------------------------------------------------------- 明細抽出


def extract(path: str, backend: str, debug: bool = False) -> dict:
    used, pages = load_chunks(path, backend)
    lines: list[dict] = []
    warnings: list[str] = []
    meta_rows: list[Row] = []
    page_subtotals: list[Optional[int]] = []
    columns: Optional[Columns] = None

    for pno, page in enumerate(pages, start=1):
        rows = cluster_rows(page.chunks)
        header_idx = None
        for i, r in enumerate(rows):
            found = match_header(r)
            if len(found) >= 2 and ("amount" in found or "name" in found):
                header_idx = i
                columns = build_columns(found, page, r)
                if debug:
                    print(f"p{pno} 見出し行 y={r.cy:.1f} 列={ {k: (round(l), round(r_)) for k, (l, r_) in columns.bounds.items()} } "
                          f"罫線={columns.from_lines} 下端={columns.y_max}", file=sys.stderr)
                break
        if header_idx is None and columns is None:
            warnings.append(f"p{pno}: 明細の見出し行（内容/数量/金額 など）が見つかりません。全行をメタ情報として扱います")
            meta_rows.extend(rows)
            page_subtotals.append(None)
            continue
        if header_idx is None:
            table_rows = rows
            warnings.append(f"p{pno}: 見出し行が無いため前ページの列位置を流用しました")
        else:
            meta_rows.extend(rows[:header_idx])
            table_rows = rows[header_idx + 1 :]

        page_sum = 0
        page_sub: Optional[int] = None
        after_table = False
        for r in table_rows:
            if columns.y_max is not None and r.cy > columns.y_max + 2:
                after_table = True
            cells: dict[str, list[Chunk]] = {}
            outside: list[Chunk] = []
            for c in r.chunks:
                col = columns.assign(c)
                if col is None:
                    outside.append(c)
                else:
                    cells.setdefault(col, []).append(c)

            def cell_text(col: str) -> str:
                cs = sorted(cells.get(col, []), key=lambda c: c.x0)
                return " ".join(c.text for c in cs).rstrip(" 　")

            if after_table or not cells:
                txt = row_text(r)
                if txt.strip():
                    lines.append({"page": pno, "kind": "note", "text": txt})
                    meta_rows.append(r)
                continue

            name, spec = cell_text("name"), cell_text("spec")
            qty_t, unit_t = cell_text("qty"), cell_text("unit")
            up_t, amt_t, rem_t = cell_text("unit_price"), cell_text("amount"), cell_text("remarks")
            no_t, date_t = cell_text("no"), cell_text("date")
            if debug:
                print(f"  p{pno} y={r.cy:6.1f} name={name!r} spec={spec!r} qty={qty_t!r} unit={unit_t!r} "
                      f"up={up_t!r} amt={amt_t!r} rem={rem_t!r} no={no_t!r} date={date_t!r}", file=sys.stderr)

            amount = parse_number(amt_t) if amt_t else None
            unit_price = parse_number(up_t) if up_t else None
            qty, unit_from_qty = parse_qty(qty_t) if qty_t else (None, "")
            unit = unit_t.strip(" 　") or unit_from_qty
            if not unit and qty is None and qty_t:
                unit = qty_t.strip(" 　")

            text_keys = {norm_key(t) for t in (name, spec, no_t, date_t, rem_t) if t}
            # 小計・合計行（どの列に「小計」があっても拾う）
            if text_keys & SUBTOTAL_NAMES and qty is None:
                if amount is not None:
                    page_sub = as_int_if_whole(amount)
                after_table = True  # 小計以降の行は表の外（挨拶文など）
                continue
            if text_keys & set(TOTAL_KEYWORDS) and qty is None:
                if amount is not None:
                    page_sub = as_int_if_whole(amount)
                continue
            if not name and not spec and amount is None and unit_price is None and qty is None:
                if rem_t or no_t or date_t:
                    lines.append({"page": pno, "kind": "note", "text": row_text(r)})
                continue
            if amount is None and unit_price is None and qty is None and not unit:
                lines.append({"page": pno, "kind": "header", "text": name if name else spec,
                              "spec": spec if name else ""})
                continue
            item = {
                "page": pno,
                "kind": "item",
                "no": no_t or "",
                "name": name,
                "spec": spec,
                "qty": as_int_if_whole(qty),
                "unit": unit,
                "unit_price": as_int_if_whole(unit_price),
                "amount": as_int_if_whole(amount),
                "remarks": rem_t,
            }
            if amount is None and qty is not None and unit_price is not None:
                item["amount"] = as_int_if_whole(qty * unit_price)
                warnings.append(f"p{pno} {name!r}: 金額が無いため 数量×単価 で補いました")
            if amount is not None and qty and unit_price is not None and abs(qty * unit_price - amount) > 0.5:
                warnings.append(f"p{pno} {name!r}: 数量×単価({qty}×{unit_price})≠金額({amount}) — 要確認")
            if not name and not spec:
                warnings.append(f"p{pno} y={r.cy:.0f}: 名称が空の明細（金額 {item['amount']}）— 要確認")
            if item["amount"] is not None:
                page_sum += item["amount"]
            lines.append(item)
        page_subtotals.append(page_sub)
        if page_sub is not None and abs(page_sum - page_sub) > 0.5:
            warnings.append(f"p{pno}: 明細合計 {page_sum:,} と小計 {page_sub:,} が一致しません — 抽出漏れの可能性")

    # 最初の見出し行の直後に別の見出しが続く場合、最初の見出しは工事名（タイトル）とみなす
    first_hdr = next((i for i, l in enumerate(lines) if l["kind"] != "note"), None)
    if first_hdr is not None and lines[first_hdr]["kind"] == "header":
        nxt = next((l for l in lines[first_hdr + 1 :] if l["kind"] != "note"), None)
        if nxt is not None and nxt["kind"] == "header":
            lines[first_hdr]["kind"] = "title"

    meta = extract_meta(meta_rows, pages[0].width if pages else 595.0)
    meta["page_subtotals"] = page_subtotals
    meta["title"] = next((l["text"] for l in lines if l["kind"] == "title"), None)
    items_total = sum(l["amount"] or 0 for l in lines if l["kind"] == "item")
    meta["items_total"] = items_total
    grand = next((meta["totals"][k] for k in ("合計金額", "税抜合計", "小計", "合計", "御見積金額", "見積金額")
                  if k in meta["totals"]), None)
    if grand is not None and abs(grand - items_total) > 0.5:
        warnings.append(f"明細合計 {items_total:,} が PDF の合計 {grand:,} と一致しません — 抽出漏れ/誤読の可能性")
    subs = [s for s in page_subtotals if s is not None]
    if subs and grand is None and abs(sum(subs) - items_total) > 0.5:
        warnings.append(f"明細合計 {items_total:,} が 各ページ小計の和 {sum(subs):,} と一致しません")

    return {
        "source_pdf": path,
        "backend": used,
        "pages": len(pages),
        "meta": meta,
        "lines": lines,
        "warnings": warnings,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="見積書PDF → 明細JSON")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default=None, help="出力JSON（省略時は標準出力）")
    ap.add_argument("--backend", default="auto", choices=["auto", "pdfplumber", "pypdfium2"])
    ap.add_argument("--debug", action="store_true", help="行ごとの列振り分けを標準エラーに表示")
    args = ap.parse_args()

    result = extract(args.pdf, args.backend, args.debug)
    js = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
        n_items = sum(1 for l in result["lines"] if l["kind"] == "item")
        n_hdr = sum(1 for l in result["lines"] if l["kind"] in ("header", "title"))
        print(f"書き出し: {args.out}  明細 {n_items} 行 / 見出し {n_hdr} 行 / 明細合計 {result['meta']['items_total']:,} 円 "
              f"/ backend={result['backend']}")
        for w in result["warnings"]:
            print("  警告:", w)
    else:
        print(js)


if __name__ == "__main__":
    main()
