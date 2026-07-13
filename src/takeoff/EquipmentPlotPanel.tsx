// ============================================================
// 機器プロットパネル（PDF / DXF ビューア共用サイドパネル）
//  - 機器選定の結果（部屋×機種×台数）を配置対象として一覧表示
//  - 対象を選んで図面をクリックすると1台ずつ配置される
//  - 計画台数と配置済み台数の照合（不足・超過の検知）
// ============================================================

import { useMemo } from 'react'
import { useActiveProject, useStore } from '../store'
import type { Measurement } from '../types'
import { num } from '../utils/format'
import { buildPlotTargets, plotMeasurements, plottedCountByKey } from './plot'

interface Props {
  drawingId: string
  /** 選択中の配置対象キー（`${roomId}|${plotKind}`） */
  activeKey: string | null
  /** 対象クリック時（ビューア側で plot ツールへの切替も行う） */
  onSelectTarget: (key: string) => void
}

export default function EquipmentPlotPanel({ drawingId, activeKey, onSelectTarget }: Props) {
  const project = useActiveProject()
  const loadUnits = useStore((s) => s.loadUnits)
  const models = useStore((s) => s.daikinModels)
  const removeMeasurement = useStore((s) => s.removeMeasurement)

  const targets = useMemo(
    () => buildPlotTargets(project, loadUnits, models),
    [project, loadUnits, models],
  )
  const plotted = useMemo(() => plottedCountByKey(project.measurements), [project.measurements])

  /** この図面上のプロット測定（対象キー別） */
  const plotsOnDrawing = useMemo(
    () => plotMeasurements(project.measurements).filter((m) => m.drawingId === drawingId),
    [project.measurements, drawingId],
  )

  /** 参照元の部屋が削除された等で対象リストに現れない孤立プロット */
  const orphans = useMemo(() => {
    const keys = new Set(targets.map((t) => t.key))
    return plotsOnDrawing.filter(
      (m) => !m.roomId || !m.plotKind || !keys.has(`${m.roomId}|${m.plotKind}`),
    )
  }, [plotsOnDrawing, targets])

  function clearTarget(key: string, label: string) {
    const ms = plotsOnDrawing.filter((m) => `${m.roomId}|${m.plotKind}` === key)
    if (ms.length === 0) return
    const n = ms.reduce((a, m) => a + m.points.length, 0)
    if (confirm(`「${label}」のこの図面上の配置 ${n}台 を削除しますか？`)) {
      for (const m of ms) removeMeasurement(m.id)
    }
  }

  function removeOrphan(m: Measurement) {
    if (confirm(`配置「${m.label}（${num(m.points.length)}台）」を削除しますか？`)) {
      removeMeasurement(m.id)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <h2>機器プロット（配置）</h2>
      {targets.length === 0 ? (
        <div className="muted small">
          配置できる機器がありません。先に「機器選定」タブで部屋（用途・面積）を登録すると、選定された機種がここに表示されます。
        </div>
      ) : (
        <>
          <div className="muted small" style={{ marginBottom: 6 }}>
            行を選んで図面をクリックすると1台ずつ配置されます（右クリックで1つ戻す）。
            配置は台数の照合と配置図が目的で、数量表へは機器選定からの転記が使われます（二重計上しません）。
          </div>
          <div className="tbl-wrap" style={{ maxHeight: 260, overflowY: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>部屋 / 機種</th>
                  <th className="num" style={{ width: 86 }}>配置/計画</th>
                  <th style={{ width: 46 }}></th>
                </tr>
              </thead>
              <tbody>
                {targets.map((t) => {
                  const done = plotted.get(t.key) ?? 0
                  const active = t.key === activeKey
                  const onThisDrawing = plotsOnDrawing.some(
                    (m) => `${m.roomId}|${m.plotKind}` === t.key,
                  )
                  return (
                    <tr
                      key={t.key}
                      className={active ? 'selected' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => onSelectTarget(t.key)}
                      title="クリックで配置対象に設定（機器プロットツールに切替）"
                    >
                      <td>
                        <span
                          style={{
                            display: 'inline-block',
                            width: 10,
                            height: 10,
                            background: t.color,
                            marginRight: 4,
                            border: '1px solid rgba(0,0,0,0.2)',
                          }}
                        />
                        {t.label}
                        {active && <span className="badge blue">配置中</span>}
                      </td>
                      <td className="num" style={{ whiteSpace: 'nowrap' }}>
                        {num(done)} / {num(t.planned)}
                        {done === t.planned ? (
                          <span className="badge green" title="計画台数どおり配置済み">✓</span>
                        ) : done > t.planned ? (
                          <span
                            className="badge"
                            style={{ background: '#fbdada', color: '#a02222' }}
                            title="計画台数を超えています"
                          >
                            過{num(done - t.planned)}
                          </span>
                        ) : done > 0 ? (
                          <span className="badge orange" title="計画台数に足りていません">
                            残{num(t.planned - done)}
                          </span>
                        ) : null}
                      </td>
                      <td className="center">
                        {onThisDrawing && (
                          <button
                            className="btn small danger"
                            title="この図面上のこの機器の配置をすべて削除"
                            onClick={(e) => {
                              e.stopPropagation()
                              clearTarget(t.key, t.label)
                            }}
                          >
                            ×
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="muted small" style={{ marginTop: 6 }}>
            配置/計画はプロジェクト全図面の合計です。機器選定で台数や機種を変えると計画側に即時反映されます。
          </div>
        </>
      )}

      {orphans.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="small danger-text" style={{ marginBottom: 4 }}>
            参照元の部屋が見つからない配置（部屋の削除等）:
          </div>
          {orphans.map((m) => (
            <div key={m.id} className="small" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  background: m.color,
                  border: '1px solid rgba(0,0,0,0.2)',
                }}
              />
              <span style={{ flex: 1 }}>
                {m.label}（{num(m.points.length)}台）
              </span>
              <button className="btn small danger" onClick={() => removeOrphan(m)}>
                削除
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
