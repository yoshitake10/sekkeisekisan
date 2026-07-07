// ============================================================
// DXF(CAD図面) 拾いビューア
//  - dxf-parser でモデル空間を描画し、個数/長さ/面積を拾う
//  - Measurement.points は DXF モデル空間座標で保存する
// ============================================================

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useActiveProject, useStore } from '../store'
import type { DrawingMeta, MeasureKind, Measurement, TakeoffPoint } from '../types'
import { TAKEOFF_PRESETS, TOOL_LABELS, type TakeoffTool, type TakeoffViewProps } from './contract'
import { colorForIndex, dist, measurementValue } from './geometry'
import { drawScene, parseDxf, type DxfScene } from './dxfRender'
import { genId } from '../utils/id'
import { num, parseNumber } from '../utils/format'
import MeasurementPanel from './MeasurementPanel'

// ---------- 定数 ----------

const SNAP_PX = 10 // スナップ判定距離（画面ピクセル）
const CLICK_MOVE_PX = 4 // これ以上動いたらクリック扱いしない
const MIN_SCALE = 1e-9
const MAX_SCALE = 1e9

const TOOLS: TakeoffTool[] = ['pan', 'scale', 'count', 'length', 'area']

const HINTS: Record<TakeoffTool, string> = {
  pan: 'ドラッグ: 画面移動 ／ ホイール: 拡大縮小 ／ クリック: 測定を選択',
  scale: '基準となる2点をクリック → 実寸距離[m]を入力（図面単位が不明・怪しい場合の補正用） ／ Esc: 中止',
  count: 'クリックで1点ずつ追加 → ダブルクリック か「確定」で保存（ダブルクリック位置は数えない） ／ Esc: 取消（ホイール: 拡大縮小）',
  length: 'クリックで頂点を追加（線分端点に自動スナップ）→ ダブルクリックで確定 ／ Esc: 取消',
  area: 'クリックで多角形の頂点を追加 → ダブルクリックで確定 ／ Esc: 取消',
}

interface ViewState {
  scale: number
  offsetX: number
  offsetY: number
}

/** ツール→測定種別 */
function kindOf(tool: TakeoffTool): MeasureKind | null {
  return tool === 'count' || tool === 'length' || tool === 'area' ? tool : null
}

/** 最小必要点数 */
function minPoints(kind: MeasureKind): number {
  return kind === 'count' ? 1 : kind === 'length' ? 2 : 3
}

// ---------- スナップ用の簡易空間インデックス ----------

interface SnapIndex {
  cell: number
  map: Map<string, TakeoffPoint[]>
}

function buildSnapIndex(scene: DxfScene): SnapIndex {
  const pts: TakeoffPoint[] = []
  for (const p of scene.entities) {
    if (p.type === 'polyline') {
      for (const q of p.points) pts.push(q)
    } else if (p.type === 'arc') {
      pts.push({ x: p.cx + p.r * Math.cos(p.startAngle), y: p.cy + p.r * Math.sin(p.startAngle) })
      pts.push({ x: p.cx + p.r * Math.cos(p.endAngle), y: p.cy + p.r * Math.sin(p.endAngle) })
    } else if (p.type === 'circle') {
      pts.push({ x: p.cx, y: p.cy })
    }
  }
  const w = Math.max(scene.bounds.maxX - scene.bounds.minX, 1e-9)
  const h = Math.max(scene.bounds.maxY - scene.bounds.minY, 1e-9)
  const cell = Math.max(w, h) / 256
  const map = new Map<string, TakeoffPoint[]>()
  for (const p of pts) {
    const key = `${Math.floor(p.x / cell)},${Math.floor(p.y / cell)}`
    const arr = map.get(key)
    if (arr) arr.push(p)
    else map.set(key, [p])
  }
  return { cell, map }
}

