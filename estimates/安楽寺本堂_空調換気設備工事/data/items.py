# -*- coding: utf-8 -*-
"""
数量（安楽寺 本堂 新築工事 空調・換気設備工事）
当社作図の M-1 空調設備平面図・M-2 換気設備平面図（drawings/安楽寺本堂_空調換気）の配置座標から算出。
座標・機器の定義は drawings/tools/project_data.py（図面・24時間換気計算書と共通）。
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..', 'drawings', 'tools')))
import project_data as P  # noqa: E402

# ---- 想定値（天井高・機器の取付高さは意匠未確定）
PAC_MIN = 3.0        # AC-1 床置形 1系統の冷媒管長（最小配管長 3m を確保。壁貫通・立上り・余長込み）
RAC_LEN = 4.0        # ルームエアコン 1台の冷媒管長（壁掛 2.2m → 屋外置台への立下り・余長込み）
PAC_DRAIN = 1.5      # AC-1 ドレン 1系統（室内 1.0m＋屋外放流 0.5m）
PAC_DRAIN_IN = 1.0
VVF_PAC = 5.0        # 内外連絡線 1系統
VVF_RAC = 5.0
CASE_PAC = 1.0       # 屋外化粧カバー（床置：壁貫通〜室外機）
CASE_RAC = 2.0       # 屋外化粧カバー（壁掛：立下り）
DUCT_ADD = 0.5       # ダクト 1本あたりの立上り・接続加算
U = P.U              # 図面1単位 = 0.05 m


def up(x):
    return int(math.ceil(x - 0.05))


# ---- 空調（M-1）
n_pac = 2
n_rac = 2 + 1
ref_pac = PAC_MIN * n_pac
ref_rac = RAC_LEN * n_rac
vp25 = PAC_DRAIN * n_pac
gw25 = PAC_DRAIN_IN * n_pac
vvf = VVF_PAC * n_pac + VVF_RAC * n_rac
case_l = CASE_PAC * n_pac
case_s = CASE_RAC * n_rac
sleeve_ac = n_pac + n_rac


# ---- 換気（M-2）ダクト：器具位置から外壁までの平面距離＋立上り・接続
def run(x, y, wall):
    axis, v = wall
    return abs((x if axis == 'x' else y) - v) * U


ducts = []      # (記号, 室名, 口径, 平面m, 計m)
for grp in P.SUPPLY + P.LOCAL:
    for room, x, y, wall in grp['units']:
        d = run(x, y, wall)
        ducts.append((grp['sym'], room, grp['duct'], round(d, 2), round(d + DUCT_ADD, 2)))
duct_len = {}
for sym, room, dia, d, t in ducts:
    duct_len[dia] = duct_len.get(dia, 0) + t
oa_len = {}     # 外気導入（給気）ダクト＝結露防止の保温対象
for sym, room, dia, d, t in ducts:
    if sym.startswith('SA'):
        oa_len[dia] = oa_len.get(dia, 0) + t

# 外壁貫通（＝屋外フード）の口径別数
hood = {}
for dia in [P.FAN24['duct']] * len(P.FAN24_UNITS) + [g['duct'] for g in P.SUPPLY + P.LOCAL for _ in g['units']]:
    hood[dia] = hood.get(dia, 0) + 1

n_fan24 = len(P.FAN24_UNITS)
n_grille = sum(len(g['units']) for g in P.SUPPLY)
local = {g['sym']: len(g['units']) for g in P.LOCAL}

Q = dict(ref_pac=up(ref_pac), ref_rac=up(ref_rac), vp25=up(vp25), gw25=up(gw25), vvf=up(vvf),
         case_l=up(case_l), case_s=up(case_s), sleeve_ac=sleeve_ac,
         d100=up(duct_len.get('φ100', 0)), d150=up(duct_len.get('φ150', 0)), d200=up(duct_len.get('φ200', 0)),
         ins=up(sum(oa_len.values())),
         h100=hood.get('φ100', 0), h150=hood.get('φ150', 0), h200=hood.get('φ200', 0))

M = dict(
    ref_pac=f"AC-1 床置形 {n_pac}系統 × {PAC_MIN}m（室外機は外壁直近。最小配管長 3m を確保、壁貫通・立上り・余長込み）",
    ref_rac=f"AC-2・AC-3 壁掛形 {n_rac}台 × {RAC_LEN}m（壁掛 約2.2m → 屋外置台への立下り・余長込み）",
    vp25=f"AC-1 {n_pac}系統 × {PAC_DRAIN}m（室内 {PAC_DRAIN_IN}m＋屋外放流 {PAC_DRAIN - PAC_DRAIN_IN}m）。ルームエアコンは付属ドレンホース",
    gw25=f"AC-1 ドレンの屋内部分 {PAC_DRAIN_IN}m × {n_pac}系統",
    vvf=f"内外連絡線 AC-1 {VVF_PAC}m×{n_pac}・AC-2/3 {VVF_RAC}m×{n_rac}（余長込み）",
    case_l=f"AC-1 屋外 壁貫通〜室外機 {CASE_PAC}m × {n_pac}",
    case_s=f"AC-2・AC-3 屋外立下り {CASE_RAC}m × {n_rac}",
    d100=f"給気 SA-3 ×3・局所 EF-3/EF-4 の器具〜外壁（平面）＋立上り・接続 {DUCT_ADD}m/本 ＝ {duct_len.get('φ100', 0):.2f}m",
    d150=f"給気 SA-2・局所 EF-2 ×5 の器具〜外壁（平面）＋{DUCT_ADD}m/本 ＝ {duct_len.get('φ150', 0):.2f}m",
    d200=f"給気 SA-1 ×4 の器具〜外壁（平面）＋{DUCT_ADD}m/本 ＝ {duct_len.get('φ200', 0):.2f}m",
    ins=f"外気導入（給気）ダクトの全長 ＝ {sum(oa_len.values()):.2f}m（結露防止）",
)

BASIS_TABLES = [
    ('1. 冷媒・ドレン配管（M-1 空調設備平面図：室外機は各室外壁の直近）', ['系統', '管径', '数量', '1系統(m)', '合計(m)', '想定内容'], [
        ('AC-1 SZRV80BZV 床置形（大間・外陣）', 'φ9.52/15.88', n_pac, PAC_MIN, ref_pac, M['ref_pac']),
        ('AC-2 S284ATEV-W・AC-3 S404ATEV-W 壁掛形', 'φ6.35/9.52', n_rac, RAC_LEN, ref_rac, M['ref_rac']),
        ('ドレン VP25（AC-1）', '25A', n_pac, PAC_DRAIN, vp25, M['vp25']),
        ('内外連絡線 VVF 2.0-3C', '', n_pac + n_rac, VVF_RAC, vvf, M['vvf']),
    ]),
    ('2. 換気ダクト（M-2 換気設備平面図：器具〜外壁の平面距離＋立上り・接続）', ['記号', '室名', '口径', '平面(m)', '計(m)', '備考'],
     [(s, r, dia, d, t, '給気（外気導入）' if s.startswith('SA') else '局所排気') for s, r, dia, d, t in ducts]
     + [('合計 → 内訳書', '', '', '', round(sum(t for *_, t in ducts), 2),
         f"φ100 {Q['d100']}m・φ150 {Q['d150']}m・φ200 {Q['d200']}m、保温（給気）{Q['ins']}m")]),
    ('3. 機器・外壁貫通（図面カウント）', ['項目', '数量', '備考'], [
        ('24時間換気 パイプファン V-08PP8-BL', f'{n_fan24}台', '便所(女)・小便所・便所(男) 外壁付け'),
        ('天井埋込形換気扇 VD-18ZC14 / VD-15ZC14 / VD-10ZC14', f"{local['EF-2']}・{local['EF-3']}・{local['EF-4']}台", '局所換気（排煙・台所・パントリー）'),
        ('給排気グリル P-23GHF5 / P-18GHF5 / P-13GHF5', '4・1・3個', '外気導入（給気）'),
        ('外壁貫通・深形フード φ100 / φ150 / φ200', f"{Q['h100']}・{Q['h150']}・{Q['h200']}箇所", 'パイプファン・給気・局所排気'),
        ('空調 外壁貫通（冷媒・ドレン）', f"{sleeve_ac}箇所", 'AC-1 ×2、AC-2・AC-3 ×3'),
    ]),
]

if __name__ == '__main__':
    print(Q)
    for d in ducts:
        print(d)
