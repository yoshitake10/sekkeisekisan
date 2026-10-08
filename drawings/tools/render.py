"""JWW図形を簡易ラスタ化してPNG確認する（検図用）"""
import math
import sys
from PIL import Image, ImageDraw, ImageFont

import jww

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
COL = {1: (0, 200, 200), 2: (0, 0, 0), 3: (0, 160, 0), 4: (200, 160, 0), 5: (200, 0, 200),
       6: (0, 0, 220), 7: (0, 140, 140), 8: (220, 0, 0), 9: (120, 120, 120)}


def color(e):
    c = e['pen_color']
    if c in COL:
        return COL[c]
    return (90, 90, 90)


def render(f, out, px_per_mm=3, bbox=None, only=None):
    ents = list(f.entities)
    blocks = {b['num']: b for b in f.blocks}
    if bbox is None:
        bbox = (-421, -298, 421, 298)
    x0, y0, x1, y1 = bbox
    W, H = int((x1 - x0) * px_per_mm), int((y1 - y0) * px_per_mm)
    im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im)
    T = lambda x, y: ((x - x0) * px_per_mm, (y1 - y) * px_per_mm)
    fonts = {}

    def font(sz):
        sz = max(6, int(sz))
        if sz not in fonts:
            fonts[sz] = ImageFont.truetype(FONT, sz)
        return fonts[sz]

    def draw(e, xf):
        c = e['cls']; col = color(e)
        if only and not only(e):
            return
        if c == 'CDataSen':
            dr.line([T(*xf(e['x1'], e['y1'])), T(*xf(e['x2'], e['y2']))], fill=col, width=1)
        elif c == 'CDataEnko':
            pts = []
            n = 48
            st, ar = (0, 2 * math.pi) if e['full'] else (e['start'], e['arc'])
            for i in range(n + 1):
                a = st + ar * i / n
                lx, ly = e['r'] * math.cos(a), e['r'] * e['flat'] * math.sin(a)
                t = e['tilt']
                pts.append(T(*xf(e['cx'] + lx * math.cos(t) - ly * math.sin(t), e['cy'] + lx * math.sin(t) + ly * math.cos(t))))
            dr.line(pts, fill=col, width=1)
        elif c == 'CDataSolid':
            p = e['pts']
            dr.polygon([T(*xf(p[0], p[1])), T(*xf(p[4], p[5])), T(*xf(p[6], p[7])), T(*xf(p[2], p[3]))], fill=col)
        elif c == 'CDataMoji':
            x, y = xf(e['x1'], e['y1'])
            X, Y = T(x, y)
            sz = e['sy'] * px_per_mm
            dr.text((X, Y - sz), e['text'], fill=col, font=font(sz))
        elif c == 'CDataBlock':
            b = blocks.get(e['num'])
            if not b:
                return
            ca, sa = math.cos(e['rot']), math.sin(e['rot'])

            def xf2(x, y, e=e, xf=xf):
                x, y = x * e['sx'], y * e['sy']
                return xf(e['x'] + x * ca - y * sa, e['y'] + x * sa + y * ca)
            for s in b['items']:
                draw(s, xf2)
        elif c == 'CDataSunpou':
            draw(dict(e['sen'], cls='CDataSen'), xf)
            draw(dict(e['moji'], cls='CDataMoji'), xf)

    for e in ents:
        draw(e, lambda x, y: (x, y))
    im.save(out)


if __name__ == '__main__':
    f = jww.JwwFile(sys.argv[1])
    bb = tuple(map(float, sys.argv[4].split(','))) if len(sys.argv) > 4 else None
    render(f, sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 3, bb)
