# -*- coding: utf-8 -*-
"""
原価ベース単価体系（宮地機工 参考見積8件から整理）
=================================================
参考見積の構造:
  材料 = 定価ベース材料単価 ×（1 ＋ 継手30% ＋ 消耗品15% ＋ 支持金物40%）
  工費 = 人工 × 23,225 円/人工（6330476-3: 配管工費 40人工 929,000 より）
  部門内経費 = 純工事費の 15.7%（据付・撤去）/ 19.0%（配管・ダクト・電気）
  工事諸経費 = 5%、出精値引 10〜35% で提出額を丸める
当社の整理:
  原価       = 材料原価（参考定価ベース ÷ 1.22 ＝ 仕入想定）＋ 人工 × 原価日額 19,000
  提出単価   = 原価 × 提出係数 1.22（→ 参考見積の人工単価 23,225・材料定価に一致）
  諸経費     = 22%（部門内経費 約17% ＋ 工事諸経費 5% 相当）
  出精値引   = 目標提出額を入力（空欄なら 10万円未満切捨て）
各行: (材料原価/単位, 人工/単位, 参考定価ベース単価 or None, 出典)
"""
import re

LABOR_DAY_COST = 19000     # 原価日額（円/人工）
LABOR_DAY_LIST = 23225     # 参考見積の人工単価（定価ベース）
COEF = 1.22                # 提出係数（原価 → 定価ベース）
OVERHEAD = 0.22            # 諸経費率
ROUND_UNIT = 100000        # 出精値引の丸め単位
MAT_FACTOR = 1.85          # 材料に継手・消耗品・支持金物を乗せる係数（参考見積）


def mat_cost(listed_unit):
    """参考見積の材料単価（定価ベース）→ 継手等込みの材料原価"""
    return round(listed_unit * MAT_FACTOR / COEF, -1)


