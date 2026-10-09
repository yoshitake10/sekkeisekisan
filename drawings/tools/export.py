"""JWW → A3ベクターPDF / DXF 書出し（確認・提出・他CAD用）

  python3 export.py <in.jww> <out.pdf> [<out.dxf>]

PDF: JWW上のA1(1/50)座標をA3(1/100)に0.5倍で配置。建築ベース(グループ0・1)は灰色、
     設備(グループ2)はJw_cad線色で着色。
DXF: 実寸mm（1単位=50mm）で出力。レイヤ名は「グループ番号-レイヤ番号」。
"""
import math
import sys

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

import jww

import os

from reportlab.pdfbase.ttfonts import TTFont

# 日本語TTF（IPAexゴシック等）があれば埋め込む。無ければ非埋込CIDフォント。
_TTF = [os.environ.get('JP_TTF', ''), '/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf', 'C:/Windows/Fonts/msgothic.ttc']
_ttf = next((p for p in _TTF if p and os.path.exists(p)), None)
if _ttf:
    pdfmetrics.registerFont(TTFont('JP', _ttf))
    FONT = 'JP'
else:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    FONT = 'HeiseiKakuGo-W5'
MM = 72 / 25.4
COLORS = {1: (0, .6, .7), 2: (0, 0, 0), 3: (0, .55, 0), 4: (.75, .6, 0), 5: (.8, 0, .7), 6: (0, 0, .85),
          7: (0, .5, .5), 8: (.85, 0, 0), 9: (.5, .5, .5)}
BASE_GRAY = (.45, .45, .45)
DASH = {1: None, 2: [3, 1.5], 3: [1.5, 1], 4: [0.6, 0.8], 5: [4, 1, 0.6, 1], 6: [4, 1, 0.6, 1],
        9: [4, 1, 0.6, 1, 0.6, 1]}


def walk(f):
    """(entity, 変換関数) を列挙（ブロックは展開）"""
    blocks = {b['num']: b for b in f.blocks}

    def rec(e, xf):
        if e['cls'] == 'CDataBlock':
            b = blocks.get(e['num'])
            if not b:
                return
            ca, sa = math.cos(e['rot']), math.sin(e['rot'])

            def xf2(x, y, e=e, xf=xf, ca=ca, sa=sa):
                x, y = x * e['sx'], y * e['sy']
                return xf(e['x'] + x * ca - y * sa, e['y'] + x * sa + y * ca)
            for s in b['items']:
                yield from rec(s, xf2)
        elif e['cls'] == 'CDataSunpou':
            yield from rec(dict(e['sen'], cls='CDataSen'), xf)
            yield from rec(dict(e['moji'], cls='CDataMoji'), xf)
        else:
            yield e, xf
    for e in f.entities:
        yield from rec(e, lambda x, y: (x, y))


def arc_pts(e, xf, n=72):
    st, ar = (0.0, 2 * math.pi) if e['full'] else (e['start'], e['arc'])
    pts = []
    for i in range(n + 1):
        a = st + ar * i / n
        lx, ly = e['r'] * math.cos(a), e['r'] * e['flat'] * math.sin(a)
        t = e['tilt']
        pts.append(xf(e['cx'] + lx * math.cos(t) - ly * math.sin(t), e['cy'] + lx * math.sin(t) + ly * math.cos(t)))
    return pts


