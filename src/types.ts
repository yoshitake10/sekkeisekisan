// ============================================================
// 共有型定義 — 全モジュールはこのファイルの型を使用すること
// ============================================================

// ---------- 機器（ダイキン） ----------

/** 室内機の形態 */
export type IndoorUnitType =
  | 'ceiling-cassette-4way' // 天井カセット4方向
  | 'ceiling-cassette-2way' // 天井カセット2方向
  | 'ceiling-cassette-1way' // 天井カセット1方向
  | 'ceiling-suspended' // 天井吊形
  | 'wall-mounted' // 壁掛形
  | 'concealed-duct' // 天井埋込ダクト形
  | 'floor-standing' // 床置形

export const INDOOR_UNIT_TYPE_LABELS: Record<IndoorUnitType, string> = {
  'ceiling-cassette-4way': '天井カセット4方向',
  'ceiling-cassette-2way': '天井カセット2方向',
  'ceiling-cassette-1way': '天井カセット1方向',
  'ceiling-suspended': '天井吊形',
  'wall-mounted': '壁掛形',
  'concealed-duct': '天井埋込ダクト形',
  'floor-standing': '床置形',
}

export type DaikinCategory =
  | 'skyair' // 業務用パッケージ（店舗・オフィス用）室内外セット
  | 'vrv-outdoor' // ビル用マルチ室外機
  | 'vrv-indoor' // ビル用マルチ室内機
  | 'ventilation-erv' // 全熱交換器ユニット（ベンティエール）
  | 'other'

export const DAIKIN_CATEGORY_LABELS: Record<DaikinCategory, string> = {
  skyair: '業務用パッケージ（スカイエア）',
  'vrv-outdoor': 'ビル用マルチ室外機（VRV）',
  'vrv-indoor': 'ビル用マルチ室内機（VRV）',
  'ventilation-erv': '全熱交換器ユニット',
  other: 'その他',
}

export interface DaikinModel {
  id: string
  category: DaikinCategory
  /** シリーズ名 例: FIVE STAR ZEAS / ZEAS / VRV X / ベンティエール */
  series: string
  indoorType?: IndoorUnitType
  /** 表示名 例: 天井カセット4方向 S-ラウンドフロー 3馬力 */
  name: string
  /** 代表型番（カタログ要確認） */
  modelNo: string
  /** 馬力クラス 例: "3馬力" / "8馬力" */
  hpClass?: string
  /** 冷房能力 kW */
  coolingKw?: number
  /** 暖房能力 kW */
  heatingKw?: number
  /** 風量 m3/h（換気機器用） */
  airflowM3h?: number
  /** 電源 例: 三相200V / 単相200V / 単相100V */
  powerSupply?: string
  /** メーカー希望小売価格（円・税抜）。目安値のため編集して使用する */
  priceListYen?: number
  notes?: string
}

// ---------- 負荷計算・機器選定 ----------

/** 用途別 冷房負荷原単位ほか */
export interface LoadUnit {
  /** 用途キー（表示名も兼ねる） 例: 事務所 */
  usage: string
  /** 冷房負荷原単位 W/m2 */
  coolingWm2: number
  /** 換気回数 回/h（全般換気の目安） */
  ventilationAch: number
  /** 在室人員密度 m2/人（人員換気 30m3/h・人 の算定用） */
  occupantDensityM2PerPerson: number
  notes?: string
}

/** 用途別 概算工事単価（空調換気設備工事一式） */
export interface RoughCostUnit {
  usage: string
  /** 円/m2（税抜） */
  costYenPerM2: number
  notes?: string
}

/** 部屋（機器選定の単位） */
export interface Room {
  id: string
  name: string
  /** LoadUnit.usage への参照 */
  usage: string
  areaM2: number
  ceilingHeightM: number
  /** 在室人数。未入力なら原単位から自動推定 */
  occupants?: number
  /** 冷房負荷原単位の個別上書き W/m2 */
  coolingWm2Override?: number
  /** 余裕率 例 1.05 */
  safetyFactor: number
  /** 希望する室内機形態 */
  preferredIndoorType: IndoorUnitType
  /** 台数分割（1台あたり能力 = 必要能力/台数で選定）。0 なら自動 */
  unitCount: number
  /** 選定結果: DaikinModel.id（スカイエア or VRV室内機） */
  selectedModelId?: string
  /** 選定結果: 換気 DaikinModel.id（全熱交換器） */
  selectedVentModelId?: string
  /** 全熱交換器による換気を行うか */
  useErv: boolean
  notes?: string
}

/** 部屋の計算結果（logic/selection.ts が返す） */
export interface RoomCalcResult {
  roomId: string
  /** 適用した冷房負荷原単位 W/m2 */
  coolingWm2: number
  /** 必要冷房能力 kW（余裕率込み） */
  requiredCoolingKw: number
  /** 台数（unitCount=0 のとき自動決定した値を含む） */
  unitCount: number
  /** 1台あたり必要能力 kW */
  requiredKwPerUnit: number
  /** 必要換気量 m3/h（換気回数と人員換気の大きい方） */
  requiredVentilationM3h: number
  /** 推奨機種（能力を満たす最小機） */
  recommendedModel?: DaikinModel
  /** 推奨換気機器 */
  recommendedVentModel?: DaikinModel
}

