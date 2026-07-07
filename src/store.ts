import { create } from 'zustand'
import type {
  DaikinModel,
  DrawingMeta,
  EstimateSettings,
  LoadUnit,
  Measurement,
  Project,
  QuantityItem,
  Room,
  RoughCostUnit,
  UnitPrice,
} from './types'
import { DEFAULT_LOAD_UNITS, DEFAULT_ROUGH_COSTS } from './data/loadUnits'
import { DEFAULT_DAIKIN_MODELS } from './data/daikinModels'
import { genId } from './utils/id'

// ============================================================
// 永続化（localStorage）
// ============================================================

const LS_KEY = 'sekkeisekisan_v1'

interface PersistShape {
  projects: Project[]
  activeProjectId: string
  daikinModels: DaikinModel[]
  loadUnits: LoadUnit[]
  roughCosts: RoughCostUnit[]
  unitPrices: UnitPrice[]
}

function defaultEstimate(): EstimateSettings {
  return {
    mode: 'rough',
    title: '空調換気設備工事 御見積書',
    clientName: '',
    honorific: '御中',
    companyName: '',
    companyAddress: '',
    companyTel: '',
    personInCharge: '',
    taxRatePct: 10,
    overheadRatePct: 12,
    welfareRatePct: 0,
    roundingUnitYen: 1000,
    validity: '提出後30日',
    paymentTerms: '従来通り',
    workPeriod: '別途打合せによる',
    notes: '',
    roughRows: [],
  }
}

export function createProject(name: string): Project {
  const now = new Date().toISOString()
  return {
    id: genId('prj'),
    name,
    clientName: '',
    siteName: '',
    buildingUsage: '事務所',
    totalFloorAreaM2: 0,
    createdAt: now,
    updatedAt: now,
    rooms: [],
    quantityItems: [],
    measurements: [],
    drawings: [],
    estimate: defaultEstimate(),
    memo: '',
  }
}

export function createRoom(): Room {
  return {
    id: genId('room'),
    name: '',
    usage: '事務所',
    areaM2: 0,
    ceilingHeightM: 2.6,
    safetyFactor: 1.05,
    preferredIndoorType: 'ceiling-cassette-4way',
    unitCount: 0,
    useErv: true,
  }
}

function loadPersisted(): PersistShape | null {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as PersistShape
    if (!data.projects || data.projects.length === 0) return null
    // 旧データに新フィールドを補完
    for (const p of data.projects) {
      p.estimate = { ...defaultEstimate(), ...p.estimate }
      p.rooms = (p.rooms ?? []).map((r) => ({ ...createRoom(), ...r }))
      p.quantityItems = p.quantityItems ?? []
      p.measurements = p.measurements ?? []
      p.drawings = p.drawings ?? []
    }
    return data
  } catch {
    return null
  }
}

let saveTimer: ReturnType<typeof setTimeout> | undefined

function persist(state: AppState) {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    const shape: PersistShape = {
      projects: state.projects,
      activeProjectId: state.activeProjectId,
      daikinModels: state.daikinModels,
      loadUnits: state.loadUnits,
      roughCosts: state.roughCosts,
      unitPrices: state.unitPrices,
    }
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(shape))
    } catch (e) {
      console.error('保存に失敗しました', e)
    }
  }, 400)
}

// ============================================================
// ストア
// ============================================================

export interface AppState {
  projects: Project[]
  activeProjectId: string
  daikinModels: DaikinModel[]
  loadUnits: LoadUnit[]
  roughCosts: RoughCostUnit[]
  unitPrices: UnitPrice[]

  // --- プロジェクト ---
  addProject: (name: string) => void
  removeProject: (id: string) => void
  setActiveProject: (id: string) => void
  /** アクティブプロジェクトの部分更新（updatedAt 自動更新） */
  updateProject: (patch: Partial<Project>) => void
  importProjectJson: (p: Project) => void

  // --- 部屋（機器選定） ---
  addRoom: (room?: Partial<Room>) => void
  updateRoom: (id: string, patch: Partial<Room>) => void
  removeRoom: (id: string) => void

  // --- 数量表 ---
  addQuantityItems: (items: QuantityItem[]) => void
  updateQuantityItem: (id: string, patch: Partial<QuantityItem>) => void
  removeQuantityItem: (id: string) => void
  removeQuantityBySource: (source: QuantityItem['source']) => void

  // --- 図面拾い ---
  upsertDrawing: (d: DrawingMeta) => void
  removeDrawing: (id: string) => void
  addMeasurement: (m: Measurement) => void
  updateMeasurement: (id: string, patch: Partial<Measurement>) => void
  removeMeasurement: (id: string) => void

  // --- 見積 ---
  updateEstimate: (patch: Partial<EstimateSettings>) => void

  // --- マスタ ---
  setUnitPrices: (rows: UnitPrice[]) => void
  upsertUnitPrice: (row: UnitPrice) => void
  removeUnitPrice: (id: string) => void
  upsertDaikinModel: (m: DaikinModel) => void
  removeDaikinModel: (id: string) => void
  resetDaikinModels: () => void
  setLoadUnits: (rows: LoadUnit[]) => void
  setRoughCosts: (rows: RoughCostUnit[]) => void
}

/** アクティブプロジェクトを取得するセレクタ */
export function activeProject(s: Pick<AppState, 'projects' | 'activeProjectId'>): Project {
  return s.projects.find((p) => p.id === s.activeProjectId) ?? s.projects[0]
}

