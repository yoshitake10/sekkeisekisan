import type {
  DaikinModel,
  LoadUnit,
  QuantityItem,
  Room,
  RoomCalcResult,
} from '../types'
import { genId } from '../utils/id'

// ============================================================
// 負荷計算・機器選定ロジック
//  - 冷房負荷: 面積 × 原単位(W/m2) × 余裕率
//  - 換気量: max(室容積 × 換気回数, 人数 × 30 m3/h・人)
// シンプルで説明可能な概算ロジック。詳細計算は別途行うこと。
// ============================================================

/** 用途が原単位マスタに見つからないときの冷房負荷原単位 W/m2 */
const FALLBACK_COOLING_WM2 = 130
/** 用途が見つからないときの換気回数 回/h */
const FALLBACK_ACH = 3
/** 用途が見つからないときの人員密度 m2/人 */
const FALLBACK_DENSITY_M2_PER_PERSON = 10
/** 台数自動決定時の1台あたり最大能力 kW（5馬力=14.0kW を目安） */
const MAX_KW_PER_UNIT = 14
/** 人員換気量 m3/h・人 */
const VENT_PER_PERSON_M3H = 30

/** 能力を満たす最小機を返す（coolingKw 昇順の最小） */
function pickSmallestSufficient(
  models: DaikinModel[],
  requiredKw: number,
): DaikinModel | undefined {
  let best: DaikinModel | undefined
  for (const m of models) {
    const kw = m.coolingKw ?? 0
    if (kw <= 0) continue
    if (kw >= requiredKw && (!best || kw < (best.coolingKw ?? 0))) best = m
  }
  return best
}

/** 部屋1室の負荷計算と推奨機種選定 */
export function calcRoom(
  room: Room,
  loadUnits: LoadUnit[],
  models: DaikinModel[],
): RoomCalcResult {
  const lu = loadUnits.find((u) => u.usage === room.usage)

  // --- 冷房負荷 ---
  const coolingWm2 = room.coolingWm2Override ?? lu?.coolingWm2 ?? FALLBACK_COOLING_WM2
  const requiredCoolingKw = (room.areaM2 * coolingWm2 * room.safetyFactor) / 1000

  // --- 台数（0なら自動: 1台あたり最大 14kW(5馬力) 目安） ---
  const unitCount =
    room.unitCount > 0
      ? Math.floor(room.unitCount)
      : Math.max(1, Math.ceil(requiredCoolingKw / MAX_KW_PER_UNIT))
  const requiredKwPerUnit = requiredCoolingKw / unitCount

  // --- 推奨機種（スカイエア。希望形態を優先し、なければ形態を問わず） ---
  const skyair = models.filter((m) => m.category === 'skyair')
  const recommendedModel =
    pickSmallestSufficient(
      skyair.filter((m) => m.indoorType === room.preferredIndoorType),
      requiredKwPerUnit,
    ) ?? pickSmallestSufficient(skyair, requiredKwPerUnit)

  // --- 必要換気量 ---
  let requiredVentilationM3h = 0
  if (room.useErv) {
    const ach = lu?.ventilationAch ?? FALLBACK_ACH
    const density = lu?.occupantDensityM2PerPerson ?? FALLBACK_DENSITY_M2_PER_PERSON
    const occupants =
      room.occupants ?? (density > 0 ? Math.ceil(room.areaM2 / density) : 0)
    requiredVentilationM3h = Math.max(
      room.areaM2 * room.ceilingHeightM * ach,
      occupants * VENT_PER_PERSON_M3H,
    )
  }

  // --- 推奨換気機器（風量を満たす最小機。最大機でも不足なら最大機を複数台） ---
  let recommendedVentModel: DaikinModel | undefined
  if (requiredVentilationM3h > 0) {
    const ervs = models
      .filter((m) => m.category === 'ventilation-erv' && (m.airflowM3h ?? 0) > 0)
      .sort((a, b) => (a.airflowM3h ?? 0) - (b.airflowM3h ?? 0))
    recommendedVentModel =
      ervs.find((m) => (m.airflowM3h ?? 0) >= requiredVentilationM3h) ??
      ervs[ervs.length - 1]
  }

  return {
    roomId: room.id,
    coolingWm2,
    requiredCoolingKw,
    unitCount,
    requiredKwPerUnit,
    requiredVentilationM3h,
    recommendedModel,
    recommendedVentModel,
  }
}

/** 換気機器の必要台数（必要換気量 ÷ 機器風量 の切上げ） */
export function ventUnitCount(requiredM3h: number, model: DaikinModel): number {
  if (requiredM3h <= 0) return 0
  const flow = model.airflowM3h ?? 0
  if (flow <= 0) return 1
  return Math.max(1, Math.ceil(requiredM3h / flow))
}

/**
 * 部屋一覧の選定結果を数量表項目に変換する。
 *  - selectedModelId / selectedVentModelId があればそれを優先、なければ推奨機
 *  - 同一機種は数量を集約し、備考に対象室名を列挙
 *  - 空調機器は category「機器」、換気機器は「換気工事」
 */
export function roomsToQuantityItems(
  rooms: Room[],
  loadUnits: LoadUnit[],
  models: DaikinModel[],
): QuantityItem[] {
  interface Agg {
    model: DaikinModel
    category: string
    quantity: number
    roomNames: string[]
  }
  const acc = new Map<string, Agg>()

  function add(model: DaikinModel, category: string, qty: number, roomName: string) {
    if (qty <= 0) return
    const key = `${category}|${model.id}`
    const cur = acc.get(key)
    if (cur) {
      cur.quantity += qty
      if (roomName) cur.roomNames.push(roomName)
    } else {
      acc.set(key, {
        model,
        category,
        quantity: qty,
        roomNames: roomName ? [roomName] : [],
      })
    }
  }

  for (const room of rooms) {
    const calc = calcRoom(room, loadUnits, models)

    // 空調機器（負荷が0の部屋は転記しない）
    const acModel =
      models.find((m) => m.id === room.selectedModelId) ?? calc.recommendedModel
    if (acModel && calc.requiredCoolingKw > 0) {
      add(acModel, '機器', calc.unitCount, room.name)
    }

    // 換気機器
    if (room.useErv && calc.requiredVentilationM3h > 0) {
      const ventModel =
        models.find((m) => m.id === room.selectedVentModelId) ??
        calc.recommendedVentModel
      if (ventModel) {
        add(
          ventModel,
          '換気工事',
          ventUnitCount(calc.requiredVentilationM3h, ventModel),
          room.name,
        )
      }
    }
  }

  return Array.from(acc.values()).map(
    (a): QuantityItem => ({
      id: genId('qty'),
      category: a.category,
      name: `${a.model.series} ${a.model.name}`,
      spec: a.model.modelNo,
      unit: '台',
      quantity: a.quantity,
      unitPriceYen: a.model.priceListYen,
      source: 'equipment',
      remarks: a.roomNames.length > 0 ? `対象室: ${a.roomNames.join('、')}` : undefined,
    }),
  )
}
