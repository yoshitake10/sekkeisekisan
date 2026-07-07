import { useRef } from 'react'
import { useActiveProject, useStore } from '../store'
import type { Project } from '../types'
import { num, yen, jpDate } from '../utils/format'

export default function ProjectPage() {
  const project = useActiveProject()
  const projects = useStore((s) => s.projects)
  const loadUnits = useStore((s) => s.loadUnits)
  const { addProject, removeProject, setActiveProject, updateProject, importProjectJson } =
    useStore()
  const fileRef = useRef<HTMLInputElement>(null)

  const totalQty = project.quantityItems.length
  const roomArea = project.rooms.reduce((a, r) => a + (r.areaM2 || 0), 0)
  // 見積計算(logic/estimate.ts)と同じ「行ごと四捨五入」で合算する
  const qtyAmount = project.quantityItems.reduce(
    (a, q) => a + Math.round((q.unitPriceYen ?? 0) * (q.quantity || 0)),
    0,
  )

  function exportJson() {
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${project.name || 'project'}.sekisan.json`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function onImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    f.text().then((t) => {
      try {
        const p = JSON.parse(t) as Project
        if (!p || !Array.isArray(p.rooms)) throw new Error('形式が不正です')
        importProjectJson(p)
        alert('プロジェクトを取り込みました')
      } catch (err) {
        alert('読み込みに失敗しました: ' + (err as Error).message)
      }
    })
    e.target.value = ''
  }

  return (
    <div>
      <div className="page-header">
        <h1>プロジェクト</h1>
        <div className="sub">
          案件の作成・切替と基本情報の入力。データはこのブラウザに自動保存されます（重要案件はJSON書出しで控えを推奨）。
        </div>
      </div>

      <div className="card">
        <h2>案件一覧</h2>
        <div className="toolbar">
          <button
            className="btn primary"
            onClick={() => {
              const name = prompt('新規プロジェクト名', '新規プロジェクト')
              if (name !== null) addProject(name)
            }}
          >
            ＋ 新規作成
          </button>
          <button className="btn" onClick={exportJson}>
            現在の案件をJSON書出し
          </button>
          <button className="btn" onClick={() => fileRef.current?.click()}>
            JSON読込み
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={onImportFile}
          />
        </div>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>案件名</th>
                <th>得意先</th>
                <th>現場</th>
                <th>更新日</th>
                <th style={{ width: 140 }}></th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id} className={p.id === project.id ? 'selected' : ''}>
                  <td>{p.name}</td>
                  <td>{p.clientName}</td>
                  <td>{p.siteName}</td>
                  <td className="center">{jpDate(p.updatedAt)}</td>
                  <td className="center">
                    {p.id === project.id ? (
                      <span className="badge blue">編集中</span>
                    ) : (
                      <button className="btn small" onClick={() => setActiveProject(p.id)}>
                        開く
                      </button>
                    )}{' '}
                    <button
                      className="btn small danger"
                      onClick={() => {
                        if (confirm(`「${p.name}」を削除しますか？この操作は元に戻せません。`))
                          removeProject(p.id)
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
      </div>

      <div className="card">
        <h2>基本情報</h2>
        <div className="form-row">
          <label className="field">
            <span>案件名</span>
            <input
              type="text"
              style={{ width: 260 }}
              value={project.name}
              onChange={(e) => updateProject({ name: e.target.value })}
            />
          </label>
          <label className="field">
            <span>得意先</span>
            <input
              type="text"
              style={{ width: 220 }}
              value={project.clientName}
              onChange={(e) => updateProject({ clientName: e.target.value })}
            />
          </label>
          <label className="field">
            <span>現場名・住所</span>
            <input
              type="text"
              style={{ width: 280 }}
              value={project.siteName}
              onChange={(e) => updateProject({ siteName: e.target.value })}
            />
          </label>
        </div>
        <div className="form-row">
          <label className="field">
            <span>主用途（概算見積の初期値）</span>
            <select
              value={project.buildingUsage}
              onChange={(e) => updateProject({ buildingUsage: e.target.value })}
            >
              {loadUnits.map((u) => (
                <option key={u.usage} value={u.usage}>
                  {u.usage}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>延床面積 m²</span>
            <input
              type="number"
              className="num"
              style={{ width: 120 }}
              value={project.totalFloorAreaM2 || ''}
              onChange={(e) => updateProject({ totalFloorAreaM2: Number(e.target.value) })}
            />
          </label>
        </div>
        <label className="field" style={{ width: '100%' }}>
          <span>メモ</span>
          <textarea
            rows={3}
            value={project.memo}
            onChange={(e) => updateProject({ memo: e.target.value })}
          />
        </label>
      </div>

      <div className="kpi">
        <div className="kpi-item">
          <div className="v">{num(project.rooms.length)}</div>
          <div className="k">機器選定 部屋数</div>
        </div>
        <div className="kpi-item">
          <div className="v">{num(roomArea, 1)} m²</div>
          <div className="k">選定対象 床面積合計</div>
        </div>
        <div className="kpi-item">
          <div className="v">{num(project.measurements.length)}</div>
          <div className="k">図面拾い 測定数</div>
        </div>
        <div className="kpi-item">
          <div className="v">{num(totalQty)}</div>
          <div className="k">数量表 行数</div>
        </div>
        <div className="kpi-item">
          <div className="v">{yen(qtyAmount)}</div>
          <div className="k">数量表 金額（単価入力済分）</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h2>使い方の流れ</h2>
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.9 }}>
          <li>
            <b>概算だけ欲しい場合:</b> 「見積書」タブ → 概算モードで用途と面積を入れるだけで平米単価から概算見積が出ます。
          </li>
          <li>
            <b>機器選定:</b> 「機器選定」タブで部屋（用途・面積）を登録 → 負荷計算 → ダイキン機種が自動選定されます → 数量表へ転記。
          </li>
          <li>
            <b>図面から拾う:</b> 「図面拾い」タブでPDF・DXF平面図を開き、スケール設定 → 機器のカウント／ダクト・配管の長さ／部屋面積を拾って数量表へ転記。
          </li>
          <li>
            <b>数量表がある場合:</b> 「数量表」タブでExcel/CSVをそのまま取込み。
          </li>
          <li>
            <b>単価:</b> 「単価マスタ」にお手持ちの金額情報（Excel）を取込み → 数量表で単価引当 → 「見積書」タブの詳細モードで見積書が完成します。
          </li>
        </ol>
      </div>
    </div>
  )
}