# ---------------------------------------------------------------- 単価マスタ（出典付き）
# key: (材料原価, 人工, 参考定価ベース単価(材工・部門経費除く), 出典)
MASTER = {
    # 冷媒配管（被覆銅管 10t×2 ペア、継手・支持・消耗品共）
    'REF_①': (mat_cost(1450), 0.20, 1450 * MAT_FACTOR + 0.20 * LABOR_DAY_LIST, '6330539 ペアコイル6.35+9.52 988/m・2分3分級は1,450/m想定、5 m/人工'),
    'REF_②': (mat_cost(1950), 0.21, 1950 * MAT_FACTOR + 0.21 * LABOR_DAY_LIST, '補間（9.52+15.88 4,025 と 6.35+9.52 の間）'),
    'REF_③': (mat_cost(4025), 0.22, 4025 * MAT_FACTOR + 0.22 * LABOR_DAY_LIST, '6330476-3 / 6330344-1 9.52+15.88 4,025/m、4.6 m/人工'),
    'REF_⑥': (mat_cost(5475), 0.28, 5475 * MAT_FACTOR + 0.28 * LABOR_DAY_LIST, '6330476-3 9.52+25.40 5,475/m、3.5 m/人工'),
    'REF_⑦': (mat_cost(5675), 0.30, 5675 * MAT_FACTOR + 0.30 * LABOR_DAY_LIST, '6330476-3 12.70+25.40 5,675/m、3.3 m/人工'),
    'REF_CASE': (1500, 0.10, 1194 + 0.10 * LABOR_DAY_LIST, '配管保温工事費 1,194/m（6330476-3）＋化粧ケース材'),
    'SLEEVE': (900, 0.06, None, 'VP100 スリーブ材＋取付（参考実績なし）'),
    'FIRESTOP': (4500, 0.40, None, '6330248-2 防火区画貫通 88,000/式（箇所数不明）'),
    'LEAK_TEST': (3000, 0.60, 20000, '気密テスト 15,000〜25,000/系統・真空引き 3,750〜5,640/系統（6330558/344-1/549）'),
    'REFRIGERANT': (3800, 0.0, None, 'R32 冷媒代（参考に単価行なし）'),
    # ドレン
    'VP20': (380, 0.10, 138 * MAT_FACTOR + 0.10 * LABOR_DAY_LIST, '6330539 VP13 138/m、塩ビ工費 9.3〜12 m/人工'),
    'VP25': (475, 0.11, 313 * MAT_FACTOR + 0.11 * LABOR_DAY_LIST, '6330344-1/476-3/248-2 VP25 313/m、工費 2,497/m'),
    'VP40': (760, 0.13, None, 'VP25 比例'),
    'DRAIN_INS': (900, 0.06, None, 'GW保温筒20 ALGC（参考実績なし）'),
    'DRAIN_HOSE': (300, 0.05, None, '推定'),
    # 据付
    'PAC_IN': (1600, 0.85, 21700, '6330476-3 搬入据付 238,750/11台≒21,700/台、6330284-1 25,000/台'),
    'PAC_IN_BIG': (2000, 1.00, 27860, '6330558 VRV 90クラス 27,860/台'),
    'PAC_OUT': (3000, 0.80, 21700 + 7500, '搬入据付＋基礎工事 5,800〜10,000/台（6330539/549/476-3）'),
    'PAC_OUT_BIG': (4000, 1.10, 27860 + 10000, '8〜10HP 室外機（防振ゴム・架台固定共）'),
    'RAC_SET': (750, 0.50, 12500 + 5800, '6330539 RA 搬入据付 12,500/組＋基礎 5,833/組'),
    'REMOTE_CTRL': (1000, 0.40, 9630, 'リモコン配線工事 9,630/系統（6330549/558/476-3）'),
    'CRANE': (75000, 0.0, 93750, '揚重工事費（レッカー）93,750/式（6330558）'),
    'CARRY_IN': (0, 1.0, None, '搬入・小運搬 人工'),
    'TEST_RUN': (450, 0.45, 11000, '試運転調整費 10,000〜12,500/系統（6330344-1/549/476-3）'),
    'TEST_RUN_RAC': (0, 0.10, 2500, '6330539 試運転 7,500/3台'),
    'DOCS': (5000, 1.0, None, '書類作成 人工'),
    'WIRE_PAC': (2000, 0.26, 203 * 12 + 500 * 12, 'VVF2.0-3C 203/m＋電線材料施工費 約500/m（12m/系統 8,436）→ 原価 6,900'),
    'WIRE_RAC': (166 * 5 + 300, 0.12, 203 * 5 + 500 * 5, 'VVF2.0-3C 5m/台'),
    'SLINK': (30000, 1.2, None, '集中リモコン制御線 200m 推定'),
    'BRANCH': (600, 0.25, None, '分岐管取付（支給）'),
    # 換気機器
    'FAN_PIPE': (300, 0.30, None, 'パイプファン取付（参考実績なし）'),
    'FAN_CEIL': (500, 0.45, None, '天井扇取付（参考実績なし）'),
    'FAN_DUCT': (2000, 1.20, None, '中間ファン（防振吊）取付'),
    'FAN_PRESS': (1500, 0.90, None, '有圧扇＋ウェザーカバー取付'),
    'HEX_CEIL': (2500, 1.40, None, '全熱交換器 天井埋込（ダクト接続別）'),
    'HEX_WALL': (500, 0.45, None, '壁掛ロスナイ取付'),
    'CYCLE_FAN': (300, 0.35, None, 'サイクル扇'),
    'HOOD_SUS': (300, 0.15, None, 'SUS製フード取付（支給）'),
    'WCOVER': (500, 0.20, None, 'ウェザーカバー取付（支給）'),
    # ダクト（スパイラル 亜鉛鉄板 継手・支持共）
    'SD100': (1000, 0.12, None, 'ダクト（参考実績なし・市況）'),
    'SD150': (1400, 0.14, None, ''),
    'SD200': (1900, 0.16, None, ''),
    'SD250': (2600, 0.20, None, ''),
    'SD300': (3300, 0.24, None, ''),
    'VD': (4500, 0.25, None, ''),
    'DUCT_INS_GW': (1100, 0.08, None, 'GW保温筒25 ALGC'),
    'DUCT_INS_RW': (3200, 0.15, None, 'RW50＋アルミガラスクロス＋金網'),
    'GRILLE': (None, 0.25, None, '制気口 材＋取付0.25人工'),
    'BOX': (None, 0.30, 40550, '6330248-2 チャンバー700×500×500 GW内貼 40,550/個＋取付 8,100/個 → 表面積 1.9m² ≒ 17,500円/m²(原価)'),
    'FLEX': (40000, 0.8, None, ''),
    'HOOD_KITCHEN': (None, 2.0, None, 'SUS厨房フード製作品（外注想定 原価=提出/1.22）'),
    'AIRFLOW_TEST': (10000, 4.0, None, '風量測定・試運転'),
    'INTAKE': (3000, 0.10, None, '吸気口 KS-8841PR3-SG 材＋取付'),
}


def _grille_mat(name):
    m = re.search(r'(\d{3})×(\d{3})', name)
    if not m:
        return 3000
    a = int(m.group(1)) * int(m.group(2)) / 1e6  # m²
    return round(2500 + 60000 * a, -2)


def _box_mat(name):
    m = re.search(r'(\d{3})×(\d{3})×(\d{3})', name)
    if not m:
        return 9000
    w, d, h = (int(x) / 1000 for x in m.groups())
    area = 2 * (w * d + w * h + d * h)
    return round(17500 * area, -2)


