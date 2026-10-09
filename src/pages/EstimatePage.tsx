// ============================================================
// 見積書ページ
//  - 概算見積（用途×面積×概算単価）/ 詳細見積（数量表から）の2モード
//  - 見積条件（宛名・経費率・端数処理など）の編集
//  - A4風の見積書プレビュー（印刷 / PDF保存）と Excel 書出し
// ============================================================

import { Fragment, useMemo } from 'react'
import { useActiveProject, useStore } from '../store'
import type { EstimateMode, RoughEstimateRow } from '../types'
import { computeDetailEstimate, computeRoughEstimate, itemAmountYen } from '../logic/estimate'
import type { EstimateComputed } from '../logic/estimate'
import { exportEstimateXlsx } from '../io/estimateExcel'
import { genId } from '../utils/id'
import { jpDate, num, parseNumber, yen } from '../utils/format'

/** 入力文字列→数値（変換不能は 0） */
function numOr0(s: string): number {
  const v = parseNumber(s)
  return Number.isFinite(v) ? v : 0
}

/** 数量の表示（整数はそのまま、小数は2桁まで） */
function qty(v: number): string {
  return num(v, Number.isInteger(v) ? 0 : 2)
}

/** 集計行（直接工事費計〜税込合計）。プレビュー表紙・内訳明細で共用 */
function summaryLines(
  c: EstimateComputed,
  est: { overheadRatePct: number; welfareRatePct: number; taxRatePct: number },
): { label: string; amount: number; strong?: boolean }[] {
  const lines: { label: string; amount: number; strong?: boolean }[] = [
    { label: '直接工事費 計', amount: c.directCost },
    { label: `諸経費（直接工事費の${est.overheadRatePct}%）`, amount: c.overhead },
  ]
  if (c.welfare !== 0) {
    lines.push({ label: `法定福利費（直接工事費の${est.welfareRatePct}%）`, amount: c.welfare })
  }
  if (c.rounding !== 0) {
    lines.push({ label: '出精値引（端数調整）', amount: c.rounding })
  }
  lines.push({ label: '税抜合計', amount: c.total, strong: true })
  lines.push({ label: `消費税（${est.taxRatePct}%）`, amount: c.tax })
  lines.push({ label: '御見積金額（税込）', amount: c.grandTotal, strong: true })
  return lines
}

