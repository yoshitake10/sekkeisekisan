import type { DaikinModel, IndoorUnitType } from '../types'

// ============================================================
// ダイキン機器データベース（初期データ）
//
// 【重要】収録している型番・能力・定価はいずれも「代表型番・カタログ値
// ベースの目安」です。実際の選定・見積では必ず最新のダイキン工業カタログ
// および仕切り価格で確認してください。
//  - スカイエア ZEAS: 室内機形態 × 馬力クラス（P40〜P280）を機械生成
//  - FIVE STAR ZEAS: 省エネ上位。代表的な天カセ4方向のみ収録
//  - VRV X: 室外機 8〜24馬力 / 室内機 FXYFP・FXYMP 主要クラス
//  - ベンティエール(VAM): 全熱交換器ユニット 150〜2000 m3/h
// id は選定結果の参照(Room.selectedModelId 等)に使われるため
// 決定的な値（型番ベース）とし、変更しないこと。
// ============================================================

const CATALOG_NOTE = '型番・定価はカタログ要確認の目安'

/** 馬力クラス定義（スカイエア）。base は天カセ4方向の目安定価（円・税抜） */
interface SkyairClass {
  code: number // 型番の容量コード（P40 → 40）
  hp: string
  coolingKw: number
  heatingKw: number
  base: number
  /** 単相200V仕様の設定がある容量か */
  singlePhase: boolean
}

const SKYAIR_CLASSES: SkyairClass[] = [
  { code: 40, hp: '1.5馬力', coolingKw: 4.0, heatingKw: 4.5, base: 500000, singlePhase: true },
  { code: 50, hp: '2馬力', coolingKw: 5.0, heatingKw: 5.6, base: 600000, singlePhase: true },
  { code: 63, hp: '2.5馬力', coolingKw: 6.3, heatingKw: 7.1, base: 700000, singlePhase: true },
  { code: 80, hp: '3馬力', coolingKw: 8.0, heatingKw: 9.0, base: 820000, singlePhase: true },
  { code: 112, hp: '4馬力', coolingKw: 11.2, heatingKw: 12.5, base: 1050000, singlePhase: true },
  { code: 140, hp: '5馬力', coolingKw: 14.0, heatingKw: 16.0, base: 1250000, singlePhase: true },
  { code: 160, hp: '6馬力', coolingKw: 16.0, heatingKw: 18.0, base: 1480000, singlePhase: false },
  { code: 224, hp: '8馬力', coolingKw: 22.4, heatingKw: 25.0, base: 1850000, singlePhase: false },
  { code: 280, hp: '10馬力', coolingKw: 28.0, heatingKw: 31.5, base: 2200000, singlePhase: false },
]

/** 室内機形態定義（スカイエア ZEAS）。factor は形態による価格補正係数 */
const SKYAIR_TYPES: {
  type: IndoorUnitType
  label: string
  prefix: string
  factor: number
}[] = [
  { type: 'ceiling-cassette-4way', label: '天井カセット4方向（S-ラウンドフロー）', prefix: 'SZRC', factor: 1.0 },
  { type: 'ceiling-cassette-2way', label: '天井カセット2方向', prefix: 'SZRG', factor: 1.02 },
  { type: 'ceiling-suspended', label: '天井吊形', prefix: 'SZRH', factor: 0.95 },
  { type: 'wall-mounted', label: '壁掛形', prefix: 'SZRA', factor: 0.9 },
  { type: 'concealed-duct', label: '天井埋込ダクト形', prefix: 'SZRMM', factor: 0.98 },
  { type: 'floor-standing', label: '床置形', prefix: 'SZRV', factor: 0.93 },
]

/** 1万円単位に丸めた目安定価 */
function roundPrice(v: number): number {
  return Math.round(v / 10000) * 10000
}

// ---------- スカイエア ZEAS（形態 × 馬力を機械生成） ----------

