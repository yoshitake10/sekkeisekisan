import { useStore } from '../store'
import { DEFAULT_LOAD_UNITS, DEFAULT_ROUGH_COSTS } from '../data/loadUnits'
import { parseNumber } from '../utils/format'

/** 負荷原単位・概算単価マスタの編集ページ */
export default function MasterSettingsPage() {
  const loadUnits = useStore((s) => s.loadUnits)
  const roughCosts = useStore((s) => s.roughCosts)
  const { setLoadUnits, setRoughCosts } = useStore()

  function updLoad(i: number, key: string, v: string) {
    const rows = loadUnits.map((r, idx) =>
      idx === i
        ? {
            ...r,
            [key]:
              key === 'usage' || key === 'notes' ? v : parseNumber(v) || 0,
          }
        : r,
    )
    setLoadUnits(rows)
  }

  function updCost(i: number, key: string, v: string) {
    const rows = roughCosts.map((r, idx) =>
      idx === i
        ? { ...r, [key]: key === 'usage' || key === 'notes' ? v : parseNumber(v) || 0 }
        : r,
    )
    setRoughCosts(rows)
  }

  return (
    <div>
      <div className="page-header">
        <h1>原単位・概算単価マスタ</h1>
        <div className="sub">
          機器選定に使う負荷原単位と、概算見積に使う平米単価。自社の実績値に合わせて編集してください。
        </div>
      </div>

      <div className="note">
        初期値は一般的な設計目安です。物件条件（方位・窓面積・断熱・発熱機器等）により実負荷は変動します。受注判断に使う際は必ず社内基準で補正してください。
      </div>

      <div className="card">
        <h2>用途別 負荷原単位（機器選定用）</h2>
        <div className="toolbar">
          <button
            className="btn"
            onClick={() =>
              setLoadUnits([
                ...loadUnits,
                { usage: '新規用途', coolingWm2: 130, ventilationAch: 3, occupantDensityM2PerPerson: 8 },
              ])
            }
          >
            ＋ 行追加
          </button>
          <button
            className="btn"
            onClick={() => {
              if (confirm('負荷原単位を初期値に戻しますか？')) setLoadUnits(DEFAULT_LOAD_UNITS)
            }}
          >
            初期値に戻す
          </button>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>用途</th>
                <th>冷房負荷 W/m²</th>
                <th>換気回数 回/h</th>
                <th>人員密度 m²/人</th>
                <th>備考</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {loadUnits.map((r, i) => (
                <tr key={i}>
                  <td>
                    <input type="text" value={r.usage} onChange={(e) => updLoad(i, 'usage', e.target.value)} />
                  </td>
                  <td className="num">
                    <input type="number" className="num" value={r.coolingWm2} onChange={(e) => updLoad(i, 'coolingWm2', e.target.value)} />
                  </td>
                  <td className="num">
                    <input type="number" className="num" value={r.ventilationAch} onChange={(e) => updLoad(i, 'ventilationAch', e.target.value)} />
                  </td>
                  <td className="num">
                    <input type="number" className="num" value={r.occupantDensityM2PerPerson} onChange={(e) => updLoad(i, 'occupantDensityM2PerPerson', e.target.value)} />
                  </td>
                  <td>
                    <input type="text" value={r.notes ?? ''} onChange={(e) => updLoad(i, 'notes', e.target.value)} />
                  </td>
                  <td className="center">
                    <button className="btn small danger" onClick={() => setLoadUnits(loadUnits.filter((_, idx) => idx !== i))}>
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2>用途別 概算工事単価（概算見積用）</h2>
        <div className="toolbar">
          <button
            className="btn"
            onClick={() => setRoughCosts([...roughCosts, { usage: '新規用途', costYenPerM2: 20000 }])}
          >
            ＋ 行追加
          </button>
          <button
            className="btn"
            onClick={() => {
              if (confirm('概算単価を初期値に戻しますか？')) setRoughCosts(DEFAULT_ROUGH_COSTS)
            }}
          >
            初期値に戻す
          </button>
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>用途</th>
                <th>概算単価 円/m²（税抜）</th>
                <th>備考</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {roughCosts.map((r, i) => (
                <tr key={i}>
                  <td>
                    <input type="text" value={r.usage} onChange={(e) => updCost(i, 'usage', e.target.value)} />
                  </td>
                  <td className="num">
                    <input type="number" className="num" value={r.costYenPerM2} onChange={(e) => updCost(i, 'costYenPerM2', e.target.value)} />
                  </td>
                  <td>
                    <input type="text" value={r.notes ?? ''} onChange={(e) => updCost(i, 'notes', e.target.value)} />
                  </td>
                  <td className="center">
                    <button className="btn small danger" onClick={() => setRoughCosts(roughCosts.filter((_, idx) => idx !== i))}>
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