const initial: PersistShape = loadPersisted() ?? {
  projects: [createProject('新規プロジェクト')],
  activeProjectId: '',
  daikinModels: DEFAULT_DAIKIN_MODELS,
  loadUnits: DEFAULT_LOAD_UNITS,
  roughCosts: DEFAULT_ROUGH_COSTS,
  unitPrices: [],
}
if (!initial.projects.find((p) => p.id === initial.activeProjectId)) {
  initial.activeProjectId = initial.projects[0].id
}

export const useStore = create<AppState>((set, get) => {
  /** アクティブプロジェクトへ patch を適用して保存 */
  function patchActive(fn: (p: Project) => Partial<Project>) {
    set((s) => {
      const projects = s.projects.map((p) =>
        p.id === s.activeProjectId
          ? { ...p, ...fn(p), updatedAt: new Date().toISOString() }
          : p,
      )
      return { projects }
    })
    persist(get())
  }

  function setAndPersist(partial: Partial<AppState>) {
    set(partial as AppState)
    persist(get())
  }

  return {
    ...initial,

    addProject: (name) => {
      const p = createProject(name || '新規プロジェクト')
      setAndPersist({ projects: [...get().projects, p], activeProjectId: p.id })
    },
    removeProject: (id) => {
      let projects = get().projects.filter((p) => p.id !== id)
      if (projects.length === 0) projects = [createProject('新規プロジェクト')]
      const activeProjectId =
        get().activeProjectId === id ? projects[0].id : get().activeProjectId
      setAndPersist({ projects, activeProjectId })
    },
    setActiveProject: (id) => setAndPersist({ activeProjectId: id }),
    updateProject: (patch) => patchActive(() => patch),
    importProjectJson: (p) => {
      const imported: Project = { ...createProject(p.name || 'インポート'), ...p, id: genId('prj') }
      setAndPersist({ projects: [...get().projects, imported], activeProjectId: imported.id })
    },

    addRoom: (room) =>
      patchActive((p) => ({ rooms: [...p.rooms, { ...createRoom(), ...room }] })),
    updateRoom: (id, patch) =>
      patchActive((p) => ({
        rooms: p.rooms.map((r) => (r.id === id ? { ...r, ...patch } : r)),
      })),
    removeRoom: (id) =>
      patchActive((p) => ({ rooms: p.rooms.filter((r) => r.id !== id) })),

    addQuantityItems: (items) =>
      patchActive((p) => ({ quantityItems: [...p.quantityItems, ...items] })),
    updateQuantityItem: (id, patch) =>
      patchActive((p) => ({
        quantityItems: p.quantityItems.map((q) => (q.id === id ? { ...q, ...patch } : q)),
      })),
    removeQuantityItem: (id) =>
      patchActive((p) => ({ quantityItems: p.quantityItems.filter((q) => q.id !== id) })),
    removeQuantityBySource: (source) =>
      patchActive((p) => ({
        quantityItems: p.quantityItems.filter((q) => q.source !== source),
      })),

    upsertDrawing: (d) =>
      patchActive((p) => ({
        drawings: p.drawings.some((x) => x.id === d.id)
          ? p.drawings.map((x) => (x.id === d.id ? { ...x, ...d } : x))
          : [...p.drawings, d],
      })),
    removeDrawing: (id) =>
      patchActive((p) => ({
        drawings: p.drawings.filter((d) => d.id !== id),
        measurements: p.measurements.filter((m) => m.drawingId !== id),
      })),
    addMeasurement: (m) =>
      patchActive((p) => ({ measurements: [...p.measurements, m] })),
    updateMeasurement: (id, patch) =>
      patchActive((p) => ({
        measurements: p.measurements.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      })),
    removeMeasurement: (id) =>
      patchActive((p) => ({
        measurements: p.measurements.filter((m) => m.id !== id),
      })),

    updateEstimate: (patch) =>
      patchActive((p) => ({ estimate: { ...p.estimate, ...patch } })),

    setUnitPrices: (rows) => setAndPersist({ unitPrices: rows }),
    upsertUnitPrice: (row) => {
      const list = get().unitPrices
      setAndPersist({
        unitPrices: list.some((r) => r.id === row.id)
          ? list.map((r) => (r.id === row.id ? row : r))
          : [...list, row],
      })
    },
    removeUnitPrice: (id) =>
      setAndPersist({ unitPrices: get().unitPrices.filter((r) => r.id !== id) }),

    upsertDaikinModel: (m) => {
      const list = get().daikinModels
      setAndPersist({
        daikinModels: list.some((x) => x.id === m.id)
          ? list.map((x) => (x.id === m.id ? m : x))
          : [...list, m],
      })
    },
    removeDaikinModel: (id) =>
      setAndPersist({ daikinModels: get().daikinModels.filter((m) => m.id !== id) }),
    resetDaikinModels: () => setAndPersist({ daikinModels: DEFAULT_DAIKIN_MODELS }),

    setLoadUnits: (rows) => setAndPersist({ loadUnits: rows }),
    setRoughCosts: (rows) => setAndPersist({ roughCosts: rows }),
  }
})

/** アクティブプロジェクトを返すフック */
export function useActiveProject(): Project {
  return useStore((s) => s.projects.find((p) => p.id === s.activeProjectId) ?? s.projects[0])
}
