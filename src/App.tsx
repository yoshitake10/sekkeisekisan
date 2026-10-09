import { useState } from 'react'
import ProjectPage from './pages/ProjectPage'
import EquipmentSelectionPage from './pages/EquipmentSelectionPage'
import TakeoffPage from './pages/TakeoffPage'
import QuantityTablePage from './pages/QuantityTablePage'
import PriceMasterPage from './pages/PriceMasterPage'
import EstimatePage from './pages/EstimatePage'
import EquipmentDatabasePage from './pages/EquipmentDatabasePage'
import MasterSettingsPage from './pages/MasterSettingsPage'
import { useActiveProject, useStore } from './store'

type TabKey =
  | 'project'
  | 'selection'
  | 'takeoff'
  | 'quantity'
  | 'estimate'
  | 'prices'
  | 'daikin'
  | 'masters'

const TABS: { key: TabKey; label: string; section?: string }[] = [
  { key: 'project', label: 'プロジェクト', section: '案件' },
  { key: 'selection', label: '機器選定（負荷計算）' },
  { key: 'takeoff', label: '図面拾い（PDF / DXF）' },
  { key: 'quantity', label: '数量表' },
  { key: 'estimate', label: '見積書' },
  { key: 'prices', label: '単価マスタ', section: 'マスタ' },
  { key: 'daikin', label: 'ダイキン機器DB' },
  { key: 'masters', label: '原単位・概算単価' },
]

export default function App() {
  const [tab, setTab] = useState<TabKey>('project')
  const project = useActiveProject()
  const saveError = useStore((s) => s.saveError)

  return (
    <div className="app-shell">
      <nav className="sidebar no-print">
        <div className="app-title">
          空調換気設備
          <br />
          設計積算ツール
        </div>
        {TABS.map((t) => (
          <span key={t.key}>
            {t.section && <div className="nav-section">{t.section}</div>}
            <button
              className={'nav-item' + (tab === t.key ? ' active' : '')}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          </span>
        ))}
        <div className="nav-section" style={{ marginTop: 'auto', paddingBottom: 12 }}>
          案件: {project?.name}
        </div>
      </nav>
      <div className="main-area">
        {saveError && (
          <div
            className="no-print"
            style={{
              background: '#c62f2f',
              color: '#fff',
              padding: '8px 16px',
              fontWeight: 600,
            }}
          >
            ⚠ {saveError}
          </div>
        )}
        <main className="page">
          {tab === 'project' && <ProjectPage />}
          {tab === 'selection' && <EquipmentSelectionPage />}
          {tab === 'takeoff' && <TakeoffPage />}
          {tab === 'quantity' && <QuantityTablePage />}
          {tab === 'estimate' && <EstimatePage />}
          {tab === 'prices' && <PriceMasterPage />}
          {tab === 'daikin' && <EquipmentDatabasePage />}
          {tab === 'masters' && <MasterSettingsPage />}
        </main>
      </div>
    </div>
  )
}
