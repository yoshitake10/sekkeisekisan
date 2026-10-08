"""安楽寺 本堂 新築工事 空調・換気設備 共通データ

座標は原本JWW（松森設計事務所 平面図 令和8年7月20日版）の座標系。
  1単位 = 実寸 50mm（JWW上 A1・1/50 = A3出力 1/100）
通り芯: X = -157.16 / -77.96 / 18.04 / 85.24 / 184.04
        Y =  -67.42 /  28.58 / 124.58
面積は上記平面図の壁芯から読取り（小数2位）。天井高は意匠未確定のため仮定値（要確認）。
"""
from decimal import ROUND_HALF_UP, Decimal

U = 0.05  # 1単位 = 0.05 m


def rnd(x, n=2):
    """Excel の ROUND と同じ四捨五入"""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))

# ---------------------------------------------------------------------------
# 換気対象（一体換気区画）: name, kind(居室/非居室), 矩形リスト(units), 天井高[m],
#                          換気回数n[回/h], 備考
# ---------------------------------------------------------------------------
ROOMS = [
    # 本堂部（住宅等の居室以外の居室 n=0.3）
    dict(no='1', name='外陣（大間）', kind='居室', rects=[(-157.16, -47.5, 85.24, 28.58)], h=3.3, n=0.3,
         note='天井高 仮定'),
    dict(no='2', name='廊下（広縁・南）', kind='非居室', rects=[(-147.0, -67.42, 85.24, -47.5)], h=2.7, n=0.3,
         note='外陣と一体（障子・ガラス戸 通気確保）'),
    dict(no='3', name='内陣（本陣・御本尊）', kind='居室', rects=[(-77.96, 28.58, 18.04, 150.0)], h=3.6, n=0.3,
         note='天井高 仮定（折上天井の場合は平均天井高）'),
    dict(no='4', name='護摩堂', kind='居室', rects=[(-157.16, 28.58, -77.96, 126.0)], h=3.3, n=0.3,
         note='天井高 仮定'),
    # 庫裏側（安全側に n=0.5 を採用）
    dict(no='5', name='和室(1)（床の間含む）', kind='居室',
         rects=[(32.9, 68.2, 85.3, 148.2), (18.04, 106.0, 32.9, 148.2)], h=2.4, n=0.5, note=''),
    dict(no='6', name='談話室', kind='居室',
         rects=[(85.3, 68.2, 184.04, 125.9), (108.2, 125.9, 184.04, 148.2)], h=2.4, n=0.5,
         note='パントリー・勝手口を除く'),
    dict(no='7', name='和室(2)', kind='居室', rects=[(107.6, 10.6, 184.04, 68.2)], h=2.4, n=0.5, note=''),
    dict(no='8', name='廊下（北）', kind='非居室', rects=[(18.04, 30.6, 85.3, 68.2)], h=2.4, n=0.5,
         note='物入(1.47㎡)を除く', minus=[(37.0, 30.6, 76.0, 49.4)]),
    dict(no='9', name='廊下（東）', kind='非居室', rects=[(85.3, -64.0, 106.5, 68.2)], h=2.4, n=0.5, note=''),
    dict(no='10', name='ホール', kind='非居室', rects=[(106.5, -25.9, 144.0, 9.4)], h=2.4, n=0.5, note=''),
    dict(no='11', name='玄関', kind='非居室', rects=[(107.6, -57.6, 144.0, -25.9)], h=2.4, n=0.5, note=''),
    dict(no='12', name='便所(女)', kind='非居室', rects=[(146.5, -8.2, 183.0, 9.4)], h=2.4, n=0.5, note='排気'),
    dict(no='13', name='手洗い', kind='非居室', rects=[(146.5, -27.0, 183.0, -9.4)], h=2.4, n=0.5, note=''),
    dict(no='14', name='小便所', kind='非居室', rects=[(154.7, -45.9, 183.0, -28.0)], h=2.4, n=0.5, note='排気'),
    dict(no='15', name='便所(男)', kind='非居室', rects=[(153.6, -64.7, 183.0, -47.0)], h=2.4, n=0.5, note='排気'),
    dict(no='16', name='パントリー・勝手口', kind='非居室',
         rects=[(86.5, 125.9, 108.2, 148.2)], h=2.4, n=0.5, note=''),
]

