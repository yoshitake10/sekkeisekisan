"""安楽寺 本堂 空調設備平面図(M-1)・換気設備平面図(M-2) を JWW で作図する

原本の建築平面図JWW（レイヤグループ0・1）はそのまま残し、
レイヤグループ2 に設備図形を追記する。

  python3 make_drawings.py <原本.jww> <出力フォルダ>
"""
import copy
import math
import os
import struct
import sys
import unicodedata

import jww
import project_data as P

FONT = 'ＭＳ ゴシック'
# Jw_cad 標準線色
C_BLACK, C_GREEN, C_YELLOW, C_PINK, C_BLUE, C_CYAN, C_RED, C_GRAY = 2, 3, 4, 5, 6, 7, 8, 9
# 線種
S_SOLID, S_DOT, S_DASH, S_CHAIN = 1, 2, 3, 5


def text_width(s, sx, kankaku=0.0):
    n = sum(1.0 if unicodedata.east_asian_width(c) in 'FWA' else 0.5 for c in s)
    return sx * n + kankaku * max(len(s) - 1, 0)


class Sheet:
    def __init__(self, src, glayer=2):
        self.f = jww.JwwFile(src)
        self.g = glayer
        self.new = []

    # -- primitives -------------------------------------------------------
    def _b(self, layer, color, style=S_SOLID):
        return jww.base(layer, self.g, color, style)

    def line(self, x1, y1, x2, y2, layer, color, style=S_SOLID):
        d = self._b(layer, color, style); d.update(cls='CDataSen', x1=x1, y1=y1, x2=x2, y2=y2)
        self.new.append(d)

    def poly(self, pts, layer, color, style=S_SOLID, close=False):
        pts = list(pts)
        if close:
            pts.append(pts[0])
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], layer, color, style)

    def rect(self, x1, y1, x2, y2, layer, color, style=S_SOLID):
        self.poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer, color, style, close=True)

    def circle(self, cx, cy, r, layer, color, style=S_SOLID):
        d = self._b(layer, color, style)
        d.update(cls='CDataEnko', cx=cx, cy=cy, r=r, start=0.0, arc=2 * math.pi, tilt=0.0, flat=1.0, full=1)
        self.new.append(d)

    def solid(self, pts, layer, color):
        (x1, y1), (x2, y2), (x3, y3), (x4, y4) = pts
        d = self._b(layer, color); d.update(cls='CDataSolid', pts=[x1, y1, x4, y4, x2, y2, x3, y3])
        self.new.append(d)

    def text(self, x, y, s, size, layer, color=C_BLACK, angle=0.0, align='l'):
        sx, sy = size, round(size * 1.15, 3)
        w = text_width(s, sx)
        a = math.radians(angle)
        if align == 'c':
            x, y = x - w / 2 * math.cos(a), y - w / 2 * math.sin(a)
        elif align == 'r':
            x, y = x - w * math.cos(a), y - w * math.sin(a)
        d = self._b(layer, color)
        d.update(cls='CDataMoji', x1=x, y1=y, x2=x + w * math.cos(a), y2=y + w * math.sin(a), type=0,
                 sx=sx, sy=sy, kankaku=0.0, angle=float(angle), font=FONT, text=s)
        self.new.append(d)

    def arrow(self, x1, y1, x2, y2, layer, color, head=2.2, style=S_SOLID, fill=True):
        self.line(x1, y1, x2, y2, layer, color, style)
        a = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2 - head * math.cos(a - 0.4), y2 - head * math.sin(a - 0.4))
        p2 = (x2 - head * math.cos(a + 0.4), y2 - head * math.sin(a + 0.4))
        if fill:
            self.solid([(x2, y2), p1, p2, p2], layer, color)
        else:
            self.line(x2, y2, *p1, layer, color); self.line(x2, y2, *p2, layer, color)

    def leader(self, x1, y1, x2, y2, label_lines, size, layer, color=C_BLACK, side='r'):
        """引出線＋文字（x2,y2 から水平に書出し）"""
        self.line(x1, y1, x2, y2, layer, color)
        w = max(text_width(s, size) for s in label_lines)
        if side == 'r':
            self.line(x2, y2, x2 + w + 1, y2, layer, color)
            tx = x2 + 0.5
        else:
            self.line(x2, y2, x2 - w - 1, y2, layer, color)
            tx = x2 - w - 0.5
        for i, s in enumerate(label_lines):
            self.text(tx, y2 + 0.8 - i * size * 1.45 if i else y2 + 0.8, s, size, layer, color)

    # -- 表 ------------------------------------------------------------------
    def table(self, x, y, cols, rows, size, layer, row_h=None, header_rows=1, color=C_BLACK):
        """cols: [(幅, align)], rows: [[文字...]]  左上(x,y)から下へ。罫線付き。戻り値: 下端y"""
        row_h = row_h or size * 1.9
        W = sum(c[0] for c in cols)
        yy = y
        self.line(x, yy, x + W, yy, layer, color)
        for ri, r in enumerate(rows):
            y2 = yy - row_h
            xx = x
            for (w, al), s in zip(cols, r):
                if s:
                    if al == 'c':
                        self.text(xx + w / 2, y2 + (row_h - size) / 2 + 0.2, s, size, layer, color, align='c')
                    elif al == 'r':
                        self.text(xx + w - 0.8, y2 + (row_h - size) / 2 + 0.2, s, size, layer, color, align='r')
                    else:
                        self.text(xx + 0.8, y2 + (row_h - size) / 2 + 0.2, s, size, layer, color)
                xx += w
            self.line(x, y2, x + W, y2, layer, color)
            if ri == header_rows - 1:
                self.line(x, y2 + 0.4, x + W, y2 + 0.4, layer, color)
            yy = y2
        xx = x
        for w, _ in cols:
            self.line(xx, y, xx, yy, layer, color); xx += w
        self.line(xx, y, xx, yy, layer, color)
        return yy

    # -- ヘッダ（レイヤ名・書込みグループ）----------------------------------
    def set_layer_names(self, gname, names):
        h = bytearray(self.f.header)
        # 書込みレイヤグループ
        struct.pack_into('<I', h, 24, self.g)
        gsize = 4 + 4 + 8 + 4 + 16 * 8
        for g in range(16):
            off = 28 + g * gsize
            st = struct.unpack_from('<I', h, off)[0]
            if st == 3:
                struct.pack_into('<I', h, off, 2)
        struct.pack_into('<I', h, 28 + self.g * gsize, 3)
        # 文字列: m_aStrLayName[16][16] + m_aStrGLayName[16]
        start = 2552
        r = jww.R(bytes(h), start)
        strs = [r.cstr() for _ in range(272)]
        end = r.p
        for i, n in enumerate(names):
            strs[self.g * 16 + i] = n
        strs[256 + self.g] = gname
        w = jww.W()
        for s in strs:
            w.cstr(s)
        self.f.header = bytes(h[:start]) + bytes(w.a) + bytes(h[end:])

    def replace_text(self, old, new, size=None, ymax=None):
        n = 0
        for e in self.f.entities:
            if e['cls'] == 'CDataMoji' and e['text'] == old and (ymax is None or e['y1'] < ymax):
                e['text'] = new
                if size:
                    e['sx'] = size; e['sy'] = round(size * 1.15, 3)
                w = text_width(new, e['sx'])
                a = math.radians(e['angle'])
                e['x2'] = e['x1'] + w * math.cos(a); e['y2'] = e['y1'] + w * math.sin(a)
                n += 1
        assert n, old

    def save(self, path):
        self.f.entities = self.f.entities + self.new
        self.f.save(path)


