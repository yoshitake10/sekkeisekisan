# -*- coding: utf-8 -*-
"""
明細データ（吉野家 呉海岸通店 新設工事 空調設備工事）
====================================================
工事範囲（ご指示）: 機器吊込み・冷媒配管（ガス管保温20mm）・VPドレン・ドレン配管GW保温・室外機設置
数量: 空調設備図 F-02-1 の平面実測（takeoff_f02.json、takeoff_f02.py で再計測可）＋ 立上り等の想定加算
行: dict(name, spec, qty, unit, key(単価マスタ), basis(実測/推測/実測+推測/図面カウント), memo(想定の根拠), pub(公開備考))
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'takeoff_f02.json'), encoding='utf-8'))

# ---- 想定値（室外機設置概要図・天井高から）
H_PEN = 2.7          # 外壁貫通（天井内）高さ m：厨房 CH2,500＋天井内
H_VALVE_LOW = 0.5    # 架台下段の室外機 冷媒接続高さ m
H_VALVE_UP = 1.8     # 架台上段（段間 H1,430 室外機対応で上段 1.6m 程度）の接続高さ m
RISE_LOW = round(H_PEN - H_VALVE_LOW, 2)    # 2.2
RISE_UP = round(H_PEN - H_VALVE_UP, 2)      # 0.9
DROP_IN = 0.3        # 天井内配管 → 天井カセット・ビルトイン接続
DROP_RAC = 0.6       # 天井内 → 店長室 壁掛 RAC
SLACK_PAC = 0.5      # 余長（曲がり・機器廻り）/系統
SLACK_RAC = 0.3
D_DROP_40 = 2.45     # ドレン主管 天井内(2.6m) → 接続立上り H=150
D_UP_EACH = 0.3      # ドレンアップ立上り / 台（AC-1×2・AC-2）
D_CONN_E = 0.3       # 東カセット 主管端 → 機器接続
D_DROP_RAC = 1.9     # RAC ドレン 立下り（壁内）→ H=150


def up(x):
    """数量の切上げ（0.05m 未満の端数は切捨て）"""
    return int(math.ceil(x - 0.05))


r = T
ac1w = r['R_AC1_W']['plan_m'] + RISE_LOW + DROP_IN + SLACK_PAC
ac1e = r['R_AC1_E']['plan_m'] + RISE_UP + DROP_IN + SLACK_PAC
ac2 = r['R_AC2']['plan_m'] + RISE_LOW + DROP_IN + SLACK_PAC
rac = r['R_RAC']['plan_m'] + RISE_UP + DROP_RAC + SLACK_RAC
ref_pac = ac1w + ac1e + ac2
plan_pac = r['R_AC1_W']['plan_m'] + r['R_AC1_E']['plan_m'] + r['R_AC2']['plan_m']
out_plan = sum(r[k]['outside_m'] for k in ('R_AC1_W', 'R_AC1_E', 'R_AC2', 'R_RAC'))
case = out_plan + RISE_LOW * 2 + RISE_UP * 2
D = r['D']
d25_plan = D['main_25A_east'] + D['branch_25A_AC2'] + D['branch_25A_AC1W'] + D['branch_25A_RAC']
d25 = d25_plan + D_UP_EACH * 3 + D_CONN_E + D_DROP_RAC
d30 = D['main_30A']
d40 = D['main_40A'] + D_DROP_40

# 化粧カバーは管径別（エスト見積に合わせて小径・大径を分ける）
case_pac = sum(r[k]['outside_m'] for k in ('R_AC1_W', 'R_AC1_E', 'R_AC2')) + RISE_LOW * 2 + RISE_UP
case_rac = r['R_RAC']['outside_m'] + RISE_UP
VVF_SLACK = 3.0      # 内外連絡線（VVF 2.0-3C）の余長 m/系統（端末処理・機器内配線）
vvf = ac1w + ac1e + ac2 + rac + VVF_SLACK * 4

Q = dict(ref_pac=up(ref_pac), ref_rac=up(rac), case=up(case), case_pac=up(case_pac), case_rac=up(case_rac),
         d25=up(d25), d30=up(d30), d40=up(d40), vvf=up(vvf))

memo_ref_pac = (f"平面実測 {plan_pac:.2f}m（AC-1西 {r['R_AC1_W']['plan_m']}・AC-1東 {r['R_AC1_E']['plan_m']}・AC-2 {r['R_AC2']['plan_m']}）"
                f"＋立上り（架台下段 {RISE_LOW}m×2・上段 {RISE_UP}m×1）＋機器接続 {DROP_IN}m×3＋余長 {SLACK_PAC}m×3 ＝ {ref_pac:.2f}m")
memo_ref_rac = (f"平面実測 {r['R_RAC']['plan_m']}m＋立上り（架台上段）{RISE_UP}m＋店長室 立下り {DROP_RAC}m＋余長 {SLACK_RAC}m ＝ {rac:.2f}m")
memo_case = (f"屋外の平面部 {out_plan:.2f}m（4系統 実測）＋室外機→外壁貫通の立上り（下段 {RISE_LOW}m×2・上段 {RISE_UP}m×2）＝ {case:.2f}m")
memo_case_pac = (f"AC-1×2・AC-2: 屋外平面 {r['R_AC1_W']['outside_m'] + r['R_AC1_E']['outside_m'] + r['R_AC2']['outside_m']:.2f}m（実測）"
                 f"＋立上り（下段 {RISE_LOW}m×2・上段 {RISE_UP}m×1）＝ {case_pac:.2f}m")
memo_case_rac = f"RAC: 屋外平面 {r['R_RAC']['outside_m']}m（実測）＋立上り（上段）{RISE_UP}m ＝ {case_rac:.2f}m"
memo_vvf = (f"内外連絡線＝冷媒配管の系統長（{ac1w:.2f}＋{ac1e:.2f}＋{ac2:.2f}＋{rac:.2f}m）＋余長 {VVF_SLACK}m×4系統 ＝ {vvf:.2f}m"
            f"（エスト見積も 56m）")
memo_d25 = (f"平面実測 {d25_plan:.2f}m（東主管 {D['main_25A_east']}・AC-2枝 {D['branch_25A_AC2']}・西枝 {D['branch_25A_AC1W']}・RAC {D['branch_25A_RAC']}）"
            f"＋ドレンアップ立上り {D_UP_EACH}m×3＋東カセット接続 {D_CONN_E}m＋RAC 立下り {D_DROP_RAC}m ＝ {d25:.2f}m")
memo_d40 = f"平面実測 {D['main_40A']}m＋天井内→接続立上り（H=150）への立下り {D_DROP_40}m ＝ {d40:.2f}m"

BASIS_TABLES = [
    ('1. 冷媒配管 系統別（空調設備図 F-02-1 1/50 実測＋想定）', ['系統', '管径', '平面実測(m)', '想定加算(m)', '合計(m)', '想定内容'], [
        ('AC-1（客席西 天井カセット）', 'φ9.52/15.88', r['R_AC1_W']['plan_m'], round(ac1w - r['R_AC1_W']['plan_m'], 2), round(ac1w, 2),
         f'架台下段 立上り {RISE_LOW}m・機器接続 {DROP_IN}m・余長 {SLACK_PAC}m'),
        ('AC-1（客席東 天井カセット）', 'φ9.52/15.88', r['R_AC1_E']['plan_m'], round(ac1e - r['R_AC1_E']['plan_m'], 2), round(ac1e, 2),
         f'架台上段 立上り {RISE_UP}m・機器接続 {DROP_IN}m・余長 {SLACK_PAC}m'),
        ('AC-2（厨房 天井ビルトイン）', 'φ9.52/15.88', r['R_AC2']['plan_m'], round(ac2 - r['R_AC2']['plan_m'], 2), round(ac2, 2),
         f'架台下段 立上り {RISE_LOW}m・機器接続 {DROP_IN}m・余長 {SLACK_PAC}m'),
        ('RAC（店長室 壁掛）', 'φ6.35/9.52', r['R_RAC']['plan_m'], round(rac - r['R_RAC']['plan_m'], 2), round(rac, 2),
         f'架台上段 立上り {RISE_UP}m・壁掛機への立下り {DROP_RAC}m・余長 {SLACK_RAC}m'),
        ('合計 → 内訳書', '', round(plan_pac + r['R_RAC']['plan_m'], 2), round(ref_pac + rac - plan_pac - r['R_RAC']['plan_m'], 2),
         round(ref_pac + rac, 2), f"φ9.52/15.88 {Q['ref_pac']}m・φ6.35/9.52 {Q['ref_rac']}m（切上げ）"),
    ]),
    ('2. 外部冷媒配管 化粧カバー', ['系統', '屋外平面(m)', '立上り(m)', '合計(m)', '', '備考'], [
        ('AC-1（下段）', r['R_AC1_W']['outside_m'], RISE_LOW, round(r['R_AC1_W']['outside_m'] + RISE_LOW, 2), '', '外壁 Y6 より北の線分を実測'),
        ('AC-1（上段）', r['R_AC1_E']['outside_m'], RISE_UP, round(r['R_AC1_E']['outside_m'] + RISE_UP, 2), '', ''),
        ('AC-2（下段）', r['R_AC2']['outside_m'], RISE_LOW, round(r['R_AC2']['outside_m'] + RISE_LOW, 2), '', ''),
        ('RAC（上段）', r['R_RAC']['outside_m'], RISE_UP, round(r['R_RAC']['outside_m'] + RISE_UP, 2), '', ''),
        ('合計 → 内訳書', round(out_plan, 2), round(RISE_LOW * 2 + RISE_UP * 2, 2), round(case, 2), '',
         f"9.52+15.88用 {Q['case_pac']}m（{case_pac:.2f}）・6.35+9.52用 {Q['case_rac']}m（{case_rac:.2f}）"),
    ]),
    ('3. ドレン配管（空調設備図の口径ラベルで区分）', ['区間', '口径', '平面実測(m)', '想定加算(m)', '合計(m)', '備考'], [
        ('主管 接続立上り〜西カセット合流', '40A', D['main_40A'], D_DROP_40, round(d40, 2), f'天井内→H=150 立下り {D_DROP_40}m'),
        ('主管 西カセット合流〜AC-2合流', '30A', D['main_30A'], 0.0, round(d30, 2), ''),
        ('主管 AC-2合流〜東カセット', '25A', D['main_25A_east'], D_CONN_E + D_UP_EACH, round(D['main_25A_east'] + D_CONN_E + D_UP_EACH, 2), '機器接続・ドレンアップ立上り'),
        ('AC-2 枝', '25A', D['branch_25A_AC2'], D_UP_EACH, round(D['branch_25A_AC2'] + D_UP_EACH, 2), 'ドレンアップ立上り'),
        ('西カセット 枝', '25A', D['branch_25A_AC1W'], D_UP_EACH, round(D['branch_25A_AC1W'] + D_UP_EACH, 2), 'ドレンアップ立上り'),
        ('RAC', '25A', D['branch_25A_RAC'], D_DROP_RAC, round(D['branch_25A_RAC'] + D_DROP_RAC, 2), '壁内 立下り（NDB-20-25 経由で接続）'),
        ('合計 → 内訳書', '', round(D['main_40A'] + D['main_30A'] + d25_plan, 2), round(d40 + d30 + d25 - D['main_40A'] - D['main_30A'] - d25_plan, 2),
         round(d40 + d30 + d25, 2), f"VP25 {Q['d25']}m・VP30 {Q['d30']}m・VP40 {Q['d40']}m（保温も同長）"),
    ]),
    ('4. 機器台数（換気空調機器表・室外機設置概要図）', ['記号', '台数', '備考'], [
        ('AC-1 天井カセット形 5馬力 SSRC140C', '室内2・室外2', '客席。室外機は架台①の下段・上段'),
        ('AC-2 天井ビルトイン形 5馬力 SSRB140C', '室内1・室外1', '厨房。室外機は架台②の下段。吹出しパンカー×4（支給）・ダクトは範囲外'),
        ('RAC ルームエアコン 2.2kW', '室内1・室外1', '店長室。室外機は架台②の上段'),
        ('鉄骨架台 2段積み', '2基', '特記「空調本工事」。溶融亜鉛メッキ'),
        ('外壁貫通', '4箇所', '冷媒管 4系統の外壁貫通位置（F-02-1）→ エストの「スリーブインサート費 1式」に対応'),
        ('内外連絡線 VVF 2.0-3C', f"{Q['vvf']}m", '図示なし。冷媒配管の系統長＋余長3m/系統（エスト見積 56m と一致）'),
    ]),
]
