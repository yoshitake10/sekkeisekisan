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
import { itemAmountYen } from '../logic/estimate'
import { equipmentRowsStale, inheritEditedPrices, roomsToQuantityItems } from '../logic/selection'

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

/** 行の金額（単価未設定は undefined）。見積書と同じ行ごと四捨五入（itemAmountYen）に統一 */
function amountOf(q: QuantityItem): number | undefined {
  return q.unitPriceYen === undefined || q.unitPriceYen === null
    ? undefined
    : itemAmountYen(q)
}

/** 引当マッチ用の正規化（全角英数記号→半角・小文字化・空白除去） */
function normMatch(s: string): string {
  return s
    .replace(/[！-～]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/\s+/g, '')
    .toLowerCase()
}

export default function QuantityTablePage() {
  const project = useActiveProject()
  const unitPrices = useStore((s) => s.unitPrices)
  const loadUnits = useStore((s) => s.loadUnits)
  const daikinModels = useStore((s) => s.daikinModels)
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

  /** 機器選定の内容と数量表の機器行の差異検知（転記忘れ・陳腐化の防止） */
  const equipmentSync = useMemo(() => {
    const equipRows = items.filter((q) => q.source === 'equipment')
    if (project.rooms.length === 0) return 'none' as const
    if (equipRows.length === 0) {
      const { items: fresh } = roomsToQuantityItems(project.rooms, loadUnits, daikinModels)
      return fresh.length > 0 ? ('untransferred' as const) : ('none' as const)
    }
    return equipmentRowsStale(project.rooms, loadUnits, daikinModels, items)
      ? ('stale' as const)
      : ('ok' as const)
  }, [items, project.rooms, loadUnits, daikinModels])

  /** 機器選定から（再）転記。編集済み単価は引き継ぐ */
  function retransferEquipment() {
    const { items: fresh, skippedRooms } = roomsToQuantityItems(
      project.rooms,
      loadUnits,
      daikinModels,
    )
    const prevEquip = items.filter((q) => q.source === 'equipment')
    const { items: merged, inherited } = inheritEditedPrices(fresh, prevEquip)
    removeQuantityBySource('equipment')
    addQuantityItems(merged)
    let msg = `機器選定の結果 ${merged.length} 件を数量表へ反映しました。`
    if (inherited > 0) msg += `\n（編集していた単価 ${inherited}件は引き継ぎました）`
    if (skippedRooms.length > 0)
      msg += `\n\n機種未確定のため転記されていない部屋: ${skippedRooms.join('、')}`
    alert(msg)
  }

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
    // 単価0円以下のマスタ行は誤引当防止のため自動引当の対象外
    const masters = unitPrices
      .filter((u) => u.unitPriceYen > 0)
      .map((u) => ({ u, name: normMatch(u.name), spec: normMatch(u.spec) }))
      .filter((x) => x.name !== '')
    let hit = 0
    let specSkipped = 0
    for (const q of targets) {
      const name = normMatch(q.name)
      const spec = normMatch(q.spec)
      if (name === '') continue
      /** 名称の片方向部分一致（短い方が3文字以上のときのみ） */
      const nameLoose = (x: { name: string }) => {
        const shorter = x.name.length <= name.length ? x.name : name
        const longer = x.name.length <= name.length ? name : x.name
        return shorter.length >= 3 && longer.includes(shorter)
      }
      // 1) 名称＋規格 完全一致（規格は両方空も一致扱い）
      let m = masters.find((x) => x.name === name && x.spec === spec)
      // 2) 名称の片方向部分一致。規格は両方空 or 一致のときのみ
      //    （規格が両方入っていて不一致なら引当てない）
      if (!m) m = masters.find((x) => x.spec === spec && nameLoose(x))
      if (m) {
        updateQuantityItem(q.id, { unitPriceYen: m.u.unitPriceYen, unitPriceRef: m.u.id })
        hit++
      } else if (masters.some((x) => x.name === name || nameLoose(x))) {
        // 名称は一致するが規格不一致のため見送り
        specSkipped++
      }
    }
    const missed = targets.length - hit
    alert(
      `単価マスタから ${hit}件を引当てました。` +
        (missed > 0
          ? `\n${missed}件は該当する単価が見つかりませんでした（名称・規格を確認してください）。`
          : '') +
        (specSkipped > 0
          ? `\nうち ${specSkipped}件は名称が一致するものの規格不一致のため引当てを見送りました。`
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

      {equipmentSync === 'stale' && (
        <div
          className="note"
          style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}
        >
          <span>
            ⚠ 「機器選定」の内容とこの数量表の機器行に差異があります（機器選定を変更した後、再転記されていません）。
          </span>
          <button className="btn small accent" onClick={retransferEquipment}>
            機器選定から再転記（単価は引き継ぐ）
          </button>
        </div>
      )}
      {equipmentSync === 'untransferred' && (
        <div
          className="note"
          style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}
        >
          <span>「機器選定」の選定結果がまだ数量表に転記されていません。</span>
          <button className="btn small accent" onClick={retransferEquipment}>
            機器選定から転記する
          </button>
        </div>
      )}

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
            {/* 分類は1文字入力ごとに行が別グループへ再マウントされフォーカスが
                失われるため、確定（blur / Enter）時のみストアへ反映する */}
            <CommitTextInput
              value={q.category}
              list="quantity-category-options"
              onCommit={(v) => onUpdate(q.id, { category: v })}
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

// ------------------------------------------------------------
// コミット式テキスト入力（編集中はローカル、blur / Enter で確定）
// ------------------------------------------------------------

function CommitTextInput(props: {
  value: string
  onCommit: (v: string) => void
  placeholder?: string
  list?: string
}) {
  const { value, onCommit, placeholder, list } = props
  return (
    <input
      key={value}
      type="text"
      list={list}
      defaultValue={value}
      placeholder={placeholder}
      onBlur={(e) => {
        if (e.target.value !== value) onCommit(e.target.value)
      }}
      onKeyDown={(e) => {
        // IME 変換確定の Enter では確定しない
        if (e.key === 'Enter' && !e.nativeEvent.isComposing) e.currentTarget.blur()
      }}
    />
  )
}