# ===========================================================================
# 共通: 表題欄・方位以外の注記
# ===========================================================================
def title_block(sh, name, no):
    sh.replace_text(' 平 面 図 ', name, size=4.0, ymax=-250)
    sh.replace_text('3', no, size=3.4, ymax=-250)
    sh.replace_text('7', '2', size=3.4, ymax=-250)


def wall_hood(sh, x, y, wall, layer, color, label=None):
    """外壁貫通部の外部フード記号（壁の外側に小三角）"""
    axis, v = wall
    if axis == 'x':
        sgn = 1 if v > x else -1
        sh.poly([(v, y - 2.0), (v + sgn * 3.0, y), (v, y + 2.0)], layer, color)
    else:
        sgn = 1 if v > y else -1
        sh.poly([(x - 2.0, v), (x, v + sgn * 3.0), (x + 2.0, v)], layer, color)


def duct_route(x, y, wall):
    axis, v = wall
    return [(x, y), (v, y)] if axis == 'x' else [(x, y), (x, v)]


# ===========================================================================
# M-1 空調設備平面図
# ===========================================================================
def make_m1(src, out):
    sh = Sheet(src)
    L_IU, L_OU, L_REF, L_DR, L_TX, L_TBL, L_NOTE = 0, 1, 2, 3, 4, 5, 6
    sh.set_layer_names('空調設備', ['室内機', '室外機', '冷媒配管', 'ドレン配管', '記号・文字', '機器表', '凡例・特記',
                                 '', '', '', '', '', '', '', '', ''])
    title_block(sh, '空調設備平面図', 'M-1')

    def iu_floor(x1, y1, x2, y2, tag):
        sh.rect(x1, y1, x2, y2, L_IU, C_PINK)
        sh.line(x2 - 1.2, y1, x2 - 1.2, y2, L_IU, C_PINK)           # 吹出し面
        for k in range(3):                                           # 吹出しルーバー
            yy = y1 + (y2 - y1) * (k + 1) / 4
            sh.arrow(x2 + 0.5, yy, x2 + 5.5, yy, L_IU, C_PINK, head=1.6)

    def iu_wall(x1, y1, x2, y2, front):
        sh.rect(x1, y1, x2, y2, L_IU, C_PINK)
        if front == 'down':
            sh.line(x1, y1 + 1.2, x2, y1 + 1.2, L_IU, C_PINK)
            sh.arrow((x1 + x2) / 2, y1 - 0.5, (x1 + x2) / 2, y1 - 6.0, L_IU, C_PINK, head=1.6)
        elif front == 'left':
            sh.line(x1 + 1.2, y1, x1 + 1.2, y2, L_IU, C_PINK)
            sh.arrow(x1 - 0.5, (y1 + y2) / 2, x1 - 6.0, (y1 + y2) / 2, L_IU, C_PINK, head=1.6)

    def ou(cx, cy, w, d, vertical):
        if vertical:
            x1, x2, y1, y2 = cx - d / 2, cx + d / 2, cy - w / 2, cy + w / 2
        else:
            x1, x2, y1, y2 = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2
        sh.rect(x1, y1, x2, y2, L_OU, C_PINK)
        sh.circle(cx, cy, min(w, d) * 0.36, L_OU, C_PINK)
        sh.line(cx - min(w, d) * 0.36, cy, cx + min(w, d) * 0.36, cy, L_OU, C_PINK)
        sh.line(cx, cy - min(w, d) * 0.36, cx, cy + min(w, d) * 0.36, L_OU, C_PINK)

    def pipe(pts, dpts=None):
        sh.poly(pts, L_REF, C_GREEN)
        if dpts:
            sh.poly(dpts, L_DR, C_BLUE, S_DASH)

    ac1, ac2, ac3 = P.AC
    # ---- AC-1 ×2 床置形（外陣 西側 広縁沿い）----------------------------------
    for i, cy in enumerate((17.0, 1.0)):
        x1, x2 = -156.2, -156.2 + ac1['iu'][1]
        iu_floor(x1, cy - ac1['iu'][0] / 2, x2, cy + ac1['iu'][0] / 2, 'AC-1')
        ocx = -175.0
        ou(ocx, cy, ac1['ou'][0], ac1['ou'][1], vertical=True)
        pipe([(x1 + 1.5, cy + 2.0), (ocx + 3.0, cy + 2.0)], [(x1 + 1.5, cy - 2.5), (ocx + 3.0, cy - 2.5), (ocx + 3.0, cy - 7.4)])
        sh.text(x2 + 7.0, cy + 0.6, 'AC-1-%d' % (i + 1), 3.4, L_TX, C_PINK)
        sh.text(ocx - 3.4, cy + 8.6, 'OU-1-%d' % (i + 1), 2.6, L_TX, C_PINK)
    sh.leader(-150.0, 26.0, -140.0, 40.0, ['AC-1 SZRV80BZV 床置形 ×2台', '（大間・外陣 冷7.1kW×2）'], 3.4, L_TX, C_PINK)

    # ---- AC-2 和室(1) 壁掛（北面 = 図面上側の外壁）--------------------------
    cx = 58.0
    iu_wall(cx - 8.0, 149.5 - 5.4, cx + 8.0, 149.5, 'down')
    ou(cx, 157.5, ac2['ou'][0], ac2['ou'][1], vertical=False)
    pipe([(cx - 3.0, 145.0), (cx - 3.0, 154.6)], [(cx + 4.0, 145.0), (cx + 4.0, 152.0), (cx + 10.0, 152.0)])
    sh.text(cx - 9.0, 135.0, 'AC-2', 3.4, L_TX, C_PINK)
    sh.text(cx + 7.6, 160.0, 'OU-2-1', 2.6, L_TX, C_PINK)

    # ---- AC-2 和室(2) 壁掛（東面 = 図面右側の外壁）---------------------------
    cy = 55.0
    iu_wall(184.04 - 5.4, cy - 8.0, 184.04, cy + 8.0, 'left')
    ou(193.0, cy, ac2['ou'][0], ac2['ou'][1], vertical=True)
    pipe([(181.0, cy + 3.0), (190.2, cy + 3.0)], [(181.0, cy - 4.0), (188.0, cy - 4.0), (188.0, cy - 10.0)])
    sh.text(166.0, cy - 12.0, 'AC-2', 3.4, L_TX, C_PINK)
    sh.text(196.6, cy - 4.0, 'OU-2-2', 2.6, L_TX, C_PINK)

    # ---- AC-3 談話室 壁掛（東面）---------------------------------------------
    cy = 100.0
    iu_wall(184.04 - 5.4, cy - 8.0, 184.04, cy + 8.0, 'left')
    ou(193.0, cy, ac3['ou'][0], ac3['ou'][1], vertical=True)
    pipe([(181.0, cy + 3.0), (190.2, cy + 3.0)], [(181.0, cy - 4.0), (188.0, cy - 4.0), (188.0, cy - 10.0)])
    sh.text(166.0, cy - 12.0, 'AC-3', 3.4, L_TX, C_PINK)
    sh.text(196.6, cy - 4.0, 'OU-3', 2.6, L_TX, C_PINK)

    # ---- 機器表（左余白）------------------------------------------------------
    x0, y0 = -400.0, 186.0
    sh.text(x0, y0 - 6, '空調機器表', 5.0, L_TBL)
    cols = [(13, 'c'), (63, 'l'), (9, 'c'), (21, 'l')]
    rows = [['記号', '名称・型式・仕様', '台数', '設置場所']]
    for a in P.AC:
        nm = a['name'].split('（')
        rows += [[a['sym'], nm[0], '%d' % a['qty'], a['place'].split('・')[0]],
                 ['', ('（' + nm[1]) if len(nm) > 1 else '', '', a['place'].split('・')[1] if '・' in a['place'] else ''],
                 ['', '%s %s' % (a['maker'], a['model']), '', ''],
                 ['', a['cap'], '', ''],
                 ['', '%s %s' % (a['power'], a['remote']), '', ''],
                 ['', '冷媒管 %s' % a['pipe'], '', '']]
    yb = sh.table(x0, y0 - 9, cols, rows, 3.1, L_TBL, row_h=5.6)
    for i, s in enumerate(['※機種は8月10日付 検討最終VE案', '　（提案① ダイキン）による。',
                           '※室外機の組合せ型番・外形寸法は', '　承認図にて確認のこと。']):
        sh.text(x0, yb - 6 - i * 4.8, s, 3.0, L_TBL)

    # ---- 凡例・特記（右余白）-------------------------------------------------
    x0, y0 = 318.0, 262.0
    sh.text(x0, y0, '凡  例', 5.0, L_NOTE)
    y = y0 - 10
    sh.rect(x0, y - 1.5, x0 + 10, y + 3, L_NOTE, C_PINK); sh.line(x0 + 8.8, y - 1.5, x0 + 8.8, y + 3, L_NOTE, C_PINK)
    sh.text(x0 + 14, y, '室内機（床置形・壁掛形）', 3.4, L_NOTE)
    y -= 9
    sh.rect(x0, y - 2, x0 + 10, y + 4, L_NOTE, C_PINK); sh.circle(x0 + 5, y + 1, 2.1, L_NOTE, C_PINK)
    sh.text(x0 + 14, y, '室外機', 3.4, L_NOTE)
    y -= 9
    sh.line(x0, y + 1, x0 + 10, y + 1, L_NOTE, C_GREEN); sh.text(x0 + 14, y, '冷媒配管（被覆銅管）', 3.4, L_NOTE)
    y -= 8
    sh.line(x0, y + 1, x0 + 10, y + 1, L_NOTE, C_BLUE, S_DASH); sh.text(x0 + 14, y, 'ドレン配管', 3.4, L_NOTE)
    y -= 16
    sh.text(x0, y, '特記事項', 5.0, L_NOTE)
    notes = [
        '1.機器は元請支給品とし、据付・',
        '  配管・試運転調整を本工事とする。',
        '2.冷媒配管：被覆銅管（保温材付）。',
        '  屋外露出部は化粧カバー仕上げ。',
        '  気密試験・真空乾燥を行う。',
        '3.ドレン配管：AC-1はVP25（断熱',
        '  被覆）、AC-2・3は付属ホース延長。',
        '  屋外放流、勾配1/100以上。',
        '4.電源（単相200V専用回路）・',
        '  コンセントは電気設備工事とする。',
        '5.室外機はプラスチック製架台',
        '  （防振ゴム付）据付とする。',
        '6.外壁貫通部はスリーブ＋シーリング',
        '  により防水処理を行う。',
        '7.機器位置は仏具・建具配置と',
        '  調整の上決定する。',
        '8.換気設備はM-2換気設備平面図による。',
    ]
    y -= 8
    for s in notes:
        sh.text(x0, y, s, 3.2, L_NOTE); y -= 5.4
    sh.save(out)
    return sh


