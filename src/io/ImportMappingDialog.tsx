// ============================================================
// Excel/CSV 取込用 列マッピングモーダル（数量表・単価マスタ共用）
//  - シート選択 → 先頭10行プレビュー → 列の対応付け → 開始行指定
//  - onSubmit にはマッピング済みレコード（field.key → セル値）を渡す
// ============================================================

import { useEffect, useMemo, useRef, useState } from 'react'
import { colLetter } from './excel'
import type { SheetData } from './excel'

export interface ImportField {
  /** レコードのキー 例: 'name' */
  key: string
  /** 表示ラベル 例: 名称 */
  label: string
  /** 必須列（未対応付けでは取込不可。値が空の行はスキップ） */
  required?: boolean
  /** 見出し行からの自動推定に使う語 */
  aliases?: string[]
}

export interface ImportMode {
  value: string
  label: string
}

export interface ImportMappingDialogProps {
  title: string
  sheets: SheetData[]
  fields: ImportField[]
  /** 取込モード（追加/全置換 など）。省略時は選択UIなし */
  modes?: ImportMode[]
  modeLabel?: string
  /**
   * 取込実行。records は開始行以降の各行を field.key → セル値 にしたもの。
   * 必須列が空の行は除外済み。mode は選択された取込モード（modes 省略時 ''）。
   */
  onSubmit: (records: Record<string, string | number>[], mode: string) => void
  onCancel: () => void
}

const PREVIEW_ROWS = 10
const MAX_COLS = 52

/** 見出し行の文言から列の対応を推定する */
function guessMapping(
  fields: ImportField[],
  headerRow: (string | number)[] | undefined,
): Record<string, number> {
  const map: Record<string, number> = {}
  if (!headerRow) return map
  const usedCols = new Set<number>()
  for (const f of fields) {
    const words = [f.label, ...(f.aliases ?? [])]
    let found = -1
    // 完全一致を優先し、次に部分一致
    for (const exact of [true, false]) {
      if (found >= 0) break
      for (let c = 0; c < headerRow.length && c < MAX_COLS; c++) {
        if (usedCols.has(c)) continue
        const cell = String(headerRow[c] ?? '').replace(/\s/g, '')
        if (cell === '') continue
        if (words.some((w) => (exact ? cell === w : cell.includes(w)))) {
          found = c
          break
        }
      }
    }
    if (found >= 0) {
      map[f.key] = found
      usedCols.add(found)
    }
  }
  return map
}

