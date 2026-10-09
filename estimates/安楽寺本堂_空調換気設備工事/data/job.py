# -*- coding: utf-8 -*-
"""
物件定義（宗教法人 安楽寺 本堂 新築工事 空調・換気設備工事）
================================================================
エスト準拠ルール（../../_lib_est）で御見積書を作るための定数・明細・注記。
図面: 当社作図 M-1 空調設備平面図・M-2 換気設備平面図（意匠 平面図 令和8年7月20日版ベース）
機器: 空調機・換気機器とも材工（機器費込み）。空調・換気は部門を分けて計上する。
"""
import datetime
import math

import est_rules as R
import items as IT

Q, M = IT.Q, IT.M

CLIENT = '宗教法人　安楽寺'
PROJECT_1 = '安楽寺　本堂　新築工事'
PROJECT_2 = '空調・換気設備工事'
PROJECT_FULL = '安楽寺　本堂　新築工事　空調・換気設備工事'
SITE = '安楽寺 本堂 新築工事現場（所在地は確認申請書による）'
TERM = '御協議による（建築工程に合わせて施工）'
PAYMENT = '御協議による'
VALIDITY = '10日'
EST_DATE = datetime.date(2026, 10, 9)
FILE = '御見積書_安楽寺本堂新築工事_空調換気設備工事_20261009.xlsx'

EQUIP_ROW = None            # 機器は明細の部門（１ 空調設備機器・４ 換気設備機器）として計上
WORK_TITLE = '空気調和・換気設備工事'
OH_NO = '６'
WF_EQUIP_TXT = '空調機器・換気機器'
COVER_SCOPE = dict(
    include='［空調機・換気機器を含む（材工）。電源・スイッチ等の電気工事、外壁開口補強・仕上げ補修等の建築工事は別途］',
    exclude='［空調機・換気機器を含む（材工）。電源・スイッチ等の電気工事、外壁開口補強・仕上げ補修等の建築工事は別途］',
)

# ---- 機器の単価（原価基準）
#   原価＝定価 × 仕入率（区分別、2026-10-09 確認）
#   提出単価＝原価 ÷（1－目標粗利率）を10円未満切上げ。機器の行も工事と同じ目標粗利率で積み上げる
EQ_RATES = {
    'PAC': (0.20, 'ダイキン業務用（EcoZEAS・FIVESTAR）'),
    'RAC': (0.30, 'ダイキン家庭用（定価あり）'),
    'MEV': (0.32, '三菱電機 換気機器'),
}
SRC_EQ = '原価基準（仕入率）'


def eq_cost(list_price, cls):
    return int(round(list_price * EQ_RATES[cls][0]))


def eq_price(list_price, cls):
    return int(math.ceil(eq_cost(list_price, cls) / (1 - R.TARGET_MARGIN) / 10 - 1e-9) * 10)


def eq(key, name, spec, qty, unit, list_price, cls, src_txt, place, memo=''):
    rate, label = EQ_RATES[cls]
    cost = eq_cost(list_price, cls)
    return dict(kind='item', key=key, name=name, spec=spec, qty=qty, unit=unit,
                price=eq_price(list_price, cls), src=SRC_EQ,
                ref=(f'原価基準: 定価 {list_price:,}円（{src_txt}）× 仕入率 {rate:.2f}（{label}）＝原価 {cost:,}円 '
                     f'÷（1－目標粗利率 {R.TARGET_MARGIN:.2f}）'),
                mat=cost, md=0, master='', basis='図面カウント', pub=place,
                memo=f'定価 {list_price:,}円 × 仕入率 {rate:.2f}（{label}）＝原価 {cost:,}円' + ('｜' + memo if memo else ''))


def own(key, name, spec, qty, unit, mat, md, ref, basis='図面カウント', pub=None, memo='', qmemo=None):
    d = dict(kind='item', key=key, name=name, spec=spec, qty=qty, unit=unit, src=R.SRC_OWN,
             ref=f'当社単価: {ref}（エストに単価なし）', mat=mat, md=md, master='（エストマスタに単価なし）',
             basis=basis, memo=memo)
    if pub:
        d['pub'] = pub
    if qmemo:
        d['qmemo'] = qmemo
    return d


