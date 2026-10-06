#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
（仮称）サンフレッチェ広島 三矢寮新築工事　空調設備工事 御見積書（宮地機工様式）生成
=====================================================================================
様式: 参照見積（ドーミーイン福山 空調換気見積／宮地機工様式）と同一構成
  表紙(工事) ／ 内訳書(1.空調工事) ／ 内訳書(2.換気工事) ／ 内訳書(3.金額変更案)【朱書き】
  ／ 法定福利費内訳明細書 ／ 御見積条件
  A4縦、ＭＳ Ｐゴシック、公開列のみ印刷。内部列（原価・粗利）は印刷範囲外。
金額は全て数式。基準単価（想定原価＝材料単価＋労務単価）× 提出係数(COEF) → 提出単価（10円単位）。
粗利 = 提出金額 − 基準原価。表紙内部欄に 原価合計／粗利／粗利率、粗利率別参考提出額。
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers import (fnt, put, merge, sd, set_border, grid, hline, fill_range, set_widths,  # noqa: E402
                     est_lines, text_width_pt, row_h, page_setup,
                     FILL_Y, FILL_G, FILL_L, C_GRAYTXT, FMT_AMT, FMT_QTY, FONT_NAME, PT_PER_UNIT)
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402
from openpyxl.utils.indexed_list import IndexedList  # noqa: E402
from openpyxl.workbook.defined_name import DefinedName  # noqa: E402
from openpyxl.worksheet.pagebreak import Break  # noqa: E402
from openpyxl.worksheet.properties import PageSetupProperties  # noqa: E402
import math  # noqa: E402
import pricing_v2 as PV  # noqa: E402

sys.path.insert(0, os.path.dirname(HERE))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("src_items", os.path.join(os.path.dirname(HERE), "build_estimate.py"))

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else HERE

# =====================================================================
# 案件情報
# =====================================================================
CLIENT = '株式会社共栄店舗'          # 元請（詳細工程表の作成者）。要確認
PROJECT_1 = '（仮称）サンフレッチェ広島　三矢寮新築工事'
PROJECT_2 = '空調設備工事（空調・換気／図面06ベース・金額変更案08）'
PROJECT_FULL = '（仮称）サンフレッチェ広島　三矢寮新築工事　空調設備工事'
SITE = '広島県安芸高田市吉田町西浦字日南山835-27'
TERM = '全体工期 2026年5月1日～2027年2月15日（空調工事は工程表による・別途お打ち合わせ）'
PAYMENT = '別途お打ち合わせ'
VALIDITY = '発行後3ヶ月'
EST_DATE = datetime.date(2026, 10, 6)
DATE_FMT = 'yyyy"年"m"月"d"日"'
COMPANY = '宮地機工株式会社'
REP = '代表取締役　濱本　義樹'
ZIP = '〒722-0051'
ADDR = '広島県尾道市東尾道9-9'
TEL = 'TEL.0848-20-2121'
FAX = 'FAX.0848-20-2126'
STAFF = '濱本　義武'

SH_COVER = '表紙(工事)'
SH_WF = '法定福利費内訳明細書'
SH_COND = '御見積条件'

# 見積書の種類（空調工事／換気工事で別ブック）。各ブック = ベース図面06 ＋ 追加図面08（朱書き）
KINDS = {
    'ac': dict(
        label='空調工事', file='御見積書_三矢寮新築工事_空調工事_20261006.xlsx',
        project2='空調工事（機械設備図06ベース＋金額変更案08 空調追加）',
        details=[
            dict(sheet='内訳書(1.空調工事)', no=1, heading='１．空調工事（機械設備図 06）', keys=['A1', 'A2', 'A3', 'A4'],
                 red=False, cover='空調工事（機械設備図 06）', short='空調工事', labor='空調工事 労務費'),
            dict(sheet='内訳書(2.空調追加)', no=2, heading='２．金額変更案 No5・6 空調追加（検討図 08 朱書き）', keys=['C2'],
                 red=True, cover='金額変更案 No5・6 空調追加（検討図 08）', short='空調追加', labor='空調追加 労務費'),
        ],
        cover_note='［空調機器（空調機器表・追加分 PA-P140U7GTNB・PA-P224L7HTNB）は元請様手配、電気工事・建築工事・自動制御は含まず］',
        basis_tables=[0, 1, 2, 4],
    ),
    'vent': dict(
        label='換気工事', file='御見積書_三矢寮新築工事_換気工事_20261006.xlsx',
        project2='換気工事（機械設備図06ベース＋金額変更案08 ロスナイ中止）',
        details=[
            dict(sheet='内訳書(1.換気工事)', no=1, heading='１．換気工事（機械設備図 06）', keys=['B1', 'B2', 'B3', 'B4', 'B5'],
                 red=False, cover='換気工事（機械設備図 06）', short='換気工事', labor='換気工事 労務費'),
            dict(sheet='内訳書(2.ロスナイ中止)', no=2, heading='２．金額変更案 No3・4 ロスナイ中止（検討図 08 朱書き・減額は負数表示）', keys=['C1'],
                 red=True, cover='金額変更案 No3・4 ロスナイ中止（検討図 08・減額・代替機器）', short='ロスナイ中止', labor='ロスナイ中止・代替 労務費'),
        ],
        cover_note='［換気機器（換気機器表・代替分 BFS-SUDC・V-08PPXD8）は元請様手配、電気工事・建築工事・自動制御は含まず］',
        basis_tables=[3, 4],
    ),
}

G = dict(coef_default=PV.COEF, overhead_rate=PV.OVERHEAD, rounding_unit=PV.ROUND_UNIT, labor_day_cost=PV.LABOR_DAY_COST, labor_day_list=PV.LABOR_DAY_LIST)
WELFARE_RATES = [
    ('健康保険料', 0.04890, '健康保険料率 9.780%（協会けんぽ 広島県 令和8年度）×1/2（労使折半）'),
    ('介護保険料', 0.00810, '介護保険料率 1.620%（全国一律 令和8年度）×1/2（労使折半）'),
    ('子ども・子育て支援金', 0.00115, '支援金率 0.230%（令和8年4月分〜）×1/2（労使折半）'),
    ('厚生年金保険料', 0.09150, '厚生年金保険料率 18.300%（平成29年9月以降固定）×1/2（労使折半）'),
    ('雇用保険料', 0.01050, '雇用保険料率（建設の事業）事業主負担分 1.050%'),
    ('子ども・子育て拠出金', 0.00360, '拠出金率 0.360%（事業主全額負担）'),
]

C_RED = 'C00000'
CIRC = '①②③④⑤⑥⑦⑧⑨'
FILL_RED = PatternFill('solid', fgColor='FDE9E9')


def q(sheet):
    return "'" + sheet + "'"