export default function EstimatePage() {
  const project = useActiveProject()
  const roughCosts = useStore((s) => s.roughCosts)
  const updateEstimate = useStore((s) => s.updateEstimate)

  const est = project.estimate
  const mode = est.mode
  const roughRows = est.roughRows

  const computed = useMemo(
    () =>
      mode === 'rough'
        ? computeRoughEstimate(roughRows, est)
        : computeDetailEstimate(project.quantityItems, est),
    [mode, roughRows, est, project.quantityItems],
  )

  const noPriceCount = project.quantityItems.filter(
    (q) => q.unitPriceYen === undefined || q.unitPriceYen === null,
  ).length

  const usageOptions = roughCosts.map((c) => c.usage)

  // ---------- 概算行の操作 ----------

  function setRoughRows(rows: RoughEstimateRow[]) {
    updateEstimate({ roughRows: rows })
  }

  function updateRough(id: string, patch: Partial<RoughEstimateRow>) {
    setRoughRows(roughRows.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function addRoughRow() {
    setRoughRows([
      ...roughRows,
      { id: genId('rough'), usage: '', name: '', areaM2: 0, costYenPerM2: 0 },
    ])
  }

  /** 用途を選ぶと概算単価マスタから単価を自動セット */
  function onUsageChange(r: RoughEstimateRow, usage: string) {
    const master = roughCosts.find((c) => c.usage === usage)
    updateRough(r.id, {
      usage,
      ...(master ? { costYenPerM2: master.costYenPerM2 } : {}),
    })
  }

  function costFor(usage: string): number {
    return roughCosts.find((c) => c.usage === usage)?.costYenPerM2 ?? 0
  }

  /** プロジェクトの主用途×延床面積で1行生成 */
  function genFromProject() {
    if (!project.totalFloorAreaM2 || project.totalFloorAreaM2 <= 0) {
      alert('プロジェクトページで延床面積（m²）を入力してください。')
      return
    }
    const usage = project.buildingUsage || 'その他'
    setRoughRows([
      ...roughRows,
      {
        id: genId('rough'),
        usage,
        name: '空調換気設備工事 一式',
        areaM2: project.totalFloorAreaM2,
        costYenPerM2: costFor(usage),
      },
    ])
  }

  /** 機器選定の部屋を用途ごとに面積集計して行生成 */
  function genFromRooms() {
    if (project.rooms.length === 0) {
      alert('機器選定（負荷計算）ページに部屋が登録されていません。')
      return
    }
    const order: string[] = []
    const agg = new Map<string, { area: number; count: number }>()
    for (const room of project.rooms) {
      const u = room.usage.trim() || 'その他'
      if (!agg.has(u)) {
        agg.set(u, { area: 0, count: 0 })
        order.push(u)
      }
      const a = agg.get(u)!
      a.area += room.areaM2
      a.count++
    }
    const rows: RoughEstimateRow[] = order.map((u) => {
      const a = agg.get(u)!
      return {
        id: genId('rough'),
        usage: u,
        name: `空調換気設備工事（${a.count}室）`,
        areaM2: Math.round(a.area * 100) / 100,
        costYenPerM2: costFor(u),
      }
    })
    setRoughRows([...roughRows, ...rows])
  }

  const roughAreaTotal = roughRows.reduce((s, r) => s + r.areaM2, 0)

  const lines = summaryLines(computed, est)
  const allItemsEmpty = computed.sections.every((s) => s.items.length === 0)

  // ---------- 描画 ----------

  return (
    <>
      {/* ===== 編集エリア（印刷時は非表示） ===== */}
      <div className="no-print">
        <div className="page-header">
          <h1>見積書</h1>
          <div className="sub">
            概算見積（用途×面積×概算単価）または詳細見積（数量表の積上げ）から見積書を作成し、印刷（PDF保存）・Excel書出しができます。
          </div>
        </div>

        <div className="toolbar">
          <button
            className={'btn' + (mode === 'rough' ? ' active' : '')}
            onClick={() => updateEstimate({ mode: 'rough' as EstimateMode })}
          >
            概算見積
          </button>
          <button
            className={'btn' + (mode === 'detail' ? ' active' : '')}
            onClick={() => updateEstimate({ mode: 'detail' as EstimateMode })}
          >
            詳細見積（数量表から）
          </button>
          <div className="spacer" />
          <button className="btn" onClick={() => window.print()}>
            印刷 / PDF保存
          </button>
          <button
            className="btn primary"
            onClick={() => exportEstimateXlsx(project, computed, est)}
          >
            Excel書出し
          </button>
        </div>

        <div className="kpi" style={{ marginBottom: 14 }}>
          <div className="kpi-item">
            <div className="v">{yen(computed.directCost)}</div>
            <div className="k">直接工事費</div>
          </div>
          <div className="kpi-item">
            <div className="v">{yen(computed.overhead + computed.welfare)}</div>
            <div className="k">諸経費・法定福利費</div>
          </div>
          <div className="kpi-item">
            <div className="v">{yen(computed.total)}</div>
            <div className="k">税抜合計</div>
          </div>
          <div className="kpi-item">
            <div className="v accent-text">{yen(computed.grandTotal)}</div>
            <div className="k">御見積金額（税込）</div>
          </div>
        </div>

        {mode === 'rough' ? (
          <div className="card">
            <h2>概算見積 明細（用途 × 面積 × 概算単価）</h2>
            <div className="toolbar">
              <button className="btn primary" onClick={addRoughRow}>
                ＋ 行追加
              </button>
              <button className="btn" onClick={genFromProject}>
                案件情報から生成
              </button>
              <button className="btn" onClick={genFromRooms}>
                機器選定の部屋から生成
              </button>
            </div>
            {roughRows.length === 0 && (
              <div className="note">
                概算行がありません。「案件情報から生成」（主用途×延床面積）、「機器選定の部屋から生成」（部屋を用途ごとに面積集計）、または「＋
                行追加」で作成してください。用途を選ぶと概算単価マスタの単価が自動セットされます。
              </div>
            )}
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: 170 }}>用途</th>
                    <th style={{ minWidth: 180 }}>名称</th>
                    <th className="num" style={{ width: 110 }}>面積（m²）</th>
                    <th className="num" style={{ width: 120 }}>単価（円/m²）</th>
                    <th className="num" style={{ width: 130 }}>金額（円）</th>
                    <th style={{ width: 56 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {roughRows.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <select value={r.usage} onChange={(e) => onUsageChange(r, e.target.value)}>
                          <option value="">（用途を選択）</option>
                          {usageOptions.map((u) => (
                            <option key={u} value={u}>
                              {u}
                            </option>
                          ))}
                          {r.usage !== '' && !usageOptions.includes(r.usage) && (
                            <option value={r.usage}>{r.usage}</option>
                          )}
                        </select>
                      </td>
                      <td>
                        <input
                          type="text"
                          value={r.name}
                          placeholder="例: 空調換気設備工事 一式"
                          onChange={(e) => updateRough(r.id, { name: e.target.value })}
                        />
                      </td>
                      <td className="num">
                        <input
                          type="number"
                          className="num"
                          value={r.areaM2}
                          onChange={(e) => updateRough(r.id, { areaM2: numOr0(e.target.value) })}
                        />
                      </td>
                      <td className="num">
                        <input
                          type="number"
                          className="num"
                          value={r.costYenPerM2}
                          onChange={(e) =>
                            updateRough(r.id, { costYenPerM2: numOr0(e.target.value) })
                          }
                        />
                      </td>
                      <td className="num">{yen(Math.round(r.areaM2 * r.costYenPerM2))}</td>
                      <td className="center">
                        <button
                          className="btn small danger"
                          onClick={() => setRoughRows(roughRows.filter((x) => x.id !== r.id))}
                        >
                          削除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                {roughRows.length > 0 && (
                  <tfoot>
                    <tr>
                      <td colSpan={2} style={{ textAlign: 'right' }}>
                        合計
                      </td>
                      <td className="num">{qty(roughAreaTotal)}</td>
                      <td></td>
                      <td className="num">{yen(computed.directCost)}</td>
                      <td></td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
            <div className="small muted" style={{ marginTop: 6 }}>
              ※ 概算単価は「原単位・概算単価」マスタの値です。物件条件（規模・グレード・改修/新築）に応じて単価を補正してください。
            </div>
          </div>
        ) : (
          <div className="card">
            <h2>詳細見積（数量表の積上げ）</h2>
            {project.quantityItems.length === 0 ? (
              <div className="note">
                数量表に明細がありません。「数量表」タブで行追加・Excel取込するか、図面拾い・機器選定から数量を送ってください。
              </div>
            ) : (
              noPriceCount > 0 && (
                <div className="note">
                  {noPriceCount}行が単価未入力です。数量表タブで入力するか「単価マスタから一括引当」してください（未入力行は0円で集計されます）。
                </div>
              )
            )}
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>分類</th>
                    <th className="num" style={{ width: 90 }}>件数</th>
                    <th className="num" style={{ width: 150 }}>小計（円）</th>
                  </tr>
                </thead>
                <tbody>
                  {computed.sections.map((sec) => (
                    <tr key={sec.category}>
                      <td>{sec.category}</td>
                      <td className="num">{num(sec.items.length)}</td>
                      <td className="num">{yen(sec.subtotal)}</td>
                    </tr>
                  ))}
                  {computed.sections.length === 0 && (
                    <tr>
                      <td colSpan={3} className="muted" style={{ textAlign: 'center', padding: 18 }}>
                        集計対象がありません
                      </td>
                    </tr>
                  )}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={2} style={{ textAlign: 'right' }}>
                      直接工事費 計
                    </td>
                    <td className="num">{yen(computed.directCost)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* ===== 見積条件 ===== */}
        <div className="card">
          <h2>見積条件</h2>
          <div className="form-row">
            <label className="field">
              <span>宛名（客先名）</span>
              <input
                type="text"
                style={{ width: 240 }}
                value={est.clientName}
                placeholder="例: 株式会社○○建設"
                onChange={(e) => updateEstimate({ clientName: e.target.value })}
              />
            </label>
            <label className="field">
              <span>敬称</span>
              <input
                type="text"
                style={{ width: 70 }}
                list="honorific-options"
                value={est.honorific}
                onChange={(e) => updateEstimate({ honorific: e.target.value })}
              />
            </label>
            <label className="field">
              <span>件名</span>
              <input
                type="text"
                style={{ width: 320 }}
                value={est.title}
                onChange={(e) => updateEstimate({ title: e.target.value })}
              />
            </label>
          </div>
          <div className="form-row">
            <label className="field">
              <span>自社名</span>
              <input
                type="text"
                style={{ width: 240 }}
                value={est.companyName}
                onChange={(e) => updateEstimate({ companyName: e.target.value })}
              />
            </label>
            <label className="field">
              <span>住所</span>
              <input
                type="text"
                style={{ width: 320 }}
                value={est.companyAddress}
                onChange={(e) => updateEstimate({ companyAddress: e.target.value })}
              />
            </label>
            <label className="field">
              <span>TEL</span>
              <input
                type="text"
                style={{ width: 140 }}
                value={est.companyTel}
                onChange={(e) => updateEstimate({ companyTel: e.target.value })}
              />
            </label>
            <label className="field">
              <span>担当者</span>
              <input
                type="text"
                style={{ width: 140 }}
                value={est.personInCharge}
                onChange={(e) => updateEstimate({ personInCharge: e.target.value })}
              />
            </label>
          </div>
          <div className="form-row">
            <label className="field">
              <span>消費税率（%）</span>
              <input
                type="number"
                className="num"
                style={{ width: 90 }}
                step="0.1"
                min="0"
                value={est.taxRatePct}
                onChange={(e) => updateEstimate({ taxRatePct: numOr0(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>諸経費率（% 対直接工事費）</span>
              <input
                type="number"
                className="num"
                style={{ width: 110 }}
                step="0.1"
                min="0"
                value={est.overheadRatePct}
                onChange={(e) => updateEstimate({ overheadRatePct: numOr0(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>法定福利費率（% 対直接工事費・0で非計上）</span>
              <input
                type="number"
                className="num"
                style={{ width: 110 }}
                step="0.1"
                min="0"
                value={est.welfareRatePct}
                onChange={(e) => updateEstimate({ welfareRatePct: numOr0(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>端数処理（切捨て＝出精値引）</span>
              <select
                value={String(est.roundingUnitYen)}
                onChange={(e) => updateEstimate({ roundingUnitYen: Number(e.target.value) })}
              >
                {![1, 100, 1000, 10000].includes(est.roundingUnitYen) && (
                  <option value={String(est.roundingUnitYen)}>
                    {num(est.roundingUnitYen)}円単位
                  </option>
                )}
                <option value="1">調整しない</option>
                <option value="100">100円未満 切捨て</option>
                <option value="1000">1,000円未満 切捨て</option>
                <option value="10000">10,000円未満 切捨て</option>
              </select>
            </label>
          </div>
          <div className="form-row">
            <label className="field">
              <span>見積有効期限</span>
              <input
                type="text"
                style={{ width: 160 }}
                value={est.validity}
                onChange={(e) => updateEstimate({ validity: e.target.value })}
              />
            </label>
            <label className="field">
              <span>支払条件</span>
              <input
                type="text"
                style={{ width: 200 }}
                value={est.paymentTerms}
                onChange={(e) => updateEstimate({ paymentTerms: e.target.value })}
              />
            </label>
            <label className="field">
              <span>工期</span>
              <input
                type="text"
                style={{ width: 200 }}
                value={est.workPeriod}
                onChange={(e) => updateEstimate({ workPeriod: e.target.value })}
              />
            </label>
          </div>
          <label className="field" style={{ width: '100%' }}>
            <span>備考（見積書に記載）</span>
            <textarea
              rows={3}
              value={est.notes}
              placeholder="例: 電源工事は別途。既設撤去処分費を含む。"
              onChange={(e) => updateEstimate({ notes: e.target.value })}
            />
          </label>
          <datalist id="honorific-options">
            <option value="御中" />
            <option value="様" />
            <option value="殿" />
          </datalist>
        </div>

        <div className="page-header" style={{ marginBottom: 8 }}>
          <h1 style={{ fontSize: 15 }}>見積書プレビュー</h1>
          <div className="sub">
            「印刷 / PDF保存」でこのプレビューのみが印刷されます（ブラウザの印刷ダイアログで「PDFに保存」を選択できます）。
          </div>
        </div>
      </div>

      {/* ===== 見積書プレビュー（印刷対象） ===== */}
      <div className="print-target">
        {/* --- 表紙 --- */}
        <div className="sheet">
          <div style={{ textAlign: 'right', fontSize: 11 }}>見積日：{jpDate()}</div>
          <h1>御見積書</h1>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, marginBottom: 18 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  borderBottom: '1px solid #444',
                  padding: '2px 4px 4px',
                  marginBottom: 12,
                }}
              >
                {est.clientName || '（宛名未入力）'}　{est.honorific}
              </div>
              <div>下記のとおり御見積り申し上げます。</div>
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 11.5 }}>御見積金額（消費税込）</div>
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 700,
                    borderBottom: '3px double #444',
                    display: 'inline-block',
                    padding: '2px 28px 2px 4px',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {yen(computed.grandTotal)}−
                </div>
              </div>
              <table className="no-border" style={{ marginTop: 16, width: 'auto' }}>
                <tbody>
                  <tr>
                    <td style={{ whiteSpace: 'nowrap', paddingRight: 14 }}>件　　名</td>
                    <td>{est.title}</td>
                  </tr>
                  <tr>
                    <td style={{ whiteSpace: 'nowrap', paddingRight: 14 }}>現　　場</td>
                    <td>{project.siteName}</td>
                  </tr>
                  <tr>
                    <td style={{ whiteSpace: 'nowrap', paddingRight: 14 }}>工　　期</td>
                    <td>{est.workPeriod}</td>
                  </tr>
                  <tr>
                    <td style={{ whiteSpace: 'nowrap', paddingRight: 14 }}>有効期限</td>
                    <td>{est.validity}</td>
                  </tr>
                  <tr>
                    <td style={{ whiteSpace: 'nowrap', paddingRight: 14 }}>支払条件</td>
                    <td>{est.paymentTerms}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div style={{ width: '36%', flex: 'none', fontSize: 12, paddingTop: 6 }}>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>
                {est.companyName || '（自社名未入力）'}
              </div>
              <div>{est.companyAddress}</div>
              {est.companyTel !== '' && <div>TEL：{est.companyTel}</div>}
              {est.personInCharge !== '' && <div>担当：{est.personInCharge}</div>}
            </div>
          </div>

          <div style={{ fontWeight: 600, marginBottom: 4 }}>【内　訳】</div>
          <table className="est">
            <thead>
              <tr>
                <th>分類</th>
                <th style={{ width: '32%' }}>金額（円）</th>
              </tr>
            </thead>
            <tbody>
              {computed.sections.map((sec) => (
                <tr key={sec.category}>
                  <td>{sec.category}</td>
                  <td style={{ textAlign: 'right' }}>{num(sec.subtotal)}</td>
                </tr>
              ))}
              {lines.map((l) => (
                <tr key={l.label}>
                  <td style={{ textAlign: 'right', fontWeight: l.strong ? 700 : 400 }}>{l.label}</td>
                  <td style={{ textAlign: 'right', fontWeight: l.strong ? 700 : 400 }}>
                    {num(l.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {est.notes.trim() !== '' && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600 }}>備考</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{est.notes}</div>
            </div>
          )}
        </div>

        {/* --- 内訳明細 --- */}
        <div className="sheet" style={{ pageBreakBefore: 'always', marginTop: 14 }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 8 }}>
            内訳明細{mode === 'rough' ? '（概算）' : ''}
          </div>
          <table className="est">
            <thead>
              <tr>
                <th style={{ width: '13%' }}>分類</th>
                <th>名称</th>
                <th style={{ width: '15%' }}>規格</th>
                <th style={{ width: '8%' }}>数量</th>
                <th style={{ width: '6%' }}>単位</th>
                <th style={{ width: '11%' }}>単価（円）</th>
                <th style={{ width: '13%' }}>金額（円）</th>
              </tr>
            </thead>
            <tbody>
              {computed.sections.map((sec) => (
                <Fragment key={sec.category}>
                  {sec.items.map((q, i) => (
                    <tr key={q.id}>
                      <td>{i === 0 ? sec.category : ''}</td>
                      <td>{q.name}</td>
                      <td>{q.spec}</td>
                      <td style={{ textAlign: 'right' }}>{qty(q.quantity)}</td>
                      <td style={{ textAlign: 'center' }}>{q.unit}</td>
                      <td style={{ textAlign: 'right' }}>
                        {q.unitPriceYen === undefined || q.unitPriceYen === null
                          ? '—'
                          : num(q.unitPriceYen)}
                      </td>
                      <td style={{ textAlign: 'right' }}>{num(itemAmountYen(q))}</td>
                    </tr>
                  ))}
                  {sec.items.length > 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'right', fontWeight: 600, background: '#f7f7f7' }}>
                        【{sec.category}　小計】
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 600, background: '#f7f7f7' }}>
                        {num(sec.subtotal)}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {allItemsEmpty && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: '#888', padding: 16 }}>
                    明細がありません
                  </td>
                </tr>
              )}
              {lines.map((l) => (
                <tr key={l.label}>
                  <td colSpan={6} style={{ textAlign: 'right', fontWeight: l.strong ? 700 : 400 }}>
                    {l.label}
                  </td>
                  <td style={{ textAlign: 'right', fontWeight: l.strong ? 700 : 400 }}>
                    {num(l.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
