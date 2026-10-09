import type { LoadUnit, RoughCostUnit } from '../types'

/**
 * 用途別 冷房負荷原単位（W/m2）・換気回数・人員密度の初期値。
 * 一般的な設計目安値。マスタ画面で自社基準に合わせて編集して使用する。
 */
export const DEFAULT_LOAD_UNITS: LoadUnit[] = [
  { usage: '事務所', coolingWm2: 130, ventilationAch: 3, occupantDensityM2PerPerson: 8, notes: '一般事務室' },
  { usage: '会議室', coolingWm2: 160, ventilationAch: 5, occupantDensityM2PerPerson: 3, notes: '在室密度高め' },
  { usage: '店舗（物販）', coolingWm2: 180, ventilationAch: 6, occupantDensityM2PerPerson: 4, notes: '' },
  { usage: '飲食店（客席）', coolingWm2: 220, ventilationAch: 8, occupantDensityM2PerPerson: 2, notes: '厨房負荷は別途' },
  { usage: '厨房', coolingWm2: 300, ventilationAch: 30, occupantDensityM2PerPerson: 10, notes: '排気フード別途検討' },
  { usage: '住宅・寮室', coolingWm2: 190, ventilationAch: 0.5, occupantDensityM2PerPerson: 15, notes: '24時間換気は別途' },
  { usage: '病院（病室）', coolingWm2: 150, ventilationAch: 3, occupantDensityM2PerPerson: 10, notes: '' },
  { usage: '学校（教室）', coolingWm2: 150, ventilationAch: 4, occupantDensityM2PerPerson: 2, notes: '' },
  { usage: 'ホール・集会場', coolingWm2: 200, ventilationAch: 6, occupantDensityM2PerPerson: 1.5, notes: '' },
  { usage: '工場（軽作業）', coolingWm2: 160, ventilationAch: 5, occupantDensityM2PerPerson: 15, notes: '発熱機器は別途加算' },
  { usage: 'サーバー室・電算室', coolingWm2: 400, ventilationAch: 2, occupantDensityM2PerPerson: 40, notes: '機器発熱により大きく変動' },
  { usage: '倉庫', coolingWm2: 80, ventilationAch: 2, occupantDensityM2PerPerson: 50, notes: '' },
  { usage: 'ロビー・共用部', coolingWm2: 140, ventilationAch: 3, occupantDensityM2PerPerson: 10, notes: '' },
]

/**
 * 用途別 空調換気設備工事 概算単価（円/m2・税抜）の初期値。
 * 新築・中規模の目安。物件条件で大きく変動するため必ず社内実績で補正すること。
 */
export const DEFAULT_ROUGH_COSTS: RoughCostUnit[] = [
  { usage: '事務所', costYenPerM2: 22000, notes: '個別空調＋全熱換気' },
  { usage: '会議室', costYenPerM2: 25000, notes: '' },
  { usage: '店舗（物販）', costYenPerM2: 25000, notes: '' },
  { usage: '飲食店（客席）', costYenPerM2: 32000, notes: '厨房排気含まず' },
  { usage: '厨房', costYenPerM2: 55000, notes: 'フード・給気含む目安' },
  { usage: '住宅・寮室', costYenPerM2: 15000, notes: 'ルームエアコン相当' },
  { usage: '病院（病室）', costYenPerM2: 30000, notes: '' },
  { usage: '学校（教室）', costYenPerM2: 20000, notes: '' },
  { usage: 'ホール・集会場', costYenPerM2: 28000, notes: '' },
  { usage: '工場（軽作業）', costYenPerM2: 18000, notes: 'スポット空調別途' },
  { usage: 'サーバー室・電算室', costYenPerM2: 80000, notes: '冗長構成別途' },
  { usage: '倉庫', costYenPerM2: 8000, notes: '換気主体' },
  { usage: 'ロビー・共用部', costYenPerM2: 20000, notes: '' },
]

/** 数量表・単価マスタで使う標準分類 */
export const ITEM_CATEGORIES = [
  '機器',
  'ダクト工事',
  '配管工事',
  '換気工事',
  '保温工事',
  '電気工事',
  'その他',
] as const
