#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エブリイ舟入南店 リニューアル工事 空調図（A3 1/100）の冷媒管・ドレン管 平面延長の実測
======================================================================================
冷媒管＝黒 線幅0.66pt、ドレン管＝黒 線幅0.54pt（二重線で描画→延長は1/2）。
縮尺: 図面表記 A3-1/100 → 1pt＝35.28mm（寸法 3,000・4,000 の実測で確認）。
系統は線群の外接矩形で判別（図面固有。図面改訂時は要確認）。
使い方: python3 takeoff.py <空調図.pdf> <出力ディレクトリ>
"""
import json
import math
import os
import subprocess
import sys
from collections import defaultdict

import pdfplumber
from PIL import Image, ImageDraw, ImageFont

K = 35.28 / 1000.0
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
REF = {   # 冷媒（0.66）
    'R_GP140': ((254.6, 337.4, 612.6, 444.1), 'RAS-GP140RSH4 → RPCK-GP140KA（ベーカリー作業室）9.52/15.88'),
    'R_GP112': ((676.8, 337.4, 960.6, 419.9), 'RAS-GP112RSH4 → 分岐（同時ツイン主管）9.52/15.88'),
    'R_BR1': ((948.2, 419.9, 958.1, 448.0), '分岐 → RCI-GP56KA（北）6.35/12.70'),
    'R_BR2': ((948.3, 419.9, 960.0, 585.2), '分岐 → RCI-GP56KA（南）6.35/12.70'),
    'R_MV2': ((745.1, 627.2, 745.1, 767.7), '移設元2 → 移設先2 延長 9.52/15.88'),
}
DRN = {   # ドレン（0.54、二重線）
    'D_GP140': ((250.6, 337.4, 609.1, 444.1), 'RPCK-GP140KA → 外壁（屋外排出）'),
    'D_GP112': ((672.2, 335.9, 954.8, 567.1), 'RCI-GP56KA×2 → 外壁（屋外排出）'),
    'D_MV1': ((482.5, 420.1, 708.4, 420.1), '移設元1 → 移設先1 延長'),
    'D_MV2': ((742.0, 628.0, 742.0, 766.7), '移設元2 → 移設先2 延長'),
}
MV1_REF_Y = (413.0, 422.5)   # 移設1の冷媒延長は機器外形と同じ線群になるため、長い水平線だけを拾う


def segs_of(page, lw):
    out = []
    for o in page.lines + page.curves:
        if str(o.get('stroking_color')) != '0.0' or round(o.get('linewidth', 0), 2) != lw:
            continue
        for a, b in zip(o['pts'], o['pts'][1:]):
            if math.dist(a, b) > 0.01:
                out.append((tuple(a), tuple(b)))
    return out


def chains(segs, tol=0.6):
    par = list(range(len(segs)))

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
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid[(round(pt[0] / tol) + dx, round(pt[1] / tol) + dy)]:
                        if min(math.dist(pt, segs[j][0]), math.dist(pt, segs[j][1])) <= tol:
                            par[f(i)] = f(j)
    g = defaultdict(list)
    for i in range(len(segs)):
        g[f(i)].append(segs[i])
    out = []
    for v in g.values():
        xs = [c for s in v for c in (s[0][0], s[1][0])]
        ys = [c for s in v for c in (s[0][1], s[1][1])]
        out.append(dict(segs=v, bbox=(min(xs), min(ys), max(xs), max(ys)), L=sum(math.dist(*s) for s in v)))
    return out


def pick(chs, bb):
    best = min(chs, key=lambda c: sum(abs(u - v) for u, v in zip(c['bbox'], bb)))
    assert sum(abs(u - v) for u, v in zip(best['bbox'], bb)) < 8, f'線群が見つからない: {bb}'
    return best


def main():
    pdf_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    page = pdfplumber.open(pdf_path).pages[0]
    rs, ds = segs_of(page, 0.66), segs_of(page, 0.54)
    rch, dch = chains(rs), chains(ds)
    res, draw = {}, {}
    for k, (bb, desc) in REF.items():
        c = pick(rch, bb)
        res[k] = dict(desc=desc, plan_m=round(c['L'] * K, 2))
        draw[k] = c['segs']
    mv1 = [s for s in rs if abs(s[0][1] - s[1][1]) < 0.1 and MV1_REF_Y[0] < s[0][1] < MV1_REF_Y[1] and math.dist(*s) > 100]
    assert len(mv1) == 1, mv1
    res['R_MV1'] = dict(desc='移設元1 → 移設先1 延長 9.52/15.88', plan_m=round(math.dist(*mv1[0]) * K, 2))
    draw['R_MV1'] = mv1
    for k, (bb, desc) in DRN.items():
        c = pick(dch, bb)
        double = k in ('D_GP140', 'D_GP112')
        res[k] = dict(desc=desc, plan_m=round(c['L'] * K / (2 if double else 1), 2))
        draw[k] = c['segs']
    res['scale'] = '1pt = 35.28mm（A3 1/100）'
    json.dump(res, open(os.path.join(out_dir, 'takeoff.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    # 拾い根拠画像
    dpi = 150
    S = dpi / 72.0
    tmp = os.path.join(out_dir, '_bg')
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', pdf_path, tmp], check=True)
    bg = Image.open(tmp + '.png').convert('L').point(lambda v: 150 + v * 105 // 255).convert('RGB')
    os.remove(tmp + '.png')
    d = ImageDraw.Draw(bg)
    col = {'R_GP140': (0, 150, 0), 'R_GP112': (0, 110, 60), 'R_BR1': (130, 170, 0), 'R_BR2': (130, 170, 0),
           'R_MV1': (200, 100, 0), 'R_MV2': (200, 100, 0)}
    for k, segs in draw.items():
        c = col.get(k, (0, 70, 220))
        for a, b in segs:
            d.line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=c, width=5)
    f = ImageFont.truetype(FONT, 24)
    fs = ImageFont.truetype(FONT, 22)
    labels = [('R_GP140', (300, 352), f"冷媒 GP140 {res['R_GP140']['plan_m']}m"),
              ('R_GP112', (700, 352), f"冷媒 GP112主管 {res['R_GP112']['plan_m']}m"),
              ('R_BR2', (965, 500), f"分岐 {res['R_BR1']['plan_m']}+{res['R_BR2']['plan_m']}m"),
              ('R_MV1', (520, 398), f"移設1 延長 {res['R_MV1']['plan_m']}m"),
              ('R_MV2', (752, 690), f"移設2 延長 {res['R_MV2']['plan_m']}m"),
              ('D_GP140', (300, 386), f"ドレン25A {res['D_GP140']['plan_m']}m"),
              ('D_GP112', (700, 392), f"ドレン25A {res['D_GP112']['plan_m']}m")]
    for k, (x, y), t in labels:
        w = d.textlength(t, font=f)
        d.rectangle([x * S - 3, y * S - 3, x * S + w + 3, y * S + 28], fill=(255, 255, 255))
        d.text((x * S, y * S), t, fill=col.get(k, (0, 70, 220)), font=f)
    img = bg.crop((int(150 * S), int(150 * S), int(1060 * S), int(800 * S)))
    d2 = ImageDraw.Draw(img)
    for i, t in enumerate(['拾い根拠: 空調図（A3 1/100）ベクトル線の平面延長（立上り・立下り・余長は別途加算）',
                           '緑系=冷媒管 新設（9.52/15.88・分岐6.35/12.70）　橙=移設延長　青=ドレン管 25A']):
        d2.rectangle([10, 10 + i * 30, 20 + d2.textlength(t, font=fs), 36 + i * 30], fill=(255, 255, 255))
        d2.text((14, 12 + i * 30), t, fill=(0, 0, 0), font=fs)
    img.save(os.path.join(out_dir, 'takeoff_空調図_冷媒ドレン.png'), optimize=True)


if __name__ == '__main__':
    main()
