"""Jw_cad (.jww) 読み書きモジュール（Ver.7.00形式 / MFC CArchive 互換）

既存JWWのヘッダ部は原本バイト列をそのまま保持し、図形データ部
（図形リスト＋ブロック定義リスト）を解析・再シリアライズする。
これにより既存図面（建築平面図）を壊さずに設備図形を追記できる。
"""
import struct

NEW_CLASS = 0xFFFF
CLASS_TAG = 0x8000
BIG_OBJ_TAG = 0x7FFF


class R:
    def __init__(self, b, pos=0):
        self.b, self.p = b, pos

    def u8(self):
        v = self.b[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack_from('<H', self.b, self.p)[0]; self.p += 2; return v

    def u32(self):
        v = struct.unpack_from('<I', self.b, self.p)[0]; self.p += 4; return v

    def f64(self):
        v = struct.unpack_from('<d', self.b, self.p)[0]; self.p += 8; return v

    def raw(self, n):
        v = self.b[self.p:self.p + n]; self.p += n; return v

    def _len(self):
        n = self.u8()
        if n < 0xFF:
            return n
        n = self.u16()
        if n == 0xFFFE:
            return None  # unicode marker
        if n < 0xFFFF:
            return n
        return self.u32()

    def cstr(self):
        n = self._len()
        if n is None:
            n = self._len()
            return self.raw(n * 2).decode('utf-16le')
        return self.raw(n).decode('cp932')


class W:
    def __init__(self):
        self.a = bytearray()

    def u8(self, v): self.a += struct.pack('<B', v)
    def u16(self, v): self.a += struct.pack('<H', v)
    def u32(self, v): self.a += struct.pack('<I', v & 0xFFFFFFFF)
    def f64(self, v): self.a += struct.pack('<d', v)

    def _len(self, n):
        if n < 0xFF:
            self.u8(n)
        elif n < 0xFFFE:
            self.u8(0xFF); self.u16(n)
        else:
            self.u8(0xFF); self.u16(0xFFFF); self.u32(n)

    def cstr(self, s, unicode=True):
        if unicode:
            self.u8(0xFF); self.u16(0xFFFE)
            self._len(len(s)); self.a += s.encode('utf-16le')
        else:
            e = s.encode('cp932'); self._len(len(e)); self.a += e


# ---- 図形クラス -------------------------------------------------------
BASE = ('group', 'pen_style', 'pen_color', 'pen_width', 'layer', 'glayer', 'flag')


def rd_base(r, d):
    d['group'] = r.u32(); d['pen_style'] = r.u8(); d['pen_color'] = r.u16()
    d['pen_width'] = r.u16(); d['layer'] = r.u16(); d['glayer'] = r.u16(); d['flag'] = r.u16()
    return d


def wr_base(w, d):
    w.u32(d['group']); w.u8(d['pen_style']); w.u16(d['pen_color'])
    w.u16(d['pen_width']); w.u16(d['layer']); w.u16(d['glayer']); w.u16(d['flag'])


def rd_sen(r, d=None):
    d = rd_base(r, d if d is not None else {'cls': 'CDataSen'})
    d['x1'], d['y1'], d['x2'], d['y2'] = r.f64(), r.f64(), r.f64(), r.f64()
    return d


def wr_sen(w, d):
    wr_base(w, d)
    for k in ('x1', 'y1', 'x2', 'y2'):
        w.f64(d[k])


def rd_ten(r, d=None):
    d = rd_base(r, d if d is not None else {'cls': 'CDataTen'})
    d['x'], d['y'] = r.f64(), r.f64(); d['kari'] = r.u32()
    if d['pen_style'] == 100:
        d['code'] = r.u32(); d['rot'] = r.f64(); d['scale'] = r.f64()
    return d


def wr_ten(w, d):
    wr_base(w, d); w.f64(d['x']); w.f64(d['y']); w.u32(d['kari'])
    if d['pen_style'] == 100:
        w.u32(d['code']); w.f64(d['rot']); w.f64(d['scale'])


def rd_moji(r, d=None):
    d = rd_base(r, d if d is not None else {'cls': 'CDataMoji'})
    d['x1'], d['y1'], d['x2'], d['y2'] = r.f64(), r.f64(), r.f64(), r.f64()
    d['type'] = r.u32()
    d['sx'], d['sy'], d['kankaku'], d['angle'] = r.f64(), r.f64(), r.f64(), r.f64()
    d['font'] = r.cstr(); d['text'] = r.cstr()
    return d


def wr_moji(w, d):
    wr_base(w, d)
    for k in ('x1', 'y1', 'x2', 'y2'):
        w.f64(d[k])
    w.u32(d['type'])
    for k in ('sx', 'sy', 'kankaku', 'angle'):
        w.f64(d[k])
    w.cstr(d['font']); w.cstr(d['text'])


def rd_enko(r, d=None):
    d = rd_base(r, d if d is not None else {'cls': 'CDataEnko'})
    for k in ('cx', 'cy', 'r', 'start', 'arc', 'tilt', 'flat'):
        d[k] = r.f64()
    d['full'] = r.u32()
    return d


def wr_enko(w, d):
    wr_base(w, d)
    for k in ('cx', 'cy', 'r', 'start', 'arc', 'tilt', 'flat'):
        w.f64(d[k])
    w.u32(d['full'])


def rd_solid(r, d=None):
    d = rd_base(r, d if d is not None else {'cls': 'CDataSolid'})
    d['pts'] = [r.f64() for _ in range(8)]
    if d['pen_color'] == 10:
        d['rgb'] = r.u32()
    return d


def wr_solid(w, d):
    wr_base(w, d)
    for v in d['pts']:
        w.f64(v)
    if d['pen_color'] == 10:
        w.u32(d['rgb'])


def rd_block(r, d=None):
    d = rd_base(r, d if d is not None else {'cls': 'CDataBlock'})
    for k in ('x', 'y', 'sx', 'sy', 'rot'):
        d[k] = r.f64()
    d['num'] = r.u32()
    return d


def wr_block(w, d):
    wr_base(w, d)
    for k in ('x', 'y', 'sx', 'sy', 'rot'):
        w.f64(d[k])
    w.u32(d['num'])


def rd_sunpou(r, ver):
    d = rd_base(r, {'cls': 'CDataSunpou'})
    d['sen'] = rd_sen(r, {}); d['moji'] = rd_moji(r, {})
    if ver >= 420:
        d['sxf'] = r.u16()
        d['ho1'] = rd_sen(r, {}); d['ho2'] = rd_sen(r, {})
        d['tens'] = [rd_ten(r, {}) for _ in range(4)]
    return d


def wr_sunpou(w, d, ver):
    wr_base(w, d); wr_sen(w, d['sen']); wr_moji(w, d['moji'])
    if ver >= 420:
        w.u16(d['sxf']); wr_sen(w, d['ho1']); wr_sen(w, d['ho2'])
        for t in d['tens']:
            wr_ten(w, t)


class Archive:
    """MFC CArchive の WriteObject/ReadObject 相当（クラス・オブジェクト索引管理）"""

    def __init__(self, ver):
        self.ver = ver

    # -- read --
    def read_obj(self, r):
        tag = r.u16()
        if tag == BIG_OBJ_TAG:
            raise ValueError('big tag unsupported')
        if tag == NEW_CLASS:
            schema = r.u16(); n = r.u16(); name = r.raw(n).decode('ascii')
            self.rmap.append(('class', name)); cls = name
        elif tag & CLASS_TAG:
            kind, cls = self.rmap[tag & 0x7FFF]
            assert kind == 'class', (tag, kind)
        else:
            raise ValueError('object back-reference at %d' % r.p)
        self.rmap.append(('obj', None))
        return self.read_body(r, cls)

    def read_body(self, r, cls):
        if cls == 'CDataSen': return rd_sen(r)
        if cls == 'CDataTen': return rd_ten(r)
        if cls == 'CDataMoji': return rd_moji(r)
        if cls == 'CDataEnko': return rd_enko(r)
        if cls == 'CDataSolid': return rd_solid(r)
        if cls == 'CDataBlock': return rd_block(r)
        if cls == 'CDataSunpou': return rd_sunpou(r, self.ver)
        if cls == 'CDataList':
            d = rd_base(r, {'cls': 'CDataList'})
            d['num'] = r.u32(); d['ref'] = r.u32(); d['time'] = r.u32()
            d['name'] = r.cstr()
            d['items'] = self.read_list(r)
            return d
        raise ValueError('unknown class ' + cls)

    def read_list(self, r):
        n = r.u16()
        if n == 0xFFFF:
            n = r.u32()
        return [self.read_obj(r) for _ in range(n)]

    # -- write --
    def write_obj(self, w, d):
        cls = d['cls']
        if cls in self.wclass:
            w.u16(CLASS_TAG | self.wclass[cls])
        else:
            w.u16(NEW_CLASS); w.u16(self.ver); w.u16(len(cls)); w.a += cls.encode('ascii')
            self.wclass[cls] = self.wcount; self.wcount += 1
        self.wcount += 1
        if self.wcount >= 0x7FFF:
            raise ValueError('too many objects for 16bit tags')
        {
            'CDataSen': wr_sen, 'CDataTen': wr_ten, 'CDataMoji': wr_moji,
            'CDataEnko': wr_enko, 'CDataSolid': wr_solid, 'CDataBlock': wr_block,
        }.get(cls, lambda w_, d_: None)(w, d)
        if cls == 'CDataSunpou':
            wr_sunpou(w, d, self.ver)
        elif cls == 'CDataList':
            wr_base(w, d); w.u32(d['num']); w.u32(d['ref']); w.u32(d['time'])
            w.cstr(d['name']); self.write_list(w, d['items'])

    def write_list(self, w, items):
        if len(items) < 0xFFFF:
            w.u16(len(items))
        else:
            w.u16(0xFFFF); w.u32(len(items))
        for d in items:
            self.write_obj(w, d)


class JwwFile:
    def __init__(self, path):
        b = open(path, 'rb').read()
        assert b[:8] == b'JwwData.'
        self.ver = struct.unpack_from('<I', b, 8)[0]
        key = b'\xff\xff' + struct.pack('<H', self.ver)
        cands = [b.find(key + struct.pack('<H', len(c)) + c.encode()) for c in
                 ('CDataSen', 'CDataMoji', 'CDataTen', 'CDataEnko', 'CDataSolid', 'CDataBlock', 'CDataSunpou')]
        start = min(c for c in cands if c > 0) - 2
        self.header = b[:start]
        r = R(b, start)
        ar = Archive(self.ver); ar.rmap = [None]
        self.entities = ar.read_list(r)
        self.blocks = ar.read_list(r)
        self.tail = b[r.p:]
        self.orig = b

    def to_bytes(self):
        w = W(); ar = Archive(self.ver); ar.wclass = {}; ar.wcount = 1
        ar.write_list(w, self.entities)
        ar.write_list(w, self.blocks)
        return self.header + bytes(w.a) + self.tail

    def save(self, path):
        open(path, 'wb').write(self.to_bytes())


# ---- 図形生成ヘルパ ---------------------------------------------------
def base(layer, glayer, color, style=1, width=0, group=0, flag=0):
    return {'group': group, 'pen_style': style, 'pen_color': color, 'pen_width': width,
            'layer': layer, 'glayer': glayer, 'flag': flag}