VE = 'VE案 8月10日付 定価'
WIN = '三菱電機 WIN2K 価格（税別）'
MONO = '販売店掲載の参考基準価格（税別）'

SECTIONS = [
    # ------------------------------------------------------------------ 空調
    dict(key='EQAC', no='１', title='空調設備機器', oh=False, lines=[
        dict(kind='head', name='業務用パッケージエアコン（ダイキン）'),
        eq('eq_pac', 'AC-1 床置形ペア EcoZEAS', 'SZRV80BZV（P80）単相200V', 2, '組', 1266000, 'PAC', VE,
           '大間・外陣'),
        dict(kind='head', name='ルームエアコン（ダイキン）'),
        eq('eq_rac28', 'AC-2 壁掛形', 'S284ATEV-W（2.8kW）単相200V', 2, '組', 380000, 'RAC', VE,
           '和室(1)・和室(2)'),
        eq('eq_rac40', 'AC-3 壁掛形', 'S404ATEV-W（4.0kW）単相200V', 1, '組', 450000, 'RAC', VE, '談話室'),
    ]),
    dict(key='AC', no='２', title='空調設備工事', break_after=True, lines=[
        dict(kind='head', name='搬入据付工事'),
        dict(kind='item', key='sa_out', cat='SA室外機', name='SA 室外機', spec='P80（SZRV80BZV）地上設置',
             qty=2, unit='台', mat=1500, md=0.8, master='SA室外機 地上設置 P112 13,000（P80 はエスト見積 11.2-16.0 を準用）',
             basis='図面カウント', pub='大間・外陣', memo='エスト見積の 11.2-16.0 を P80 に準用'),
        dict(kind='item', key='sa_in', cat='SA室内機床置P140', name='SA 室内機', spec='床置形 P80（転倒防止金具共）',
             qty=2, unit='台', mat=1500, md=0.8, master='SA室内機 床置形 P140 13,000（P80 に準用）',
             basis='図面カウント', pub='大間・外陣', memo='エストマスタ 床置形 P140 を P80 に準用'),
        dict(kind='item', key='ra_out', cat='RA室外機', name='RA 室外機', spec='セパレート 2.2-5.0（S284/S404）',
             qty=3, unit='台', mat=500, md=0.4, master='ルームエアコン 室外機 地上設置 2,000',
             basis='図面カウント', pub='和室・談話室'),
        dict(kind='item', key='ra_in', cat='RA室内機壁掛', name='RA 室内機', spec='壁掛（据付板・ドレンホース共）',
             qty=3, unit='台', mat=800, md=0.5, master='ルームエアコン 室内機 壁掛形 P22 5,000',
             basis='図面カウント', pub='和室・談話室'),
        dict(kind='head', name='基礎工事'),
        dict(kind='item', key='base_sa', cat='縁石11.2-16.0', name='基礎工事', spec='縁石基礎（SA 室外機 P80）',
             qty=2, unit='台', mat=2500, md=0.15, master='基礎工事 スカイエア 縁石基礎 P28〜P140 5,000',
             basis='図面カウント', pub='大間・外陣', memo='エスト見積 縁石 11.2-16.0 を準用'),
        own('base_ra', '室外機置台', 'RA 室外機用 プラ製（防振ゴム付）', 3, '台', 2500, 0.1,
            '置台 2,500＋0.1人工', pub='和室・談話室'),
        dict(kind='head', name='試運転調整費'),
        dict(kind='item', key='tr_sa', cat='試運転SA', name='試運転調整費', spec='SA 室外機（-160）', qty=2, unit='台',
             mat=450, md=0.45, master='', basis='図面カウント'),
        dict(kind='item', key='tr_ra', cat='試運転RA', name='試運転調整費', spec='RA 室外機（0-56）', qty=3, unit='台',
             mat=0, md=0.15, master='', basis='図面カウント'),
        dict(kind='exp', idx=0),
        dict(kind='exp', idx=1),
        dict(kind='exp', idx=2),
    ]),
    dict(key='PIPE', no='３', title='配管設備工事', break_after=True, lines=[
        dict(kind='head', name='冷媒（冷媒銅管）'),
        dict(kind='item', key='p_pac', cat='被覆銅管9.52+15.88', name='冷媒用被覆銅管（10+20t）', spec='9.52+15.88mm（10t+20t）AC-1',
             qty=Q['ref_pac'], unit='m', mat=('EST', 1.05), md=0,
             master='冷媒配管（テープ巻き）新築 φ9.5/15.9 5m以下29,500＋1m追加5,900（仕様違い）', basis='推測',
             qmemo=M['ref_pac'], memo=M['ref_pac']),
        dict(kind='item', key='p_rac', cat='被覆銅管6.35+9.52', name='冷媒用被覆銅管（10+20t）', spec='6.35+9.52mm（10t+20t）AC-2・AC-3',
             qty=Q['ref_rac'], unit='m', mat=('EST', 1.05), md=0,
             master='冷媒配管（テープ巻き）新築 φ6.4/9.5 5m以下26,000＋1m追加5,300（仕様違い）', basis='推測',
             qmemo=M['ref_rac'], memo=M['ref_rac']),
        dict(kind='pct', key='j_ref', name='継手類', rate=R.PCT_REF['joint'], base=['p_pac', 'p_rac']),
        dict(kind='pct', key='c_ref', name='消耗品', rate=R.PCT_REF['consum'], base=['p_pac', 'p_rac']),
        dict(kind='pct', key='s_ref', name='支持金物', rate=R.PCT_REF['support'], base=['p_pac', 'p_rac']),
        dict(kind='head', name='排水（硬質塩化ビニル管）'),
        dict(kind='item', key='vp25', cat='VP25', name='硬質塩化ビニル管', spec='VP 25A（AC-1 ドレン）', qty=Q['vp25'], unit='m',
             mat=('EST', 1.10), md=0, master='ドレン配管 新築 5m以下14,200＋1m追加2,800（参考）', basis='推測',
             qmemo=M['vp25'], memo=M['vp25']),
        dict(kind='pct', key='j_vp', name='継手類', rate=R.PCT_VP['joint'], base=['vp25']),
        dict(kind='pct', key='c_vp', name='消耗品', rate=R.PCT_VP['consum'], base=['vp25']),
        dict(kind='pct', key='s_vp', name='支持金物', rate=R.PCT_VP['support'], base=['vp25']),
        dict(kind='head', name='電線・ケーブル類'),
        dict(kind='item', key='vvf', cat='VVF2.0-3C', name='VVFケーブル（内外連絡線）', spec='600V VV-F 2.0mm-3C', qty=Q['vvf'], unit='m',
             mat=('EST', 1.00), md=0, master='', basis='推測', qmemo=M['vvf'], memo=M['vvf']),
        dict(kind='labor', key='lab_ref', name='配管工費（冷媒配管）', base=['p_pac', 'p_rac'], rate='EST_LABOR_PIPE',
             memo='歩掛 公共建築工事標準単価積算基準 R8 表M1-1-50（液管＋ガス管）× エスト労務単価'),
        dict(kind='labor', key='lab_vp', name='配管工費（塩ビ管類）', base=['vp25'], rate='EST_LABOR_PIPE',
             memo='歩掛 同 表M1-1-46 排水・屋内一般 × エスト労務単価'),
        dict(kind='labor', key='lab_el', name='電線材料施工費', base=['vvf'], rate='EST_LABOR_ELEC',
             memo='歩掛 0.017人/m × エスト電工労務単価（エスト見積から逆算）'),
        dict(kind='head', name='配管保温工事費'),
        dict(kind='item', key='cov_l', cat='化粧カバー大径', name='樹脂製化粧カバー', spec='9.52+15.88 屋外（AC-1）',
             qty=Q['case_l'], unit='m', mat=2400, md=0.10, master='外装仕上げ スカイダクト φ9.5/15.9 5m以下15,800＋1m追加2,600',
             basis='推測', qmemo=M['case_l'], memo=M['case_l']),
        dict(kind='item', key='cov_s', cat='化粧カバー小径', name='樹脂製化粧カバー', spec='6.35+9.52 屋外（AC-2・3）',
             qty=Q['case_s'], unit='m', mat=1800, md=0.10, master='外装仕上げ スカイダクト φ6.4/9.5 5m以下10,500＋1m追加2,100',
             basis='推測', qmemo=M['case_s'], memo=M['case_s']),
        dict(kind='item', key='gw', cat='GW25', name='排水VP保温 GW20mm+ALGC', spec='屋内隠蔽 25A', qty=Q['gw25'], unit='m',
             mat=900, md=0.06, master='', basis='推測', qmemo=M['gw25'], memo=M['gw25']),
        dict(kind='head', name='貫通・試験'),
        dict(kind='item', key='slv', cat='スリーブ1箇所', name='スリーブインサート費', spec='外壁貫通 穴あけ・シーリング',
             qty=Q['sleeve_ac'], unit='箇所', mat=1500, md=0.25, master='', basis='図面カウント', memo='AC-1 ×2・RAC ×3'),
        dict(kind='item', key='lk_sa', cat='気密SA', name='気密テスト費', spec='SA', qty=2, unit='系統',
             mat=2000, md=0.45, master='', basis='図面カウント'),
        dict(kind='item', key='lk_ra', cat='気密RA', name='気密テスト費', spec='RA', qty=3, unit='系統',
             mat=1000, md=0.3, master='', basis='図面カウント'),
        dict(kind='item', key='vc_sa', cat='真空SA', name='真空引き・ガス充填', spec='SA（基本料金）', qty=2, unit='系統',
             mat=500, md=0.15, master='', basis='図面カウント', memo='配管長はチャージレス範囲内のため追加充填なし'),
        dict(kind='item', key='vc_ra', cat='真空RA', name='真空引き・ガス充填', spec='RA（基本料金）', qty=3, unit='系統',
             mat=300, md=0.12, master='', basis='図面カウント'),
        dict(kind='exp', idx=0),
        dict(kind='exp', idx=1),
        dict(kind='exp', idx=2),
    ]),
    # ------------------------------------------------------------------ 換気
    dict(key='EQV', no='４', title='換気設備機器', oh=False, lines=[
        dict(kind='head', name='24時間換気（第3種機械換気）'),
        eq('eq_ef1', 'EF-1 パイプ用ファン', 'V-08PP8-BL（三菱）φ100 BL品', 3, '台', 12300, 'MEV', WIN,
           '便所・小便所'),
        dict(kind='head', name='局所換気'),
        eq('eq_ef2', 'EF-2 天井埋込形換気扇', 'VD-18ZC14（三菱）φ150 排煙用', 5, '台', 39800, 'MEV', MONO,
           '外陣・内陣・護摩堂'),
        eq('eq_ef3', 'EF-3 天井埋込形換気扇', 'VD-15ZC14（三菱）φ100 台所', 1, '台', 25200, 'MEV', MONO, '談話室'),
        eq('eq_ef4', 'EF-4 天井埋込形換気扇', 'VD-10ZC14（三菱）φ100', 1, '台', 20700, 'MEV', MONO, 'パントリー'),
        dict(kind='head', name='給気口（外気導入）'),
        eq('eq_sa1', 'SA-1 給排気グリル', 'P-23GHF5（三菱）φ200 フィルター付', 4, '個', 10900, 'MEV', WIN, '外陣・内陣'),
        eq('eq_sa2', 'SA-2 給排気グリル', 'P-18GHF5（三菱）φ150 フィルター付', 1, '個', 6000, 'MEV', MONO, '護摩堂'),
        eq('eq_sa3', 'SA-3 給排気グリル', 'P-13GHF5（三菱）φ100 フィルター付', 3, '個', 4600, 'MEV', MONO + '（税込5,060円）',
           '和室・談話室'),
        dict(kind='head', name='屋外フード'),
        eq('eq_h100', '深形フード', 'P-13VSQ4（三菱）φ100 SUS 防虫網付', Q['h100'], '個', 10500, 'MEV', MONO, '外壁'),
        eq('eq_h150', '深形フード', 'P-18VSQ4（三菱）φ150 SUS 防虫網付', Q['h150'], '個', 13300, 'MEV', WIN, '外壁'),
        eq('eq_h200', '深形フード', 'P-23VSQ4（三菱）φ200 SUS 防虫網付', Q['h200'], '個', 33400, 'MEV', MONO, '外壁'),
    ]),
    dict(key='VENT', no='５', title='換気設備工事', exp_key='VENT', lines=[
        dict(kind='head', name='機器取付工事'),
        own('f_pipe', 'パイプ用ファン取付', 'V-08PP8-BL 外壁付け（VU100共）', IT.n_fan24, '台', 800, 0.35,
            '材料800（VU100・ビス）＋0.35人工', pub='便所・小便所'),
        own('f_ceil18', '天井埋込形換気扇取付', 'VD-18ZC14（吊ボルト共）', IT.local['EF-2'], '台', 800, 0.6,
            '材料800（吊ボルト・振れ止め）＋0.6人工', pub='外陣・内陣・護摩堂'),
        own('f_ceil', '天井埋込形換気扇取付', 'VD-15ZC14・VD-10ZC14', IT.local['EF-3'] + IT.local['EF-4'], '台', 500, 0.45,
            '材料500＋0.45人工', pub='談話室・パントリー'),
        own('grille', '給排気グリル取付', 'φ100〜φ200 ダクト接続共', IT.n_grille, '個', 300, 0.25,
            '材料300＋0.25人工'),
        own('hood', '屋外フード取付', '深形フード φ100〜φ200', Q['h100'] + Q['h150'] + Q['h200'], '個', 300, 0.15,
            '材料300＋0.15人工'),
        dict(kind='head', name='ダクト工事'),
        own('d100', 'スパイラルダクト', 'φ100 継手・支持金物共', Q['d100'], 'm', 1000, 0.12, '材料1,000＋0.12人工/m（三矢寮 当社想定）',
            basis='実測+推測', qmemo=M['d100'], memo=M['d100']),
        own('d150', 'スパイラルダクト', 'φ150 継手・支持金物共', Q['d150'], 'm', 1400, 0.14, '材料1,400＋0.14人工/m（同）',
            basis='実測+推測', qmemo=M['d150'], memo=M['d150']),
        own('d200', 'スパイラルダクト', 'φ200 継手・支持金物共', Q['d200'], 'm', 1900, 0.16, '材料1,900＋0.16人工/m（同）',
            basis='実測+推測', qmemo=M['d200'], memo=M['d200']),
        own('d_ins', 'ダクト保温', 'GW25＋ALGC 外気導入ダクト', Q['ins'], 'm', 1100, 0.08,
            '材料1,100＋0.08人工/m（同）', basis='実測+推測', qmemo=M['ins'], memo=M['ins']),
        dict(kind='head', name='外壁貫通'),
        own('pen100', '外壁貫通処理', 'φ100 穴あけ・防水処理', Q['h100'], '箇所', 800, 0.25,
            '材料800＋0.25人工', memo='木造外壁。開口補強・外装仕上げ補修は建築'),
        own('pen150', '外壁貫通処理', 'φ150 穴あけ・防水処理', Q['h150'], '箇所', 1000, 0.30, '材料1,000＋0.30人工'),
        own('pen200', '外壁貫通処理', 'φ200 穴あけ・防水処理', Q['h200'], '箇所', 1200, 0.35, '材料1,200＋0.35人工'),
        dict(kind='head', name='試運転調整'),
        own('vtest', '試運転調整費', '風量確認・24時間換気運転確認', 1, '式', 3000, 1.0, '材料3,000＋1.0人工'),
        dict(kind='exp', idx=0),
        dict(kind='exp', idx=1),
        dict(kind='exp', idx=2),
    ]),
]

