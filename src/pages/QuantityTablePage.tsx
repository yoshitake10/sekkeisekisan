// ============================================================
// 数量表ページ
//  - 図面拾い / 機器選定 / Excel取込 / 手入力 の数量を一元管理
//  - 分類ごとにグループ化して小計を表示、単価マスタから一括引当
// ============================================================

import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useActiveProject, useStore } from '../store'
import type { QuantityItem, QuantitySource } from '../types'
import { QUANTITY_SOURCE_LABELS } from '../types'
import { ITEM_CATEGORIES } from '../data/loadUnits'
import { genId } from '../utils/id'
import { num, parseNumber, yen } from '../utils/format'
import { downloadXlsx, readWorkbook } from '../io/excel'
import type { SheetData } from '../io/excel'
import ImportMappingDialog from '../io/ImportMappingDialog'
import type { ImportField } from '../io/ImportMappingDialog'

const UNCATEGORIZED = '（未分類）'

const SOURCE_BADGE_CLASS: Record<QuantitySource, string> = {
  manual: 'badge',
  import: 'badge orange',
  takeoff: 'badge blue',
  equipment: 'badge green',
}

const IMPORT_FIELDS: ImportField[] = [
  { key: 'name', label: '名称', required: true, aliases: ['品名', '工事名称', '項目', '名 称', '摘要'] },
  { key: 'category', label: '分類', aliases: ['カテゴリ', '種別', '工種', '科目'] },
  { key: 'spec', label: '規格', aliases: ['仕様', '型番', '型式', 'サイズ', '規 格'] },
  { key: 'unit', label: '単位', aliases: ['単 位'] },
  { key: 'quantity', label: '数量', aliases: ['数 量', '員数'] },
  { key: 'unitPrice', label: '単価', aliases: ['複合単価', '単 価', '単価（円）'] },
  { key: 'remarks', label: '備考', aliases: ['注記', 'メモ', '備 考'] },
]

/** 行の金額（単価未設定は undefined） */
function amountOf(q: QuantityItem): number | undefined {
  return q.unitPriceYen === undefined || q.unitPriceYen === null
    ? undefined
    : q.quantity * q.unitPriceYen
}

