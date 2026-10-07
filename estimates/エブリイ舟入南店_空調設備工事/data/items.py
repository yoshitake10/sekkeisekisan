# -*- coding: utf-8 -*-
"""
数量（エブリイ舟入南店 リニューアル工事 空調設備工事）
空調図（A3 1/100）の平面実測（takeoff.json）＋ 立上り等の想定加算
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'takeoff.json'), encoding='utf-8'))

# ---- 想定値（天井高・外壁開口高さの図示なし）
H_PEN = 3.0          # 外壁開口（天井内）の高さ m
RISE_LOW = 2.5       # 二段置き架台 下段（RAS-GP140RSH4 想定）接続 0.5m → 外壁開口
RISE_UP = 1.2        # 上段（RAS-GP112RSH4 想定）接続 1.8m → 外壁開口
DROP_RPCK = 0.5      # 天井内 → 厨房用天吊（RPCK）
DROP_RCI = 0.3       # 天井内 → 天井カセット（RCI）
SLACK = 0.5          # 余長（新設1系統あたり）
SLACK_BR = 0.3       # 余長（ツイン分岐1本あたり）
MV_END = 1.0         # 移設延長の両端（立下り・既設接続）計
D_UP_RPCK = 0.5      # ドレンアップメカ立上り
D_UP_RCI = 0.3       # カセット内蔵ドレンアップ立上り
D_OUT = 1.0          # 外壁から屋外排出まで
D_MV_END = 0.5       # 移設ドレン延長の接続部
VVF_SLACK = 3.0      # 内外連絡線の余長（新設1系統）
VVF_MV_END = 1.0     # 移設 内外連絡線の延長（中間接続部）


def up(x):
    return int(math.ceil(x - 0.05))


r = T
gp140 = r['R_GP140']['plan_m'] + RISE_LOW + DROP_RPCK + SLACK
gp112 = r['R_GP112']['plan_m'] + RISE_UP + SLACK
br = r['R_BR1']['plan_m'] + r['R_BR2']['plan_m'] + (DROP_RCI + SLACK_BR) * 2
mv = r['R_MV1']['plan_m'] + r['R_MV2']['plan_m'] + MV_END * 2
d140 = r['D_GP140']['plan_m'] + D_UP_RPCK + D_OUT
d112 = r['D_GP112']['plan_m'] + D_UP_RCI * 2 + D_OUT
dmv = r['D_MV1']['plan_m'] + r['D_MV2']['plan_m'] + D_MV_END * 2
drain = d140 + d112 + dmv
drain_in = drain - D_OUT * 2
case = RISE_LOW + RISE_UP + 0.3 * 2
vvf = (gp140 + VVF_SLACK) + (gp112 + br + VVF_SLACK) + (r['R_MV1']['plan_m'] + r['R_MV2']['plan_m'] + VVF_MV_END * 2)

Q = dict(ref_new=up(gp140 + gp112), ref_br=up(br), ref_mv=up(mv), vp25=up(drain), gw25=up(drain_in), case=up(case), vvf=up(vvf))

M = dict(
    ref_new=(f"平面実測 GP140系統 {r['R_GP140']['plan_m']}m＋GP112主管 {r['R_GP112']['plan_m']}m"
             f"＋立上り（架台下段 {RISE_LOW}m・上段 {RISE_UP}m）＋RPCK立下り {DROP_RPCK}m＋余長 {SLACK}m×2 ＝ {gp140 + gp112:.2f}m"),
    ref_br=(f"平面実測 分岐→RCI {r['R_BR1']['plan_m']}m・{r['R_BR2']['plan_m']}m＋立下り {DROP_RCI}m×2＋余長 {SLACK_BR}m×2 ＝ {br:.2f}m"),
    ref_mv=(f"平面実測 移設1 {r['R_MV1']['plan_m']}m・移設2 {r['R_MV2']['plan_m']}m＋両端（立下り・既設接続）{MV_END}m×2 ＝ {mv:.2f}m"),
    vp25=(f"平面実測 GP140系統 {r['D_GP140']['plan_m']}m・GP112系統 {r['D_GP112']['plan_m']}m・移設 {r['D_MV1']['plan_m']}m＋{r['D_MV2']['plan_m']}m"
          f"＋ドレンアップ立上り（{D_UP_RPCK}m＋{D_UP_RCI}m×2）＋屋外排出 {D_OUT}m×2＋移設接続 {D_MV_END}m×2 ＝ {drain:.2f}m"),
    gw25=f"ドレン管のうち屋内部分（屋外排出 {D_OUT}m×2 を除く）＝ {drain_in:.2f}m",
    case=f"屋外の立上り（下段 {RISE_LOW}m・上段 {RISE_UP}m）＋曲がり部 0.3m×2 ＝ {case:.2f}m",
    vvf=(f"内外連絡線＝新設 GP140 {gp140:.2f}m＋GP112 {gp112 + br:.2f}m（ツイン渡り含む）＋余長 {VVF_SLACK}m×2、"
         f"移設延長 {r['R_MV1']['plan_m'] + r['R_MV2']['plan_m']:.2f}m＋{VVF_MV_END}m×2 ＝ {vvf:.2f}m"),
)

BASIS_TABLES = [
    ('1. 冷媒配管（空調図 A3 1/100 実測＋想定）', ['系統', '管径', '平面実測(m)', '想定加算(m)', '合計(m)', '想定内容'], [
        ('GP140（RPCK-GP140KA ベーカリー作業室）', 'φ9.52/15.88', r['R_GP140']['plan_m'], round(gp140 - r['R_GP140']['plan_m'], 2), round(gp140, 2),
         f'架台下段 立上り {RISE_LOW}m・天吊への立下り {DROP_RPCK}m・余長 {SLACK}m'),
        ('GP112 主管（同時ツイン）', 'φ9.52/15.88', r['R_GP112']['plan_m'], round(gp112 - r['R_GP112']['plan_m'], 2), round(gp112, 2),
         f'架台上段 立上り {RISE_UP}m・余長 {SLACK}m'),
        ('GP112 分岐（RCI-GP56KA×2）', 'φ6.35/12.70', round(r['R_BR1']['plan_m'] + r['R_BR2']['plan_m'], 2),
         round(br - r['R_BR1']['plan_m'] - r['R_BR2']['plan_m'], 2), round(br, 2), f'カセットへの立下り {DROP_RCI}m・余長 {SLACK_BR}m ×2'),
        ('移設1・2 延長（既設 80形）', 'φ9.52/15.88', round(r['R_MV1']['plan_m'] + r['R_MV2']['plan_m'], 2), MV_END * 2, round(mv, 2),
         f'両端の立下り・既設配管との接続 {MV_END}m×2'),
        ('合計 → 内訳書', '', '', '', round(gp140 + gp112 + br + mv, 2),
         f"新設 9.52/15.88 {Q['ref_new']}m・分岐 6.35/12.70 {Q['ref_br']}m・移設延長 9.52/15.88 {Q['ref_mv']}m"),
    ]),
    ('2. ドレン配管 VP25（二重線の1/2を延長とする）', ['系統', '口径', '平面実測(m)', '想定加算(m)', '合計(m)', '備考'], [
        ('GP140（RPCK）→ 外壁', '25A', r['D_GP140']['plan_m'], D_UP_RPCK + D_OUT, round(d140, 2), 'ドレンアップメカ立上り・屋外排出'),
        ('GP112（RCI×2）→ 外壁', '25A', r['D_GP112']['plan_m'], D_UP_RCI * 2 + D_OUT, round(d112, 2), '内蔵ドレンアップ立上り・屋外排出'),
        ('移設1・2 延長', '25A', round(r['D_MV1']['plan_m'] + r['D_MV2']['plan_m'], 2), D_MV_END * 2, round(dmv, 2), '既設ドレンとの接続'),
        ('合計 → 内訳書', '', '', '', round(drain, 2), f"VP25 {Q['vp25']}m・保温（屋内）{Q['gw25']}m"),
    ]),
    ('3. 機器・付帯（空調図）', ['記号', '数量', '備考'], [
        ('RAS-GP140RSH4（日立 5HP）＋RPCK-GP140KA（厨房用天吊）', '1組', 'ドレンアップメカ DUCK-140KA2 付'),
        ('RAS-GP112RSH4（日立 4HP）＋RCI-GP56KA×2（天井カセット4方向）', '1組', '同時ツイン（分岐管付）'),
        ('二段置き架台', '1基', '室外機2台を上下に設置（要見積）'),
        ('移設（既設 80形）', '2台', '移設元1→移設先1、移設元2→移設先2'),
        ('外壁開口', '2箇所', '新設冷媒管・ドレン管の貫通'),
        ('内外連絡線 VVF 2.0-3C', f"{Q['vvf']}m", M['vvf']),
    ]),
]
