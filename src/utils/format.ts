/** 3桁区切りの円表示（小数切捨て） */
export function yen(v: number | undefined | null): string {
  if (v === undefined || v === null || Number.isNaN(v)) return ''
  return '¥' + Math.round(v).toLocaleString('ja-JP')
}

/** 3桁区切り数値。digits で小数桁 */
export function num(v: number | undefined | null, digits = 0): string {
  if (v === undefined || v === null || Number.isNaN(v)) return ''
  return v.toLocaleString('ja-JP', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** 指定単位で切上げ 例: roundUp(12345, 1000) = 13000 */
export function roundUp(v: number, unit: number): number {
  if (unit <= 0) return Math.round(v)
  return Math.ceil(v / unit) * unit
}

/** 指定単位で切捨て */
export function roundDown(v: number, unit: number): number {
  if (unit <= 0) return Math.round(v)
  return Math.floor(v / unit) * unit
}

/** 文字列→数値（カンマ・全角数字・空白を許容）。変換不能は NaN */
export function parseNumber(s: string | number | undefined | null): number {
  if (typeof s === 'number') return s
  if (s === undefined || s === null) return NaN
  const half = String(s)
    .replace(/[０-９．]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/[,，\s円¥]/g, '')
  if (half === '') return NaN
  return Number(half)
}

/** 今日の日付 YYYY-MM-DD */
export function todayStr(): string {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** 日本式日付表示 例: 2026年7月7日 */
export function jpDate(iso?: string): string {
  const d = iso ? new Date(iso) : new Date()
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}
