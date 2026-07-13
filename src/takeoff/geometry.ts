import type { TakeoffPoint } from '../types'

/** ポリラインの全長（図面単位） */
export function polylineLength(points: TakeoffPoint[]): number {
  let len = 0
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x
    const dy = points[i].y - points[i - 1].y
    len += Math.hypot(dx, dy)
  }
  return len
}

/** 多角形の面積（図面単位^2、靴紐公式・絶対値） */
export function polygonArea(points: TakeoffPoint[]): number {
  if (points.length < 3) return 0
  let s = 0
  for (let i = 0; i < points.length; i++) {
    const a = points[i]
    const b = points[(i + 1) % points.length]
    s += a.x * b.y - b.x * a.y
  }
  return Math.abs(s) / 2
}

/** 2点間距離 */
export function dist(a: TakeoffPoint, b: TakeoffPoint): number {
  return Math.hypot(b.x - a.x, b.y - a.y)
}

/** 測定種別ごとの実数値を計算する。scale: 1図面単位あたりのm */
export function measurementValue(
  kind: 'count' | 'length' | 'area' | 'plot',
  points: TakeoffPoint[],
  scaleMPerUnit: number | undefined,
): number {
  if (kind === 'count' || kind === 'plot') return points.length
  const s = scaleMPerUnit ?? 0
  if (kind === 'length') return polylineLength(points) * s
  return polygonArea(points) * s * s
}

/** 拾いカテゴリごとの既定色 */
export const MEASURE_COLORS = [
  '#e5484d',
  '#0090ff',
  '#30a46c',
  '#f76b15',
  '#8e4ec6',
  '#00a2c7',
  '#ffe629',
  '#e93d82',
]

export function colorForIndex(i: number): string {
  return MEASURE_COLORS[i % MEASURE_COLORS.length]
}
