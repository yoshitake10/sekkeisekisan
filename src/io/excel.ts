// ============================================================
// Excel 入出力ヘルパー（SheetJS / xlsx）
//  - readWorkbook: xlsx / xls / csv を読み、全シートを2次元配列化
//  - downloadXlsx: ブックを生成してブラウザからダウンロード
// 完全クライアントサイドで動作する（外部通信なし）
// ============================================================

import * as XLSX from 'xlsx'

export interface SheetData {
  sheetName: string
  rows: (string | number)[][]
}

/** セル値を string | number に正規化する（空は ''） */
function normalizeCell(v: unknown): string | number {
  if (v === undefined || v === null) return ''
  if (typeof v === 'number') return Number.isFinite(v) ? v : ''
  if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE'
  if (v instanceof Date) {
    const m = String(v.getMonth() + 1).padStart(2, '0')
    const d = String(v.getDate()).padStart(2, '0')
    return `${v.getFullYear()}-${m}-${d}`
  }
  return String(v)
}

/**
 * CSV をテキストとして読む。UTF-8 で読んで文字化け（置換文字）が出た場合は
 * Shift_JIS として再デコードする（国内の単価表 CSV は Shift_JIS が多いため）。
 */
async function readCsvText(file: File): Promise<string> {
  const buf = await file.arrayBuffer()
  const utf8 = new TextDecoder('utf-8').decode(buf)
  if (!utf8.includes('�')) return utf8
  try {
    return new TextDecoder('shift_jis').decode(buf)
  } catch {
    return utf8
  }
}

/**
 * 結合セルの展開: 結合範囲の左上セルの値を範囲内の全セルへコピーする。
 * （sheet_to_json は結合範囲の左上以外を空セルとして返すため）
 */
function expandMerges(ws: XLSX.WorkSheet, rows: (string | number)[][]): void {
  const merges = ws['!merges']
  if (!merges || merges.length === 0) return
  for (const rng of merges) {
    const v = rows[rng.s.r]?.[rng.s.c]
    if (v === undefined || v === '') continue
    for (let r = rng.s.r; r <= rng.e.r && r < rows.length; r++) {
      const row = rows[r]
      for (let c = rng.s.c; c <= rng.e.c; c++) {
        if (r === rng.s.r && c === rng.s.c) continue
        while (row.length <= c) row.push('')
        row[c] = v
      }
    }
  }
}

/**
 * xlsx / xls / csv ファイルを読み、全シートを2次元配列にして返す。
 * 空セルは '' に統一。数値セルは number のまま返す。
 * 空行も保持する（取込モーダルの行番号を Excel の行番号と一致させるため）。
 */
export async function readWorkbook(
  file: File,
): Promise<{ sheetName: string; rows: (string | number)[][] }[]> {
  const isCsv = /\.csv$/i.test(file.name)
  let wb: XLSX.WorkBook
  if (isCsv) {
    const text = await readCsvText(file)
    // raw: true — 日付様の文字列（例: 2026-07-07）が Excel シリアル値に
    // 変換されるのを防ぎ、セルを文字列のまま保持する（数値化は取込側で行う）
    wb = XLSX.read(text, { type: 'string', raw: true })
  } else {
    const buf = await file.arrayBuffer()
    wb = XLSX.read(buf, { type: 'array', cellDates: true })
  }
  return wb.SheetNames.map((sheetName) => {
    const ws = wb.Sheets[sheetName]
    const raw = ws
      ? (XLSX.utils.sheet_to_json(ws, {
          header: 1,
          defval: '',
          blankrows: true,
        }) as unknown[][])
      : []
    const rows = raw.map((row) => row.map(normalizeCell))
    if (ws) expandMerges(ws, rows)
    return { sheetName, rows }
  })
}

/**
 * シート群からブックを生成してダウンロードする。
 * colWidths は各列の幅（おおよその文字数, !cols の wch）。
 */
export function downloadXlsx(
  fileName: string,
  sheets: { name: string; rows: (string | number)[][]; colWidths?: number[] }[],
): void {
  const wb = XLSX.utils.book_new()
  const used = new Set<string>()
  sheets.forEach((s, i) => {
    const ws = XLSX.utils.aoa_to_sheet(s.rows)
    if (s.colWidths && s.colWidths.length > 0) {
      ws['!cols'] = s.colWidths.map((wch) => ({ wch }))
    }
    // シート名: 31文字制限・禁止文字・重複を回避
    let name = (s.name || `Sheet${i + 1}`).replace(/[\\/?*[\]:]/g, ' ').slice(0, 31)
    if (used.has(name)) name = `${name.slice(0, 28)}_${i + 1}`
    used.add(name)
    XLSX.utils.book_append_sheet(wb, ws, name)
  })
  XLSX.writeFile(wb, fileName)
}

/** 0始まりの列番号 → Excel 列名（A, B, ..., Z, AA, ...） */
export function colLetter(index: number): string {
  let n = index
  let s = ''
  do {
    s = String.fromCharCode(65 + (n % 26)) + s
    n = Math.floor(n / 26) - 1
  } while (n >= 0)
  return s
}
