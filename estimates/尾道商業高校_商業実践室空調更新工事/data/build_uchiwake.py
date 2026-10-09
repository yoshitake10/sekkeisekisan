# -*- coding: utf-8 -*-
"""尾道商業高校 商業実践室空調更新工事
提出済み 御見積書（見積番号 6330515-2）の明細を、学校指定の様式「仕様書（工事内訳書）」の
区分（①空調設備機器 ②空調設備工事 ③アスベスト含有調査）に振り分けて記入する。

  python3 build_uchiwake.py <出力先ディレクトリ>

出力（どちらも 合計 1,800,000 円（税別）＝提出済み見積と同額）
  工事内訳書_..._値引按分.xlsx       様式どおり（値引行なし）。出精値引 -641,500 を全項目に同率で按分
  工事内訳書_..._出精値引行あり.xlsx  各項目は見積書の金額のまま、計③ の下に「出精値引」行を追加

様式ファイルは openpyxl で開き直すと秘密度ラベル（docMetadata/LabelInfo.xml）・customXml・
プリンタ設定が落ちるので、ZIP 内の XML だけを書き換える。
"""
import os
import sys
import zipfile
from copy import deepcopy

from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "様式_仕様書(工事内訳書).xlsx")
BASENAME = "工事内訳書_尾道商業高校_商業実践室空調更新工事_6330515-2"

ESTIMATE_TOTAL = 1_800_000   # 提出済み見積の合計（税別）
DISCOUNT = -641_500          # 提出済み見積の 8 出精値引
TAX_RATE = "0.1"             # 消費税 10%（様式の 消費税 欄に数式で入れる）
HEADER_NOTE = "見積番号 6330515-2　宮地機工株式会社"

# ---------------------------------------------------------------------------
# 提出済み見積書（PDF 6330515-2）の明細。金額は税別・値引前。（ ）内は PDF の頁
# ---------------------------------------------------------------------------
SRC = {
    # 1 空調設備機器（p2）機器合計 1,655,000
    "1.SSRH280DD 天井吊形": 1_610_000,
    "1.BRC1G4 運転リモコン": 23_000,
    "1.BRE50B2F センシングユニット 2式": 22_000,
    # 2 空調設備工事（p2）計 198,000
    "2.搬入据付工事": 53_750,
    "2.基礎工事": 7_500,
    "2.リモコン配線工事": 9_630,
    "2.揚重工事費（レッカー費等）": 56_250,
    "2.試運転調整費": 12_500,
    "2.冷媒回収処理費": 31_250,
    "2.消耗品及び雑材料": 5_200,
    "2.資材運搬交通費": 7_100,
    "2.現場経費": 14_820,
    # 3 配管設備工事（p3）計 343,000
    "3.冷媒用被覆銅管 9.52+15.88 2m": 8_050,
    "3.冷媒用被覆銅管 12.70+25.40 2m": 11_350,
    "3.冷媒 継手類": 23_933,
    "3.冷媒 消耗品": 11_967,
    "3.冷媒 支持金物": 31_910,
    "3.排水 VP20A 2m": 450,
    "3.排水 継手類": 90,
    "3.排水 消耗品": 45,
    "3.排水 支持金物": 113,
    "3.VVF 2.0mm-3C 10m（内外連絡線）": 2_030,
    "3.配管工費(冷媒配管)": 100_170,
    "3.配管工費(塩ビ管類)": 4_190,
    "3.電線材料施工費": 9_600,
    "3.配管保温工事費": 32_250,
    "3.配管切廻接続費(冷媒/ドレン)": 23_750,
    "3.配管切廻接続費(ラッキング)": 8_750,
    "3.配線切廻接続費": 3_750,
    "3.気密テスト費": 12_500,
    "3.真空引き・ガス充填": 2_500,
    "3.消耗品及び雑材料": 8_700,
    "3.資材運搬費": 14_900,
    "3.現場経費": 32_002,
    # 4 アスベスト事前調査（p3）計 75,000
    "4.アスベスト事前調査": 75_000,
    # 5 電気設備工事（p3-4）計 38,000
    "5.電源線脱着作業": 31_250,
    "5.消耗品及び雑材料": 1_000,
    "5.資材運搬交通費": 1_700,
    "5.現場経費": 4_050,
    # 6 撤去工事（p4）計 95,000
    "6.既設機器撤去工事費": 81_250,
    "6.消耗品及び雑材料": 2_500,
    "6.資材運搬交通費": 3_400,
    "6.現場経費": 7_850,
    # 7 工事諸経費（p4）計 37,500
    "7.工事諸経費": 37_500,
}
PDF_SECTION_TOTALS = {"1": 1_655_000, "2": 198_000, "3": 343_000, "4": 75_000,
                      "5": 38_000, "6": 95_000, "7": 37_500}

