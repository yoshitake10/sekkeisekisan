// ============================================================
// 単価マスタページ
//  - 自社の複合単価・見積実績を Excel から取り込んで単価マスタ化
//  - 数量表の「単価マスタから一括引当」の引当元になる
// ============================================================

import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useStore } from '../store'
import type { UnitPrice } from '../types'
import { ITEM_CATEGORIES } from '../data/loadUnits'
import { genId } from '../utils/id'
import { num, parseNumber, yen } from '../utils/format'
import { downloadXlsx, readWorkbook } from '../io/excel'
import type { SheetData } from '../io/excel'
import ImportMappingDialog from '../io/ImportMappingDialog'
import type { ImportField, ImportMode } from '../io/ImportMappingDialog'

const IMPORT_FIELDS: ImportField[] = [
  { key: 'name', label: '名称', required: true, aliases: ['品名', '工事名称', '項目', '名 称', '摘要'] },
  { key: 'unitPrice', label: '単価', required: true, aliases: ['複合単価', '単 価', '単価（円）', '材工単価'] },
  { key: 'category', label: '分類', aliases: ['カテゴリ', '種別', '工種', '科目'] },
  { key: 'spec', label: '規格', aliases: ['仕様', '型番', '型式', 'サイズ', '規 格'] },
  { key: 'unit', label: '単位', aliases: ['単 位'] },
  { key: 'source', label: '出典', aliases: ['根拠', '出所', '備考', '年度'] },
]

const IMPORT_MODES: ImportMode[] = [
  { value: 'append', label: '追加（既存マスタに追記）' },
  { value: 'replace', label: '全置換（既存マスタを削除して取込）' },
]

