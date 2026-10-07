#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空調設備図 F-02-1（吉野家 呉海岸店 新設工事、1/50・A3）の冷媒管・ドレン管 平面延長の実測
==========================================================================================
図面はモノクロ。灰色(0.574)=建築背景、黒(0.0)=設備。配管・リモコン線・ダクトは黒 線幅0.72pt。
端点が接する線分を連結して「線群」にし、位置で系統を判別する（図面固有の判別なので図面改訂時は要確認）。
縮尺: 通り芯 Y6-Y5 910mm ＝ 51.6pt ほか → 1pt ＝ 17.64mm（A3で1/50）。

使い方: python3 takeoff_f02.py <換気空調機器表.pdf（2ページ目がF-02-1）> <出力ディレクトリ>
出力: takeoff_f02.json（系統別延長）、takeoff_F02_冷媒ドレン.png（拾い根拠画像）
"""
import json
import math
import os
import subprocess
import sys
from collections import defaultdict

import pdfplumber
from PIL import Image, ImageDraw, ImageFont

MM_PER_PT = 17.64
K = MM_PER_PT / 1000.0          # pt → m
PAGE = 1                        # 0始まり: 2ページ目が F-02-1 空調設備図
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'

# 系統の判別（線群の外接矩形 pt: x0, y0, x1, y1 の目安）。図面上の「R」「D」記号と口径ラベルで確認済み
EXPECT = {
    'R_AC1_W': ((453, 167, 794, 460), '冷媒 AC-1 室外機(架台下段)→客席西 天井カセット φ9.52/15.88'),
    'R_AC1_E': ((794, 138, 843, 509), '冷媒 AC-1 室外機(架台上段)→客席東 天井カセット φ9.52/15.88'),
    'R_AC2':   ((538, 167, 737, 390), '冷媒 AC-2 室外機(架台下段)→天井ビルトイン φ9.52/15.88'),
    'R_RAC':   ((397, 163, 723, 270), '冷媒 RAC 室外機(架台上段)→店長室 壁掛 φ6.35/9.52'),
    'D_MAIN':  ((431, 311, 833, 448), 'ドレン 主管＋AC-2枝（40A/30A/25A）'),
    'D_AC1_W': ((470, 448, 491, 469), 'ドレン 客席西カセット枝 25A'),
    'D_RAC':   ((416, 306, 432, 313), 'ドレン RAC 25A（店長室 壁際 接続立上りまで）'),
}
X_WEST_TEE = 485.1   # 西カセット枝の合流点（主管 40A/30A の境）
X_AC2_TEE = 678.4    # AC-2 枝の合流点（主管 30A/25A の境）
Y_MAIN = 447.9       # ドレン主管（天井内 横引き）
Y_WALL = 196.0       # 外壁（通り芯 Y6）。これより北(小さいy)は屋外


def load_segments(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    p = pdf.pages[PAGE]
    segs = []
    for o in p.lines + p.curves:
        if str(o.get('stroking_color')) != '0.0' or round(o.get('linewidth', 0), 2) != 0.72:
            continue
        pts = o['pts']
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, b) > 0.01:
                segs.append((tuple(a), tuple(b)))
    return p, segs


def chains(segs, tol=0.6):
    n = len(segs)
    par = list(range(n))

    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    grid = defaultdict(list)
    for i, (a, b) in enumerate(segs):
        for pt in (a, b):
            grid[(round(pt[0] / tol), round(pt[1] / tol))].append(i)
    for i, (a, b) in enumerate(segs):
        for pt in (a, b):
            gx, gy = round(pt[0] / tol), round(pt[1] / tol)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid[(gx + dx, gy + dy)]:
                        sa, sb = segs[j]
                        if min(math.dist(pt, sa), math.dist(pt, sb)) <= tol:
                            par[f(i)] = f(j)
    groups = defaultdict(list)
    for i in range(n):
        groups[f(i)].append(segs[i])
    out = []
    for g in groups.values():
        xs = [c for s in g for c in (s[0][0], s[1][0])]
        ys = [c for s in g for c in (s[0][1], s[1][1])]
        out.append(dict(segs=g, bbox=(min(xs), min(ys), max(xs), max(ys)),
                        L=sum(math.dist(*s) for s in g)))
    return out


def pick(chs, bbox):
    def d(c):
        return sum(abs(u - v) for u, v in zip(c['bbox'], bbox))
    best = min(chs, key=d)
    assert d(best) < 8, f'線群が見つからない（図面改訂？）: {bbox} 最近傍 {best["bbox"]}'
    return best


def clip_len(s, x0, x1):
    """水平線分のうち x0〜x1 の部分の長さ"""
    (ax, ay), (bx, by) = s
    lo, hi = max(min(ax, bx), x0), min(max(ax, bx), x1)
    return max(0.0, hi - lo)


def outside_len(s):
    """外壁（Y6）より北＝屋外部分の長さ（縦・横線分のみ）"""
    (ax, ay), (bx, by) = s
    if abs(ay - by) < 0.01:   # 水平
        return math.dist((ax, ay), (bx, by)) if ay < Y_WALL else 0.0
    lo, hi = min(ay, by), max(ay, by)
    return max(0.0, min(hi, Y_WALL) - lo) if abs(ax - bx) < 0.01 else (math.dist((ax, ay), (bx, by)) if hi < Y_WALL else 0.0)


def main():
    pdf_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    page, segs = load_segments(pdf_path)
    chs = chains(segs)
    sel = {k: pick(chs, bb) for k, (bb, _) in EXPECT.items()}
    res = {}
    for k in ('R_AC1_W', 'R_AC1_E', 'R_AC2', 'R_RAC'):
        c = sel[k]
        res[k] = dict(desc=EXPECT[k][1], plan_m=round(c['L'] * K, 2),
                      outside_m=round(sum(outside_len(s) for s in c['segs']) * K, 2))
    # ドレン主管を口径別に分割
    d40 = d30 = d25 = 0.0
    ac2_branch = 0.0
    for s in sel['D_MAIN']['segs']:
        (ax, ay), (bx, by) = s
        L = math.dist(*s)
        horiz_main = abs(ay - Y_MAIN) < 0.3 and abs(by - Y_MAIN) < 0.3
        if horiz_main:
            d40 += clip_len(s, 0, X_WEST_TEE)
            d30 += clip_len(s, X_WEST_TEE, X_AC2_TEE)
            d25 += clip_len(s, X_AC2_TEE, 9999)
        elif min(ax, bx) > 655:            # AC-2 枝（縦・横）
            ac2_branch += L
        elif max(ax, bx) <= X_WEST_TEE:    # 西側の縦主管・接続点への横引き・曲がり
            d40 += L
        else:
            d30 += L
    res['D'] = dict(
        desc='ドレン（平面実測、m）',
        main_40A=round(d40 * K, 2), main_30A=round(d30 * K, 2), main_25A_east=round(d25 * K, 2),
        branch_25A_AC2=round(ac2_branch * K, 2), branch_25A_AC1W=round(sel['D_AC1_W']['L'] * K, 2),
        branch_25A_RAC=round(sel['D_RAC']['L'] * K, 2))
    res['scale'] = f'1pt = {MM_PER_PT}mm（A3 1/50、通り芯間隔で確認）'
    json.dump(res, open(os.path.join(out_dir, 'takeoff_f02.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))

    # ---- 拾い根拠画像 ----
    dpi = 150
    S = dpi / 72.0
    tmp = os.path.join(out_dir, '_f02_bg')
    subprocess.run(['pdftoppm', '-r', str(dpi), '-f', str(PAGE + 1), '-l', str(PAGE + 1), '-png', '-singlefile', pdf_path, tmp], check=True)
    bg = Image.open(tmp + '.png').convert('L').point(lambda v: 150 + v * 105 // 255).convert('RGB')
    os.remove(tmp + '.png')
    d = ImageDraw.Draw(bg)
    col = {'R_AC1_W': (0, 150, 0), 'R_AC1_E': (0, 110, 60), 'R_AC2': (20, 170, 120), 'R_RAC': (120, 170, 0),
           'D_MAIN': (0, 70, 220), 'D_AC1_W': (0, 70, 220), 'D_RAC': (0, 70, 220)}
    for k, c in sel.items():
        for a, b in c['segs']:
            d.line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=col[k], width=5)
    f = ImageFont.truetype(FONT, 26)
    fs = ImageFont.truetype(FONT, 22)
    lab = [
        ('R_AC1_W', (470, 425), f"AC-1(西) 平面{res['R_AC1_W']['plan_m']}m"),
        ('R_AC1_E', (808, 300), f"AC-1(東) 平面{res['R_AC1_E']['plan_m']}m"),
        ('R_AC2', (545, 247), f"AC-2 平面{res['R_AC2']['plan_m']}m"),
        ('R_RAC', (420, 232), f"RAC 平面{res['R_RAC']['plan_m']}m"),
        ('D_MAIN', (478, 360), f"D40A {res['D']['main_40A']}m"),
        ('D_MAIN', (560, 452), f"D30A {res['D']['main_30A']}m"),
        ('D_MAIN', (720, 452), f"D25A {res['D']['main_25A_east']}m"),
    ]
    for k, (x, y), t in lab:
        w = d.textlength(t, font=f)
        d.rectangle([x * S - 3, y * S - 3, x * S + w + 3, y * S + 30], fill=(255, 255, 255))
        d.text((x * S, y * S), t, fill=col[k], font=f)
    crop = (int(230 * S), int(40 * S), int(1010 * S), int(640 * S))
    img = bg.crop(crop)
    d2 = ImageDraw.Draw(img)
    legend = ['拾い根拠: 空調設備図 F-02-1（1/50）ベクトル線の平面延長（立上り・立下り・余長は別途加算）',
              '緑系=冷媒管（AC-1×2・AC-2: φ9.52/15.88、RAC: φ6.35/9.52）　青=ドレン管（40A/30A/25A）',
              'リモコンケーブル・ダクト（AC-2→吹出しパンカー）は本見積の範囲外のため着色なし']
    for i, t in enumerate(legend):
        d2.rectangle([10, 10 + i * 30, 20 + d2.textlength(t, font=fs), 36 + i * 30], fill=(255, 255, 255))
        d2.text((14, 12 + i * 30), t, fill=(0, 0, 0), font=fs)
    img.save(os.path.join(out_dir, 'takeoff_F02_冷媒ドレン.png'), optimize=True)


if __name__ == '__main__':
    main()
