#!/bin/sh
# 安楽寺本堂 空調・換気設備図一式を再生成する
#   JWW(M-1,M-2) → PDF/DXF、24時間換気計算書 xlsx → PDF(LibreOffice)
# 日本語フォント埋込みには JP_TTF=<IPAexゴシック等のttf> を指定する。
set -e
cd "$(dirname "$0")"
D="../安楽寺本堂_空調換気"
python3 make_drawings.py "$D/source/平面図_8-20_da3-100.jww" "$D"
for n in M-1_空調設備平面図 M-2_換気設備平面図; do
  python3 export.py "$D/$n.jww" "$D/$n.pdf" "$D/$n.dxf"
done
python3 make_calc.py "$D/24時間換気計算書.xlsx"
(cd "$D" && soffice --headless --calc --convert-to pdf "24時間換気計算書.xlsx" --outdir . >/dev/null 2>&1)
echo done