const skyairZeas: DaikinModel[] = SKYAIR_TYPES.flatMap((t) =>
  SKYAIR_CLASSES.map(
    (c): DaikinModel => ({
      id: `sa-${t.prefix.toLowerCase()}-${c.code}`,
      category: 'skyair',
      series: 'スカイエア ZEAS',
      indoorType: t.type,
      name: `${t.label} ${c.hp}`,
      modelNo: `${t.prefix}${c.code}BJ`,
      hpClass: c.hp,
      coolingKw: c.coolingKw,
      heatingKw: c.heatingKw,
      powerSupply: '三相200V',
      priceListYen: roundPrice(c.base * t.factor),
      notes: c.singlePhase
        ? `三相200V基本・単相200V仕様あり。${CATALOG_NOTE}`
        : CATALOG_NOTE,
    }),
  ),
)

// ---------- FIVE STAR ZEAS（省エネ上位・代表機のみ） ----------

const FIVE_STAR_CODES = [50, 80, 112, 140, 224]

const fiveStarZeas: DaikinModel[] = FIVE_STAR_CODES.map((code): DaikinModel => {
  const c = SKYAIR_CLASSES.find((x) => x.code === code)!
  return {
    id: `fs-ssrc-${code}`,
    category: 'skyair',
    series: 'FIVE STAR ZEAS',
    indoorType: 'ceiling-cassette-4way',
    name: `天井カセット4方向（S-ラウンドフロー） ${c.hp} 省エネ上位`,
    modelNo: `SSRC${code}BJ`,
    hpClass: c.hp,
    coolingKw: c.coolingKw,
    heatingKw: c.heatingKw,
    powerSupply: '三相200V',
    priceListYen: roundPrice(c.base * 1.15),
    notes: `省エネ性上位シリーズ（高効率）。${CATALOG_NOTE}`,
  }
})

// ---------- VRV X 室外機 ----------

const VRV_OUTDOOR: {
  code: number
  hp: string
  coolingKw: number
  heatingKw: number
  price: number
}[] = [
  { code: 224, hp: '8馬力', coolingKw: 22.4, heatingKw: 25.0, price: 2800000 },
  { code: 280, hp: '10馬力', coolingKw: 28.0, heatingKw: 31.5, price: 3300000 },
  { code: 335, hp: '12馬力', coolingKw: 33.5, heatingKw: 37.5, price: 3900000 },
  { code: 400, hp: '14馬力', coolingKw: 40.0, heatingKw: 45.0, price: 4500000 },
  { code: 450, hp: '16馬力', coolingKw: 45.0, heatingKw: 50.0, price: 5000000 },
  { code: 504, hp: '18馬力', coolingKw: 50.4, heatingKw: 56.5, price: 5500000 },
  { code: 560, hp: '20馬力', coolingKw: 56.0, heatingKw: 63.0, price: 6100000 },
  { code: 615, hp: '22馬力', coolingKw: 61.5, heatingKw: 69.0, price: 6600000 },
  { code: 675, hp: '24馬力', coolingKw: 67.0, heatingKw: 75.0, price: 7200000 },
]

const vrvOutdoor: DaikinModel[] = VRV_OUTDOOR.map(
  (c): DaikinModel => ({
    id: `vrvo-rxyp-${c.code}`,
    category: 'vrv-outdoor',
    series: 'VRV X',
    name: `ビル用マルチ室外機 VRV X ${c.hp}`,
    modelNo: `RXYP${c.code}D`,
    hpClass: c.hp,
    coolingKw: c.coolingKw,
    heatingKw: c.heatingKw,
    powerSupply: '三相200V',
    priceListYen: c.price,
    notes: `モジュール組合せで増強可。${CATALOG_NOTE}`,
  }),
)

// ---------- VRV 室内機 ----------