BASIS_TABLES = IT.BASIS_TABLES
BASIS_NOTE = (
    '数量拾い根拠（内部用）　当社作図 M-1 空調設備平面図・M-2 換気設備平面図（JWW、1単位＝実寸50mm）の配置座標から算出',
    '空調は室外機を各室の外壁直近に置く計画のため配管は短く、最小配管長・立下り・余長を想定値で計上。換気ダクトは器具〜外壁の平面距離＋立上り・接続 0.5m/本。'
    '座標・機器定義は drawings/tools/project_data.py',
)

SRC_RULE_NOTES = [
    '機器（１ 空調設備機器・４ 換気設備機器）: 原価＝定価×仕入率（ダイキン業務用0.20・家庭用0.30・三菱電機換気0.32）、'
    '提出単価＝原価÷（1－目標粗利率0.20）を10円未満切上げ。部門内経費・工事諸経費の対象外',
    '換気設備工事の部門内経費は、エスト見積に換気部門の規則がないため配管設備工事と同率（3%→5%→10%）を当社設定',
    '工事諸経費＝（空調設備工事＋配管設備工事＋換気設備工事）×5%',
]

NOTES = {
    'cover': [
        '本見積は当社作図の空調設備平面図（M-1）・換気設備平面図（M-2）および24時間換気計算書に基づき作成しております。数量は図面より当社にて拾い出しており、実施数量との差異は別途精算とさせていただきます。',
        '空調機（ダイキン SZRV80BZV×2組、S284ATEV-W×2組、S404ATEV-W×1組）および換気機器（三菱電機 パイプ用ファン・天井埋込形換気扇・給排気グリル・深形フード）を含みます（材工）。',
        '電源・専用回路・スイッチ（24時間換気の常時運転表示を含む）等の電気工事、外壁開口の補強・外装仕上げ補修・天井開口補強等の建築工事、揚重機、足場・仮設、産業廃棄物処分は含みません。',
        '天井高・機器の取付位置は意匠図確定前の想定です。変更が生じた場合は御協議のうえ精算させていただきます。',
        '本見積書に記載なき事項については別途とさせて頂きます。工事に係る電気・水道は無償支給願います。本見積金額には消費税は含まれておりません。',
        '詳細条件は別紙「御見積条件」をご参照ください。',
    ],
    'conditions': [
        '本見積は当社作図の空調設備平面図（M-1）・換気設備平面図（M-2）（意匠 平面図 令和8年7月20日版ベース）および24時間換気計算書に基づいて作成しています。空調機の機種は8月10日付 検討最終VE案（提案① ダイキン）、換気機器は三菱電機製としています。',
        '空調工事の範囲: 空調機の搬入・据付（AC-1 床置形 SZRV80BZV×2組〔大間・外陣〕、AC-2 壁掛形 S284ATEV-W×2組〔和室(1)・和室(2)〕、AC-3 壁掛形 S404ATEV-W×1組〔談話室〕）、室外機基礎（縁石基礎・置台）、冷媒配管（被覆銅管 液管10t・ガス管20t）・屋外化粧カバー、ドレン配管（VP 25A）・保温、内外連絡線（VVF 2.0-3C）、外壁貫通部の処理、気密試験・真空引き、試運転調整。',
        '換気工事の範囲: 24時間換気（第3種機械換気）用パイプ用ファン V-08PP8-BL×3台、局所換気用天井埋込形換気扇（VD-18ZC14×5台〔焼香・護摩の排煙〕、VD-15ZC14・VD-10ZC14 各1台）、給気用給排気グリル×8個、スパイラルダクト（φ100〜φ200）・外気導入ダクトの保温、深形フード（ステンレス製・防虫網付）×18個、外壁貫通処理、試運転調整（風量確認）。',
        '機器の単価は、メーカー定価（空調機はVE案の定価、換気機器は三菱電機の価格〔税別〕）を基準に当社にて算定しています。機器のメーカー価格改定（三菱電機は2027年1月1日改定予定）が生じた場合は御協議させていただきます。',
        '24時間換気の有効換気量は、パイプ用ファン V-08PP8-BL のP-Q線図（電源周波数60Hz）により算定しています（80 m³/h/台×3台＝240 m³/h ≧ 必要有効換気量185.1 m³/h）。天井高の確定により必要換気量が増える場合は機器の見直しをお願いすることがあります。',
        '電源・専用回路（空調機 単相200V×5回路、換気扇 単相100V）・スイッチ・接地等の電気工事、リモコン配線（本体リモコン・ワイヤレスリモコンのため不要の想定）は含みません。',
        '外壁の開口補強・外装仕上げの補修、天井開口の補強・点検口、揚重機（クレーン等）、足場・高所作業車等の仮設、産業廃棄物（機器の梱包材を含む）の処分は含みません。外壁貫通部の穴あけ・防水処理は本見積に含みます。',
        '冷媒の追加充填は、配管長が各機器のチャージレス配管長以内のため計上していません（真空引き・ガス充填は基本料金）。',
        'ドレンは、AC-1は硬質塩化ビニル管（VP 25A、屋内部分は保温）で、AC-2・AC-3は付属ドレンホースで屋外へ開放排水する想定です（側溝・桝への接続は含みません）。',
        '工期は建築工程に合わせた通常の日中作業を前提としております。夜間・休日作業、工程変更や他工事との輻輳による手待ち、工期延長に伴う経費増は別途協議とさせていただきます。',
        '労務費に係る法定福利費（事業主負担分）は工事費に含んでおり、その額は御見積書表紙および別紙「法定福利費内訳明細書」のとおりです。',
        '本見積書に記載なき事項については別途とさせていただきます。工事に係る電気・水道は無償支給願います。本見積金額には消費税は含まれておりません。本書有効期間は10日です。',
    ],
    'checks': [
        '施工場所（地番）をご教示ください。24時間換気は電源周波数60Hz（中国電力管内）で算定しています（50Hzの場合も 204 m³/h で適合）。',
        '天井高（外陣・内陣・護摩堂の格天井・折上天井を含む）が未確定のため、24時間換気計算は仮定値（外陣3.3m・内陣3.6m・護摩堂3.3m・その他2.4m）で行っています。',
        '室外機は各室の外壁直近（大間・外陣は西側、和室(1)は北側、和室(2)・談話室は東側）に置く計画です。設置場所の地盤・景観上の制約があればご指示ください。',
        'AC-1（床置形）の位置は大間・外陣の西側 広縁としています。仏具・建具の配置と干渉する場合はご指示ください。',
        '換気扇・給気口の位置、ダクトルートは当社計画です。天井内の梁・野縁との取合いにより変更となる場合があります。',
        '機器の型番・価格（特に空調機のVE案定価、三菱電機機器の価格）は提出前に最新の価格表で確認します。',
    ],
}