# ===========================================================================
# M-2 換気設備平面図（シックハウス対策 24時間換気）
# ===========================================================================
def make_m2(src, out, calc):
    sh = Sheet(src)
    L_F24, L_FL, L_SA, L_DUCT, L_PATH, L_TX, L_TBL, L_NOTE = 0, 1, 2, 3, 4, 5, 6, 7
    sh.set_layer_names('換気設備', ['換気扇(24h)', '換気扇(局所)', '給気口', 'ダクト・フード', '換気経路', '記号・文字',
                                 '機器表', '計算表・特記', '', '', '', '', '', '', '', ''])
    title_block(sh, '換気設備平面図', 'M-2')

    def fan(x, y, color, layer):
        sh.rect(x - 3, y - 3, x + 3, y + 3, layer, color)
        sh.circle(x, y, 2.2, layer, color)
        for a in (0, 120, 240):
            r = math.radians(a)
            sh.line(x, y, x + 2.2 * math.cos(r), y + 2.2 * math.sin(r), layer, color)

    def grille(x, y):
        sh.rect(x - 3, y - 3, x + 3, y + 3, L_SA, C_GREEN)
        for k in (-1.5, 0, 1.5):
            sh.line(x - 3, y + k, x + 3, y + k, L_SA, C_GREEN)

    def duct(x, y, wall, color, start_off=3.0, label=None):
        (ax, ay), (bx, by) = duct_route(x, y, wall)
        # 器具の外形から立上げ
        if ax == bx:
            sgn = 1 if by > ay else -1
            ay += sgn * start_off
        else:
            sgn = 1 if bx > ax else -1
            ax += sgn * start_off
        sh.line(ax, ay, bx, by, L_DUCT, color)
        wall_hood(sh, x, y, wall, L_DUCT, color)
        if label:
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if ax == bx:
                sh.text(mx + 1.0, my, label, 2.4, L_DUCT, color, angle=90.0, align='c')
            else:
                sh.text(mx, my + 0.8, label, 2.4, L_DUCT, color, align='c')

    # ---- 24時間換気 EF-1 パイプ用ファン（外壁貫通・壁付）-----------------------
    def pipefan(x, y, wall, color, layer):
        axis, v = wall
        sgn = 1 if v > (x if axis == 'x' else y) else -1
        if axis == 'x':
            bx = v - sgn * 1.0                      # 本体は外壁内面に取付
            sh.rect(min(bx, bx - sgn * 5.0), y - 3.2, max(bx, bx - sgn * 5.0), y + 3.2, layer, color)
            sh.circle(bx - sgn * 2.5, y, 2.0, layer, color)
            for a in (0, 120, 240):
                r = math.radians(a)
                sh.line(bx - sgn * 2.5, y, bx - sgn * 2.5 + 2.0 * math.cos(r), y + 2.0 * math.sin(r), layer, color)
            for k in (-1.6, 1.6):                   # 壁貫通パイプ φ100
                sh.line(bx, y + k, v, y + k, L_DUCT, color)
        else:
            by = v - sgn * 1.0
            sh.rect(x - 3.2, min(by, by - sgn * 5.0), x + 3.2, max(by, by - sgn * 5.0), layer, color)
            sh.circle(x, by - sgn * 2.5, 2.0, layer, color)
            for k in (-1.6, 1.6):
                sh.line(x + k, by, x + k, v, L_DUCT, color)
        wall_hood(sh, x, y, wall, L_DUCT, color)

    for u in P.FAN24_UNITS:
        pipefan(u['x'], u['y'], u['wall'], C_RED, L_F24)
        sh.text(u['x'] - 5.5, u['y'] + 3.6, 'EF-1', 3.0, L_TX, C_RED, align='r')
    f = P.FAN24
    sh.leader(186.0, -37.0, 200.0, -18.0, ['EF-1 %s ×%d台' % (f['model'], len(P.FAN24_UNITS)),
                                          'パイプファン 24時間常時運転',
                                          '有効換気量 %.0fm³/h/台(%dHz)' % (calc['q_eff'], P.HZ)], 3.4, L_TX, C_RED)

    # ---- 給気口 SA -------------------------------------------------------------
    for s in P.SUPPLY:
        for (room, x, y, wall) in s['units']:
            grille(x, y)
            duct(x, y, wall, C_GREEN, label=s['duct'])
            sh.text(x + 3.6, y + 3.6, s['sym'], 3.0, L_TX, C_GREEN)

    # ---- 局所換気 ---------------------------------------------------------------
    for s in P.LOCAL:
        for (room, x, y, wall) in s['units']:
            fan(x, y, C_BLUE, L_FL)
            duct(x, y, wall, C_BLUE, label=s['duct'])
            sh.text(x - 3.6, y + 3.6, s['sym'], 3.0, L_TX, C_BLUE, align='r')

    # ---- 換気経路（アンダーカット）-------------------------------------------
    paths = [
        (-118.0, 36.0, -118.0, 21.0),      # 護摩堂→外陣
        (10.0, 48.0, 26.0, 48.0),          # 内陣→北廊下
        (60.0, 75.0, 60.0, 61.0),          # 和室(1)→北廊下
        (78.0, 50.0, 93.0, 50.0),          # 北廊下→東廊下
        (95.0, 76.0, 95.0, 62.0),          # 談話室→東廊下
        (97.0, 131.0, 97.0, 120.0),        # パントリー→談話室
        (115.0, 40.0, 100.0, 40.0),        # 和室(2)→東廊下
        (76.0, -20.0, 94.0, -20.0),        # 外陣→東廊下
        (96.0, -8.0, 112.0, -8.0),         # 東廊下→ホール
        (125.0, -36.0, 125.0, -20.0),      # 玄関→ホール
        (139.0, 2.0, 152.0, 2.0),          # ホール→便所(女)
        (139.0, -18.0, 152.0, -18.0),      # ホール→手洗い
        (165.0, -21.0, 165.0, -33.0),      # 手洗い→小便所
        (165.0, -40.0, 165.0, -52.0),      # 小便所→便所(男)
    ]
    for p in paths:
        sh.arrow(*p, L_PATH, C_RED, head=2.4, style=S_DOT)
    # 給気→室内の流れ（外陣 長手方向）
    sh.arrow(-140.0, 18.0, -60.0, 18.0, L_PATH, C_RED, head=2.4, style=S_DOT)
    sh.arrow(-50.0, 18.0, 30.0, 18.0, L_PATH, C_RED, head=2.4, style=S_DOT)
    sh.arrow(90.0, 30.0, 90.0, 0.0, L_PATH, C_RED, head=2.4, style=S_DOT)
    sh.text(-100.0, 20.5, '換気経路（建具アンダーカット10mm以上）', 3.0, L_PATH, C_RED)

    # ---- 機器表（左余白）------------------------------------------------------
    x0, y0 = -400.0, 186.0
    sh.text(x0, y0 - 6, '換気機器表', 5.0, L_TBL)
    cols = [(12, 'c'), (64, 'l'), (9, 'c'), (21, 'l')]
    f = P.FAN24
    rows = [['記号', '名称・型式・仕様', '台数', '設置場所'],
            ['EF-1', '%s（24時間換気用）' % f['name'][:7], '%d' % len(P.FAN24_UNITS), '便所(女)'],
            ['', '%s %s %s' % (f['maker'], f['model'], f['spec'][:5]), '', '小便所'],
            ['', 'φ100 壁付 有効換気量%.0fm³/h' % calc['q_eff'], '', '便所(男)'],
            ['', '%s %.1fW(%dHz) 常時運転' % (f['power'], f['watt'][P.HZ], P.HZ), '', '']]
    place = {'SA-1': ['外陣×3', '内陣×1'], 'SA-2': ['護摩堂'], 'SA-3': ['和室(1)', '和室(2)', '談話室'],
             'EF-2': ['外陣×3', '内陣×1', '護摩堂×1'], 'EF-3': ['談話室'], 'EF-4': ['パントリー']}
    for s in P.SUPPLY + P.LOCAL:
        pl = place[s['sym']] + ['', '']
        kind = '外気給気' if s['sym'].startswith('SA') else '局所換気'
        rows += [[s['sym'], '%s（%s）' % (s['name'], kind), '%d' % len(s['units']), pl[0]],
                 ['', '%s %s%s' % (P.MAKER_VENT, s['model'], '（%s）' % s['color'] if s['color'] else ''), '', pl[1]],
                 ['', '%s ダクト%s' % (s['spec'], s['duct']), '', pl[2]]]
    yb = sh.table(x0, y0 - 9, cols, rows, 3.0, L_TBL, row_h=5.3)
    for i, s in enumerate(['※外壁フード：ステンレス製深型（防虫網付）', '※EF-2〜4（局所換気）は必要有効換気量に',
                           '　算入しない。', '※型式・性能は三菱電機 納入仕様書・',
                           '　P-Q線図による（電源周波数60Hz）。']):
        sh.text(x0, yb - 5.5 - i * 4.6, s, 2.9, L_TBL)

    # ---- 凡例 --------------------------------------------------------------------
    x0, y0 = 318.0, -40.0
    y = y0
    sh.text(x0, y, '凡  例', 5.0, L_NOTE)
    y -= 10
    sh.rect(x0 + 1.5, y - 2.2, x0 + 6.5, y + 4.2, L_NOTE, C_RED); sh.circle(x0 + 4, y + 1, 2.0, L_NOTE, C_RED)
    sh.text(x0 + 11, y, 'パイプファン（24時間換気用）', 3.3, L_NOTE)
    y -= 9
    fan(x0 + 4, y + 1, C_BLUE, L_NOTE); sh.text(x0 + 11, y, '換気扇（局所換気用）', 3.3, L_NOTE)
    y -= 9
    grille(x0 + 4, y + 1); sh.text(x0 + 11, y, '給気口（外気導入グリル）', 3.3, L_NOTE)
    y -= 9
    sh.line(x0, y + 1, x0 + 7, y + 1, L_NOTE, C_GREEN); sh.poly([(x0 + 7, y - 1), (x0 + 10, y + 1), (x0 + 7, y + 3)], L_NOTE, C_GREEN)
    sh.text(x0 + 11, y, 'ダクト・外壁フード', 3.3, L_NOTE)
    y -= 9
    sh.arrow(x0, y + 1, x0 + 9, y + 1, L_NOTE, C_RED, head=2.2, style=S_DOT)
    sh.text(x0 + 11, y, '換気経路（UC・ガラリ）', 3.3, L_NOTE)

    # ---- 24時間換気 計算表（右余白）---------------------------------------------
    x0, y0 = 318.0, 266.0
    sh.text(x0, y0, '24時間換気 計算表', 5.0, L_TBL)
    sh.text(x0, y0 - 5.5, '令20条の8 第3種機械換気（全館一体）', 2.9, L_TBL)
    cols = [(23, 'l'), (12, 'r'), (13, 'c'), (14, 'r'), (7, 'r'), (12, 'r')]
    rows = [['室  名', 'A㎡', 'h m', 'V m³', 'n', 'Vr']]
    for g in calc['groups']:
        rows.append([g['name'], '%.2f' % g['A'], g['h'], '%.2f' % g['V'], '%.1f' % g['n'], '%.1f' % g['Vr']])
    rows.append(['合  計', '%.2f' % calc['sumA'], '', '%.2f' % calc['sumV'], '', '%.1f' % calc['sumVr']])
    yb = sh.table(x0, y0 - 9, cols, rows, 2.7, L_TBL, row_h=5.0)
    y = yb - 6.5
    lines = [
        ('必要有効換気量 Vr＝Σ n·A·h', C_BLACK), ('　　　　　　　＝%.1f m³/h' % calc['sumVr'], C_BLACK),
        ('有効換気量 Ve＝%.0f×%d台' % (calc['q_eff'], len(P.FAN24_UNITS)), C_BLACK),
        ('　　　　　　　＝%.1f m³/h' % calc['Ve'], C_BLACK),
        ('（EF-1 P-Q線図 %dHz 相当長%.1fm）' % (P.HZ, calc['eq_len']), C_BLACK),
        ('判定 Ve≧Vr …… OK（%.2f倍）' % (calc['Ve'] / calc['sumVr']), C_RED),
        ('n：本堂部0.3、庫裏側0.5（安全側）', C_BLACK),
        ('h：天井高は仮定値（要確認）', C_BLACK),
    ]
    for s, c in lines:
        sh.text(x0, y, s, 3.1, L_TBL, c); y -= 5.0
    y -= 5
    sh.text(x0, y, '特記事項（シックハウス対策）', 4.2, L_NOTE)
    notes = [
        '1.EF-1(パイプファン)は24時間常時',
        '  運転とし、スイッチに表示を行う。',
        '2.建具アンダーカット：居室・廊下',
        '  10mm以上（有効開口100cm²以上）、',
        '  便所20mm以上又はガラリとする。',
        '3.内装仕上げはF☆☆☆☆材とする。',
        '4.天井裏等（令20条の9）は建材に',
        '  よる措置（F☆☆☆以上）とする。',
        '5.収納（物置・物入・押入）は換気',
        '  経路外とし、F☆☆☆☆材とする。',
        '6.天井高確定後に再計算すること。',
        '7.詳細は別添 24時間換気計算書による。',
    ]
    y -= 7
    for s in notes:
        sh.text(x0, y, s, 3.1, L_NOTE); y -= 5.0
    sh.save(out)
    return sh


if __name__ == '__main__':
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    make_m1(src, os.path.join(outdir, 'M-1_空調設備平面図.jww'))
    make_m2(src, os.path.join(outdir, 'M-2_換気設備平面図.jww'), P.calc_summary())
    print('ok')