# PDF は アスベスト事前調査 1式 のみ。様式の5行へは次の内訳で割り付ける（調査会社の内訳で要確認）
ASBESTOS_SPLIT = {29: 44_000, 30: 16_000, 31: 3_000, 32: 5_000, 33: 7_000}

PIPING = [k for k in SRC if k.startswith("3.") and k not in (
    "3.配管保温工事費", "3.配管切廻接続費(ラッキング)",
    "3.消耗品及び雑材料", "3.資材運搬費", "3.現場経費")]

# 様式の行: (数量, 振り分ける PDF 明細, 規格欄に書く内容 or None)
#   数量は様式に記入済みの値（E 列）。単価 G ＝ 金額 ÷ 数量。
ROWS = {
    # ① 空調設備機器
    7: (1, ["1.SSRH280DD 天井吊形"], None),
    8: (1, ["1.BRC1G4 運転リモコン"], None),
    9: (2, ["1.BRE50B2F センシングユニット 2式"], None),
    # ② 空調設備工事（PDF の 2 空調設備・3 配管設備・5 電気設備・6 撤去・7 工事諸経費）
    13: (1, ["2.搬入据付工事"], None),
    14: (1, ["2.基礎工事"], None),
    15: (1, ["2.リモコン配線工事"], None),
    16: (1, PIPING, "冷媒管・ドレン管・内外連絡線"),
    17: (1, ["2.揚重工事費（レッカー費等）"], "揚重（レッカー等）"),
    18: (1, ["6.既設機器撤去工事費"], None),
    19: (1, ["3.配管保温工事費", "3.配管切廻接続費(ラッキング)"], "保温・ラッキング切廻し"),
    20: (1, ["5.電源線脱着作業"], "電源線脱着"),
    21: (1, ["2.試運転調整費"], None),
    22: (1, ["2.冷媒回収処理費"], None),
    23: (1, ["2.消耗品及び雑材料", "3.消耗品及び雑材料",
             "5.消耗品及び雑材料", "6.消耗品及び雑材料"], None),
    24: (1, ["2.資材運搬交通費", "3.資材運搬費",
             "5.資材運搬交通費", "6.資材運搬交通費"], None),
    25: (1, ["2.現場経費", "3.現場経費", "5.現場経費", "6.現場経費",
             "7.工事諸経費"], "現場経費・工事諸経費"),
    # ③ アスベスト含有調査（ASBESTOS_SPLIT で割付）
    29: (2, ["4.アスベスト事前調査"], None),
    30: (2, ["4.アスベスト事前調査"], None),
    31: (1, ["4.アスベスト事前調査"], None),
    32: (1, ["4.アスベスト事前調査"], None),
    33: (1, ["4.アスベスト事前調査"], None),
}
SECTIONS = {10: [7, 8, 9], 26: list(range(13, 26)), 34: list(range(29, 34))}


def gross_amounts():
    """様式の各行の値引前金額（＝PDF の金額の合計）"""
    out = {}
    for r, (_, keys, _) in ROWS.items():
        out[r] = ASBESTOS_SPLIT[r] if r in ASBESTOS_SPLIT else sum(SRC[k] for k in keys)
    return out


def check_source():
    for sec, total in PDF_SECTION_TOTALS.items():
        s = sum(v for k, v in SRC.items() if k.startswith(sec + "."))
        assert s == total, (sec, s, total)
    assert sum(SRC.values()) + DISCOUNT == ESTIMATE_TOTAL
    assert sum(ASBESTOS_SPLIT.values()) == SRC["4.アスベスト事前調査"]
    used = [k for r, (_, keys, _) in ROWS.items() if r not in ASBESTOS_SPLIT for k in keys]
    assert sorted(used) == sorted(k for k in SRC if not k.startswith("4.")), "振り分け漏れ／重複"
    g = gross_amounts()
    assert sum(g.values()) == sum(SRC.values())
    for r, (qty, _, _) in ROWS.items():
        assert g[r] % qty == 0, (r, g[r], qty)


