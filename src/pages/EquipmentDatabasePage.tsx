import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { num, parseNumber } from '../utils/format'
import { DAIKIN_CATEGORY_LABELS } from '../types'
import type { DaikinCategory, DaikinModel } from '../types'
import { genId } from '../utils/id'

const CATEGORIES = Object.keys(DAIKIN_CATEGORY_LABELS) as DaikinCategory[]

/** ダイキン機器データベースページ */
export default function EquipmentDatabasePage() {
  const models = useStore((s) => s.daikinModels)
  const upsertDaikinModel = useStore((s) => s.upsertDaikinModel)
  const removeDaikinModel = useStore((s) => s.removeDaikinModel)
  const resetDaikinModels = useStore((s) => s.resetDaikinModels)

  const [category, setCategory] = useState<'all' | DaikinCategory>('all')
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return models.filter((m) => {
      if (category !== 'all' && m.category !== category) return false
      if (q === '') return true
      const hay = [m.series, m.name, m.modelNo, m.hpClass ?? '', m.notes ?? '', m.powerSupply ?? '']
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [models, category, query])

  /** インライン編集の共通処理 */
  function upd(m: DaikinModel, patch: Partial<DaikinModel>) {
    upsertDaikinModel({ ...m, ...patch })
  }

  /** 数値入力（空欄は undefined） */
  function numOrUndef(v: string): number | undefined {
    if (v.trim() === '') return undefined
    const n = parseNumber(v)
    return Number.isNaN(n) ? undefined : n
  }

  function addBlank() {
    upsertDaikinModel({
      id: genId('dkn'),
      category: category === 'all' ? 'other' : category,
      series: '',
      name: '新規機種',
      modelNo: '',
      notes: '',
    })
  }

  function resetAll() {
    if (
      confirm(
        '機器データベースを初期データに戻しますか？\n（追加・編集した機種と定価はすべて失われます）',
      )
    ) {
      resetDaikinModels()
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>ダイキン機器データベース</h1>
        <div className="sub">
          機器選定・数量表で使用するダイキン機器のマスタです。定価や型番は自社の仕入条件に合わせて編集できます。
        </div>
      </div>

      <div className="note">
        収録データは代表型番・目安定価です。正式見積時は最新カタログ・仕切り価格で確認してください。
      </div>

      <div className="card">
        <h2>機種一覧</h2>
        <div className="toolbar">
          <label className="field">
            <span>カテゴリ</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as 'all' | DaikinCategory)}
            >
              <option value="all">すべて</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {DAIKIN_CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>検索（型番・名称・シリーズ）</span>
            <input
              type="text"
              value={query}
              placeholder="例: SZRC80 / 天井カセット"
              style={{ width: 220 }}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <span className="muted small">
            {num(filtered.length)} 件 / 全 {num(models.length)} 件
          </span>
          <div className="spacer" />
          <button className="btn primary" onClick={addBlank}>
            ＋ 機種追加
          </button>
          <button className="btn" onClick={resetAll}>
            初期データに戻す
          </button>
        </div>

        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ minWidth: 130 }}>カテゴリ</th>
                <th style={{ minWidth: 110 }}>シリーズ</th>
                <th style={{ minWidth: 220 }}>名称</th>
                <th style={{ minWidth: 110 }}>型番</th>
                <th style={{ width: 90 }}>馬力</th>
                <th style={{ width: 75 }}>冷房 kW</th>
                <th style={{ width: 75 }}>暖房 kW</th>
                <th style={{ width: 85 }}>風量 m³/h</th>
                <th style={{ width: 90 }}>電源</th>
                <th style={{ width: 105 }}>定価（円・税抜）</th>
                <th style={{ minWidth: 180 }}>備考</th>
                <th style={{ width: 52 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={12} className="center muted">
                    該当する機種がありません。カテゴリ・検索条件を変更するか「＋ 機種追加」で登録してください。
                  </td>
                </tr>
              )}
              {filtered.map((m) => (
                <tr key={m.id}>
                  <td>
                    <select
                      value={m.category}
                      onChange={(e) => upd(m, { category: e.target.value as DaikinCategory })}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {DAIKIN_CATEGORY_LABELS[c]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="text"
                      value={m.series}
                      onChange={(e) => upd(m, { series: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={m.name}
                      onChange={(e) => upd(m, { name: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={m.modelNo}
                      onChange={(e) => upd(m, { modelNo: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={m.hpClass ?? ''}
                      placeholder="例: 3馬力"
                      onChange={(e) => upd(m, { hpClass: e.target.value || undefined })}
                    />
                  </td>
                  <td className="num">
                    <input
                      type="number"
                      className="num"
                      step={0.1}
                      value={m.coolingKw ?? ''}
                      onChange={(e) => upd(m, { coolingKw: numOrUndef(e.target.value) })}
                    />
                  </td>
                  <td className="num">
                    <input
                      type="number"
                      className="num"
                      step={0.1}
                      value={m.heatingKw ?? ''}
                      onChange={(e) => upd(m, { heatingKw: numOrUndef(e.target.value) })}
                    />
                  </td>
                  <td className="num">
                    <input
                      type="number"
                      className="num"
                      value={m.airflowM3h ?? ''}
                      onChange={(e) => upd(m, { airflowM3h: numOrUndef(e.target.value) })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={m.powerSupply ?? ''}
                      placeholder="例: 三相200V"
                      onChange={(e) => upd(m, { powerSupply: e.target.value || undefined })}
                    />
                  </td>
                  <td className="num">
                    <input
                      type="number"
                      className="num"
                      step={1000}
                      value={m.priceListYen ?? ''}
                      onChange={(e) => upd(m, { priceListYen: numOrUndef(e.target.value) })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={m.notes ?? ''}
                      onChange={(e) => upd(m, { notes: e.target.value || undefined })}
                    />
                  </td>
                  <td className="center">
                    <button
                      className="btn small danger"
                      onClick={() => {
                        if (confirm(`機種「${m.modelNo || m.name}」を削除しますか？`)) {
                          removeDaikinModel(m.id)
                        }
                      }}
                    >
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="small muted" style={{ marginTop: 8 }}>
          ・機器選定ページの推奨選定には「業務用パッケージ（スカイエア）」の冷房kWと「全熱交換器ユニット」の風量を使用します。
          ・機種を削除・変更すると、その機種を手動選択していた部屋は推奨機選定に戻ります。
        </div>
      </div>
    </div>
  )
}
