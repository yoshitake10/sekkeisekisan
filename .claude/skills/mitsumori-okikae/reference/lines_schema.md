# lines.json の形

`extract_estimate_pdf.py` の出力。スキャン PDF などで自動抽出できないときは、この形で手作りしてから `build_estimate_xlsx.py` に渡す。

```json
{
  "source_pdf": "元見積.pdf",
  "meta": {
    "date_text": "令和8年9月15日", "date_iso": "2026-09-15",
    "customer": "有限会社 原田製麵", "vendor": "株式会社 空創", "title": "エアコン更新工事",
    "totals": {"合計金額": 2450000, "消費税額": 245000, "今回ご見積額": 2695000},
    "page_subtotals": [1698830, 751170], "items_total": 2450000
  },
  "lines": [
    {"page": 1, "kind": "title",  "text": "エアコン更新工事"},
    {"page": 1, "kind": "header", "text": "機器）三菱電機製　ビル用マルチエアコン"},
    {"page": 1, "kind": "item",   "name": "　　室外機　PUHY-SGRP280DM", "spec": "",
                                  "qty": 1, "unit": "台", "unit_price": null, "amount": 907500, "remarks": ""},
    {"page": 1, "kind": "item",   "name": "1）旧商品撤去処分", "qty": 1, "unit": "式", "unit_price": null, "amount": 80000},
    {"page": 2, "kind": "note",   "text": "ありがとうございます"}
  ],
  "warnings": []
}
```

## kind
| kind | 意味 | 生成側の扱い |
|---|---|---|
| title | 工事名などのタイトル行（最初の見出しの直後に別の見出しが続くとき） | 表紙・内訳の【…】行。`--cover-title` で上書き可 |
| header | 区分見出し（金額の無い行） | ［…］行。区分（表紙の集計単位）の始まり |
| item | 明細 | 明細行。`name` 先頭の「1）」などの番号は外し、区分の始まりとみなす |
| note | 表の外の文（挨拶文など） | 無視 |

## item の項目
- `qty` が無い（null）行は数量 1 扱いにはならず、金額ベースで計算する（`G` 列は空）
- `unit_price` がある行は 単価ベース（`I` に数式、`K = G×I`）、無い行は 金額ベース（`K` に数式）
- `amount` がマイナス、または名称に「値引」を含む行は、それ自体を 1 つの区分として表紙に載せる
- 名称先頭の全角スペースは字下げとして扱い、生成時に最大 2 個に丸める