def unit_prices_gross():
    g = gross_amounts()
    return {r: g[r] // ROWS[r][0] for r in ROWS}


def unit_prices_prorated():
    """出精値引を全行に同率で按分。単価は 100 円単位に丸め、端数は ACP-1（7 行）で調整"""
    g = gross_amounts()
    gross_total = sum(g.values())
    unit = {}
    for r, (qty, _, _) in ROWS.items():
        unit[r] = round(g[r] / qty * ESTIMATE_TOTAL / gross_total, -2)
        unit[r] = int(unit[r])
    diff = ESTIMATE_TOTAL - sum(unit[r] * ROWS[r][0] for r in ROWS)
    unit[7] += diff
    assert sum(unit[r] * ROWS[r][0] for r in ROWS) == ESTIMATE_TOTAL
    return unit


# ---------------------------------------------------------------------------
# xlsx（ZIP 内 XML）の書き換え
# ---------------------------------------------------------------------------
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
N = "{%s}" % NS


def col_index(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


class Sheet:
    def __init__(self, xml, sst_xml):
        self.root = etree.fromstring(xml)
        self.sst = etree.fromstring(sst_xml)
        self.sst_index = {}
        for i, si in enumerate(self.sst.findall(N + "si")):
            self.sst_index.setdefault("".join(si.itertext()), i)
        self.new_refs = 0

    def cell(self, ref):
        rnum = "".join(ch for ch in ref if ch.isdigit())
        sd = self.root.find(N + "sheetData")
        row = sd.find(f"{N}row[@r='{rnum}']")
        c = row.find(f"{N}c[@r='{ref}']")
        if c is None:
            c = etree.SubElement(row, N + "c", r=ref)
            cells = sorted(row.findall(N + "c"), key=lambda e: col_index(e.get("r")))
            for e in cells:
                row.remove(e)
                row.append(e)
        return c

    @staticmethod
    def _clear(c):
        for ch in list(c):
            c.remove(ch)
        c.attrib.pop("t", None)

    def number(self, ref, value, style=None):
        c = self.cell(ref)
        self._clear(c)
        etree.SubElement(c, N + "v").text = str(value)
        if style is not None:
            c.set("s", str(style))

    def formula(self, ref, f, cached):
        c = self.cell(ref)
        self._clear(c)
        etree.SubElement(c, N + "f").text = f
        etree.SubElement(c, N + "v").text = str(cached)

    def cached(self, ref, value):
        c = self.cell(ref)
        assert c.find(N + "f") is not None, ref
        v = c.find(N + "v")
        if v is None:
            v = etree.SubElement(c, N + "v")
        v.text = str(value)

    def string(self, ref, text):
        c = self.cell(ref)
        self._clear(c)
        if text not in self.sst_index:
            si = etree.SubElement(self.sst, N + "si")
            etree.SubElement(si, N + "t").text = text
            self.sst_index[text] = len(self.sst.findall(N + "si")) - 1
        c.set("t", "s")
        etree.SubElement(c, N + "v").text = str(self.sst_index[text])
        self.new_refs += 1

    def fit_to_one_page(self):
        sp = self.root.find(N + "sheetPr")
        if sp is None:
            sp = etree.Element(N + "sheetPr")
            self.root.insert(0, sp)
        psp = sp.find(N + "pageSetUpPr")
        if psp is None:
            psp = etree.SubElement(sp, N + "pageSetUpPr")
        psp.set("fitToPage", "1")
        ps = self.root.find(N + "pageSetup")
        ps.set("fitToWidth", "1")
        ps.set("fitToHeight", "1")

    def dump(self):
        self.sst.set("uniqueCount", str(len(self.sst.findall(N + "si"))))
        self.sst.set("count", str(int(self.sst.get("count", "0")) + self.new_refs))
        x = lambda e: etree.tostring(e, xml_declaration=True, encoding="UTF-8", standalone=True)
        return x(self.root), x(self.sst)


def add_minus_style(styles_xml):
    """金額欄の書式（xf 1）を複製し、負数を赤括弧ではなく -641,500 と表示する書式を追加"""
    root = etree.fromstring(styles_xml)
    nf = root.find(N + "numFmts")
    fid = max(int(e.get("numFmtId")) for e in nf) + 1
    etree.SubElement(nf, N + "numFmt", numFmtId=str(fid), formatCode="#,##0_);-#,##0_)")
    nf.set("count", str(len(nf)))
    xfs = root.find(N + "cellXfs")
    xf = deepcopy(xfs[1])
    xf.set("numFmtId", str(fid))
    xfs.append(xf)
    xfs.set("count", str(len(xfs)))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), len(xfs) - 1


def build(out_path, unit, with_discount_row):
    zin = zipfile.ZipFile(TEMPLATE)
    files = {i.filename: zin.read(i.filename) for i in zin.infolist()}
    infos = zin.infolist()

    sh = Sheet(files["xl/worksheets/sheet1.xml"], files["xl/sharedStrings.xml"])
    sh.string("E3", HEADER_NOTE)

    amount = {}
    for r, (qty, _, spec) in ROWS.items():
        sh.number(f"G{r}", unit[r])
        amount[r] = unit[r] * qty
        sh.cached(f"H{r}", amount[r])
        if spec:
            sh.string(f"D{r}", spec)
    for r, rows in SECTIONS.items():
        amount[r] = sum(amount[x] for x in rows)
        sh.cached(f"H{r}", amount[r])

    total = amount[10] + amount[26] + amount[34]
    if with_discount_row:
        styles_xml, minus_xf = add_minus_style(files["xl/styles.xml"])
        files["xl/styles.xml"] = styles_xml
        sh.string("B35", "　出精値引")
        sh.number("H35", DISCOUNT, style=minus_xf)
        total += DISCOUNT
        sh.formula("H36", "SUM(H10,H26,H34,H35)", total)
    else:
        sh.cached("H36", total)
    assert total == ESTIMATE_TOTAL, total

    tax = int(total * float(TAX_RATE))
    sh.formula("H38", f"ROUNDDOWN(H36*{TAX_RATE},0)", tax)
    sh.cached("H40", total + tax)
    sh.fit_to_one_page()
    files["xl/worksheets/sheet1.xml"], files["xl/sharedStrings.xml"] = sh.dump()

    # 数式を足したので calcChain は捨て、開いたときに全再計算させる
    files.pop("xl/calcChain.xml")
    files["xl/_rels/workbook.xml.rels"] = files["xl/_rels/workbook.xml.rels"].replace(
        b'<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" Target="calcChain.xml"/>', b"")
    files["[Content_Types].xml"] = files["[Content_Types].xml"].replace(
        b'<Override PartName="/xl/calcChain.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>', b"")
    assert b"calcChain" not in files["xl/_rels/workbook.xml.rels"] + files["[Content_Types].xml"]
    wb = files["xl/workbook.xml"]
    assert b'<calcPr calcId="191028"/>' in wb
    files["xl/workbook.xml"] = wb.replace(b'<calcPr calcId="191028"/>', b'<calcPr calcId="191028" fullCalcOnLoad="1"/>')

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in infos:
            if info.filename in files:
                zout.writestr(info, files[info.filename], compress_type=zipfile.ZIP_DEFLATED)
    return {"①": amount[10], "②": amount[26], "③": amount[34],
            "出精値引": DISCOUNT if with_discount_row else 0,
            "合計": total, "消費税": tax, "総合計": total + tax}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    check_source()
    variants = [("値引按分", unit_prices_prorated(), False),
                ("出精値引行あり", unit_prices_gross(), True)]
    for name, unit, disc in variants:
        path = os.path.join(out_dir, f"{BASENAME}_{name}.xlsx")
        res = build(path, unit, disc)
        print(name, path)
        for r in sorted(ROWS):
            print(f"  {r:>2} 単価 {unit[r]:>10,} × {ROWS[r][0]} = {unit[r] * ROWS[r][0]:>10,}")
        print("  ", "  ".join(f"{k} {v:,}" for k, v in res.items()))


if __name__ == "__main__":
    main()