function findSnap(idx: SnapIndex, p: TakeoffPoint, radius: number): TakeoffPoint | null {
  const range = Math.min(3, Math.max(1, Math.ceil(radius / idx.cell)))
  const cx = Math.floor(p.x / idx.cell)
  const cy = Math.floor(p.y / idx.cell)
  let best: TakeoffPoint | null = null
  let bestD = radius
  for (let ix = cx - range; ix <= cx + range; ix++) {
    for (let iy = cy - range; iy <= cy + range; iy++) {
      const arr = idx.map.get(`${ix},${iy}`)
      if (!arr) continue
      for (const q of arr) {
        const d = Math.hypot(q.x - p.x, q.y - p.y)
        if (d < bestD) {
          bestD = d
          best = q
        }
      }
    }
  }
  return best
}

// ---------- 本体 ----------

export default function DxfTakeoff({ file, drawingId }: TakeoffViewProps) {
  const project = useActiveProject()
  const upsertDrawing = useStore((s) => s.upsertDrawing)
  const addMeasurement = useStore((s) => s.addMeasurement)
  const updateMeasurement = useStore((s) => s.updateMeasurement)

  const meta = project.drawings.find((d) => d.id === drawingId)
  const measurements = useMemo(
    () => project.measurements.filter((m) => m.drawingId === drawingId),
    [project.measurements, drawingId],
  )

  // --- 状態 ---
  const [scene, setScene] = useState<DxfScene | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<ViewState>({ scale: 1, offsetX: 0, offsetY: 0 })
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [tool, setTool] = useState<TakeoffTool>('pan')
  const [pending, setPending] = useState<TakeoffPoint[]>([])
  const [hover, setHover] = useState<{ p: TakeoffPoint; snapped: boolean } | null>(null)
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)
  const [target, setTarget] = useState({ label: '室内機', category: '機器', unitName: '台' })
  const [scaleDraft, setScaleDraft] = useState<{ points: TakeoffPoint[]; input: string } | null>(null)
  const [dragging, setDragging] = useState(false)

  const wrapRef = useRef<HTMLDivElement>(null)
  const baseRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const fittedRef = useRef(false)
  const dragRef = useRef<{ sx: number; sy: number; view0: ViewState } | null>(null)
  const downRef = useRef<{ sx: number; sy: number; moved: boolean } | null>(null)

  const kind = kindOf(tool)
  const scaleMPerUnit = meta?.scaleMPerUnit

  // --- ファイル読込・パース ---
  useEffect(() => {
    let cancelled = false
    setScene(null)
    setParseError(null)
    setLoading(true)
    fittedRef.current = false
    setPending([])
    setScaleDraft(null)
    file
      .text()
      .then((text) => {
        if (cancelled) return
        try {
          setScene(parseDxf(text))
        } catch (e) {
          setParseError(e instanceof Error ? e.message : String(e))
        }
        setLoading(false)
      })
      .catch((e) => {
        if (cancelled) return
        setParseError(`ファイルを読み込めませんでした: ${String(e)}`)
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [file])

  // --- DrawingMeta の初期化（DXF既定は mm = 0.001 m/単位） ---
  useEffect(() => {
    if (!meta) {
      upsertDrawing({ id: drawingId, kind: 'dxf', fileName: file.name, scaleMPerUnit: 0.001, pageIndex: 0 })
    } else if (meta.scaleMPerUnit === undefined) {
      upsertDrawing({ ...meta, scaleMPerUnit: 0.001 })
    }
  }, [meta, drawingId, file, upsertDrawing])

  // --- キャンバスサイズ追従 ---
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // --- 座標変換 ---
  const toScreen = useCallback(
    (p: TakeoffPoint) => ({ x: p.x * view.scale + view.offsetX, y: view.offsetY - p.y * view.scale }),
    [view],
  )
  const toModel = useCallback(
    (sx: number, sy: number): TakeoffPoint => ({
      x: (sx - view.offsetX) / view.scale,
      y: (view.offsetY - sy) / view.scale,
    }),
    [view],
  )

  // --- 全体表示 ---
  const fitView = useCallback(() => {
    if (!scene || size.w <= 0 || size.h <= 0) return
    const bw = Math.max(scene.bounds.maxX - scene.bounds.minX, 1e-9)
    const bh = Math.max(scene.bounds.maxY - scene.bounds.minY, 1e-9)
    const scale = Math.min(size.w / bw, size.h / bh) * 0.92
    const cx = (scene.bounds.minX + scene.bounds.maxX) / 2
    const cy = (scene.bounds.minY + scene.bounds.maxY) / 2
    setView({ scale, offsetX: size.w / 2 - cx * scale, offsetY: size.h / 2 + cy * scale })
  }, [scene, size])

  useEffect(() => {
    if (scene && size.w > 0 && !fittedRef.current) {
      fitView()
      fittedRef.current = true
    }
  }, [scene, size, fitView])

  // --- ズーム（ホイール。passive:false が必要なため native で登録） ---
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const sx = e.clientX - rect.left
      const sy = e.clientY - rect.top
      const factor = e.deltaY < 0 ? 1.25 : 0.8
      setView((v) => {
        const ns = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor))
        const mx = (sx - v.offsetX) / v.scale
        const my = (v.offsetY - sy) / v.scale
        return { scale: ns, offsetX: sx - mx * ns, offsetY: sy + my * ns }
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const zoomCenter = useCallback(
    (factor: number) => {
      const sx = size.w / 2
      const sy = size.h / 2
      setView((v) => {
        const ns = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor))
        const mx = (sx - v.offsetX) / v.scale
        const my = (v.offsetY - sy) / v.scale
        return { scale: ns, offsetX: sx - mx * ns, offsetY: sy + my * ns }
      })
    },
    [size],
  )

  // --- スナップインデックス ---
  const snapIndex = useMemo(() => (scene ? buildSnapIndex(scene) : null), [scene])

  const snapModelPoint = useCallback(
    (p: TakeoffPoint): { p: TakeoffPoint; snapped: boolean } => {
      if (!snapIndex || (tool !== 'length' && tool !== 'scale')) return { p, snapped: false }
      const hit = findSnap(snapIndex, p, SNAP_PX / view.scale)
      return hit ? { p: hit, snapped: true } : { p, snapped: false }
    },
    [snapIndex, tool, view.scale],
  )

  // --- 測定色（同ラベルは同色） ---
  const colorFor = useCallback(
    (label: string): string => {
      const ex = measurements.find((m) => m.label === label)
      if (ex) return ex.color
      const labels = new Set(measurements.map((m) => m.label))
      return colorForIndex(labels.size)
    },
    [measurements],
  )

  // --- 測定の確定 ---
  const commitPending = useCallback(
    (pointsArg?: TakeoffPoint[]) => {
      const k = kindOf(tool)
      if (!k) return
      const pts = pointsArg ?? pending
      if (pts.length < minPoints(k)) return
      const label = target.label.trim() || TOOL_LABELS[tool]
      const m: Measurement = {
        id: genId('ms'),
        drawingId,
        pageIndex: 0,
        kind: k,
        label,
        category: target.category.trim() || 'その他',
        unitName: target.unitName.trim() || (k === 'count' ? '個' : k === 'length' ? 'm' : 'm2'),
        points: pts,
        value: measurementValue(k, pts, scaleMPerUnit),
        color: colorFor(label),
      }
      addMeasurement(m)
      setSelectedId(m.id)
      setPending([])
    },
    [tool, pending, target, drawingId, scaleMPerUnit, colorFor, addMeasurement],
  )
  const commitRef = useRef(commitPending)
  commitRef.current = commitPending

  // --- Esc / Enter ---
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPending([])
        setScaleDraft(null)
      } else if (e.key === 'Enter') {
        const t = e.target as HTMLElement | null
        if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA')) return
        commitRef.current()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // --- ツール切替時: 拾い対象プリセットを追従・作業中の点をクリア ---
  const prevKindRef = useRef<MeasureKind | null>(null)
  useEffect(() => {
    const k = kindOf(tool)
    if (k && k !== prevKindRef.current) {
      const preset = TAKEOFF_PRESETS.find((p) => p.kind === k)
      if (preset) setTarget({ label: preset.label, category: preset.category, unitName: preset.unitName })
    }
    prevKindRef.current = k
    setPending([])
    if (tool !== 'scale') setScaleDraft(null)
  }, [tool])

  // --- スケール変更時に既存の長さ/面積測定を再計算（手修正済みの数量は上書きしない） ---
  const rescaleMeasurements = useCallback(
    (newScale: number) => {
      for (const m of measurements) {
        if (m.kind === 'count' || m.points.length === 0 || m.valueOverridden) continue
        updateMeasurement(m.id, { value: measurementValue(m.kind, m.points, newScale) })
      }
    },
    [measurements, updateMeasurement],
  )

  const baseMeta: DrawingMeta = meta ?? {
    id: drawingId,
    kind: 'dxf',
    fileName: file.name,
    pageIndex: 0,
  }

  function setUnit(u: 'mm' | 'cm' | 'm') {
    const s = u === 'mm' ? 0.001 : u === 'cm' ? 0.01 : 1
    upsertDrawing({ ...baseMeta, scaleMPerUnit: s })
    rescaleMeasurements(s)
  }

  const unitValue =
    scaleMPerUnit === 0.001 ? 'mm' : scaleMPerUnit === 0.01 ? 'cm' : scaleMPerUnit === 1 ? 'm' : 'custom'

  // --- 2点実測スケール補正 ---
  function applyScaleDraft() {
    if (!scaleDraft || scaleDraft.points.length < 2) return
    const dModel = dist(scaleDraft.points[0], scaleDraft.points[1])
    const realM = parseNumber(scaleDraft.input)
    if (!Number.isFinite(realM) || realM <= 0 || dModel <= 0) {
      alert('実寸距離は 0 より大きい数値[m]で入力してください。')
      return
    }
    const s = realM / dModel
    upsertDrawing({ ...baseMeta, scaleMPerUnit: s })
    rescaleMeasurements(s)
    setScaleDraft(null)
    setTool('pan')
  }

  // --- ブロック集計 → count 測定として追加 ---
  function addBlockAsCount(name: string) {
    if (!scene) return
    const count = scene.insertCounts[name] ?? 0
    if (count <= 0) return
    const pts = scene.insertPoints[name] ?? []
    const m: Measurement = {
      id: genId('ms'),
      drawingId,
      pageIndex: 0,
      kind: 'count',
      label: name,
      category: '機器',
      unitName: '個',
      points: pts,
      value: count,
      color: colorFor(name),
      spec: 'ブロック集計',
    }
    addMeasurement(m)
    setSelectedId(m.id)
  }

  // --- ポインタ操作 ---
  function eventPos(e: React.PointerEvent | React.MouseEvent): { sx: number; sy: number } {
    const rect = wrapRef.current!.getBoundingClientRect()
    return { sx: e.clientX - rect.left, sy: e.clientY - rect.top }
  }

  function onPointerDown(e: React.PointerEvent) {
    if (!wrapRef.current) return
    const { sx, sy } = eventPos(e)
    downRef.current = { sx, sy, moved: false }
    const panDrag = e.button === 1 || (e.button === 0 && tool === 'pan')
    if (panDrag) {
      dragRef.current = { sx, sy, view0: view }
      setDragging(true)
      wrapRef.current.setPointerCapture(e.pointerId)
    }
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!wrapRef.current) return
    const { sx, sy } = eventPos(e)
    const down = downRef.current
    if (down && Math.hypot(sx - down.sx, sy - down.sy) > CLICK_MOVE_PX) down.moved = true
    const drag = dragRef.current
    if (drag) {
      setView({
        scale: drag.view0.scale,
        offsetX: drag.view0.offsetX + (sx - drag.sx),
        offsetY: drag.view0.offsetY + (sy - drag.sy),
      })
      return
    }
    if (tool !== 'pan') setHover(snapModelPoint(toModel(sx, sy)))
  }

  function onPointerUp(e: React.PointerEvent) {
    if (dragRef.current && wrapRef.current) {
      wrapRef.current.releasePointerCapture(e.pointerId)
    }
    dragRef.current = null
    setDragging(false)
  }

  function onClick(e: React.MouseEvent) {
    if (downRef.current?.moved) return
    if (e.detail > 1) return // ダブルクリックの2回目の click は無視（点の重複追加を防ぐ）
    if (!wrapRef.current || !scene) return
    const { sx, sy } = eventPos(e)
    if (tool === 'pan') {
      setSelectedId(hitTest(sx, sy))
      return
    }
    if (tool === 'scale') {
      const { p } = snapModelPoint(toModel(sx, sy))
      setScaleDraft((cur) =>
        !cur || cur.points.length >= 2 ? { points: [p], input: '' } : { points: [...cur.points, p], input: '' },
      )
      return
    }
    const { p } = snapModelPoint(toModel(sx, sy))
    setPending((prev) => [...prev, p])
  }

  function onDoubleClick() {
    if (downRef.current?.moved) return
    if (!kind || !scene) return
    // click 側で e.detail > 1 を無視しているため、ダブルクリック位置は pending に1点だけ入っている
    if (kind === 'count') {
      // 個数カウントのダブルクリックは確定操作。ダブルクリック位置（末尾1点）は個数に含めない
      const pts = pending.slice(0, -1)
      if (pts.length === 0) {
        setPending([])
        return
      }
      commitPending(pts)
    } else {
      // length / area はダブルクリック位置を最終頂点として確定
      commitPending()
    }
  }

  /** pan ツールのクリックで測定を選択（頂点近傍 10px） */
  function hitTest(sx: number, sy: number): string | undefined {
    let bestId: string | undefined
    let bestD = 10
    for (const m of measurements) {
      for (const p of m.points) {
        const s = toScreen(p)
        const d = Math.hypot(s.x - sx, s.y - sy)
        if (d < bestD) {
          bestD = d
          bestId = m.id
        }
      }
    }
    return bestId
  }

  // --- ベース描画（図面） ---
  useEffect(() => {
    const canvas = baseRef.current
    if (!canvas || size.w <= 0 || size.h <= 0) return
    const dpr = window.devicePixelRatio || 1
    const bw = Math.round(size.w * dpr)
    const bh = Math.round(size.h * dpr)
    if (canvas.width !== bw) canvas.width = bw
    if (canvas.height !== bh) canvas.height = bh
    canvas.style.width = `${size.w}px`
    canvas.style.height = `${size.h}px`
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)
    if (!scene) return
    // 図面範囲を「用紙」風に白背景で描画
    const x0 = scene.bounds.minX * view.scale + view.offsetX
    const y0 = view.offsetY - scene.bounds.maxY * view.scale
    const w = (scene.bounds.maxX - scene.bounds.minX) * view.scale
    const h = (scene.bounds.maxY - scene.bounds.minY) * view.scale
    const pad = 12
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(x0 - pad, y0 - pad, w + pad * 2, h + pad * 2)
    drawScene(ctx, scene, view)
  }, [scene, view, size])

  // --- オーバーレイ描画（測定・作業中・スナップ） ---
  useEffect(() => {
    const canvas = overlayRef.current
    if (!canvas || size.w <= 0 || size.h <= 0) return
    const dpr = window.devicePixelRatio || 1
    const bw = Math.round(size.w * dpr)
    const bh = Math.round(size.h * dpr)
    if (canvas.width !== bw) canvas.width = bw
    if (canvas.height !== bh) canvas.height = bh
    canvas.style.width = `${size.w}px`
    canvas.style.height = `${size.h}px`
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)

    const S = (p: TakeoffPoint) => ({ x: p.x * view.scale + view.offsetX, y: view.offsetY - p.y * view.scale })

    function label(text: string, x: number, y: number, color: string) {
      if (!ctx) return
      ctx.font = 'bold 11px sans-serif'
      ctx.textBaseline = 'bottom'
      ctx.lineWidth = 3
      ctx.strokeStyle = 'rgba(255,255,255,0.9)'
      ctx.strokeText(text, x + 6, y - 4)
      ctx.fillStyle = color
      ctx.fillText(text, x + 6, y - 4)
    }

    function drawCountMarkers(pts: TakeoffPoint[], color: string, selected: boolean) {
      if (!ctx) return
      for (const p of pts) {
        const s = S(p)
        ctx.beginPath()
        ctx.arc(s.x, s.y, selected ? 9 : 7, 0, Math.PI * 2)
        ctx.fillStyle = color + '55'
        ctx.fill()
        ctx.lineWidth = selected ? 2.5 : 1.5
        ctx.strokeStyle = color
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(s.x - 3, s.y)
        ctx.lineTo(s.x + 3, s.y)
        ctx.moveTo(s.x, s.y - 3)
        ctx.lineTo(s.x, s.y + 3)
        ctx.lineWidth = 1.2
        ctx.stroke()
      }
    }

    function drawPath(pts: TakeoffPoint[], color: string, selected: boolean, close: boolean, fill: boolean) {
      if (!ctx || pts.length === 0) return
      ctx.beginPath()
      const s0 = S(pts[0])
      ctx.moveTo(s0.x, s0.y)
      for (let i = 1; i < pts.length; i++) {
        const s = S(pts[i])
        ctx.lineTo(s.x, s.y)
      }
      if (close) ctx.closePath()
      if (fill) {
        ctx.fillStyle = color + '2e'
        ctx.fill()
      }
      if (selected) {
        ctx.lineWidth = 6
        ctx.strokeStyle = 'rgba(255,255,255,0.85)'
        ctx.stroke()
      }
      ctx.lineWidth = selected ? 3 : 2
      ctx.strokeStyle = color
      ctx.stroke()
      // 頂点
      for (const p of pts) {
        const s = S(p)
        ctx.fillStyle = color
        ctx.fillRect(s.x - 2.5, s.y - 2.5, 5, 5)
      }
    }

    // 確定済み測定
    for (const m of measurements) {
      if (m.points.length === 0) continue
      const selected = m.id === selectedId
      if (m.kind === 'count') {
        drawCountMarkers(m.points, m.color, selected)
        if (selected) {
          const s = S(m.points[0])
          label(`${m.label}（${num(m.value)} ${m.unitName}）`, s.x, s.y, m.color)
        }
      } else if (m.kind === 'length') {
        drawPath(m.points, m.color, selected, false, false)
        const mid = S(m.points[Math.floor((m.points.length - 1) / 2)])
        label(`${m.label} ${num(m.value, 2)}${m.unitName}`, mid.x, mid.y, m.color)
      } else {
        drawPath(m.points, m.color, selected, true, true)
        const c = m.points.reduce((a, p) => ({ x: a.x + p.x / m.points.length, y: a.y + p.y / m.points.length }), { x: 0, y: 0 })
        const sc = S(c)
        label(`${m.label} ${num(m.value, 2)}${m.unitName}`, sc.x, sc.y, m.color)
      }
    }

    // 作業中の測定（破線＋ホバー点まで）
    if (kind && (pending.length > 0 || hover)) {
      const color = colorFor(target.label.trim() || TOOL_LABELS[tool])
      const preview = hover && kind !== 'count' ? [...pending, hover.p] : pending
      ctx.setLineDash([5, 4])
      if (kind === 'count') {
        drawCountMarkers(pending, color, false)
      } else if (preview.length >= 2) {
        drawPath(preview, color, false, kind === 'area', kind === 'area')
      }
      ctx.setLineDash([])
      // 進捗表示（現在値）
      if (hover && pending.length > 0) {
        const v = measurementValue(kind, kind === 'count' ? pending : preview, scaleMPerUnit)
        const hs = S(hover.p)
        const unitName = kind === 'count' ? '点' : target.unitName || (kind === 'length' ? 'm' : 'm2')
        label(`${num(v, kind === 'count' ? 0 : 2)} ${unitName}`, hs.x, hs.y, '#17324d')
      }
    }

    // スケール補正の2点
    if (scaleDraft && scaleDraft.points.length > 0) {
      ctx.setLineDash([6, 4])
      drawPath(scaleDraft.points, '#f76b15', false, false, false)
      ctx.setLineDash([])
    }

    // スナップマーカー
    if (hover?.snapped) {
      const s = S(hover.p)
      ctx.strokeStyle = '#0b62c4'
      ctx.lineWidth = 1.6
      ctx.strokeRect(s.x - 5, s.y - 5, 10, 10)
    }
  }, [measurements, pending, hover, selectedId, view, size, tool, kind, scaleDraft, target, colorFor, scaleMPerUnit])

  // --- ブロック集計（個数降順） ---
  const blockRows = useMemo(() => {
    if (!scene) return []
    return Object.entries(scene.insertCounts).sort((a, b) => b[1] - a[1])
  }, [scene])

  const pendingValid = kind !== null && pending.length >= minPoints(kind)
  const scaleDModel = scaleDraft && scaleDraft.points.length === 2 ? dist(scaleDraft.points[0], scaleDraft.points[1]) : 0

  const cursor = dragging ? 'grabbing' : tool === 'pan' ? 'grab' : 'crosshair'

  // ---------- 描画 ----------

  if (parseError) {
    return (
      <div className="card">
        <h2>DXF読込エラー</h2>
        <div className="note danger-text">{parseError}</div>
        <div className="muted small">
          対象ファイル: {file.name}（対応形式: ASCII DXF。バイナリDXF・DWGは非対応です。CADから「DXF（ASCII）」で書き出してください）
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* ツールバー */}
      <div className="toolbar">
        {TOOLS.map((t) => (
          <button
            key={t}
            className={'btn small' + (tool === t ? ' active' : '')}
            onClick={() => setTool(t)}
            title={HINTS[t]}
          >
            {TOOL_LABELS[t]}
          </button>
        ))}
        <span style={{ borderLeft: '1px solid var(--border)', alignSelf: 'stretch' }} />
        <button className="btn small" onClick={() => zoomCenter(1.25)} title="拡大">
          ＋
        </button>
        <button className="btn small" onClick={() => zoomCenter(0.8)} title="縮小">
          －
        </button>
        <button className="btn small" onClick={fitView} title="図面全体を表示">
          全体表示
        </button>
        <span style={{ borderLeft: '1px solid var(--border)', alignSelf: 'stretch' }} />
        <label className="field">
          <span>図面単位</span>
          <select value={unitValue} onChange={(e) => setUnit(e.target.value as 'mm' | 'cm' | 'm')}>
            <option value="mm">mm（1単位=1mm）</option>
            <option value="cm">cm（1単位=1cm）</option>
            <option value="m">m（1単位=1m）</option>
            {unitValue === 'custom' && <option value="custom">実測補正値</option>}
          </select>
        </label>
        <span className="badge blue">
          {scaleMPerUnit
            ? `1単位 = ${num(scaleMPerUnit * 1000, scaleMPerUnit * 1000 < 10 ? 3 : 1)} mm`
            : 'スケール未設定'}
        </span>
        <span className="spacer" />
        {kind && (
          <>
            <span className="muted small">作業中: {pending.length} 点</span>
            <button className="btn small primary" disabled={!pendingValid} onClick={() => commitPending()}>
              確定
            </button>
            <button className="btn small" disabled={pending.length === 0} onClick={() => setPending([])}>
              取消(Esc)
            </button>
          </>
        )}
      </div>

      <div className="takeoff-layout">
        {/* キャンバス */}
        <div
          ref={wrapRef}
          className="takeoff-canvas-wrap"
          style={{ cursor, touchAction: 'none' }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={() => setHover(null)}
          onClick={onClick}
          onDoubleClick={onDoubleClick}
        >
          <canvas ref={baseRef} />
          <canvas ref={overlayRef} />
          {loading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span className="badge">DXFを読み込み中…</span>
            </div>
          )}
          {/* 2点実測スケールの入力フォーム */}
          {scaleDraft && scaleDraft.points.length === 2 && (
            <div
              onClick={(e) => e.stopPropagation()}
              onDoubleClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              onPointerMove={(e) => e.stopPropagation()}
              onPointerUp={(e) => e.stopPropagation()}
              style={{
                position: 'absolute',
                top: 10,
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 6,
                background: '#fff',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '10px 12px',
                boxShadow: '0 2px 10px rgba(0,0,0,0.25)',
              }}
            >
              <div className="small muted" style={{ marginBottom: 6 }}>
                2点間の実寸距離を入力してください（図面上: {num(scaleDModel, 1)} 単位）
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input
                  type="text"
                  autoFocus
                  style={{ width: 90 }}
                  className="num"
                  placeholder="例: 5.4"
                  value={scaleDraft.input}
                  onChange={(e) => setScaleDraft({ ...scaleDraft, input: e.target.value })}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') applyScaleDraft()
                  }}
                />
                <span className="small">m</span>
                <button className="btn small primary" onClick={applyScaleDraft}>
                  適用
                </button>
                <button className="btn small" onClick={() => setScaleDraft(null)}>
                  キャンセル
                </button>
              </div>
            </div>
          )}
          <div className="takeoff-hint">{HINTS[tool]}</div>
        </div>

        {/* サイドパネル */}
        <div className="takeoff-side">
          {/* 拾い対象 */}
          <div className="card" style={{ marginBottom: 0 }}>
            <h2>拾い対象</h2>
            {kind ? (
              <>
                <div className="form-row" style={{ marginBottom: 6 }}>
                  <label className="field">
                    <span>プリセット</span>
                    <select
                      value={
                        TAKEOFF_PRESETS.some((p) => p.kind === kind && p.label === target.label)
                          ? target.label
                          : '__custom'
                      }
                      onChange={(e) => {
                        const p = TAKEOFF_PRESETS.find((x) => x.kind === kind && x.label === e.target.value)
                        if (p) setTarget({ label: p.label, category: p.category, unitName: p.unitName })
                      }}
                    >
                      {TAKEOFF_PRESETS.filter((p) => p.kind === kind).map((p) => (
                        <option key={p.label} value={p.label}>
                          {p.label}
                        </option>
                      ))}
                      <option value="__custom">（自由入力）</option>
                    </select>
                  </label>
                </div>
                <div className="form-row" style={{ marginBottom: 0 }}>
                  <label className="field">
                    <span>名称</span>
                    <input
                      type="text"
                      style={{ width: 130 }}
                      value={target.label}
                      onChange={(e) => setTarget({ ...target, label: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>分類</span>
                    <input
                      type="text"
                      style={{ width: 80 }}
                      value={target.category}
                      onChange={(e) => setTarget({ ...target, category: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>単位</span>
                    <input
                      type="text"
                      style={{ width: 44 }}
                      value={target.unitName}
                      onChange={(e) => setTarget({ ...target, unitName: e.target.value })}
                    />
                  </label>
                </div>
              </>
            ) : (
              <div className="muted small">
                「個数カウント」「長さ拾い」「面積拾い」ツールを選ぶと、拾い対象（名称・分類・単位）を設定できます。
              </div>
            )}
          </div>

          {/* ブロック集計 */}
          {scene && blockRows.length > 0 && (
            <div className="card" style={{ marginBottom: 0 }}>
              <h2>ブロック集計（{num(blockRows.length)}種）</h2>
              <div className="muted small" style={{ marginBottom: 6 }}>
                CADブロック（シンボル）の挿入数です。「拾いに追加」で個数測定として登録できます。
              </div>
              <div className="tbl-wrap" style={{ maxHeight: 220, overflowY: 'auto' }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>ブロック名</th>
                      <th className="num">個数</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {blockRows.map(([name, count]) => (
                      <tr key={name}>
                        <td style={{ wordBreak: 'break-all' }}>{name}</td>
                        <td className="num">{num(count)}</td>
                        <td className="center">
                          <button className="btn small" onClick={() => addBlockAsCount(name)}>
                            拾いに追加
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 測定一覧（共通パネル） */}
          <MeasurementPanel
            drawingId={drawingId}
            pageIndex={0}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id)}
          />
        </div>
      </div>
    </div>
  )
}