export default function ImportMappingDialog(props: ImportMappingDialogProps) {
  const { title, sheets, fields, modes, modeLabel, onSubmit, onCancel } = props
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [sheetIdx, setSheetIdx] = useState(0)
  /** データ開始行（1始まり）。既定は 2（1行目を見出しとみなす） */
  const [startRow, setStartRow] = useState(2)
  /** field.key → 列index（未選択は -1） */
  const [mapping, setMapping] = useState<Record<string, number>>({})
  const [mode, setMode] = useState(modes && modes.length > 0 ? modes[0].value : '')

  const sheet = sheets[sheetIdx]
  const rows = useMemo(() => sheet?.rows ?? [], [sheet])
  const maxCols = useMemo(
    () => Math.min(MAX_COLS, rows.reduce((m, r) => Math.max(m, r.length), 0)),
    [rows],
  )

  useEffect(() => {
    const dlg = dialogRef.current
    if (dlg && !dlg.open) dlg.showModal()
  }, [])

  // シート・開始行が変わったら見出し行から列対応を推定し直す
  useEffect(() => {
    const headerRowIdx = Math.max(0, startRow - 2)
    setMapping(guessMapping(fields, rows[headerRowIdx]))
    // fields は呼び出し側で固定のため依存に含めない
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetIdx, startRow, rows])

  function colOptionLabel(c: number): string {
    const headerRowIdx = Math.max(0, startRow - 2)
    const sample = String(rows[headerRowIdx]?.[c] ?? '').slice(0, 12)
    return sample ? `${colLetter(c)}列（${sample}）` : `${colLetter(c)}列`
  }

  function handleSubmit() {
    const missing = fields.filter((f) => f.required && (mapping[f.key] ?? -1) < 0)
    if (missing.length > 0) {
      alert(`必須列が未選択です: ${missing.map((f) => f.label).join('、')}`)
      return
    }
    const records: Record<string, string | number>[] = []
    for (let r = startRow - 1; r < rows.length; r++) {
      const row = rows[r]
      if (!row) continue
      const rec: Record<string, string | number> = {}
      let hasValue = false
      for (const f of fields) {
        const c = mapping[f.key] ?? -1
        const v = c >= 0 ? (row[c] ?? '') : ''
        rec[f.key] = v
        if (String(v).trim() !== '') hasValue = true
      }
      if (!hasValue) continue
      // 必須列が空の行はスキップ
      if (fields.some((f) => f.required && String(rec[f.key]).trim() === '')) continue
      records.push(rec)
    }
    if (records.length === 0) {
      alert('取込対象の行がありません。開始行と列の対応付けを確認してください。')
      return
    }
    onSubmit(records, mode)
  }

  const previewRows = rows.slice(0, PREVIEW_ROWS)

  return (
    <dialog
      ref={dialogRef}
      className="modal"
      style={{ maxWidth: 860 }}
      onCancel={(e) => {
        e.preventDefault()
        onCancel()
      }}
    >
      <h2 style={{ fontSize: 15, margin: '0 0 10px' }}>{title}</h2>

      <div className="form-row">
        <label className="field">
          <span>対象シート</span>
          <select value={sheetIdx} onChange={(e) => setSheetIdx(Number(e.target.value))}>
            {sheets.map((s, i) => (
              <option key={i} value={i}>
                {s.sheetName}（{s.rows.length}行）
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>データ開始行（見出しの次の行）</span>
          <input
            type="number"
            className="num"
            min={1}
            max={Math.max(1, rows.length)}
            value={startRow}
            onChange={(e) => {
              const v = Math.floor(Number(e.target.value))
              setStartRow(Number.isFinite(v) && v >= 1 ? v : 1)
            }}
            style={{ width: 90 }}
          />
        </label>
        {modes && modes.length > 0 && (
          <label className="field">
            <span>{modeLabel ?? '取込モード'}</span>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              {modes.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <h3 style={{ fontSize: 12.5, margin: '8px 0 4px' }}>
        プレビュー（先頭{Math.min(PREVIEW_ROWS, rows.length)}行）
      </h3>
      <div className="tbl-wrap" style={{ maxHeight: 220, overflowY: 'auto', marginBottom: 10 }}>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 36 }}>行</th>
              {Array.from({ length: maxCols }, (_, c) => (
                <th key={c}>{colLetter(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {previewRows.map((row, r) => (
              <tr key={r} style={r + 1 >= startRow ? undefined : { opacity: 0.45 }}>
                <td className="center muted">{r + 1}</td>
                {Array.from({ length: maxCols }, (_, c) => (
                  <td key={c} style={{ whiteSpace: 'nowrap', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {String(row[c] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="muted" colSpan={maxCols + 1}>
                  このシートにデータがありません
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="small muted" style={{ marginBottom: 10 }}>
        薄く表示されている行は見出し等として取込対象外です（開始行より前）。
      </div>

      <h3 style={{ fontSize: 12.5, margin: '8px 0 4px' }}>列の対応付け</h3>
      <div className="form-row">
        {fields.map((f) => (
          <label className="field" key={f.key}>
            <span>
              {f.label}
              {f.required && <span className="danger-text">（必須）</span>}
            </span>
            <select
              value={mapping[f.key] ?? -1}
              onChange={(e) =>
                setMapping((m) => ({ ...m, [f.key]: Number(e.target.value) }))
              }
            >
              <option value={-1}>— 取込まない —</option>
              {Array.from({ length: maxCols }, (_, c) => (
                <option key={c} value={c}>
                  {colOptionLabel(c)}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <div className="toolbar" style={{ marginTop: 14, marginBottom: 0 }}>
        <div className="spacer" />
        <button className="btn" onClick={onCancel}>
          キャンセル
        </button>
        <button className="btn primary" onClick={handleSubmit}>
          取込を実行
        </button>
      </div>
    </dialog>
  )
}