def price(section, name, spec, unit, old_price):
    """(材料原価, 人工, 参考定価ベース単価 or None, 出典キー)"""
    n = name + ' ' + spec
    if '冷媒配管 ①' in name: k = 'REF_①'
    elif '冷媒配管 ②' in name: k = 'REF_②'
    elif '冷媒配管 ③' in name: k = 'REF_③'
    elif '冷媒配管 ⑥' in name: k = 'REF_⑥'
    elif '冷媒配管 ⑦' in name: k = 'REF_⑦'
    elif '化粧ケース' in name: k = 'REF_CASE'
    elif 'スリーブ材' in name: k = 'SLEEVE'
    elif '区画貫通' in name: k = 'FIRESTOP'
    elif '気密試験' in name: k = 'LEAK_TEST'
    elif '冷媒追加充填' in name: k = 'REFRIGERANT'
    elif 'VP20' in name: k = 'VP20'
    elif 'VP25' in name: k = 'VP25'
    elif 'VP40' in name: k = 'VP40'
    elif 'ドレン管 保温' in name: k = 'DRAIN_INS'
    elif 'ドレンホース' in name: k = 'DRAIN_HOSE'
    elif '室内機 据付' in name: k = 'PAC_IN_BIG' if ('10HP' in spec or '8HP' in spec) else 'PAC_IN'
    elif '室外機 据付' in name: k = 'PAC_OUT_BIG' if ('10HP' in spec or '8HP' in spec) else 'PAC_OUT'
    elif name.startswith('RAC-') and '据付' in name: k = 'RAC_SET'
    elif '集中リモコン CR-1 取付' in name: k = 'REMOTE_CTRL'
    elif '揚重' in name: k = 'CRANE'
    elif '搬入' in name: k = 'CARRY_IN'
    elif '試運転調整 RAC' in name: k = 'TEST_RUN_RAC'
    elif '試運転調整・風量測定' in name: k = 'AIRFLOW_TEST'
    elif '試運転調整' in name: k = 'TEST_RUN'
    elif '書類' in name: k = 'DOCS'
    elif 'RAC 内外連絡線' in name: k = 'WIRE_RAC'
    elif 'リモコン線・内外連絡線' in name: k = 'WIRE_PAC'
    elif 'S-LINK' in spec or '制御配線' in name: k = 'SLINK'
    elif '分岐管' in name: k = 'BRANCH'
    elif 'ビルトインダクト用' in name: k = 'FLEX'
    elif 'パイプファン' in name: k = 'FAN_PIPE'
    elif '天井扇' in name or '親子扇' in name: k = 'FAN_CEIL'
    elif '中間ファン' in name and 'リモコン' not in name: k = 'FAN_DUCT'
    elif '有圧扇' in name: k = 'FAN_PRESS'
    elif '全熱交換器 据付' in name: k = 'HEX_CEIL'
    elif '壁掛ロスナイ' in name: k = 'HEX_WALL'
    elif 'サイクル扇' in name: k = 'CYCLE_FAN'
    elif 'リモコン配線' in name: k = 'REMOTE_CTRL'
    elif 'ウェザーカバー' in name: k = 'WCOVER'
    elif 'SUS製フード' in name: k = 'HOOD_SUS'
    elif '厨房フード' in name: k = 'HOOD_KITCHEN'
    elif '吸気口 内部' in name: k = 'INTAKE'
    elif '乾燥機排気用スリーブ' in name: k = 'SLEEVE'
    elif 'スパイラルダクト' in name or '貫通部ダクト' in name:
        k = {'100': 'SD100', '150': 'SD150', '200': 'SD200', '250': 'SD250', '300': 'SD300'}[re.search(r'(\d{3})φ', n).group(1)]
    elif name.startswith('VD'): k = 'VD'
    elif 'フレキシブル' in name: k = 'FLEX'
    elif 'OAダクト 保温' in name: k = 'DUCT_INS_GW'
    elif '厨房排気ダクト 保温' in name: k = 'DUCT_INS_RW'
    elif name.startswith(('VHS', 'HS')): k = 'GRILLE'
    elif name.startswith('BOX'): k = 'BOX'
    else:
        # 既定: 旧仮単価を原価とみなし、労務率50%で按分
        lab = old_price * 0.5
        return round(old_price - lab, -2), round(lab / LABOR_DAY_COST, 2), None, '旧仮単価（按分）'
    mat, md, ref, src = MASTER[k]
    if k == 'GRILLE': mat = _grille_mat(name)
    if k == 'BOX':
        mat = _box_mat(name)
        ref = round((mat + md * LABOR_DAY_COST) * COEF)
    if k == 'HOOD_KITCHEN': mat = round(old_price / COEF - md * LABOR_DAY_COST, -3)
    if k == 'SLEEVE' and '乾燥機' in name: mat, md = 6000, 0.3
    if k == 'CARRY_IN':
        # 一式: 旧仮単価（提出）→ 原価換算し人工に
        md = round(old_price / COEF / LABOR_DAY_COST, 1); mat = 0
    if k == 'DOCS': md = round(old_price / COEF / LABOR_DAY_COST, 1)
    if k == 'SLINK' and '追加' in name: mat, md = 12000, 0.5
    if k == 'FLEX' and 'ビルトイン' in name: mat, md = 45000, 1.0
    return mat, md, ref, src
