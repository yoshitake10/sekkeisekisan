# -*- coding: utf-8 -*-
"""
内訳書の明細定義（エスト見積 6330560-1 と同じ並び・同じ算式）
==============================================================
kind:
  head  … 小見出し
  item  … 数量×単価（price=エスト単価。src が要見積/単価要確認ならアラート）
  tbd   … 要見積（単価なし）。概算原価 prov を内部に持ち、既定では「別途見積」で金額 0
  pct   … 管金額 × 率（継手類・消耗品・支持金物）。原価も同率
  labor … 工費 = Σ(数量×歩掛) × エスト労務単価（10円未満切上げ）。原価 = 人工 × 労務原価日額
  exp   … 部門内経費（消耗品及び雑材料・資材運搬費・現場経費）。エストの積上げ規則
mat:
  数値 … 材料原価/単位
  ('EST', loss) … エスト材料単価 × 材料原価率 × 管長割増（建設物価相当）
"""
import items as IT

Q = IT.Q
SRC_EST = 'エスト見積'
SRC_CALC = 'エスト算式'
SRC_OWN = '当社単価（要確認）'
SRC_TBD = '要見積'

SECTIONS = [
    dict(key='AC', no='２', title='空調設備工事', cover='空調設備工事', lines=[
        dict(kind='head', name='搬入据付工事'),
        dict(kind='item', key='ra_out', name='RA 室外機', spec='セパレート2.2-5.0（店長室 RAC）架台上段', qty=1, unit='台',
             price=6250, src=SRC_EST, mat=500, md=0.5, est=(1, 6250, 6250), master='RA室外機 地上設置 P22 2,000',
             basis='図面カウント', memo='架台上段への揚重を人工に含む', pub='支給品の据付'),
        dict(kind='item', key='ra_in', name='RA 室内機', spec='壁掛 2.2kW（店長室）', qty=1, unit='台',
             price=6250, src=SRC_EST, mat=500, md=0.4, est=(1, 6250, 6250), master='RA室内機 壁掛形 P22 5,000',
             basis='図面カウント', memo='', pub='支給品の据付'),
        dict(kind='item', key='sa_out', name='SA 室外機', spec='11.2-16.0（AC-1×2・AC-2、5HP）', qty=3, unit='台',
             price=8750, src=SRC_EST, mat=1500, md=0.967, est=(2, 8750, 17500), master='SA室外機 地上設置 P140 15,000',
             basis='図面カウント', memo='架台下段2台 0.8人・上段1台 1.3人（揚重）の平均。エストは2台（AC-1を1系統と入力した可能性）',
             pub='支給品の据付'),
        dict(kind='item', key='sa_duct', name='SA 室内機', spec='ダクト形11.2-16（AC-2 天井ビルトイン 5HP）', qty=1, unit='台',
             price=27500, src=SRC_EST, mat=2500, md=1.2, est=(1, 27500, 27500), master='SA室内機 ダクト形 P140 23,000',
             basis='図面カウント', memo='吊ボルト・受け金物共', pub='支給品の吊込み'),
        dict(kind='item', key='sa_cas', name='SA 室内機', spec='カセット形2.8-16（AC-1 天井カセット 5HP）', qty=2, unit='台',
             price=25000, src=SRC_EST, mat=2000, md=0.9, est=(2, 25000, 50000), master='SA室内機 天井埋込カセット形 P140 29,000',
             basis='図面カウント', memo='吊ボルト・受け金物・化粧パネル取付共', pub='支給品の吊込み'),
        dict(kind='head', name='基礎工事'),
        dict(kind='item', key='base', name='縁石', spec='22.4-28.0（2段架台用）', qty=2, unit='台',
             price=7500, src=SRC_EST, mat=3000, md=0.15, est=(2, 7500, 15000), master='縁石基礎 P224〜P280 8,000（P140 5,000）',
             basis='図面カウント', memo='架台2基分。エストは 22.4-28.0×2 ＋ 11.2-16.0×1（5,000）の3台', pub=''),
        dict(kind='tbd', key='frame1', name='架台制作及び取付費', spec='鉄骨2段積み 溶融亜鉛メッキ（AC-1 上下段用・防振ゴム共）',
             qty=1, unit='基', prov=300000, est=(1, None, 0), master='（エストマスタに単価なし）', basis='図面カウント',
             memo='単価情報が少なく要見積。製作品は高額になりやすい。概算原価は鋼材約130kg×製作2,000円/kg＋めっき・運搬・据付を想定'),
        dict(kind='tbd', key='frame2', name='架台制作及び取付費', spec='鉄骨2段積み 溶融亜鉛メッキ（AC-2 下段・RAC 上段用・防振ゴム共）',
             qty=1, unit='基', prov=250000, est=None, master='（エストマスタに単価なし）', basis='図面カウント',
             memo='同上（上段がRAのため軽量）。鉄工所またはメーカーの見積で差し替え'),
        dict(kind='head', name='試運転調整費'),
        dict(kind='item', key='tr_sa', name='試運転調整費', spec='SA 室外機（-160）', qty=3, unit='台',
             price=10000, src=SRC_EST, mat=450, md=0.45, est=(2, 10000, 20000), master='', basis='図面カウント',
             memo='エストは2台', pub=''),
        dict(kind='item', key='tr_ra', name='試運転調整費', spec='RA 室外機（0-56）', qty=1, unit='台',
             price=2500, src=SRC_EST, mat=0, md=0.1, est=(1, 2500, 2500), master='', basis='図面カウント', memo='', pub=''),
        dict(kind='exp', idx=0, est=(1, None, 4500)),
        dict(kind='exp', idx=1, est=(1, None, 6200)),
        dict(kind='exp', idx=2, est=(1, None, 13300)),
    ]),
    dict(key='PIPE', no='３', title='配管設備工事', cover='配管設備工事', lines=[
        dict(kind='head', name='冷媒（冷媒銅管）'),
        dict(kind='item', key='p_rac', name='冷媒用被覆銅管（10+20t）', spec='6.35+9.52mm（10t+20t）RAC', qty=Q['ref_rac'], unit='m',
             price=3388, src=SRC_EST, mat=('EST', 1.05), md=0, bug=0.104, est=(10, 3388, 33880),
             master='冷媒配管（テープ巻き）新築 φ6.4/9.5 5m以下26,000＋1m追加5,300（仕様違い）',
             basis='実測+推測', memo=IT.memo_ref_rac, pub=''),
        dict(kind='item', key='p_pac', name='冷媒用被覆銅管（10+20t）', spec='9.52+15.88mm（10t+20t）AC-1×2・AC-2', qty=Q['ref_pac'], unit='m',
             price=5138, src=SRC_EST, mat=('EST', 1.05), md=0, bug=0.150, est=(35, 5138, 179830),
             master='冷媒配管（テープ巻き）新築 φ9.5/15.9 5m以下29,500＋1m追加5,900（仕様違い）',
             basis='実測+推測', memo=IT.memo_ref_pac, pub=''),
        dict(kind='pct', key='j_ref', name='継手類', rate=0.30, base=['p_rac', 'p_pac'], est=(1, None, 64107)),
        dict(kind='pct', key='c_ref', name='消耗品', rate=0.15, base=['p_rac', 'p_pac'], est=(1, None, 32054)),
        dict(kind='pct', key='s_ref', name='支持金物', rate=0.40, base=['p_rac', 'p_pac'], est=(1, None, 85475)),
        dict(kind='head', name='排水（硬質塩化ビニル管）'),
        dict(kind='item', key='vp25', name='硬質塩化ビニル管', spec='VP 25A', qty=Q['d25'], unit='m',
             price=313, src=SRC_EST, mat=('EST', 1.10), md=0, bug=0.074, est=(9, 313, 2817), master='',
             basis='実測+推測', memo=IT.memo_d25, pub=''),
        dict(kind='item', key='vp30', name='硬質塩化ビニル管', spec='VP 30A', qty=Q['d30'], unit='m',
             price=363, src=SRC_EST, mat=('EST', 1.10), md=0, bug=0.079, est=(4, 363, 1452), master='',
             basis='実測', memo='', pub=''),
        dict(kind='item', key='vp40', name='硬質塩化ビニル管', spec='VP 40A', qty=Q['d40'], unit='m',
             price=363, src=SRC_EST, mat=('EST', 1.10), md=0, bug=0.101, est=(6, 363, 2178), master='',
             basis='実測+推測', memo=IT.memo_d40, pub=''),
        dict(kind='pct', key='j_vp', name='継手類', rate=0.20, base=['vp25', 'vp30', 'vp40'], est=(1, None, 1288)),
        dict(kind='pct', key='c_vp', name='消耗品', rate=0.10, base=['vp25', 'vp30', 'vp40'], est=(1, None, 644)),
        dict(kind='pct', key='s_vp', name='支持金物', rate=0.25, base=['vp25', 'vp30', 'vp40'], est=(1, None, 1610)),
        dict(kind='item', key='chk', name='ドレンホース用逆止弁', spec='NDB-20-25（図示品）', qty=1, unit='個',
             price=5730, src=SRC_OWN, mat=2800, md=0.1, est=None, master='（エストに単価なし）', basis='図面カウント',
             memo='エストに単価がないため当社単価（前回見積）で仮計上。仕入価格を確認', pub=''),
        dict(kind='head', name='電線・ケーブル類'),
        dict(kind='item', key='vvf', name='VVFケーブル（内外連絡線）', spec='600V VV-F 2.0mm-3C', qty=Q['vvf'], unit='m',
             price=203, src=SRC_EST, mat=('EST', 1.00), md=0, bug=0.017, est=(56, 203, 11368), master='',
             basis='推測', memo=IT.memo_vvf, pub=''),
        dict(kind='labor', key='lab_ref', name='配管工費（冷媒配管）', base=['p_rac', 'p_pac'], rate='EST_LABOR_PIPE', est=(1, None, 212290),
             memo='歩掛 公共建築工事標準単価積算基準 R8 表M1-1-50（液管＋ガス管）× エスト労務単価'),
        dict(kind='labor', key='lab_vp', name='配管工費（塩ビ管類）', base=['vp25', 'vp30', 'vp40'], rate='EST_LABOR_PIPE', est=(1, None, 53600),
             memo='歩掛 同 表M1-1-46 排水・屋内一般 × エスト労務単価'),
        dict(kind='labor', key='lab_el', name='電線材料施工費', base=['vvf'], rate='EST_LABOR_ELEC', est=(1, None, 31990),
             memo='歩掛 0.017人/m × エスト電工労務単価（エスト見積から逆算）'),
        dict(kind='head', name='配管保温工事費'),
        dict(kind='item', key='cov_rac', name='樹脂製化粧カバー', spec='冷媒用被覆銅管（10+20t）6.35+9.52 屋外', qty=Q['case_rac'], unit='m',
             price=4225, src=SRC_EST, mat=1800, md=0.10, est=(5, 4225, 21125),
             master='外装仕上げ スカイダクト φ6.4/9.5 5m以下10,500＋1m追加2,100',
             basis='実測+推測', memo=IT.memo_case_rac, pub=''),
        dict(kind='item', key='cov_pac', name='樹脂製化粧カバー', spec='冷媒用被覆銅管（10+20t）9.52+15.88 屋外', qty=Q['case_pac'], unit='m',
             price=5525, src=SRC_EST, mat=2400, md=0.10, est=(10, 5525, 55250),
             master='外装仕上げ スカイダクト φ9.5/15.9 5m以下15,800＋1m追加2,600',
             basis='実測+推測', memo=IT.memo_case_pac, pub=''),
        dict(kind='item', key='gw25', name='排水VP保温 GW20mm+ALGC', spec='屋内隠蔽 25A', qty=Q['d25'], unit='m',
             price=2563, src=SRC_EST, mat=900, md=0.06, est=(9, 2563, 23067), master='', basis='実測+推測',
             memo='ドレン管 VP25 と同長', pub=''),
        dict(kind='item', key='gw30', name='排水VP保温 GW20mm+ALGC', spec='屋内隠蔽 30A', qty=Q['d30'], unit='m',
             price=2713, src=SRC_EST, mat=1000, md=0.065, est=(4, 2713, 10852), master='', basis='実測', memo='', pub=''),
        dict(kind='item', key='gw40', name='排水VP保温 GW20mm+ALGC', spec='屋内隠蔽 40A', qty=Q['d40'], unit='m',
             price=2950, src=SRC_EST, mat=1100, md=0.07, est=(6, 2950, 17700), master='', basis='実測+推測',
             memo='ドレン管 VP40 と同長', pub=''),
        dict(kind='item', key='slv', name='スリーブインサート費', spec='外壁貫通 4箇所（穴明け・シーリング）', qty=1, unit='式',
             price=50000, src=SRC_EST, mat=6000, md=1.0, est=(1, None, 50000), master='', basis='図面カウント',
             memo='冷媒管4系統の外壁貫通。原価は材料1,500円＋0.25人工/箇所', pub=''),
        dict(kind='head', name='気密テスト費'),
        dict(kind='item', key='lk_sa', name='気密テスト費', spec='SA', qty=3, unit='系統',
             price=12500, src=SRC_EST, mat=2000, md=0.45, est=(2, 12500, 25000), master='', basis='図面カウント',
             memo='エストは2系統', pub=''),
        dict(kind='item', key='lk_ra', name='気密テスト費', spec='RA', qty=1, unit='系統',
             price=10000, src=SRC_EST, mat=1000, md=0.2, est=(1, 10000, 10000), master='', basis='図面カウント', memo='', pub=''),
        dict(kind='head', name='真空引き・ガス充填（基本料金）'),
        dict(kind='item', key='vc_sa', name='真空引き・ガス充填', spec='SA（基本料金）', qty=3, unit='系統',
             price=2500, src=SRC_EST, mat=500, md=0.15, est=(2, 2500, 5000), master='', basis='図面カウント',
             memo='エストは2系統。追加充填はチャージレス長以内のため計上なし', pub=''),
        dict(kind='item', key='vc_ra', name='真空引き・ガス充填', spec='RA（基本料金）', qty=1, unit='系統',
             price=1880, src=SRC_EST, mat=300, md=0.1, est=(1, 1880, 1880), master='', basis='図面カウント', memo='', pub=''),
        dict(kind='exp', idx=0, est=(1, None, 28100)),
        dict(kind='exp', idx=1, est=(1, None, 48200)),
        dict(kind='exp', idx=2, est=(1, None, 101247)),
    ]),
]

# エスト見積にあって当社明細に対応行がないもの（比較表用）
EST_ONLY = [
    ('空調設備工事', '縁石 11.2-16.0', 1, 5000, 5000, '図面の架台は2基のため計上せず（2段架台用 22.4-28.0×2 に含む）'),
    ('配管設備工事', '調整', 1, None, -4, 'エストの端数調整'),
]