export default function QuantityTablePage() {
  const project = useActiveProject()
  const unitPrices = useStore((s) => s.unitPrices)
  const addQuantityItems = useStore((s) => s.addQuantityItems)
  const updateQuantityItem = useStore((s) => s.updateQuantityItem)
  const removeQuantityItem = useStore((s) => s.removeQuantityItem)
  const removeQuantityBySource = useStore((s) => s.removeQuantityBySource)

  const fileRef = useRef<HTMLInputElement>(null)
  const [importSheets, setImportSheets] = useState<SheetData[] | null>(null)
  const [sourceFilter, setSourceFilter] = useState<'all' | QuantitySource>('all')

  const items = project.quantityItems

  const filtered = useMemo(
    () => (sourceFilter === 'all' ? items : items.filter((q) => q.source === sourceFilter)),
    [items, sourceFilter],
  )

  /** 分類ごとにグループ化（出現順を維持） */
  const groups = useMemo(() => {
    const order: string[] = []
    const map = new Map<string, QuantityItem[]>()
    for (const q of filtered) {
      const key = q.category.trim() || UNCATEGORIZED
      if (!map.has(key)) {
        map.set(key, [])
        order.push(key)
      }
      map.get(key)!.push(q)
    }
    return order.map((category) => {
      const rows = map.get(category)!
      const subtotal = rows.reduce((s, q) => s + (amountOf(q) ?? 0), 0)
      return { category, rows, subtotal }
    })
  }, [filtered])

  const totalAmount = groups.reduce((s, g) => s + g.subtotal, 0)
  const noPriceCount = filtered.filter((q) => q.unitPriceYen === undefined || q.unitPriceYen === null).length
  const importCount = items.filter((q) => q.source === 'import').length

  const categoryOptions = useMemo(() => {
    const set = new Set<string>(ITEM_CATEGORIES)
    for (const q of items) if (q.category.trim()) set.add(q.category.trim())
    return Array.from(set)
  }, [items])

  // ---------- 行操作 ----------

  function addRow() {
    addQuantityItems([
      {
        id: genId('qty'),
        category: 'その他',
        name: '',
        spec: '',
        unit: '式',
        quantity: 1,
        source: 'manual',
      },
    ])
  }

  function setUnitPriceText(q: QuantityItem, text: string) {
    if (text.trim() === '') {
      updateQuantityItem(q.id, { unitPriceYen: undefined, unitPriceRef: undefined })
      return
    }
    const v = parseNumber(text)
    updateQuantityItem(q.id, {
      unitPriceYen: Number.isFinite(v) ? v : 0,
      unitPriceRef: undefined, // 手入力したので引当参照は解除
    })
  }

  // ---------- Excel/CSV 取込 ----------

  async function onImportFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const sheets = await readWorkbook(file)
      if (sheets.length === 0 || sheets.every((s) => s.rows.length === 0)) {
        alert('ファイルにデータがありません。')
        return
      }
      setImportSheets(sheets)
    } catch (err) {
      console.error(err)
      alert('ファイルの読込みに失敗しました。対応形式: Excel（xlsx / xls）、CSV')
    }
  }

  function handleImportSubmit(records: Record<string, string | number>[]) {
    const newItems: QuantityItem[] = records.map((r) => {
      const qty = parseNumber(r.quantity)
      const price = String(r.unitPrice).trim() === '' ? NaN : parseNumber(r.unitPrice)
      return {
        id: genId('qty'),
        category: String(r.category).trim() || 'その他',
        name: String(r.name).trim(),
        spec: String(r.spec).trim(),
        unit: String(r.unit).trim() || '式',
        quantity: Number.isFinite(qty) ? qty : 0,
        unitPriceYen: Number.isFinite(price) ? price : undefined,
        source: 'import',
        remarks: String(r.remarks).trim() || undefined,
      }
    })
    addQuantityItems(newItems)
    setImportSheets(null)
    alert(`${newItems.length}行を数量表に取り込みました（出典: 取込）。`)
  }

  // ---------- 単価マスタから一括引当 ----------

  function assignPricesFromMaster() {
    if (unitPrices.length === 0) {
      alert('単価マスタが空です。先に「単価マスタ」ページで単価を登録・取込してください。')
      return
    }
    const targets = items.filter((q) => q.unitPriceYen === undefined || q.unitPriceYen === null)
    if (targets.length === 0) {
      alert('単価未設定の行はありません。')
      return
    }
    let hit = 0
    for (const q of targets) {
      const name = q.name.trim()
      const spec = q.spec.trim()
      if (name === '') continue
      // 1) 名称＋規格 完全一致 → 2) 名称 完全一致 → 3) 名称 部分一致（双方向）
      let m = unitPrices.find((u) => u.name.trim() === name && u.spec.trim() === spec)
      if (!m) m = unitPrices.find((u) => u.name.trim() === name)
      if (!m)
        m = unitPrices.find((u) => {
          const un = u.name.trim()
          return un !== '' && (un.includes(name) || name.includes(un))
        })
      if (m) {
        updateQuantityItem(q.id, { unitPriceYen: m.unitPriceYen, unitPriceRef: m.id })
        hit++
      }
    }
    alert(
      `単価マスタから ${hit}件を引当てました。` +
        (targets.length - hit > 0
          ? `\n${targets.length - hit}件は該当する単価が見つかりませんでした（名称・規格を確認してください）。`
          : ''),
    )
  }

  // ---------- Excel 書出し ----------

  function exportXlsx() {
    const header = ['分類', '名称', '規格', '単位', '数量', '単価（円）', '金額（円）', '出典', '備考']
    const rows: (string | number)[][] = [header]
    for (const g of groups) {
      for (const q of g.rows) {
        rows.push([
          q.category,
          q.name,
          q.spec,
          q.unit,
          q.quantity,
          q.unitPriceYen ?? '',
          amountOf(q) ?? '',
          QUANTITY_SOURCE_LABELS[q.source],
          q.remarks ?? '',
        ])
      }
      rows.push([`【${g.category}　小計】`, '', '', '', '', '', g.subtotal, '', ''])
    }
    rows.push(['合計（税抜）', '', '', '', '', '', totalAmount, '', ''])
    downloadXlsx(`数量表_${project.name || '無題'}.xlsx`, [
      { name: '数量表', rows, colWidths: [14, 30, 22, 8, 10, 12, 14, 10, 24] },
    ])
  }

  // ---------- 描画 ----------

  return (
    <div>
      <div className="page-header">
        <h1>数量表</h1>
        <div className="sub">
          図面拾い・機器選定・Excel取込・手入力の数量を一元管理します。単価マスタから一括で単価を引当て、詳細見積の内訳に使用します。
        </div>
      </div>

      <div className="toolbar">
        <button className="btn primary" onClick={addRow}>
          ＋ 行追加
        </button>
        <button className="btn" onClick={() => fileRef.current?.click()}>
          Excel/CSV取込
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          style={{ display: 'none' }}
          onChange={onImportFile}
        />
        <button className="btn accent" onClick={assignPricesFromMaster} disabled={items.length === 0}>
          単価マスタから一括引当
        </button>
        <button className="btn" onClick={exportXlsx} disabled={filtered.length === 0}>
          Excel書出し
        </button>
        <div className="spacer" />
        <label className="field">
          <span>出典で絞込</span>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as 'all' | QuantitySource)}
          >
            <option value="all">すべて（{items.length}件）</option>
            {(Object.keys(QUANTITY_SOURCE_LABELS) as QuantitySource[]).map((s) => (
              <option key={s} value={s}>
                {QUANTITY_SOURCE_LABELS[s]}（{items.filter((q) => q.source === s).length}件）
              </option>
            ))}
          </select>
        </label>
        <button
          className="btn danger"
          disabled={importCount === 0}
          onClick={() => {
            if (confirm(`Excel/CSVから取り込んだ ${importCount}行 をすべて削除しますか？`)) {
              removeQuantityBySource('import')
            }
          }}
        >
          取込行のみ削除
        </button>
      </div>

      <div className="card">
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 110 }}>分類</th>
                <th style={{ minWidth: 160 }}>名称</th>
                <th style={{ minWidth: 120 }}>規格</th>
                <th style={{ width: 60 }}>単位</th>
                <th className="num" style={{ width: 80 }}>数量</th>
                <th className="num" style={{ width: 100 }}>単価（円）</th>
                <th className="num" style={{ width: 110 }}>金額（円）</th>
                <th style={{ width: 70 }}>出典</th>
                <th style={{ minWidth: 110 }}>備考</th>
                <th style={{ width: 56 }}></th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <GroupRows
                  key={g.category}
                  category={g.category}
                  rows={g.rows}
                  subtotal={g.subtotal}
                  onUpdate={updateQuantityItem}
                  onRemove={removeQuantityItem}
                  onUnitPriceText={setUnitPriceText}
                />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={10} className="muted" style={{ textAlign: 'center', padding: 24 }}>
                    数量がありません。「＋ 行追加」で手入力するか、図面拾い・機器選定・Excel取込から数量を追加してください。
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={6} style={{ textAlign: 'right' }}>
                  合計（税抜）
                  {noPriceCount > 0 && (
                    <span className="small danger-text">　※単価未設定 {noPriceCount}件を除く</span>
                  )}
                </td>
                <td className="num">{yen(totalAmount)}</td>
                <td colSpan={3}></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <datalist id="quantity-category-options">
          {categoryOptions.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </div>

      {importSheets && (
        <ImportMappingDialog
          title="数量表への Excel/CSV 取込 — 列の対応付け"
          sheets={importSheets}
          fields={IMPORT_FIELDS}
          onSubmit={handleImportSubmit}
          onCancel={() => setImportSheets(null)}
        />
      )}
    </div>
  )
}