def to_pdf(f, out, title='', equip_groups=(2,)):
    W, H = landscape(A3)
    c = canvas.Canvas(out, pagesize=(W, H))
    c.setTitle(title)
    k = 0.5 * MM  # A1座標[mm] → A3[pt]
    T = lambda x, y: (W / 2 + x * k, H / 2 + y * k)
    # 建築ベース → 設備 の順に描く
    ents = list(walk(f))
    for equip in (False, True):
        for e, xf in ents:
            if (e['glayer'] in equip_groups) != equip:
                continue
            col = COLORS.get(e['pen_color'], (0, 0, 0)) if equip else BASE_GRAY
            c.setStrokeColorRGB(*col); c.setFillColorRGB(*col)
            c.setLineWidth(0.35 if equip else 0.15)
            d = DASH.get(e['pen_style'])
            c.setDash(d if d else [])
            cls = e['cls']
            if cls == 'CDataSen':
                c.line(*T(*xf(e['x1'], e['y1'])), *T(*xf(e['x2'], e['y2'])))
            elif cls == 'CDataEnko':
                p = c.beginPath()
                pts = [T(*q) for q in arc_pts(e, xf)]
                p.moveTo(*pts[0])
                for q in pts[1:]:
                    p.lineTo(*q)
                c.drawPath(p, stroke=1, fill=0)
            elif cls == 'CDataSolid':
                q = e['pts']
                pts = [T(*xf(q[0], q[1])), T(*xf(q[4], q[5])), T(*xf(q[6], q[7])), T(*xf(q[2], q[3]))]
                p = c.beginPath(); p.moveTo(*pts[0])
                for q2 in pts[1:]:
                    p.lineTo(*q2)
                p.close()
                c.drawPath(p, stroke=0, fill=1)
            elif cls == 'CDataMoji':
                x, y = T(*xf(e['x1'], e['y1']))
                x2, y2 = T(*xf(e['x2'], e['y2']))
                size = e['sy'] * k
                if size <= 0 or not e['text'].strip():
                    continue
                ang = e['angle'] + math.degrees(math.atan2(*reversed([a - b for a, b in zip(T(*xf(1, 0)), T(*xf(0, 0)))])))
                L = math.hypot(x2 - x, y2 - y)
                tw = pdfmetrics.stringWidth(e['text'], FONT, size)
                c.saveState(); c.translate(x, y); c.rotate(ang)
                t = c.beginText(); t.setFont(FONT, size)
                if L > 0 and tw > 0:
                    t.setHorizScale(100.0 * L / tw)
                t.setTextOrigin(0, size * 0.12); t.textOut(e['text']); c.drawText(t)
                c.restoreState()
    c.showPage(); c.save()


def to_dxf(f, out):
    import ezdxf
    doc = ezdxf.new('R2010', setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    S = 50.0
    aci = {1: 4, 2: 7, 3: 3, 4: 2, 5: 6, 6: 5, 7: 4, 8: 1, 9: 8}
    style = doc.styles.new('JP', dxfattribs={'font': 'msgothic.ttc'})
    for e, xf in walk(f):
        lay = '%X-%X' % (e['glayer'], e['layer'])
        if lay not in doc.layers:
            doc.layers.add(lay)
        at = {'layer': lay, 'color': aci.get(e['pen_color'], 7)}
        cls = e['cls']
        if cls == 'CDataSen':
            a, b = xf(e['x1'], e['y1']), xf(e['x2'], e['y2'])
            msp.add_line((a[0] * S, a[1] * S), (b[0] * S, b[1] * S), dxfattribs=at)
        elif cls == 'CDataEnko':
            pts = [(x * S, y * S) for x, y in arc_pts(e, xf)]
            msp.add_lwpolyline(pts, dxfattribs=at)
        elif cls == 'CDataSolid':
            q = e['pts']
            pts = [xf(q[0], q[1]), xf(q[4], q[5]), xf(q[6], q[7]), xf(q[2], q[3])]
            msp.add_solid([(x * S, y * S) for x, y in (pts[0], pts[1], pts[3], pts[2])], dxfattribs=at)
        elif cls == 'CDataMoji' and e['text'].strip():
            x, y = xf(e['x1'], e['y1']); x2, y2 = xf(e['x2'], e['y2'])
            ang = e['angle'] + math.degrees(math.atan2(*reversed([a - b for a, b in zip(xf(1, 0), xf(0, 0))])))
            t = msp.add_text(e['text'], dxfattribs=dict(at, height=e['sy'] * S, rotation=ang, style='JP'))
            t.set_placement((x * S, y * S))
    doc.saveas(out)


if __name__ == '__main__':
    f = jww.JwwFile(sys.argv[1])
    to_pdf(f, sys.argv[2], title=sys.argv[2].rsplit('/', 1)[-1])
    if len(sys.argv) > 3:
        to_dxf(f, sys.argv[3])