export default function PriceMasterPage() {
  const unitPrices = useStore((s) => s.unitPrices)
  const setUnitPrices = useStore((s) => s.setUnitPrices)
  const upsertUnitPrice = useStore((s) => s.upsertUnitPrice)
  const removeUnitPrice = useStore((s) => s.removeUnitPrice)

  const fileRef = useRef<HTMLInputElement>(null)
  const [importSheets, setImportSheets] = useState<SheetData[] | null>(null)
  const [keyword, setKeyword] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')

  const categoryOptions = useMemo(() => {
    const set = new Set<string>(ITEM_CATEGORIES)
    for (const u of unitPrices) if (u.category.trim()) set.add(u.category.trim())
    return Array.from(set)
  }, [unitPrices])

  const filtered = useMemo(() => {
    const kw = keyword.trim()
    return unitPrices.filter((u) => {
      if (categoryFilter !== 'all' && u.category.trim() !== categoryFilter) return false
      if (kw === '') return true
      return [u.name, u.spec, u.category].some((s) => s.includes(kw))
    })
  }, [unitPrices, keyword, categoryFilter])

  // ---------- 行操作 ----------

  function addRow() {
    upsertUnitPrice({
      id: genId('up'),
      category: 'その他',
      name: '',
      spec: '',
      unit: '式',
      unitPriceYen: 0,
    })
  }

  function upd(row: UnitPrice, patch: Partial<UnitPrice>) {
    upsertUnitPrice({ ...row, ...patch })
  }

  // ---------- Excel 取込 ----------

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

  function handleImportSubmit(records: Record<string, string | number>[], mode: string) {
    const rows: UnitPrice[] = records.map((r) => {
      const price = parseNumber(r.unitPrice)
      return {
        id: genId('up'),
        category: String(r.category).trim() || 'その他',
        name: String(r.name).trim(),
        spec: String(r.spec).trim(),
        unit: String(r.unit).trim() || '式',
        unitPriceYen: Number.isFinite(price) ? price : 0,
        source: String(r.source).trim() || undefined,
      }
    })
    if (mode === 'replace') {
      if (!confirm(`既存の単価マスタ ${unitPrices.length}件 を削除して ${rows.length}件 に置き換えます。よろしいですか？`)) {
        return
      }
      setUnitPrices(rows)
    } else {
      setUnitPrices([...unitPrices, ...rows])
    }
    setImportSheets(null)
    alert(
      mode === 'replace'
        ? `単価マスタを ${rows.length}件 に置き換えました。`
        : `単価マスタに ${rows.length}件 を追加しました。`,
    )
  }

  // ---------- Excel 書出し ----------

  function exportXlsx() {
    const header = ['分類', '名称', '規格', '単位', '単価（円）', '出典']
    const rows: (string | number)[][] = [
      header,
      ...unitPrices.map((u) => [
        u.category,
        u.name,
        u.spec,
        u.unit,
        u.unitPriceYen,
        u.source ?? '',
      ]),
    ]
    downloadXlsx('単価マスタ.xlsx', [
      { name: '単価マスタ', rows, colWidths: [14, 32, 24, 8, 12, 20] },
    ])
  }

  // ---------- 描画 ----------

  return (
    <div>
      <div className="page-header">
        <h1>単価マスタ</h1>
        <div className="sub">
          数量表の「単価マスタから一括引当」で参照される自社単価の台帳です。ブラウザ内に保存され、外部には送信されません。
        </div>
      </div>

      <div className="note">
        お手持ちの複合単価表・見積実績のExcelを取り込んで自社単価マスタとして使えます。名称・規格が数量表の表記と一致しているほど自動引当の精度が上がります。
      </div>

      <div className="toolbar">
        <label className="field">
          <span>検索（名称 / 規格 / 分類）</span>
          <input
            type="text"
            value={keyword}
            placeholder="例: スパイラルダクト"
            style={{ width: 220 }}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </label>
        <label className="field">
          <span>分類</span>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="all">すべて</option>
            {categoryOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <div className="spacer" />
        <button className="btn primary" onClick={addRow}>
          ＋ 行追加
        </button>
        <button className="btn" onClick={() => fileRef.current?.click()}>
          Excel取込
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          style={{ display: 'none' }}
          onChange={onImportFile}
        />
        <button className="btn" onClick={exportXlsx} disabled={unitPrices.length === 0}>
          Excel書出し
        </button>
      </div>

      <div className="card">
        <div className="toolbar" style={{ marginBottom: 6 }}>
          <span className="muted small">
            登録 {num(unitPrices.length)}件
            {(keyword.trim() !== '' || categoryFilter !== 'all') && (
              <>　／　絞込表示 {num(filtered.length)}件</>
            )}
          </span>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 120 }}>分類</th>
                <th style={{ minWidth: 180 }}>名称</th>
                <th style={{ minWidth: 140 }}>規格</th>
                <th style={{ width: 70 }}>単位</th>
                <th className="num" style={{ width: 110 }}>単価（円）</th>
                <th style={{ minWidth: 120 }}>出典</th>
                <th style={{ width: 56 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.id}>
                  <td>
                    <input
                      type="text"
                      list="price-master-category-options"
                      value={u.category}
                      onChange={(e) => upd(u, { category: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={u.name}
                      placeholder="名称"
                      onChange={(e) => upd(u, { name: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={u.spec}
                      onChange={(e) => upd(u, { spec: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={u.unit}
                      onChange={(e) => upd(u, { unit: e.target.value })}
                    />
                  </td>
                  <td className="num">
                    <input
                      type="number"
                      className="num"
                      value={u.unitPriceYen}
                      onChange={(e) => {
                        const v = parseNumber(e.target.value)
                        upd(u, { unitPriceYen: Number.isFinite(v) ? v : 0 })
                      }}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={u.source ?? ''}
                      placeholder="例: 2026年度 社内単価"
                      onChange={(e) => upd(u, { source: e.target.value || undefined })}
                    />
                  </td>
                  <td className="center">
                    <button
                      className="btn small danger"
                      onClick={() => removeUnitPrice(u.id)}
                    >
                      削除
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 24 }}>
                    {unitPrices.length === 0
                      ? '単価マスタが空です。「＋ 行追加」か「Excel取込」で単価を登録してください。'
                      : '検索条件に一致する単価がありません。'}
                  </td>
                </tr>
              )}
            </tbody>
            {filtered.length > 0 && (
              <tfoot>
                <tr>
                  <td colSpan={4} style={{ textAlign: 'right' }}>
                    表示中の単価 平均
                  </td>
                  <td className="num">
                    {yen(filtered.reduce((s, u) => s + u.unitPriceYen, 0) / filtered.length)}
                  </td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        <datalist id="price-master-category-options">
          {categoryOptions.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </div>

      {importSheets && (
        <ImportMappingDialog
          title="単価マスタへの Excel 取込 — 列の対応付け"
          sheets={importSheets}
          fields={IMPORT_FIELDS}
          modes={IMPORT_MODES}
          modeLabel="取込モード"
          onSubmit={handleImportSubmit}
          onCancel={() => setImportSheets(null)}
        />
      )}
    </div>
  )
}