# =====================================================================
# 明細データ（図面拾い結果）— 前回ワークブックの明細リストを流用
#   行: (区分06/08, 名称, 規格, 数量, 単位, 基準単価(想定原価・材工), 根拠, 内部メモ)
# =====================================================================
def load_items():
    src = open(os.path.join(os.path.dirname(HERE), 'build_estimate.py'), encoding='utf-8').read()
    body = src.split('A1 = [')[1].split('SECTIONS = [')[0]
    ns = {}
    exec('A1 = [' + body, ns)
    return {k: ns[k] for k in ['A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'B3', 'B4', 'B5', 'C1', 'C2']}


ITEMS = load_items()

# 材料費／労務費の按分率（労務費率）— 法定福利費の算定基礎（労務費）を内訳書で求めるための想定
LABOR_RATIO = {
    '据付': 0.85, '取付': 0.80, '搬入': 0.90, '配線': 0.60, '試運転': 0.95, '書類': 0.90,
    '配管': 0.45, 'ケース': 0.40, 'スリーブ': 0.35, '貫通': 0.50, '充填': 0.10, '試験': 0.90,
    '保温': 0.55, 'ホース': 0.60, 'ダクト': 0.50, 'ダンパー': 0.40, 'フレキ': 0.45,
    'VHS': 0.30, 'HS ': 0.30, 'BOX': 0.30, 'フード 取付': 0.90, 'ウェザーカバー': 0.90, 'フード': 0.25,
    '吸気口': 0.35, '分岐管': 0.90, 'リモコン': 0.60, '一式': 0.50,
}


def split_cost(name, spec, price):
    """基準単価を材料・労務に按分（100円単位）。名称のキーワードで労務率を決める"""
    txt = name + ' ' + spec
    ratio = None
    for key in ['フード 取付', 'ウェザーカバー', '吸気口', '分岐管', 'リモコン', '試運転', '搬入', '据付', '取付',
                '配線', '書類', '充填', '試験', '貫通', 'スリーブ', 'ケース', 'ホース', '保温', 'フレキ',
                'ダンパー', 'ダクト', '配管', 'VHS', 'HS ', 'BOX', 'フード']:
        if key in txt:
            ratio = LABOR_RATIO[key]
            break
    if ratio is None:
        ratio = LABOR_RATIO['一式']
    lab = int(round(price * ratio / 100.0)) * 100
    lab = max(0, min(lab, price))
    return price - lab, lab


PUBLIC_REMARK = {
    '実測': '図面実測数量', '推測': '想定数量（別紙条件書）', '実測+推測': '図面実測＋想定（別紙）',
    '図面カウント': '', '－': '',
}


def to_lines(keys):
    out = []
    for k in keys:
        for (kb, name, spec, qty, unit, price, basis, note) in ITEMS[k]:
            mat, md, ref, src = PV.price(k, name, spec, unit, price)
            pub = PUBLIC_REMARK.get(basis, '')
            txt = name + spec
            if ('支給品' in txt or '元請支給' in txt) and '支給外' not in txt:
                pub = pub or '支給品の取付費'
            elif (k in ('A1', 'B1') or '据付' in name) and not any(w in name for w in ('搬入', '書類', '配線', '取付')):
                pub = pub or '本体は元請様支給'
            elif '減額' in note or '(中止)' in name:
                pub = pub or '図面08 中止に伴う減額'
            out.append(dict(section=k, name=name, spec=spec, qty=qty, unit=unit, mat=mat, md=md, ref=ref, src=src,
                            basis=basis, memo=note, pub=pub, red=(kb == '08')))
    return out


SECTION_TITLES = {
    'A1': '（1）空調機器据付（機器は元請様支給）', 'A2': '（2）冷媒配管', 'A3': '（3）ドレン配管',
    'A4': '（4）付帯工事・試運転調整',
    'B1': '（1）換気機器据付（機器は元請様支給）', 'B2': '（2）ダクト工事', 'B3': '（3）ダクト保温',
    'B4': '（4）制気口・ボックス', 'B5': '（5）フード類・その他',
    'C1': '（1）No3・4 ロスナイ中止（減額・代替機器）', 'C2': '（2）No5・6 空調追加',
}

NOTES = {
    'cover': [
        '本見積は機械設備図（図面No.06 若本建築事務所 \'26.1.31）に基づき当社にて数量を拾い出して積算しております。金額変更案検討図（図面No.08）による追加・変更は内訳書 No.3（朱書き）に計上しています。実施数量との差異は別途精算とさせていただきます。',
        '空調機器・換気機器（室内機・室外機・リモコン・換気扇・全熱交換器・屋外機架台・ドレンアップ等 機器表記載の本体および付属品）は元請様手配のため含みません（据付・取付費のみ計上）。',
        '機器の電源供給・接地等の電気工事、基礎・躯体貫通穴明け・スリーブ穴埋め・天井点検口等の建築工事、衛生・消火・ガス・浄化槽設備、自動制御設備は含みません。',
        '機器・資材の揚重機（クレーン・レッカー等）、仮設設備、産業廃棄物の処分は元請様にてご手配・ご負担願います。',
        '一式計上および想定数量の項目は別紙「御見積条件」記載の前提にて計上しており、実数量確定後に精算させていただきます。',
        '本見積書に記載なき事項については別途とさせて頂きます。工事に係る電気・水道は無償支給願います。',
        '本見積金額には消費税は含まれておりません。有効期限内でも銅管・鋼材等の市況が著しく変動した場合は再見積をさせていただくことがあります。',
    ],
    'conditions': [
        '本見積は機械設備図 06（特記仕様書・空調機器表・換気機器表・空調平面図・換気平面図・厨房廻り詳細図）に基づき当社にて拾い出した数量により積算しております。配管・ダクトの平面延長は図面（A3 1:300、厨房詳細 1:70）から計測し、立上り・立下り・機器接続部および図面に経路の記載がない部分は想定数量として計上しています（別紙【2】参照）。',
        '金額変更案検討図 08 のうち No3・4（ロスナイ中止）および No5・6（空調追加）を内訳書 No.3 に朱書きで計上しています。ロスナイ中止はベース計上分の減額と代替機器（中間ファン・パイプファン・吸気口）の計上を併記しています。No1（庇中止）・No2（既存フェンス再利用）は対象外です。',
        '空調機器・換気機器は元請様手配のため本見積には含みません（室内機・室外機・集中リモコン・換気扇・中間ファン・全熱交換器・パイプファン・有圧扇・屋外機架台（2段架台含む）・ドレンアップ・SUS製フード・ウェザーカバー等、機器表記載の本体および付属品）。本見積は上記機器の搬入・据付・取付費のみを計上しています。',
        '追加空調（追AC1〜5 同時トリプル）の分岐管は機器付属品として元請様支給を想定し、取付費のみ計上しています。支給外の場合は別途申し受けます。',
        '機器の電源供給（電源・動力配線、盤、接地、インバータ盤）は電気工事とし含みません。機器付属の制御盤およびリモコン制御の配管・配線（工事区分表「機械」）は本見積に計上しています。',
        '基礎（室外機基礎）、躯体・外壁の穴明け、スリーブ・型枠の穴埋め、天井点検口、天井・壁の開口補強および仕上げ補修は建築工事とし含みません（工事区分表による）。外壁貫通スリーブ材のみ計上しています。',
        '冷媒管は被覆銅管（製造者標準品）とし、露出部は化粧ケース仕上げとして計上しています。特記仕様書は脱酸銅管／被覆銅管とも未選択のため、管種凡例（被覆銅管）によっています。',
        'ドレン管の保温は特記仕様書の保温表に記載がないため、公共建築工事標準仕様書に準じ天井内 GW保温筒20 ALGC として計上しています。不要の場合は減額いたします。',
        '厨房フード①〜④（SUS製、グリスフィルター付）は機械設備図のフードリストにより本見積に計上しています。厨房機器工事の範囲となる場合は減額いたします。',
        'ロスナイ中止後の OA 側ダクト・制気口は図示どおり自然給気として残置する前提で計上しています。撤去・変更がある場合は別途協議とさせていただきます。',
        '冷媒配管の追加充填ガスは想定量で計上しています。系統・配管長の確定後に精算いたします。',
        '施工図・竣工図（完成図）の作成、風量測定・試験成績書の作成、官庁検査対応は含みません。必要な場合は別途お見積りいたします。',
        '仮設（足場・高所作業車・仮設電気・水道・資材置場等）および産業廃棄物の処分費は元請様にてご負担願います（当社発生材は指定集積場所への分別搬出まで）。',
        '工期は全体工程表（2026.8.18 共栄店舗）に基づく通常の日中作業を前提としております。夜間・休日作業、工程の大幅な変更や他工事との輻輳による手待ち、工期延長に伴う経費増は別途協議とさせていただきます。',
        '本見積書に記載なき事項については別途とさせていただきます。工事に係る電気・水道は無償支給願います。',
        '本見積金額には消費税は含まれておりません。労務費に係る法定福利費（事業主負担分）は別紙「法定福利費内訳明細書」のとおり計上しています。',
    ],
    'checks': [
        '宛名は元請様を株式会社共栄店舗（詳細工程表作成者）と想定して記載しています。ご指定があれば修正します。',
        '空調平面図の配管線（冷媒管＝黒線、ドレン管＝青線）および換気平面図のダクト線（排気＝黒太線、給気＝青線）をベクトルデータから計測しています。機器記号と重なる短い線分は除外しているため、実測値は若干少なめになる傾向があります。',
        '2F 寮室のルームエアコン（RAC-3 66台）は図面に配管線の記載がなく、壁掛機→バルコニー屋外機 4m/台 の想定です。',
        '追AC1〜5 は図面08に配管経路の記載がなく、室内機・室外機の位置から経路長を推定しています（別紙【2】）。',
        '区画貫通処理は空調平面図1Fの区画貫通部記号（●）2箇所と、追加空調の廊下区画壁 各系統1箇所の想定です。',
        'SUS製フード・ウェザーカバーは換気機器表の付属品として元請様支給と解釈し、取付費のみ計上しています。',
        '吸気口 KS-8841PR3-SG（図面08 朱書き）は支給範囲が不明のため材工で計上しています。支給の場合は材料分を減額します。',
    ],
}


# =====================================================================
# 内訳書
# =====================================================================
def build_detail(ws, cfg):
    no, heading, section_keys, red = cfg['no'], cfg['heading'], cfg['keys'], cfg['red']
    lines = to_lines(section_keys)
    color = C_RED if red else None
    set_widths(ws, dict(A=4, B=27, C=24, D=4, E=8, F=5, G=10, H=13, I=15,
                        J=10, K=7, L=10, M=10, N=7, O=12, P=12, Q=9, R=12, S=8, T=11, U=8, V=40))
    merge(ws, 'A1:I1')
    put(ws, 'A1', '内　訳　書', size=16, bold=True, h='center', color=color)
    merge(ws, 'J1:V1')
    put(ws, 'J1', '原　価　内　訳　書（内部用・印刷範囲外）', size=11, bold=True, h='center',
        color=C_GRAYTXT, fill=FILL_G)
    fill_range(ws, 'J1:V1', FILL_G)
    ws.row_dimensions[1].height = 26
    put(ws, 'A2', '工事名：' + PROJECT_FULL + '　' + KIND_LABEL[0], color=color)
    put(ws, 'I2', f'内訳書 No.{no}', h='right', color=color)
    ws.row_dimensions[2].height = 18
    merge(ws, 'A3:B3')
    merge(ws, 'C3:D3')
    for ref, txt in [('A3', '名　　称'), ('C3', '規格・寸法'), ('E3', '数 量'), ('F3', '単位'),
                     ('G3', '単　価'), ('H3', '金　　額'), ('I3', '備　考')]:
        put(ws, ref, txt, h='center', fill=FILL_G)
    fill_range(ws, 'A3:I3', FILL_G)
    for ref, txt in [('J3', '材料原価'), ('K3', '人工/単位'), ('L3', '労務原価'), ('M3', '基準原価単価'), ('N3', '提出係数'),
                     ('O3', '基準原価'), ('P3', '労務費(提出)'), ('Q3', '数量根拠'), ('R3', '粗利'),
                     ('S3', '粗利率'), ('T3', '参考定価ベース'), ('U3', '当社/参考'), ('V3', '単価出典・メモ（内部）')]:
        put(ws, ref, txt, size=9, h='center', fill=FILL_G, color=C_GRAYTXT, shrink=True)
    ws.row_dimensions[3].height = 20
    merge(ws, 'A4:I4')
    put(ws, 'A4', heading, bold=True, color=color, shrink=True)
    ws.row_dimensions[4].height = 18
    merge(ws, 'A5:B5')
    merge(ws, 'C5:D5')
    ws.row_dimensions[5].height = 18
    r = 6
    cur_sec = None
    wrapped = []
    for ln in lines:
        if ln['section'] != cur_sec:
            cur_sec = ln['section']
            merge(ws, f'A{r}:I{r}')
            put(ws, f'A{r}', SECTION_TITLES[cur_sec], size=10, bold=True, color=color, shrink=True)
            ws.row_dimensions[r].height = 18
            r += 1
        merge(ws, f'A{r}:B{r}')
        name_txt = '　' + ln['name']
        long_name = text_width_pt(name_txt, 10) > (31 - 0.8) * PT_PER_UNIT / 0.85
        put(ws, f'A{r}', name_txt, size=10, wrap=long_name, shrink=not long_name, color=color)
        merge(ws, f'C{r}:D{r}')
        put(ws, f'C{r}', ln['spec'] or None, size=10, shrink=True, indent=1, color=color)
        put(ws, f'E{r}', ln['qty'], size=10, h='right', fmt='#,##0_ ;[Red]-#,##0_ ', color=color)
        put(ws, f'F{r}', ln['unit'], size=10, h='center', color=color)
        put(ws, f'G{r}', f'=IF(M{r}="","",ROUND(M{r}*N{r},-1))', size=10, h='right', fmt=FMT_AMT, color=color)
        put(ws, f'H{r}', f'=IF(G{r}="","",ROUND(E{r}*G{r},0))', size=10, h='right',
            fmt='#,##0_ ;[Red]-#,##0_ ', color=color)
        put(ws, f'I{r}', ln['pub'] or None, size=10, h='center', shrink=True, color=color)
        put(ws, f'J{r}', ln['mat'], size=10, h='right', fmt=FMT_AMT, fill=FILL_Y)
        put(ws, f'K{r}', ln['md'], size=10, h='right', fmt='0.00', fill=FILL_Y)
        put(ws, f'L{r}', f'=ROUND(K{r}*LABOR_DAY,0)', size=10, h='right', fmt=FMT_AMT)
        put(ws, f'M{r}', f'=J{r}+L{r}', size=10, h='right', fmt=FMT_AMT)
        put(ws, f'N{r}', '=COEF', size=10, h='center', fmt='0.00', fill=FILL_Y)
        put(ws, f'O{r}', f'=E{r}*M{r}', size=10, h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
        put(ws, f'P{r}', f'=ROUND(E{r}*L{r}*N{r},0)', size=10, h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
        put(ws, f'Q{r}', ln['basis'], size=9, h='center', shrink=True,
            fill=(FILL_RED if ln['basis'] == '推測' else None))
        put(ws, f'R{r}', f'=IF(H{r}="","",H{r}-O{r})', size=10, h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
        put(ws, f'S{r}', f'=IF(OR(H{r}="",H{r}=0),"",R{r}/H{r})', size=10, h='right', fmt='0.0%')
        put(ws, f'T{r}', (round(ln['ref']) if ln['ref'] else None), size=10, h='right', fmt=FMT_AMT)
        put(ws, f'U{r}', (f'=IF(OR(T{r}="",T{r}=0),"",G{r}/T{r})' if ln['ref'] else None), size=10, h='right', fmt='0%')
        put(ws, f'V{r}', ((ln['src'] + '｜' if ln['src'] else '') + (ln['memo'] or '')) or None, size=9)
        ws.row_dimensions[r].height = 18
        if long_name:
            ws.row_dimensions[r].height = max(18, row_h(est_lines(name_txt, 31, 10), 10))
            wrapped.append(r)
        r += 1
    last = r - 1
    blank = r
    merge(ws, f'A{blank}:B{blank}')
    merge(ws, f'C{blank}:D{blank}')
    ws.row_dimensions[blank].height = 18
    sub = blank + 1
    merge(ws, f'A{sub}:D{sub}')
    put(ws, f'A{sub}', '【小　　計】', bold=True, h='center', color=color)
    put(ws, f'H{sub}', f'=SUM(H6:H{blank})', bold=True, h='right', fmt='#,##0_ ;[Red]-#,##0_ ', color=color)
    put(ws, f'O{sub}', f'=SUM(O6:O{blank})', bold=True, h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
    put(ws, f'P{sub}', f'=SUM(P6:P{blank})', bold=True, h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
    put(ws, f'K{sub}', f'=SUMPRODUCT(E6:E{blank},K6:K{blank})', bold=True, h='right', fmt='#,##0.0')
    put(ws, f'R{sub}', f'=H{sub}-O{sub}', bold=True, h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
    put(ws, f'S{sub}', f'=IF(H{sub}=0,"",R{sub}/H{sub})', bold=True, h='right', fmt='0.0%')
    ws.row_dimensions[sub].height = 22
    grid(ws, f'A3:I{sub}', outer='medium', vert='thin', horiz='hair')
    grid(ws, f'J3:V{sub}', outer='thin', vert='thin', horiz='hair')
    for rng in ('A3:I3', 'J3:V3'):
        hline(ws, rng, 'bottom', 'thin')
    hline(ws, f'A{sub}:I{sub}', 'top', 'medium')
    hline(ws, f'J{sub}:V{sub}', 'top', 'medium')
    for c in range(1, 10):
        set_border(ws.cell(sub, c), bottom='medium')
    set_border(ws.cell(sub, 1), left='medium')
    set_border(ws.cell(sub, 9), right='medium')
    page_setup(ws, f'A1:I{sub}', fit_h=0, title_rows='1:3', footer='&P / &N')
    return dict(first=6, last=last, blank=blank, sub=sub, lines=lines, wrapped=wrapped, cfg=cfg)


# =====================================================================
# 法定福利費内訳明細書
# =====================================================================
def build_welfare(ws, details):
    set_widths(ws, dict(A=2, B=25, C=9, D=9, E=14, F=16, G=31))
    merge(ws, 'B1:G1')
    put(ws, 'B1', '法 定 福 利 費 内 訳 明 細 書', size=14, bold=True, h='center')
    ws.row_dimensions[1].height = 26
    merge(ws, 'B2:G2')
    put(ws, 'B2', f'="（御見積書 No."&{q(SH_COVER)}!K3&" の添付資料）"', size=10, h='center')
    ws.row_dimensions[2].height = 16
    put(ws, 'B4', '見積年月日', fill=FILL_L, indent=1)
    merge(ws, 'C4:E4')
    put(ws, 'C4', f"={q(SH_COVER)}!J4", h='left', fmt=DATE_FMT, indent=1)
    put(ws, 'F4', '見積No.', fill=FILL_L, indent=1)
    put(ws, 'G4', f'=IF({q(SH_COVER)}!K3="","",{q(SH_COVER)}!K3)', h='left', indent=1)
    for r, lab, val in [(5, '発注者名', CLIENT + '　御中'), (6, '工事名', PROJECT_FULL), (7, '施工場所', SITE)]:
        put(ws, f'B{r}', lab, fill=FILL_L, indent=1)
        merge(ws, f'C{r}:G{r}')
        put(ws, f'C{r}', val, shrink=True, indent=1)
    put(ws, 'B8', '会社名', fill=FILL_L, indent=1)
    merge(ws, 'C8:E8')
    put(ws, 'C8', COMPANY, indent=1)
    put(ws, 'F8', '所在地', fill=FILL_L, indent=1)
    put(ws, 'G8', ADDR, indent=1)
    grid(ws, 'B4:G8', outer='thin', vert='thin', horiz='thin')
    for r in range(4, 9):
        ws.row_dimensions[r].height = 20
    ws.row_dimensions[3].height = 8
    ws.row_dimensions[9].height = 10
    put(ws, 'B10', '【1】　労務費の内訳（法定福利費の算定基礎）', bold=True)
    ws.row_dimensions[10].height = 20
    note1 = ('※ 本見積の労務費は、内訳書各項目の材工共単価のうち労務費相当額（自社施工分）の合計です。'
             '機器は元請様手配のため含みません。')
    merge(ws, 'B11:G11')
    put(ws, 'B11', note1, size=10, wrap=True)
    ws.row_dimensions[11].height = row_h(est_lines(note1, 104, 10), 10)
    put(ws, 'B12', '項　　目', h='center', fill=FILL_G)
    merge(ws, 'C12:D12')
    put(ws, 'C12', '労務費（円）', h='center', fill=FILL_G)
    merge(ws, 'E12:G12')
    put(ws, 'E12', '摘　　要', h='center', fill=FILL_G)
    fill_range(ws, 'B12:G12', FILL_G)
    rows1 = []
    for i, d in enumerate(details):
        rows1.append((13 + i, d['cfg']['labor'], f"={q(d['cfg']['sheet'])}!P{d['sub']}",
                      f"内訳書 No.{d['cfg']['no']} 各項目の労務費相当額の合計"))
    tot_row = 13 + len(details)
    rows1.append((tot_row, '労 務 費 合 計', f'=SUM(C13:C{tot_row - 1})', '← 法定福利費の算定基礎額'))
    for r, lab, f, memo in rows1:
        bold = (r == tot_row)
        put(ws, f'B{r}', lab, bold=bold, h=('center' if bold else None), indent=(0 if bold else 1))
        merge(ws, f'C{r}:D{r}')
        put(ws, f'C{r}', f, bold=bold, h='right', fmt=FMT_AMT)
        merge(ws, f'E{r}:G{r}')
        put(ws, f'E{r}', memo, size=10, bold=bold, indent=1)
    for r in range(12, tot_row + 1):
        ws.row_dimensions[r].height = 20
    grid(ws, f'B12:G{tot_row}', outer='medium', vert='thin', horiz='thin')
    hline(ws, f'B{tot_row}:G{tot_row}', 'top', 'double')
    for c in range(2, 8):
        set_border(ws.cell(tot_row, c), bottom='medium')
    r = tot_row + 1
    ws.row_dimensions[r].height = 10
    r += 1
    put(ws, f'B{r}', '【2】　法定福利費の算定', bold=True)
    ws.row_dimensions[r].height = 20
    r += 1
    merge(ws, f'B{r}:G{r}')
    put(ws, f'B{r}', '計算式：　法定福利費 ＝ 労務費 × 事業主負担料率　（保険ごとに円未満切捨て）', size=10)
    ws.row_dimensions[r].height = 18
    r += 1
    hdr2 = r
    put(ws, f'B{r}', '保険の種類', h='center', fill=FILL_G)
    merge(ws, f'C{r}:D{r}')
    put(ws, f'C{r}', '対象労務費（円）', size=10, h='center', fill=FILL_G)
    put(ws, f'E{r}', '事業主負担料率', size=10, h='center', fill=FILL_G)
    put(ws, f'F{r}', '法定福利費（円）', size=10, h='center', fill=FILL_G)
    put(ws, f'G{r}', '算定根拠', h='center', fill=FILL_G)
    fill_range(ws, f'B{r}:G{r}', FILL_G)
    ws.row_dimensions[r].height = 22
    r += 1
    labor_cell = f'$C${tot_row}'
    for name, rate, basis in WELFARE_RATES:
        put(ws, f'B{r}', name, indent=1)
        merge(ws, f'C{r}:D{r}')
        put(ws, f'C{r}', f'={labor_cell}', h='right', fmt=FMT_AMT)
        put(ws, f'E{r}', rate, h='right', fmt='0.000%_ ')
        put(ws, f'F{r}', f'=ROUNDDOWN(C{r}*E{r},0)', h='right', fmt=FMT_AMT)
        put(ws, f'G{r}', basis, size=9, wrap=True)
        ws.row_dimensions[r].height = max(22, row_h(est_lines(basis, 31, 9), 9, pad=5))
        r += 1
    wf_first, wf_last = hdr2 + 1, r - 1
    tot = r
    put(ws, f'B{tot}', '合　　計', bold=True, h='center')
    merge(ws, f'C{tot}:D{tot}')
    put(ws, f'E{tot}', f'=SUM(E{wf_first}:E{wf_last})', bold=True, h='right', fmt='0.000%_ ')
    put(ws, f'F{tot}', f'=SUM(F{wf_first}:F{wf_last})', bold=True, h='right', fmt=FMT_AMT)
    ws.row_dimensions[tot].height = 24
    grid(ws, f'B{hdr2}:G{tot}', outer='medium', vert='thin', horiz='thin')
    hline(ws, f'B{tot}:G{tot}', 'top', 'double')
    for c in range(2, 8):
        set_border(ws.cell(tot, c), bottom='medium')
    ws.row_dimensions[tot + 1].height = 10
    notes = ['※ 料率は見積作成時点（令和8年度）の公表料率によります。料率が改定された場合は改定後の料率により精算させていただきます。',
             f'※ 法定福利費は御見積書の{CIRC[len(details)]}に計上しています。']
    r = tot + 2
    for t in notes:
        merge(ws, f'B{r}:G{r}')
        put(ws, f'B{r}', t, size=10, wrap=True)
        ws.row_dimensions[r].height = row_h(est_lines(t, 104, 10), 10)
        r += 1
    last = r - 1
    page_setup(ws, f'B1:G{last}', fit_h=1)
    return dict(labor_total=labor_cell, total_row=tot, rate_cell=f'$E${tot}', amount_cell=f'F{tot}')


# =====================================================================
# 表紙(工事)
# =====================================================================
def build_cover(ws, details, wf, kind):
    n = len(details)
    FIRST = 22
    WF_ROW = FIRST + n
    OH_ROW = WF_ROW + 1
    DISC_ROW = OH_ROW + 2
    set_widths(ws, dict(A=6, B=8, C=3, D=15, E=9, F=9, G=7, H=5, I=7, J=7, K=14, L=12,
                        M=26, N=12, O=12, P=12, Q=9, R=12, S=12))
    merge(ws, 'A1:L2')
    put(ws, 'A1', '御　見　積　書', size=20, bold=True, h='center')
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 22
    put(ws, 'J3', 'No.', h='right')
    merge(ws, 'K3:L3')
    put(ws, 'K3', None, h='center')
    hline(ws, 'K3:L3', 'bottom', 'thin')
    ws.row_dimensions[3].height = 20
    merge(ws, 'J4:L4')
    put(ws, 'J4', EST_DATE, h='right', fmt=DATE_FMT)
    ws.row_dimensions[4].height = 20
    merge(ws, 'A5:F5')
    put(ws, 'A5', CLIENT, size=14, h='center')
    hline(ws, 'A5:F5', 'bottom', 'thin')
    put(ws, 'G5', '御中', size=12, h='left')
    ws.row_dimensions[5].height = 26
    ws.row_dimensions[6].height = 12
    TOTAL_ROW = DISC_ROW + 1
    put(ws, 'A7', '金額', size=12, h='center')
    merge(ws, 'B7:E7')
    put(ws, 'B7', f'="¥"&TEXT(K{TOTAL_ROW},"#,##0")&"-"', size=14, bold=True, h='center')
    hline(ws, 'B7:E7', 'bottom', 'double')
    put(ws, 'F7', '（税別）', h='left')
    put(ws, 'H7', COMPANY, size=12, bold=True)
    ws.row_dimensions[7].height = 28
    ws.row_dimensions[8].height = 10
    merge(ws, 'A9:F9')
    put(ws, 'A9', '上記の通り御見積申し上げます。', h='left')
    put(ws, 'H9', REP)
    put(ws, 'A10', '何卒ご用命賜わりますようお願い申し上げます。')
    put(ws, 'H11', ZIP)
    merge(ws, 'A12:B12')
    put(ws, 'A12', '工事名', h='distributed', indent=1)
    merge(ws, 'D12:G12')
    put(ws, 'D12', PROJECT_1, shrink=True)
    put(ws, 'H12', ADDR)
    merge(ws, 'D13:G13')
    put(ws, 'D13', kind['project2'], shrink=True)
    put(ws, 'H13', TEL)
    put(ws, 'K13', FAX)
    merge(ws, 'A14:B14')
    put(ws, 'A14', '施工場所', h='distributed', indent=1)
    merge(ws, 'D14:G14')
    put(ws, 'D14', SITE, size=10, shrink=True)
    put(ws, 'H14', '担当者')
    put(ws, 'J14', STAFF)
    for r, lab, val in [(15, '工事期限', TERM), (16, '御支払条件', PAYMENT), (17, '有効期限', VALIDITY)]:
        merge(ws, f'A{r}:B{r}')
        put(ws, f'A{r}', lab, h='distributed', indent=1)
        merge(ws, f'D{r}:L{r}')
        put(ws, f'D{r}', val, shrink=True)
    for r in range(9, 18):
        ws.row_dimensions[r].height = 19
    ws.row_dimensions[14].height = 22
    ws.row_dimensions[18].height = 12
    merge(ws, 'B19:F19')
    merge(ws, 'I19:J19')
    for ref, txt, sz in [('A19', '項　目', 10), ('B19', '内　　　容', 11), ('G19', '数 量', 11), ('H19', '単位', 10),
                         ('I19', '単  価', 11), ('K19', '金　　額', 11), ('L19', '備　考', 11)]:
        put(ws, ref, txt, size=sz, h='center', fill=FILL_G, shrink=True)
    fill_range(ws, 'A19:L19', FILL_G)
    merge(ws, 'B20:L20')
    put(ws, 'B20', '【' + PROJECT_FULL + '　' + kind['label'] + '】', indent=1, shrink=True)
    merge(ws, 'B21:L21')
    put(ws, 'B21', kind['cover_note'], size=10, indent=1, shrink=True)
    for r in range(22, TOTAL_ROW + 1):
        merge(ws, f'B{r}:F{r}')
        merge(ws, f'I{r}:J{r}')
    rows = []
    for i, d in enumerate(details):
        rows.append((FIRST + i, CIRC[i], d['cfg']['cover'], f"={q(d['cfg']['sheet'])}!H{d['sub']}",
                     f"内訳書 No.{d['cfg']['no']}", C_RED if d['cfg']['red'] else None))
    rows.append((WF_ROW, CIRC[n], '法定福利費（労務費に係る事業主負担分）', f"={q(SH_WF)}!{wf['amount_cell']}", '別紙明細書', None))
    rows.append((OH_ROW, CIRC[n + 1], '諸経費（現場経費・資材運搬・工事諸経費）', f'=ROUND(SUM(K{FIRST}:K{WF_ROW - 1})*OVERHEAD_RATE,-3)',
                 f'="{CIRC[0]}〜{CIRC[n - 1]}計の"&TEXT(OVERHEAD_RATE,"0%")', None))
    for r, no, name, fk, remark, color in rows:
        put(ws, f'A{r}', no, h='center', color=color)
        put(ws, f'B{r}', name, indent=1, shrink=True, color=color)
        put(ws, f'G{r}', 1, h='right', fmt=FMT_QTY, color=color)
        put(ws, f'H{r}', '式', h='center', color=color)
        put(ws, f'I{r}', f'=K{r}', h='right', fmt='#,##0_ ;[Red]-#,##0_ ', color=color)
        put(ws, f'K{r}', fk, h='right', fmt='#,##0_ ;[Red]-#,##0_ ', color=color)
        put(ws, f'L{r}', remark, size=10, h='center', shrink=True, color=color)
    put(ws, f'B{DISC_ROW}', '出精値引き', indent=1)
    put(ws, f'K{DISC_ROW}', f'=IF(TARGET="",FLOOR(SUM(K{FIRST}:K{OH_ROW}),ROUND_UNIT)-SUM(K{FIRST}:K{OH_ROW}),TARGET-SUM(K{FIRST}:K{OH_ROW}))', h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
    put(ws, f'L{DISC_ROW}', '端数調整', size=10, h='center')
    put(ws, f'B{TOTAL_ROW}', '　合　　計', bold=True, indent=1)
    put(ws, f'K{TOTAL_ROW}', f'=SUM(K{FIRST}:K{DISC_ROW})', bold=True, h='right', fmt=FMT_AMT)
    put(ws, f'L{TOTAL_ROW}', '（税別）', size=10, h='center')
    for r in range(19, TOTAL_ROW + 1):
        ws.row_dimensions[r].height = 24
    ws.row_dimensions[20].height = 22
    ws.row_dimensions[21].height = 20
    grid(ws, f'A19:L{TOTAL_ROW}', outer='medium', vert='thin', horiz='thin')
    hline(ws, f'A{TOTAL_ROW}:L{TOTAL_ROW}', 'top', 'double')
    for c in range(1, 13):
        set_border(ws.cell(TOTAL_ROW, c), bottom='medium')
    ws.row_dimensions[TOTAL_ROW + 1].height = 12
    r = TOTAL_ROW + 2
    cover_notes = [t.replace('金額変更案検討図（図面No.08）による追加・変更は内訳書 No.3（朱書き）に計上しています。',
                             ('金額変更案検討図（図面No.08）の No5・6 空調追加は内訳書 No.2（朱書き）に計上しています。換気工事は別途御見積書によります。'
                              if kind['label'] == '空調工事' else
                              '金額変更案検討図（図面No.08）の No3・4 ロスナイ中止は内訳書 No.2（朱書き）に減額・代替機器を計上しています。空調工事は別途御見積書によります。'))
                   for t in NOTES['cover']]
    for t in cover_notes + ['詳細条件は別紙「御見積条件」をご参照ください。']:
        put(ws, f'A{r}', '※', size=9.5, h='center', v='top')
        merge(ws, f'B{r}:L{r}')
        put(ws, f'B{r}', t, size=9.5, wrap=True, v='top')
        ws.row_dimensions[r].height = row_h(est_lines(t, 96, 9.5), 9.5, pad=3)
        r += 1
    last_note = r - 1

    # ---- 内部エリア（M〜S、印刷範囲外）: 単価設定・原価・粗利 ----
    put(ws, 'M3', '【設定・内部用】（印刷範囲外）', bold=True, color=C_GRAYTXT, fill=FILL_G)
    put(ws, 'N3', None, fill=FILL_G)
    params = [
        (4, '提出係数（原価→定価ベース単価）', G['coef_default'], '0.00', True),
        (5, '諸経費率（現場経費・運搬・雑材・工事諸経費）', G['overhead_rate'], '0%', True),
        (6, '出精値引き 丸め単位（目標額空欄時）', G['rounding_unit'], '#,##0', True),
        (7, '法定福利費率（労務費比）', '=WELFARE_RATE', '0.000%', False),
        (8, '労務原価日額（円/人工）', G['labor_day_cost'], '#,##0', True),
        (9, '目標提出額（税別・空欄なら丸め）', None, '#,##0', True),
        (10, '参考：宮地機工 人工単価（定価ベース）', G['labor_day_list'], '#,##0', False),
    ]
    for rr, lab, val, fmt, is_input in params:
        put(ws, f'M{rr}', lab, size=10, color=C_GRAYTXT, fill=FILL_G, shrink=True)
        put(ws, f'N{rr}', val, h='right', fmt=fmt, fill=(FILL_Y if is_input else None))
    grid(ws, 'M3:N10', outer='thin', vert='thin', horiz='thin')
    put(ws, 'M11', '※ 原価＝材料原価＋人工×N8。提出単価＝原価×N4（1.22で参考見積の人工単価23,225に一致）。目標提出額 N9 を入れると出精値引きで合わせる', size=9, color=C_GRAYTXT)
    for ref, txt in [('M19', '内部集計（原価・粗利）'), ('N19', '基準原価'), ('O19', '労務費(提出)'),
                     ('P19', '粗利'), ('Q19', '粗利率')]:
        put(ws, ref, txt, size=10, h='center', color=C_GRAYTXT, fill=FILL_G, shrink=True)
    for i, d in enumerate(details):
        rr = FIRST + i
        put(ws, f'M{rr}', CIRC[i] + d['cfg']['short'], size=10)
        sh = d['cfg']['sheet']
        put(ws, f'N{rr}', f"={q(sh)}!O{d['sub']}", h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
        put(ws, f'O{rr}', f"={q(sh)}!P{d['sub']}", h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
        put(ws, f'P{rr}', f'=K{rr}-N{rr}', h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
        put(ws, f'Q{rr}', f'=IF(K{rr}=0,"",P{rr}/K{rr})', h='right', fmt='0.0%')
    put(ws, f'M{WF_ROW}', CIRC[n] + '法定福利費（原価＝提出値）', size=10, shrink=True)
    put(ws, f'N{WF_ROW}', f'=K{WF_ROW}', h='right', fmt=FMT_AMT)
    put(ws, f'M{OH_ROW}', CIRC[n + 1] + '諸経費（原価計上なし）', size=10, shrink=True)
    put(ws, f'N{OH_ROW}', 0, h='right', fmt=FMT_AMT)
    put(ws, f'M{DISC_ROW}', '出精値引き（原価なし・粗利から控除）', size=10, shrink=True)
    put(ws, f'N{DISC_ROW}', 0, h='right', fmt=FMT_AMT)
    put(ws, f'P{DISC_ROW}', f'=K{DISC_ROW}', h='right', fmt='#,##0_ ;[Red]-#,##0_ ')
    put(ws, f'M{TOTAL_ROW}', '合計（原価合計／粗利／粗利率）', size=10, bold=True, shrink=True)
    put(ws, f'N{TOTAL_ROW}', f'=SUM(N{FIRST}:N{DISC_ROW})', bold=True, h='right', fmt=FMT_AMT)
    put(ws, f'O{TOTAL_ROW}', f'=SUM(O{FIRST}:O{DISC_ROW})', h='right', fmt=FMT_AMT)
    put(ws, f'P{TOTAL_ROW}', f'=K{TOTAL_ROW}-N{TOTAL_ROW}', bold=True, h='right', fmt=FMT_AMT)
    put(ws, f'Q{TOTAL_ROW}', f'=IF(K{TOTAL_ROW}=0,"",P{TOTAL_ROW}/K{TOTAL_ROW})', bold=True, h='right', fmt='0.0%')
    grid(ws, f'M19:Q{TOTAL_ROW}', outer='thin', vert='thin', horiz='hair')
    hline(ws, 'M19:Q19', 'bottom', 'thin')
    hline(ws, f'M{TOTAL_ROW}:Q{TOTAL_ROW}', 'top', 'thin')
    put(ws, 'M32', '粗利率別 参考提出額（税別・万円未満切上げ）', size=10, color=C_GRAYTXT, fill=FILL_G, shrink=True)
    put(ws, 'N32', '参考提出額', size=10, h='center', color=C_GRAYTXT, fill=FILL_G)
    put(ws, 'O32', '必要提出係数', size=10, h='center', color=C_GRAYTXT, fill=FILL_G)
    for i, rate in enumerate([0.10, 0.15, 0.20, 0.25, 0.30]):
        rr = 33 + i
        put(ws, f'M{rr}', rate, h='center', fmt='"粗利率 "0%')
        put(ws, f'N{rr}', f'=ROUNDUP($N${TOTAL_ROW}/(1-M{rr}),-4)', h='right', fmt=FMT_AMT)
        put(ws, f'O{rr}', f'=IF(SUM($N${FIRST}:$N${WF_ROW - 1})=0,"",ROUND(($N${TOTAL_ROW}/(1-M{rr})-$N${WF_ROW}-$K${OH_ROW})/SUM($N${FIRST}:$N${WF_ROW - 1}),3))',
            h='right', fmt='0.000')
    grid(ws, 'M32:O37', outer='thin', vert='thin', horiz='thin')
    put(ws, 'M38', '※ 必要提出係数は諸経費を現状額に固定した場合の目安', size=9, color=C_GRAYTXT)
    page_setup(ws, f'A1:L{last_note}', fit_h=1)
    return dict(last_note=last_note, total_row=TOTAL_ROW)


# =====================================================================
# 御見積条件
# =====================================================================
def build_conditions(ws, details, kind):
    W = dict(A=5, B=10, C=25, D=20, E=16, F=19)
    set_widths(ws, W)
    BF = W['B'] + W['C'] + W['D'] + W['E'] + W['F']
    put(ws, 'A1', '御見積条件・注意事項', size=14, bold=True)
    ws.row_dimensions[1].height = 24
    put(ws, 'A2', PROJECT_FULL + '　' + kind['label'] + '　御見積書 添付', size=10)
    ws.row_dimensions[2].height = 16
    ws.row_dimensions[3].height = 8
    r = 4
    put(ws, f'A{r}', '【1】御見積条件・注意事項', size=12, bold=True)
    ws.row_dimensions[r].height = 22
    r += 1
    for i, t in enumerate(conditions_for(kind), 1):
        put(ws, f'A{r}', f'{i}.', h='right', v='top')
        merge(ws, f'B{r}:F{r}')
        put(ws, f'B{r}', t, wrap=True, v='top')
        ws.row_dimensions[r].height = row_h(est_lines(t, BF, 11), 11, pad=8)
        r += 1
    ws.row_dimensions[r].height = 10
    r += 1
    break_after = r - 1
    ws.row_breaks.append(Break(id=break_after))
    put(ws, f'A{r}', '【2】想定数量（推測）項目の前提', size=12, bold=True)
    ws.row_dimensions[r].height = 22
    r += 1
    merge(ws, f'A{r}:F{r}')
    put(ws, f'A{r}', '図面に数量・経路の記載がなく当社にて想定した項目です。「図面実測＋想定」は平面延長を図面計測し、立上り等を想定加算したものです。実数量確定後に精算させていただきます。', size=10, wrap=True)
    ws.row_dimensions[r].height = row_h(2, 10, pad=4)
    r += 1
    hdr = r
    put(ws, f'A{r}', 'No.', size=10, h='center', fill=FILL_G)
    put(ws, f'B{r}', '内訳書', size=10, h='center', fill=FILL_G)
    put(ws, f'C{r}', '項　　目', size=10, h='center', fill=FILL_G)
    merge(ws, f'D{r}:E{r}')
    put(ws, f'D{r}', '前提・想定内容', size=10, h='center', fill=FILL_G)
    put(ws, f'F{r}', '数量（区分）', size=10, h='center', fill=FILL_G)
    fill_range(ws, f'A{r}:F{r}', FILL_G)
    ws.row_dimensions[r].height = 20
    r += 1
    k = 0
    for d in details:
        no = f"No.{d['cfg']['no']}"
        for ln in d['lines']:
            if ln['basis'] not in ('推測', '実測+推測') or not ln['memo']:
                continue
            k += 1
            item = ln['name'] + ((' ' + ln['spec']) if ln['spec'] else '')
            qtxt = f"{ln['qty']:,} {ln['unit']}（{'想定' if ln['basis']=='推測' else '実測＋想定'}）"
            put(ws, f'A{r}', k, size=10, h='center', v='center')
            put(ws, f'B{r}', no, size=10, h='center', v='center')
            put(ws, f'C{r}', item, size=10, wrap=True, v='center', indent=1)
            merge(ws, f'D{r}:E{r}')
            put(ws, f'D{r}', ln['memo'], size=10, wrap=True, v='center', indent=1)
            put(ws, f'F{r}', qtxt, size=10, wrap=True, v='center', h='center')
            nl = max(est_lines(item, W['C'] - 3, 10), est_lines(ln['memo'], W['D'] + W['E'] - 3, 10),
                     est_lines(qtxt, W['F'], 10))
            ws.row_dimensions[r].height = max(18, row_h(nl, 10, pad=4))
            r += 1
    grid(ws, f'A{hdr}:F{r - 1}', outer='medium', vert='thin', horiz='thin')
    ws.row_dimensions[r].height = 10
    r += 1
    put(ws, f'A{r}', '【3】図面読み取りに関する確認事項', size=12, bold=True)
    ws.row_dimensions[r].height = 22
    r += 1
    for i, t in enumerate(checks_for(kind), 1):
        put(ws, f'A{r}', f'{i}.', h='right', v='top')
        merge(ws, f'B{r}:F{r}')
        put(ws, f'B{r}', t, wrap=True, v='top')
        ws.row_dimensions[r].height = row_h(est_lines(t, BF, 11), 11, pad=8)
        r += 1
    last = r - 1
    page_setup(ws, f'A1:F{last}', fit_h=0)
    ws.print_title_rows = None
    return dict(last=last, n_assump=k)



# =====================================================================
# 数量拾い根拠（内部用・印刷範囲外扱い）
# =====================================================================
BASIS_TABLES = [
    ("1. 冷媒配管（ベース06）系統別", ["系統", "口径記号", "平面実測(m)", "推測加算(m)", "合計(m)", "推測内容"], [
        ("RAC-2×3 和室・洋室・DK", "①", 28.1, 9.0, 37.1, "屋外機→屋内機 立上り 3台×3m"),
        ("AC-7 面談室", "②", 13.0, 4.0, 17.0, "北西ゾーン実測60.3mを3系統に配分。立上り4m"),
        ("AC-5 管理人室", "②", 18.0, 4.0, 22.0, "同上"),
        ("AC-1 ホール(ツイン)", "⑦主/③枝", 29.0, 4.0, 33.0, "主管17m・枝管12m。立上り4m(⑦)"),
        ("AC-6/AC-8/AC-9/RAC-1×2 厨房ブロック", "③/②/③/①", 22.2, 20.0, 42.2, "重なり配管の未計測補正8m(RAC-1休憩室)・立上り4系統×3〜4m"),
        ("AC-1 食堂・ミーティング(ツイン×2)", "⑦主/③枝", 30.7, 8.0, 38.7, "各系統 主管8m・枝管7.5m。立上り各4m"),
        ("AC-10 多目的スペース(2F)", "③", 10.2, 11.5, 21.7, "2F平面3.5m・立管(1F地上→2F天井)8m"),
        ("AC-2 コーチルーム(ツイン)", "⑥主/③枝", 11.1, 4.0, 15.1, "主管5m・枝管6m。立上り4m"),
        ("AC-1 トレーニング(ツイン)＋AC-5 ケア室", "⑦/③ ・ ②", 32.0, 8.0, 40.0, "AC-1 主8m枝12m・AC-5 12m。立上り各4m"),
        ("AC-3 脱衣室(ツイン)", "③主/②枝", 13.9, 4.0, 17.9, "主管7m・枝管7m。立上り4m"),
        ("RAC-2×5 来客室", "①", 2.7, 18.0, 20.7, "屋外機が各室直近。1台4m×5台"),
        ("RAC-3×66 2F寮室等", "①", 0.0, 264.0, 264.0, "図面に配管線なし。壁掛機→バルコニー屋外機 4m/台"),
        ("RAC-4 寮務スタッフ室", "②", 0.0, 5.0, 5.0, "同上 5m"),
        ("合計", "", 211.0, 363.5, 574.5, "口径別: ①360 ②77 ③96 ⑥9 ⑦57 (m・端数調整後)"),
    ]),
    ("2. ドレン配管（ベース06）", ["区分", "口径", "平面実測(m)", "推測加算(m)", "合計(m)", "備考"], [
        ("1F 空調平面図 青線(D)", "VP20", 6.6, 30.0, 36.6, "RAC-1/2 ドレンアップ吐出→屋外 10台×3m"),
        ("1F 空調平面図 青線(D)", "VP25", 87.3, 0.0, 87.3, "口径ラベル未割当31.3mを25/40へ比例配分済"),
        ("1F 空調平面図 青線(D)", "VP40", 50.2, 18.0, 68.2, "立下り・屋外放流部 12箇所×1.5m"),
        ("2F 空調平面図 青線(D) AC-10", "VP25", 6.1, 0.0, 6.1, ""),
        ("合計", "", 150.2, 48.0, 198.2, ""),
    ]),
    ("3. 冷媒配管（図面08 追加空調・すべて推測）", ["系統", "口径記号", "平面実測(m)", "推測(m)", "合計(m)", "推定根拠"], [
        ("追AC1 PA-P140U7GTNB トリプル", "③主/①枝", 0, 51, 51, "室外機:物干場側(AC-3隣) 室内機:ホール・洗濯室前廊下・階段ホール"),
        ("追AC2 PA-P224L7HTNB トリプル", "⑥主/③枝", 0, 57, 57, "室外機:南側(AC-1/5隣) 室内機:1F南廊下3箇所"),
        ("追AC3 PA-P224L7HTNB トリプル", "⑥主/③枝", 0, 64, 64, "室外機:東側地上 室内機:2F北廊下3箇所"),
        ("追AC4 PA-P224L7HTNB トリプル", "⑥主/③枝", 0, 51, 51, "室外機:東側地上(倉庫2東) 室内機:階段ホール2・南廊下1"),
        ("追AC5 PA-P224L7HTNB トリプル", "⑥主/③枝", 0, 69, 69, "室外機:東側地上 室内機:2F南廊下3箇所"),
        ("合計", "", 0, 292, 292, "口径別: ①35 ③184 ⑥73"),
    ]),
    ("4. ダクト（ベース06）", ["図面", "系統", "100φ(m)", "150φ(m)", "200φ(m)", "250φ(m)", "300φ(m)", "備考"], [
        ("1F換気平面図(p22) 黒太線", "EA", 62.6, 122.4, 25.2, 0, 0, "150φに口径未判読16.6m含む（実測）"),
        ("1F換気平面図(p22) 青線", "OA", 3.5, 50.4, 45.7, 0, 0, "150φに未判読9.1m含む（実測）"),
        ("2F換気平面図(p23) 黒太線", "EA", 5.2, 28.2, 9.8, 0, 0, "実測"),
        ("2F換気平面図(p23) 青線", "OA", 0, 0, 3.5, 0, 0, "実測"),
        ("厨房廻り詳細図(p24) 1:70", "EA", 0, 0, 9.0, 6.0, 5.0, "推測（二重線表記のため目視換算）"),
        ("厨房廻り詳細図(p24) 1:70", "OA(FS-1/2・F-3給気)", 0, 0, 7.5, 6.0, 3.0, "推測"),
        ("外壁貫通部・フード接続", "EA/OA", 0, 58.0, 0, 0, 0, "推測 1.0m/箇所×58"),
        ("合計", "", 71.3, 259.0, 100.7, 12.0, 8.0, "内訳書は端数切上げ"),
    ]),
    ("5. 機器台数（図面カウント）", ["記号", "台数", "備考"], [
        ("AC-1 (ツイン) 室内8/室外4", "4系統", "空調機器表・平面図"),
        ("AC-2,3 (ツイン) 室内各2/室外各1", "2系統", ""),
        ("AC-5,6,7,8,9,10 室内各1/室外各1", "7台", "AC-5は2台"),
        ("RAC-1/2/3/4", "2/8/66/1", "2F寮室×16+×3+×11+×8+×4+×24=66"),
        ("追AC1 室内3/室外1、追AC2〜5 室内各3/室外各1", "5系統", "図面08 p19・p20 朱書き □ 位置より"),
        ("区画貫通部 ●", "1F 2箇所", "空調平面図1F 凡例"),
        ("VD", "1F 9・2F 4", "換気平面図ラベル数"),
    ]),
]


def build_basis(ws, kind):
    set_widths(ws, dict(A=36, B=18, C=12, D=12, E=12, F=12, G=12, H=60))
    put(ws, 'A1', '数量拾い根拠（内部用）　※計測方法: PDF図面(A3 1:300、厨房詳細 1:70)のベクトル線分を色・線幅で分離し延長を集計。「実測」=図面線分の平面延長、「推測」=図面に無い部分の推定', size=10, bold=True)
    r = 3
    for ti, (title, headers, rows) in enumerate(BASIS_TABLES):
        if ti not in kind['basis_tables']:
            continue
        put(ws, f'A{r}', title, bold=True, fill=FILL_L)
        r += 1
        for i, h in enumerate(headers):
            put(ws, f'{chr(65 + i)}{r}', h, size=10, bold=True, h='center', fill=FILL_G)
        hdr = r
        r += 1
        for row in rows:
            for i, v in enumerate(row):
                put(ws, f'{chr(65 + i)}{r}', v, size=10, h=('left' if isinstance(v, str) else 'right'),
                    fmt=('#,##0.0' if isinstance(v, float) else None))
            r += 1
        grid(ws, f'A{hdr}:{chr(64 + len(headers))}{r - 1}', outer='thin', vert='thin', horiz='hair')
        r += 1
    page_setup(ws, f'A1:H{r}', fit_h=0)
    ws.page_setup.orientation = 'landscape'


# =====================================================================
KIND_LABEL = ['']


def conditions_for(kind):
    base = NOTES['conditions']
    if kind['label'] == '空調工事':
        drop = ('ロスナイ', '吸気口', 'フード①')
        repl = {base[1]: base[1].replace('No3・4（ロスナイ中止）および No5・6（空調追加）を内訳書 No.3 に朱書きで計上しています。ロスナイ中止はベース計上分の減額と代替機器（中間ファン・パイプファン・吸気口）の計上を併記しています。',
                                         'No5・6（空調追加 追AC1〜5）を内訳書 No.2 に朱書きで計上しています。No3・4（ロスナイ中止）は換気工事の見積書に計上しています。')}
    else:
        drop = ('冷媒管は', '追加空調', '追加充填', 'ドレン管の保温')
        repl = {base[1]: base[1].replace('No3・4（ロスナイ中止）および No5・6（空調追加）を内訳書 No.3 に朱書きで計上しています。ロスナイ中止はベース計上分の減額と代替機器（中間ファン・パイプファン・吸気口）の計上を併記しています。',
                                         'No3・4（ロスナイ中止）を内訳書 No.2 に朱書きで計上しています。ベース計上分の減額と代替機器（中間ファン・パイプファン・吸気口）の計上を併記しています。No5・6（空調追加）は空調工事の見積書に計上しています。')}
    out = []
    for t in base:
        if any(k in t for k in drop):
            continue
        out.append(repl.get(t, t))
    return out


def checks_for(kind):
    base = NOTES['checks']
    if kind['label'] == '空調工事':
        drop = ('換気平面図', 'SUS製フード', '吸気口')
        out = [t.replace('（冷媒管＝黒線、ドレン管＝青線）および換気平面図のダクト線（排気＝黒太線、給気＝青線）', '（冷媒管＝黒線、ドレン管＝青線）') for t in base if not any(k in t for k in drop)]
    else:
        drop = ('RAC-3', '追AC', '区画貫通')
        out = [t.replace('空調平面図の配管線（冷媒管＝黒線、ドレン管＝青線）および換気平面図のダクト線', '換気平面図のダクト線') for t in base if not any(k in t for k in drop)]
    return out


def build_master(ws):
    set_widths(ws, dict(A=14, B=12, C=9, D=12, E=12, F=14, G=14, H=10, I=70))
    put(ws, 'A1', '単価マスタ（内部）　原価＝材料原価＋人工×労務原価日額、提出（定価ベース）＝原価×提出係数。参考列は宮地機工 参考見積8件（2025.11〜2026.10）から整理', size=10, bold=True)
    put(ws, 'A2', f'労務原価日額 {PV.LABOR_DAY_COST:,} 円/人工　参考見積の人工単価 {PV.LABOR_DAY_LIST:,} 円/人工（6330476-3 配管工費 40人工 929,000）　提出係数 {PV.COEF}　材料係数 ×{PV.MAT_FACTOR}（継手30%＋消耗15%＋支持金物40%）', size=9)
    hdr = ['キー', '材料原価', '人工', '労務原価', '原価', '提出(定価ベース)', '参考定価ベース', '当社/参考', '出典・根拠']
    for i, h in enumerate(hdr, 1):
        put(ws, f'{chr(64 + i)}4', h, size=10, bold=True, h='center', fill=FILL_G)
    r = 5
    for k, (mat, md, ref, src) in PV.MASTER.items():
        put(ws, f'A{r}', k, size=10)
        put(ws, f'B{r}', mat, size=10, h='right', fmt=FMT_AMT)
        put(ws, f'C{r}', md, size=10, h='right', fmt='0.00')
        put(ws, f'D{r}', f'=ROUND(C{r}*LABOR_DAY,0)', size=10, h='right', fmt=FMT_AMT)
        put(ws, f'E{r}', f'=IF(B{r}="","",B{r}+D{r})', size=10, h='right', fmt=FMT_AMT)
        put(ws, f'F{r}', f'=IF(E{r}="","",ROUND(E{r}*COEF,-1))', size=10, h='right', fmt=FMT_AMT)
        put(ws, f'G{r}', (round(ref) if ref else None), size=10, h='right', fmt=FMT_AMT)
        put(ws, f'H{r}', (f'=IF(OR(G{r}="",F{r}=""),"",F{r}/G{r})' if ref else None), size=10, h='right', fmt='0%')
        put(ws, f'I{r}', src, size=9)
        r += 1
    grid(ws, f'A4:I{r - 1}', outer='thin', vert='thin', horiz='hair')
    r += 1
    put(ws, f'A{r}', '参考見積の経費構造', size=10, bold=True, fill=FILL_L)
    rows = [('部門内経費', '消耗品及び雑材料 2.6%＋資材運搬交通費 3.5%＋現場経費 7.4% ＝ 15.7%（据付・撤去）／ 3.0%＋4.1%＋8.6% ＝ 19.0%（配管・ダクト・電気）'),
            ('工事諸経費', '直接工事費の 5.0%'),
            ('出精値引', '6330247-1 18.4%／6330248-2 35.1%／6330284-1 14.8%／6330539 26.8%／6330549 22.3%／6330558 12.0%／6330476-3 9.9%／6330344-1 24.9%'),
            ('法定福利費', '労務費×16.04%（金額内含で注記）。当社は別項目で 16.375%（令和8年度）'),
            ('据付単価', '搬入据付 21,700/台（6330476-3 11台）・27,860/台（6330558 VRV）・25,000/台（6330284-1 GHP 24台）・12,500/組（6330539 RA）・12,900/台（6330344-1 天吊）'),
            ('配管', '冷媒 9.52+15.88 4,025/m・9.52+25.40 5,475・12.70+25.40 5,675（10t×2）、ペアコイル 6.35+9.52 988、VP25 313/m・VP13 138/m、配管工費 4.6〜5 m/人工（冷媒）・9〜12 m/人工（塩ビ）'),
            ('その他', 'リモコン配線 9,630/系統、試運転 10,000〜12,500/系統、気密 15,000〜25,000、真空引き 3,750〜5,640、揚重 93,750〜337,500/式、撤去 18,000〜19,500/台、冷媒回収 18,750〜31,250/式、VVF 203/m・電線施工 約500/m')]
    for a, b in rows:
        r += 1
        put(ws, f'A{r}', a, size=10, bold=True)
        merge(ws, f'B{r}:I{r}')
        put(ws, f'B{r}', b, size=9, wrap=True)
        ws.row_dimensions[r].height = 28
    page_setup(ws, f'A1:I{r}', fit_h=0)
    ws.page_setup.orientation = 'landscape'


def build_book(kind):
    KIND_LABEL[0] = kind['label']
    wb = Workbook()
    base = fnt(11)
    wb._fonts = IndexedList([base])
    wb._named_styles['Normal'].font = base
    wb.properties.creator = COMPANY
    wb.properties.title = '御見積書 ' + PROJECT_FULL + ' ' + kind['label']

    ws_cover = wb.active
    ws_cover.title = SH_COVER
    ws_details = [wb.create_sheet(d['sheet']) for d in kind['details']]
    ws_wf = wb.create_sheet(SH_WF)
    ws_cd = wb.create_sheet(SH_COND)
    ws_bs = wb.create_sheet('数量拾い根拠(内部)')
    ws_pm = wb.create_sheet('単価マスタ(内部)')

    details = [build_detail(ws, cfg) for ws, cfg in zip(ws_details, kind['details'])]
    wf = build_welfare(ws_wf, details)
    cv = build_cover(ws_cover, details, wf, kind)
    cd = build_conditions(ws_cd, details, kind)
    build_basis(ws_bs, kind)
    build_master(ws_pm)

    names = {
        'COEF': f"{q(SH_COVER)}!$N$4",
        'OVERHEAD_RATE': f"{q(SH_COVER)}!$N$5",
        'ROUND_UNIT': f"{q(SH_COVER)}!$N$6",
        'WELFARE_RATE': f"{q(SH_WF)}!{wf['rate_cell']}",
        'LABOR_DAY': f"{q(SH_COVER)}!$N$8",
        'TARGET': f"{q(SH_COVER)}!$N$9",
    }
    for k, ref in names.items():
        wb.defined_names[k] = DefinedName(k, attr_text=ref)
    wb.active = 0
    for ws in wb.worksheets:
        ws.sheet_view.tabSelected = (ws.title == SH_COVER)
    wb.calculation.fullCalcOnLoad = True
    out = os.path.join(OUT_DIR, kind['file'])
    wb.save(out)
    return dict(out=out, details=[{k: v for k, v in d.items() if k not in ('lines', 'cfg')} for d in details],
                welfare=wf, cover=cv, conditions=cd)


def main():
    info = {k: build_book(v) for k, v in KINDS.items()}
    print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