# 換気対象外（建具で区画された収納。F☆☆☆☆材使用とし、換気経路に含めない）
EXCLUDED = ['物置', '物入（西）', '物入（北廊下）', '押入', '位牌棚・地袋', '前机・地袋']


def area(room):
    a = sum((x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in room['rects'])
    a -= sum((x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in room.get('minus', []))
    return rnd(a * U * U, 2)


# ---------------------------------------------------------------------------
# 24時間換気（第3種機械換気）排気ファン
#   有効換気量はメーカー公表値（直管相当長20m時）を採用 ※ダクト直管相当長が20m以下であることを確認
# ---------------------------------------------------------------------------
FAN24 = dict(sym='EF-1', model='FY-17C8', maker='パナソニック', name='天井埋込形換気扇（低騒音形・ルーバーセット）',
             duct='φ100', q0=95.0, q_eff=80.5, eq_len_ref=20.0, watt=7.6, power='単相100V')
FAN24_UNITS = [
    # (設置室, x, y, 吐出し方向の外壁x/y, ダクト実長m, 曲り数)
    dict(room='便所(女)', x=172.0, y=0.6, wall=('x', 184.04), duct_len=0.8, bends=1),
    dict(room='小便所', x=172.0, y=-37.0, wall=('x', 184.04), duct_len=0.8, bends=1),
    dict(room='便所(男)', x=172.0, y=-56.0, wall=('x', 184.04), duct_len=0.8, bends=1),
]
# 直管相当長の算定用（パナソニック技術資料の一般値: 90°エルボ1個=直管1.5m相当、
#   外壁パイプフード（深型・防虫網付）=直管10m相当 として安全側に設定）
EQ_ELBOW = 1.5
EQ_HOOD = 10.0

# 給気口（外気導入ダクト付 給排気グリル）  units: (室名, x, y, ダクト接続外壁)
SUPPLY = [
    dict(sym='SA-1', model='VB-GE200P-T', name='給排気グリル', spec='シャッター・フィルター付', color='ライトブラウン', duct='φ200',
         units=[('外陣（大間）', -120.0, -40.0, ('y', -67.42)), ('外陣（大間）', -40.0, -40.0, ('y', -67.42)),
                ('外陣（大間）', 45.0, -40.0, ('y', -67.42)), ('内陣（本陣・御本尊）', -55.0, 40.0, ('x', -157.16))]),
    dict(sym='SA-2', model='VB-GE150P-T', name='給排気グリル', spec='シャッター・フィルター付', color='ライトブラウン', duct='φ150',
         units=[('護摩堂', -140.0, 45.0, ('x', -157.16))]),
    dict(sym='SA-3', model='VB-GE100P3-T', name='給排気グリル', spec='シャッター・フィルター付', color='ライトブラウン', duct='φ100',
         units=[('和室(1)', 70.0, 140.0, ('y', 148.2)), ('和室(2)', 150.0, 22.0, ('x', 184.04))]),
    dict(sym='SA-4', model='VB-GE100P3-W', name='給排気グリル', spec='シャッター・フィルター付', color='ホワイト', duct='φ100',
         units=[('談話室', 165.0, 80.0, ('x', 184.04))]),
]

# 局所換気（24時間換気の有効換気量には算入しない）
LOCAL = [
    dict(sym='EF-2', model='FY-32JG8/84', name='天井埋込形換気扇', spec='焼香・護摩の排煙用', color='', duct='φ150',
         units=[('外陣（大間）', -105.0, 0.0, ('y', -67.42)), ('外陣（大間）', -25.0, 0.0, ('y', -67.42)),
                ('外陣（大間）', 60.0, 0.0, ('y', -67.42)), ('内陣（本陣・御本尊）', -10.0, 40.0, ('y', -67.42)),
                ('護摩堂', -118.0, 75.0, ('x', -157.16))]),
    dict(sym='EF-3', model='FY-27JK8/84', name='天井埋込形換気扇', spec='台所・湯沸し用', color='', duct='φ100',
         units=[('談話室', 170.0, 125.0, ('x', 184.04))]),
    dict(sym='EF-4', model='FY-24CG8', name='天井埋込形換気扇', spec='パントリー用', color='', duct='φ100',
         units=[('パントリー', 97.0, 138.0, ('y', 148.2))]),
]

# ---------------------------------------------------------------------------
# 空調（8月10日付 検討最終VE案 提案①ダイキン）
# ---------------------------------------------------------------------------
AC = [
    dict(sym='AC-1', name='業務用パッケージエアコン 床置形ペア（EcoZEAS P80）', model='SZRV80BZV', maker='ダイキン',
         cap='冷7.1kW／暖8.0kW', power='単相200V', qty=2, place='大間・外陣', remote='本体リモコン',
         pipe='液φ9.52／ガスφ15.88', iu=(12.0, 5.4, 'floor'), ou=(15.9, 6.0)),
    dict(sym='AC-2', name='ルームエアコン 壁掛形', model='S284ATEV-W', maker='ダイキン',
         cap='冷2.8kW／暖4.0kW', power='単相200V', qty=2, place='和室(1)・和室(2)', remote='ワイヤレスリモコン',
         pipe='液φ6.35／ガスφ9.52', iu=(16.0, 5.4, 'wall'), ou=(13.5, 5.7)),
    dict(sym='AC-3', name='ルームエアコン 壁掛形', model='S404ATEV-W', maker='ダイキン',
         cap='冷4.0kW／暖5.3kW', power='単相200V', qty=1, place='談話室', remote='ワイヤレスリモコン',
         pipe='液φ6.35／ガスφ9.52', iu=(16.0, 5.4, 'wall'), ou=(15.3, 5.7)),
]


# 図面記載用のまとめ区分
GROUPS = [
    ('外陣・広縁', ['1', '2']), ('内陣', ['3']), ('護摩堂', ['4']), ('和室(1)', ['5']),
    ('談話室他', ['6', '16']), ('和室(2)', ['7']), ('廊下・ホール等', ['8', '9', '10', '11']),
    ('便所・手洗い', ['12', '13', '14', '15']),
]


def fan_eq_len(u):
    """ダクト直管相当長[m] = 実長 + 曲り数×エルボ相当長 + 外壁フード相当長"""
    return round(u['duct_len'] + u['bends'] * EQ_ELBOW + EQ_HOOD, 1)


def calc_summary():
    rooms = []
    for r in ROOMS:
        A = area(r); V = rnd(A * r['h']); Vr = rnd(V * r['n'])
        rooms.append(dict(no=r['no'], name=r['name'], kind=r['kind'], A=A, h=r['h'], V=V, n=r['n'], Vr=Vr,
                          note=r['note']))
    byno = {r['no']: r for r in rooms}
    groups = []
    for name, nos in GROUPS:
        rs = [byno[n] for n in nos]
        hs = sorted(set(r['h'] for r in rs), reverse=True)
        ns = sorted(set(r['n'] for r in rs))
        assert len(ns) == 1, name
        groups.append(dict(name=name, A=round(sum(r['A'] for r in rs), 2), h='/'.join('%.1f' % h for h in hs),
                           V=round(sum(r['V'] for r in rs), 2), n=ns[0], Vr=round(sum(r['Vr'] for r in rs), 2)))
    assert sorted(n for _, nos in GROUPS for n in nos) == sorted(byno)
    eq_len = max(fan_eq_len(u) for u in FAN24_UNITS)
    Ve = round(FAN24['q_eff'] * len(FAN24_UNITS), 1)
    return dict(rooms=rooms, groups=groups, sumA=round(sum(r['A'] for r in rooms), 2),
                sumV=round(sum(r['V'] for r in rooms), 2), sumVr=rnd(sum(r['Vr'] for r in rooms), 1),
                Ve=Ve, eq_len=eq_len)
