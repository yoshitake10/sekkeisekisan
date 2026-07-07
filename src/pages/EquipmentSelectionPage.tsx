import { useMemo } from 'react'
import { useActiveProject, useStore } from '../store'
import { calcRoom, roomsToQuantityItems, ventUnitCount } from '../logic/selection'
import { num, parseNumber } from '../utils/format'
import { INDOOR_UNIT_TYPE_LABELS } from '../types'
import type { DaikinModel, IndoorUnitType, Room } from '../types'

const INDOOR_TYPES = Object.keys(INDOOR_UNIT_TYPE_LABELS) as IndoorUnitType[]

/** 機器選定（負荷計算）ページ */
export default function EquipmentSelectionPage() {
  const project = useActiveProject()
  const loadUnits = useStore((s) => s.loadUnits)
  const models = useStore((s) => s.daikinModels)
  const addRoom = useStore((s) => s.addRoom)
  const updateRoom = useStore((s) => s.updateRoom)
  const removeRoom = useStore((s) => s.removeRoom)
  const addQuantityItems = useStore((s) => s.addQuantityItems)
  const removeQuantityBySource = useStore((s) => s.removeQuantityBySource)

  const rooms = project.rooms

  // 手動変更セレクト用: スカイエア一覧（形態→能力順）
  const skyairOptions = useMemo(() => {
    return models
      .filter((m) => m.category === 'skyair')
      .slice()
      .sort((a, b) => {
        const ta = a.indoorType ? INDOOR_TYPES.indexOf(a.indoorType) : 99
        const tb = b.indoorType ? INDOOR_TYPES.indexOf(b.indoorType) : 99
        if (ta !== tb) return ta - tb
        return (a.coolingKw ?? 0) - (b.coolingKw ?? 0)
      })
  }, [models])

  // 手動変更セレクト用: 全熱交換器一覧（風量順）
  const ervOptions = useMemo(() => {
    return models
      .filter((m) => m.category === 'ventilation-erv')
      .slice()
      .sort((a, b) => (a.airflowM3h ?? 0) - (b.airflowM3h ?? 0))
  }, [models])

  // 部屋ごとの計算結果
  const calcs = useMemo(
    () => rooms.map((r) => calcRoom(r, loadUnits, models)),
    [rooms, loadUnits, models],
  )

  /** 行ごとの実際に使う機種（手動選択があれば優先） */
  function effectiveModels(room: Room, i: number) {
    const calc = calcs[i]
    const acModel =
      models.find((m) => m.id === room.selectedModelId) ?? calc.recommendedModel
    const ventModel = room.useErv
      ? models.find((m) => m.id === room.selectedVentModelId) ?? calc.recommendedVentModel
      : undefined
    const ventCount =
      ventModel && calc.requiredVentilationM3h > 0
        ? ventUnitCount(calc.requiredVentilationM3h, ventModel)
        : 0
    return { calc, acModel, ventModel, ventCount }
  }

  // 合計KPI
  const totals = useMemo(() => {
    let area = 0
    let kw = 0
    let acUnits = 0
    let ventUnits = 0
    rooms.forEach((r, i) => {
      const calc = calcs[i]
      area += r.areaM2
      kw += calc.requiredCoolingKw
      if (calc.requiredCoolingKw > 0) acUnits += calc.unitCount
      if (r.useErv && calc.requiredVentilationM3h > 0) {
        const ventModel =
          models.find((m) => m.id === r.selectedVentModelId) ?? calc.recommendedVentModel
        if (ventModel) ventUnits += ventUnitCount(calc.requiredVentilationM3h, ventModel)
      }
    })
    return { area, kw, acUnits, ventUnits }
  }, [rooms, calcs, models])

  /** 数量表へ転記 */
  function transferToQuantity() {
    const items = roomsToQuantityItems(rooms, loadUnits, models)
    removeQuantityBySource('equipment')
    addQuantityItems(items)
    alert(
      `機器選定の結果 ${items.length} 件を数量表へ転記しました。\n` +
        '（数量表にあった機器選定由来の行は置き換えられています）',
    )
  }

  /** 数値入力の共通処理（空欄は undefined、数値化できなければ変更しない） */
  function numPatch(v: string): number | undefined {
    if (v.trim() === '') return undefined
    const n = parseNumber(v)
    return Number.isNaN(n) ? undefined : n
  }

  return (
    <div>
      <div className="page-header">
        <h1>機器選定（負荷計算）</h1>
        <div className="sub">
          部屋ごとに面積と用途を入力すると、冷房負荷と必要換気量からダイキン スカイエア・全熱交換器の推奨機種を選定します。
        </div>
      </div>

      <div className="note">
        必要冷房能力 = 面積 × 冷房負荷原単位(W/m²) × 余裕率。原単位は「原単位・概算単価」マスタの用途別の値を使用し、部屋ごとの上書きも可能です。
        必要換気量 = max(面積 × 天井高 × 換気回数, 人数 × 30m³/h・人)。人数が空欄の場合は用途別の人員密度から自動算定します。
        概算選定のため、方位・窓面積・断熱・発熱機器などの条件によっては詳細な熱負荷計算で確認してください。
      </div>

      <div className="kpi" style={{ marginBottom: 12 }}>
        <div className="kpi-item">
          <div className="v">{num(totals.area, 1)} m²</div>
          <div className="k">合計面積</div>
        </div>
        <div className="kpi-item">
          <div className="v">{num(totals.kw, 1)} kW</div>
          <div className="k">合計必要冷房能力</div>
        </div>
        <div className="kpi-item">
          <div className="v">{num(totals.acUnits)} 台</div>
          <div className="k">室内機台数</div>
        </div>
        <div className="kpi-item">
          <div className="v">{num(totals.ventUnits)} 台</div>
          <div className="k">換気（全熱交換器）台数</div>
        </div>
      </div>

      <div className="card">
        <h2>部屋一覧と選定結果</h2>
        <div className="toolbar">
          <button className="btn primary" onClick={() => addRoom({ name: `部屋${rooms.length + 1}` })}>
            ＋ 部屋を追加
          </button>
          <div className="spacer" />
          <button className="btn accent" onClick={transferToQuantity} disabled={rooms.length === 0}>
            数量表へ転記
          </button>
        </div>

        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ minWidth: 110 }}>部屋名</th>
                <th style={{ minWidth: 110 }}>用途</th>
                <th style={{ width: 75 }}>面積 m²</th>
                <th style={{ width: 65 }}>天井高 m</th>
                <th style={{ width: 65 }}>人数</th>
                <th style={{ width: 80 }}>原単位 W/m²</th>
                <th style={{ width: 65 }}>余裕率</th>
                <th style={{ minWidth: 140 }}>室内機形態</th>
                <th style={{ width: 60 }}>台数</th>
                <th style={{ minWidth: 110 }}>必要能力</th>
                <th style={{ minWidth: 230 }}>選定機種（空調）</th>
                <th style={{ width: 46 }}>換気</th>
                <th style={{ width: 90 }}>必要換気量</th>
                <th style={{ minWidth: 220 }}>選定機種（換気）</th>
                <th style={{ width: 52 }}></th>
              </tr>
            </thead>
            <tbody>
              {rooms.length === 0 && (
                <tr>
                  <td colSpan={15} className="center muted">
                    部屋がありません。「＋ 部屋を追加」から入力を開始してください。
                  </td>
                </tr>
              )}
              {rooms.map((r, i) => {
                const { calc, acModel, ventModel, ventCount } = effectiveModels(r, i)
                const lu = loadUnits.find((u) => u.usage === r.usage)
                const density = lu?.occupantDensityM2PerPerson ?? 10
                const autoOccupants = density > 0 ? Math.ceil(r.areaM2 / density) : 0
                const shortage =
                  acModel !== undefined &&
                  (acModel.coolingKw ?? 0) < calc.requiredKwPerUnit
                return (
                  <tr key={r.id}>
                    <td>
                      <input
                        type="text"
                        value={r.name}
                        placeholder="例: 事務室1"
                        onChange={(e) => updateRoom(r.id, { name: e.target.value })}
                      />
                    </td>
                    <td>
                      <select
                        value={r.usage}
                        onChange={(e) => updateRoom(r.id, { usage: e.target.value })}
                      >
                        {!loadUnits.some((u) => u.usage === r.usage) && (
                          <option value={r.usage}>{r.usage}</option>
                        )}
                        {loadUnits.map((u) => (
                          <option key={u.usage} value={u.usage}>
                            {u.usage}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        className="num"
                        min={0}
                        value={r.areaM2}
                        onChange={(e) =>
                          updateRoom(r.id, { areaM2: numPatch(e.target.value) ?? 0 })
                        }
                      />
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        className="num"
                        step={0.1}
                        min={0}
                        value={r.ceilingHeightM}
                        onChange={(e) =>
                          updateRoom(r.id, { ceilingHeightM: numPatch(e.target.value) ?? 0 })
                        }
                      />
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        className="num"
                        min={0}
                        value={r.occupants ?? ''}
                        placeholder={`自動${autoOccupants}`}
                        title="空欄の場合は用途別の人員密度から自動算定"
                        onChange={(e) =>
                          updateRoom(r.id, { occupants: numPatch(e.target.value) })
                        }
                      />
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        className="num"
                        min={0}
                        value={r.coolingWm2Override ?? ''}
                        placeholder={String(lu?.coolingWm2 ?? 130)}
                        title="空欄の場合は用途別マスタの原単位を使用"
                        onChange={(e) =>
                          updateRoom(r.id, { coolingWm2Override: numPatch(e.target.value) })
                        }
                      />
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        className="num"
                        step={0.05}
                        min={0}
                        value={r.safetyFactor}
                        onChange={(e) =>
                          updateRoom(r.id, { safetyFactor: numPatch(e.target.value) ?? 1 })
                        }
                      />
                    </td>
                    <td>
                      <select
                        value={r.preferredIndoorType}
                        onChange={(e) =>
                          updateRoom(r.id, {
                            preferredIndoorType: e.target.value as IndoorUnitType,
                            selectedModelId: undefined,
                          })
                        }
                      >
                        {INDOOR_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {INDOOR_UNIT_TYPE_LABELS[t]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        className="num"
                        min={0}
                        value={r.unitCount}
                        title="0 の場合は自動（1台あたり最大14kW目安で分割）"
                        onChange={(e) =>
                          updateRoom(r.id, { unitCount: numPatch(e.target.value) ?? 0 })
                        }
                      />
                    </td>
                    <td className="num">
                      <div>{num(calc.requiredCoolingKw, 1)} kW</div>
                      <div className="small muted">
                        {calc.unitCount}台 × {num(calc.requiredKwPerUnit, 1)}kW
                      </div>
                    </td>
                    <td>
                      {acModel ? (
                        <div>
                          {acModel.modelNo}（{acModel.hpClass ?? `${num(acModel.coolingKw ?? 0, 1)}kW`}）{' '}
                          {r.selectedModelId ? (
                            <span className="badge orange">手動</span>
                          ) : (
                            <span className="badge blue">推奨</span>
                          )}
                          {shortage && <span className="badge" style={{ background: '#fbdada', color: '#a02222' }}>能力不足</span>}
                        </div>
                      ) : (
                        <div className="danger-text">該当機種なし</div>
                      )}
                      <select
                        value={r.selectedModelId ?? ''}
                        onChange={(e) =>
                          updateRoom(r.id, { selectedModelId: e.target.value || undefined })
                        }
                      >
                        <option value="">
                          推奨機を使用{calc.recommendedModel ? `（${calc.recommendedModel.modelNo}）` : ''}
                        </option>
                        {skyairOptions.map((m: DaikinModel) => (
                          <option key={m.id} value={m.id}>
                            {m.modelNo} {m.hpClass}{' '}
                            {m.indoorType ? INDOOR_UNIT_TYPE_LABELS[m.indoorType] : ''}（
                            {num(m.coolingKw ?? 0, 1)}kW）
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="center">
                      <input
                        type="checkbox"
                        checked={r.useErv}
                        title="全熱交換器による換気を行う"
                        onChange={(e) => updateRoom(r.id, { useErv: e.target.checked })}
                      />
                    </td>
                    <td className="num">
                      {r.useErv ? `${num(calc.requiredVentilationM3h)} m³/h` : <span className="muted">—</span>}
                    </td>
                    <td>
                      {r.useErv ? (
                        <>
                          {ventModel ? (
                            <div>
                              {ventModel.modelNo} × {ventCount}台{' '}
                              {r.selectedVentModelId ? (
                                <span className="badge orange">手動</span>
                              ) : (
                                <span className="badge blue">推奨</span>
                              )}
                            </div>
                          ) : (
                            <div className="muted">—</div>
                          )}
                          <select
                            value={r.selectedVentModelId ?? ''}
                            onChange={(e) =>
                              updateRoom(r.id, {
                                selectedVentModelId: e.target.value || undefined,
                              })
                            }
                          >
                            <option value="">
                              推奨機を使用
                              {calc.recommendedVentModel ? `（${calc.recommendedVentModel.modelNo}）` : ''}
                            </option>
                            {ervOptions.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.modelNo}（{num(m.airflowM3h ?? 0)}m³/h）
                              </option>
                            ))}
                          </select>
                        </>
                      ) : (
                        <span className="muted">換気なし</span>
                      )}
                    </td>
                    <td className="center">
                      <button
                        className="btn small danger"
                        onClick={() => {
                          if (confirm(`部屋「${r.name || '(無名)'}」を削除しますか？`)) removeRoom(r.id)
                        }}
                      >
                        削除
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="small muted" style={{ marginTop: 8 }}>
          ・台数欄に 0 を入力すると自動分割（1台あたり最大14kW＝5馬力目安）。
          ・推奨機種は希望形態のスカイエアから能力を満たす最小機を選定し、該当がない場合は形態を問わず選定します。
          ・機器の定価は「ダイキン機器DB」の目安定価を数量表に初期設定します。
        </div>
      </div>
    </div>
  )
}