const VRV_INDOOR_CLASSES: {
  code: number
  hp: string
  coolingKw: number
  heatingKw: number
  price4way: number
}[] = [
  { code: 22, hp: '0.8馬力相当', coolingKw: 2.2, heatingKw: 2.5, price4way: 350000 },
  { code: 28, hp: '1馬力相当', coolingKw: 2.8, heatingKw: 3.2, price4way: 370000 },
  { code: 36, hp: '1.5馬力相当', coolingKw: 3.6, heatingKw: 4.0, price4way: 395000 },
  { code: 45, hp: '1.8馬力相当', coolingKw: 4.5, heatingKw: 5.0, price4way: 420000 },
  { code: 56, hp: '2.3馬力相当', coolingKw: 5.6, heatingKw: 6.3, price4way: 450000 },
  { code: 63, hp: '2.5馬力相当', coolingKw: 6.3, heatingKw: 7.1, price4way: 480000 },
  { code: 71, hp: '2.8馬力相当', coolingKw: 7.1, heatingKw: 8.0, price4way: 510000 },
  { code: 80, hp: '3馬力相当', coolingKw: 8.0, heatingKw: 9.0, price4way: 545000 },
  { code: 90, hp: '3.6馬力相当', coolingKw: 9.0, heatingKw: 10.0, price4way: 580000 },
  { code: 112, hp: '4馬力相当', coolingKw: 11.2, heatingKw: 12.5, price4way: 650000 },
  { code: 140, hp: '5馬力相当', coolingKw: 14.0, heatingKw: 16.0, price4way: 730000 },
  { code: 160, hp: '6馬力相当', coolingKw: 16.0, heatingKw: 18.0, price4way: 800000 },
]

/** 天井カセット4方向 FXYFP（全クラス） */
const vrvIndoor4way: DaikinModel[] = VRV_INDOOR_CLASSES.map(
  (c): DaikinModel => ({
    id: `vrvi-fxyfp-${c.code}`,
    category: 'vrv-indoor',
    series: 'VRV室内機',
    indoorType: 'ceiling-cassette-4way',
    name: `天井カセット4方向（ラウンドフロー） ${c.coolingKw.toFixed(1)}kWクラス`,
    modelNo: `FXYFP${c.code}M`,
    hpClass: c.hp,
    coolingKw: c.coolingKw,
    heatingKw: c.heatingKw,
    powerSupply: '単相200V',
    priceListYen: roundPrice(c.price4way),
    notes: CATALOG_NOTE,
  }),
)

/** 天井埋込ダクト形 FXYMP（主要クラス） */
const VRV_DUCT_CODES = [28, 36, 45, 56, 71, 90, 112, 140, 160]

const vrvIndoorDuct: DaikinModel[] = VRV_DUCT_CODES.map((code): DaikinModel => {
  const c = VRV_INDOOR_CLASSES.find((x) => x.code === code)!
  return {
    id: `vrvi-fxymp-${c.code}`,
    category: 'vrv-indoor',
    series: 'VRV室内機',
    indoorType: 'concealed-duct',
    name: `天井埋込ダクト形 ${c.coolingKw.toFixed(1)}kWクラス`,
    modelNo: `FXYMP${c.code}M`,
    hpClass: c.hp,
    coolingKw: c.coolingKw,
    heatingKw: c.heatingKw,
    powerSupply: '単相200V',
    priceListYen: roundPrice(c.price4way * 0.97),
    notes: CATALOG_NOTE,
  }
})

// ---------- 全熱交換器ユニット ベンティエール（VAM-J） ----------

const VAM_SERIES: { flow: number; price: number }[] = [
  { flow: 150, price: 180000 },
  { flow: 250, price: 210000 },
  { flow: 350, price: 250000 },
  { flow: 500, price: 300000 },
  { flow: 650, price: 350000 },
  { flow: 800, price: 430000 },
  { flow: 1000, price: 490000 },
  { flow: 1500, price: 740000 },
  { flow: 2000, price: 910000 },
]

const ventilationErv: DaikinModel[] = VAM_SERIES.map(
  (c): DaikinModel => ({
    id: `erv-vam-${c.flow}`,
    category: 'ventilation-erv',
    series: 'ベンティエール',
    name: `全熱交換器ユニット 天井埋込ダクト形 ${c.flow}m³/hタイプ`,
    modelNo: `VAM${c.flow}J`,
    airflowM3h: c.flow,
    powerSupply: '単相200V',
    priceListYen: c.price,
    notes: CATALOG_NOTE,
  }),
)

// ---------- 統合 ----------

export const DEFAULT_DAIKIN_MODELS: DaikinModel[] = [
  ...skyairZeas,
  ...fiveStarZeas,
  ...vrvOutdoor,
  ...vrvIndoor4way,
  ...vrvIndoorDuct,
  ...ventilationErv,
]
