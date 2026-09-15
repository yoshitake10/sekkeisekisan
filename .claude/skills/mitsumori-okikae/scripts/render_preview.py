#!/usr/bin/env python3
"""
render_preview.py — xlsx を LibreOffice で PDF 化し、各ページを PNG にして目視確認用に出力する。

使い方:
    python3 render_preview.py 見積書.xlsx [--outdir preview] [--scale 1.6]

- LibreOffice (soffice) が無い環境では PDF 化をスキップしてその旨を表示する
- フォント: テンプレートの HGSｺﾞｼｯｸM が無い環境では代替フォントで描画される（配置確認用）
- 元の xlsx は書き換えない（LibreOffice で再保存すると図形が失われることがあるため、必ずコピーで扱う）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def to_pdf(xlsx: Path, outdir: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("soffice が見つからないため PDF 化をスキップします", file=sys.stderr)
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lo_profile_") as prof, tempfile.TemporaryDirectory(prefix="lo_in_") as tmpin:
        # 入力はコピーを渡す（元ファイルを触らせない）
        src = Path(tmpin) / xlsx.name
        shutil.copy2(xlsx, src)
        env = dict(os.environ, SAL_USE_VCLPLUGIN="svp")
        cmd = [soffice, f"-env:UserInstallation={Path(prof).as_uri()}", "--headless", "--convert-to", "pdf",
               "--outdir", str(outdir), str(src)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
        pdf = outdir / (xlsx.stem + ".pdf")
        if not pdf.exists():
            print("PDF 化に失敗:", r.stdout, r.stderr, file=sys.stderr)
            return None
        return pdf


def to_png(pdf: Path, outdir: Path, scale: float) -> list[Path]:
    import pypdfium2 as pdfium  # type: ignore

    doc = pdfium.PdfDocument(str(pdf))
    outs = []
    for i in range(len(doc)):
        img = doc[i].render(scale=scale).to_pil()
        p = outdir / f"{pdf.stem}_p{i + 1}.png"
        img.save(p)
        outs.append(p)
    return outs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--outdir", default="preview")
    ap.add_argument("--scale", type=float, default=1.6)
    a = ap.parse_args()
    xlsx = Path(a.xlsx)
    outdir = Path(a.outdir)
    pdf = to_pdf(xlsx, outdir)
    if pdf is None:
        sys.exit(1)
    print("PDF:", pdf)
    try:
        for p in to_png(pdf, outdir, a.scale):
            print("PNG:", p)
    except ImportError:
        print("pypdfium2 が無いため PNG 化はスキップ（PDF を直接確認してください）", file=sys.stderr)


if __name__ == "__main__":
    main()