// ---------- 単価マスタ ----------

export interface UnitPrice {
  id: string
  /** 分類 例: 機器 / ダクト工事 / 配管工事 / 換気工事 / その他 */
  category: string
  name: string
  spec: string
  /** 単位 例: 台 / m / 個 / 式 */
  unit: string
  /** 単価（円・税抜。材工共など運用に合わせる） */
  unitPriceYen: number
  /** 出典・備考 例: 2026年度 社内単価 */
  source?: string
}

// ---------- 数量表 ----------

export type QuantitySource = 'manual' | 'import' | 'takeoff' | 'equipment'

export const QUANTITY_SOURCE_LABELS: Record<QuantitySource, string> = {
  manual: '手入力',
  import: '取込',
  takeoff: '図面拾い',
  equipment: '機器選定',
}

export interface QuantityItem {
  id: string
  /** 分類 例: 機器 / ダクト工事 / 配管工事 / 換気工事 / その他 */
  category: string
  name: string
  spec: string
  unit: string
  quantity: number
  /** 単価（円）。単価マスタから引当てるか手入力 */
  unitPriceYen?: number
  /** 引当てた UnitPrice.id */
  unitPriceRef?: string
  source: QuantitySource
  /** source='takeoff' のとき転記元図面ID（再転記時の置換に使用） */
  drawingId?: string
  remarks?: string
}

// ---------- 図面拾い ----------

export type MeasureKind = 'count' | 'length' | 'area'

export interface TakeoffPoint {
  x: number
  y: number
}

/**
 * 拾い測定。
 * points の座標系:
 *  - PDF: 対象ページの PDF ユーザー空間（スケール1で描画したときのピクセル座標）
 *  - DXF: モデル空間座標（図面単位）
 * value はスケール適用後の実数値（count=個数, length=m, area=m2）
 */
export interface Measurement {
  id: string
  drawingId: string
  pageIndex: number
  kind: MeasureKind
  /** 拾い対象名 例: 室内機 / 角ダクト / 冷媒配管 */
  label: string
  /** 数量表の分類に対応 例: 機器 / ダクト工事 */
  category: string
  /** 単位 例: 台 / m / m2 */
  unitName: string
  points: TakeoffPoint[]
  value: number
  color: string
  /** 規格・メモ */
  spec?: string
  /** ユーザーが数量を手修正した場合 true（スケール再計算で上書きしない） */
  valueOverridden?: boolean
}

export interface DrawingMeta {
  id: string
  kind: 'pdf' | 'dxf'
  fileName: string
  /**
   * スケール: 図面上の1単位が実寸何mか。
   * PDF: 1描画ピクセル(scale=1) → m。未設定は undefined。
   *      複数ページPDFは scaleByPage を優先し、この値は pageIndex の
   *      ページで設定された旧データ互換値として扱う。
   * DXF: 1図面単位 → m（mm図面なら 0.001）。図面全体で1つ。
   */
  scaleMPerUnit?: number
  /** スケール設定対象ページ（PDFのみ複数ページ想定） */
  pageIndex?: number
  /** PDF: ページ番号(0始まり)ごとのスケール。縮尺の異なるページ混在に対応 */
  scaleByPage?: Record<number, number>
  /** 再関連付け時の同一性確認用ファイルサイズ（bytes） */
  fileSize?: number
}

// ---------- 見積 ----------

export type EstimateMode = 'rough' | 'detail'

export interface RoughEstimateRow {
  id: string
  /** 用途（RoughCostUnit.usage 参照。自由入力も可） */
  usage: string
  name: string
  areaM2: number
  costYenPerM2: number
}

export interface EstimateSettings {
  mode: EstimateMode
  title: string
  clientName: string
  /** 敬称 例: 御中 */
  honorific: string
  companyName: string
  companyAddress: string
  companyTel: string
  personInCharge: string
  /** 消費税率 % */
  taxRatePct: number
  /** 諸経費率 %（直接工事費に対して） */
  overheadRatePct: number
  /** 法定福利費率 %（労務費相当に対する簡易計上。0で非表示） */
  welfareRatePct: number
  /** 端数処理単位 円 例: 1000 */
  roundingUnitYen: number
  /** 見積有効期限 例: 提出後30日 */
  validity: string
  /** 支払条件 */
  paymentTerms: string
  /** 工期 */
  workPeriod: string
  notes: string
  /** 概算見積の行 */
  roughRows: RoughEstimateRow[]
}

// ---------- プロジェクト ----------

export interface Project {
  id: string
  name: string
  clientName: string
  siteName: string
  /** 主用途（概算見積の初期値に使用） */
  buildingUsage: string
  totalFloorAreaM2: number
  createdAt: string
  updatedAt: string
  rooms: Room[]
  quantityItems: QuantityItem[]
  measurements: Measurement[]
  drawings: DrawingMeta[]
  estimate: EstimateSettings
  memo: string
}