// ------------------------------------------------------------
// 分類グループ（明細行＋小計行）
// ------------------------------------------------------------

function GroupRows(props: {
  category: string
  rows: QuantityItem[]
  subtotal: number
  onUpdate: (id: string, patch: Partial<QuantityItem>) => void
  onRemove: (id: string) => void
  onUnitPriceText: (q: QuantityItem, text: string) => void
}) {
  const { category, rows, subtotal, onUpdate, onRemove, onUnitPriceText } = props
  return (
    <>
      {rows.map((q) => (
        <tr key={q.id}>
          <td>
            <input
              type="text"
              list="quantity-category-options"
              value={q.category}
              onChange={(e) => onUpdate(q.id, { category: e.target.value })}
            />
          </td>
          <td>
            <input
              type="text"
              value={q.name}
              placeholder="名称"
              onChange={(e) => onUpdate(q.id, { name: e.target.value })}
            />
          </td>
          <td>
            <input
              type="text"
              value={q.spec}
              onChange={(e) => onUpdate(q.id, { spec: e.target.value })}
            />
          </td>
          <td>
            <input
              type="text"
              value={q.unit}
              onChange={(e) => onUpdate(q.id, { unit: e.target.value })}
            />
          </td>
          <td className="num">
            <input
              type="number"
              className="num"
              value={q.quantity}
              onChange={(e) => {
                const v = parseNumber(e.target.value)
                onUpdate(q.id, { quantity: Number.isFinite(v) ? v : 0 })
              }}
            />
          </td>
          <td className="num">
            <input
              type="number"
              className="num"
              value={q.unitPriceYen ?? ''}
              placeholder="未設定"
              onChange={(e) => onUnitPriceText(q, e.target.value)}
            />
          </td>
          <td className="num">{amountOf(q) === undefined ? <span className="muted small">—</span> : yen(amountOf(q)!)}</td>
          <td className="center">
            <span className={SOURCE_BADGE_CLASS[q.source]}>{QUANTITY_SOURCE_LABELS[q.source]}</span>
          </td>
          <td>
            <input
              type="text"
              value={q.remarks ?? ''}
              onChange={(e) => onUpdate(q.id, { remarks: e.target.value || undefined })}
            />
          </td>
          <td className="center">
            <button className="btn small danger" onClick={() => onRemove(q.id)}>
              削除
            </button>
          </td>
        </tr>
      ))}
      <tr>
        <td colSpan={6} style={{ background: '#f2f5f8', fontWeight: 600, textAlign: 'right' }}>
          {category}　小計（{num(rows.length)}件）
        </td>
        <td className="num" style={{ background: '#f2f5f8', fontWeight: 600 }}>
          {yen(subtotal)}
        </td>
        <td colSpan={3} style={{ background: '#f2f5f8' }}></td>
      </tr>
    </>
  )
}