ALERT_NOTES = [
    '機器の仕入率はダイキン業務用0.20・家庭用0.30・三菱電機換気0.32（job.py の EQ_RATES）。目標粗利率を変えた場合は機器の提出単価も job.py で再生成',
    '空調機の定価は VE案（8/10付）の値。三菱電機機器は WIN2K／販売店掲載の価格（税別）',
    '天井高・冷媒管長・ダクト立上りは想定値（items.py 先頭で変更可）',
    '施工場所（地番）未確定',
]

COST_NOTES = [
    '機器: 原価＝定価×仕入率（ダイキン業務用 EcoZEAS・FIVESTAR 0.20、ダイキン家庭用 0.30、三菱電機 換気機器 0.32）。'
    '内訳書 L 列＝原価（定額）、提出単価＝原価÷（1－0.20）の10円未満切上げ',
    '据付の人工: SA 室外 0.8・床置室内 0.8、RA 室外 0.4・室内 0.5 人工/台。縁石基礎 材料2,500＋0.15、RA 置台 2,500＋0.1',
    '試運転: SA 材料450＋0.45、RA 0.15人工。気密: SA 2,000＋0.45、RA 1,000＋0.3。真空引き: SA 500＋0.15、RA 300＋0.12',
    '化粧カバー: 大径2,400・小径1,800円/m＋0.10人工/m。GW保温 25A: 900＋0.06人工/m。スリーブ: 材料1,500＋0.25人工/箇所',
    '換気: パイプファン取付 800＋0.35、天井扇 VD-18 800＋0.6・VD-15/10 500＋0.45、グリル 300＋0.25、フード 300＋0.15、'
    'スパイラルダクト φ100 1,000＋0.12・φ150 1,400＋0.14・φ200 1,900＋0.16（/m、三矢寮の当社想定）、ダクト保温 1,100＋0.08/m、'
    '外壁貫通 φ100 800＋0.25・φ150 1,000＋0.30・φ200 1,200＋0.35、試運転 3,000＋1.0人工',
    '当社単価の項目（要確認）は 原価×1.25 を100円切上げ（粗利20%相当）。エストに同種の単価が見つかれば差し替える',
]
