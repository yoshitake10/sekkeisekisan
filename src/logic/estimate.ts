// ============================================================
// 見積計算ロジック
//  - computeDetailEstimate: 数量表（QuantityItem[]）から詳細見積
//  - computeRoughEstimate:  概算行（RoughEstimateRow[]）から概算見積
//  積上げの流れ（両者共通）:
//    分類ごと小計 → 直接工事費 → 諸経費（overheadRatePct）
//    → 法定福利費（welfareRatePct・直接工事費に対して。0なら計上なし）
//    → 小計 → 端数調整（roundingUnitYen で切捨て。調整額はマイナス計上＝出精値引）
//    → 税抜合計 → 消費税 → 税込合計
// ============================================================

import type { EstimateSettings, QuantityItem, RoughEstimateRow } from '../types'
import { roundDown } from '../utils/format'

export interface EstimateComputed {
  /** 分類ごとの明細と小計（円） */
  sections: { category: string; items: QuantityItem[]; subtotal: number }[]
  /** 直接工事費（分類小計の合計・円） */
  directCost: number
  /** 諸経費（円） */
  overhead: number
  /** 法定福利費（円。welfareRatePct=0 のとき 0） */
  welfare: number
  /** 小計＝直接工事費＋諸経費＋法定福利費（端数調整前・円） */
  subtotal: number
  /** 端数調整額（出精値引。0 またはマイナスの円） */
  rounding: number
  /** 税抜合計（＝小計＋端数調整） */
  total: number
  /** 消費税（円） */
  tax: number
  /** 税込合計（円） */
  grandTotal: number
}

/** 明細1行の金額（円・整数）。単価未入力は 0 円として扱う */
export function itemAmountYen(q: QuantityItem): number {
  return Math.round(q.quantity * (q.unitPriceYen ?? 0))
}

/** 分類ごとにグループ化して小計を算出する（出現順を維持） */
function buildSections(items: QuantityItem[]): EstimateComputed['sections'] {
  const order: string[] = []
  const map = new Map<string, QuantityItem[]>()
  for (const q of items) {
    const key = q.category.trim() || 'その他'
    if (!map.has(key)) {
      map.set(key, [])
      order.push(key)
    }
    map.get(key)!.push(q)
  }
  return order.map((category) => {
    const rows = map.get(category)!
    return {
      category,
      items: rows,
      subtotal: rows.reduce((s, q) => s + itemAmountYen(q), 0),
    }
  })
}

/** 分類小計から経費・端数調整・税までを積み上げる（詳細/概算 共通） */
function finalize(
  sections: EstimateComputed['sections'],
  est: EstimateSettings,
): EstimateComputed {
  const directCost = sections.reduce((s, sec) => s + sec.subtotal, 0)
  const overhead = Math.round((directCost * (est.overheadRatePct || 0)) / 100)
  const welfare =
    est.welfareRatePct > 0 ? Math.round((directCost * est.welfareRatePct) / 100) : 0
  const subtotal = directCost + overhead + welfare
  // 端数調整: 指定単位で切捨て、差額をマイナス（出精値引）として計上
  const total = roundDown(subtotal, est.roundingUnitYen || 0)
  const rounding = total - subtotal
  const tax = Math.floor((total * (est.taxRatePct || 0)) / 100)
  const grandTotal = total + tax
  return { sections, directCost, overhead, welfare, subtotal, rounding, total, tax, grandTotal }
}

/**
 * 詳細見積: 数量表の明細から分類ごとに積み上げる。
 * 単価未入力（unitPriceYen が undefined）の行は 0 円として合算される。
 */
export function computeDetailEstimate(
  items: QuantityItem[],
  est: EstimateSettings,
): EstimateComputed {
  return finalize(buildSections(items), est)
}

/** 概算行を QuantityItem 風の明細に変換する（名称＝name（用途）、単位＝m2） */
export function roughRowToItem(r: RoughEstimateRow): QuantityItem {
  const usage = r.usage.trim()
  const name = r.name.trim()
  return {
    id: r.id,
    category: '概算工事費',
    name: name && usage ? `${name}（${usage}）` : name || usage,
    spec: '',
    unit: 'm2',
    quantity: r.areaM2,
    unitPriceYen: r.costYenPerM2,
    source: 'manual',
  }
}

/**
 * 概算見積: 用途×面積×概算単価の行を「概算工事費」1分類の明細に変換し、
 * 経費・端数調整・税は詳細見積と同一ロジックで積み上げる。
 */
export function computeRoughEstimate(
  rows: RoughEstimateRow[],
  est: EstimateSettings,
): EstimateComputed {
  const items = rows.map(roughRowToItem)
  const sections: EstimateComputed['sections'] = [
    {
      category: '概算工事費',
      items,
      subtotal: items.reduce((s, q) => s + itemAmountYen(q), 0),
    },
  ]
  return finalize(sections, est)
}
