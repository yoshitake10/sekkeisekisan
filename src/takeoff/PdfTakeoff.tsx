import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist'
import { useActiveProject, useStore } from '../store'
import type { DrawingMeta, MeasureKind, Measurement, TakeoffPoint } from '../types'
import { genId } from '../utils/id'
import { num, parseNumber } from '../utils/format'
import { colorForIndex, dist, measurementValue, polygonArea, polylineLength } from './geometry'
import { TAKEOFF_PRESETS, TOOL_LABELS } from './contract'
import type { TakeoffTool, TakeoffViewProps } from './contract'
import MeasurementPanel from './MeasurementPanel'
import EquipmentPlotPanel from './EquipmentPlotPanel'
import { buildPlotTargets, drawPlotMarker, findPlotMeasurement, newPlotMeasurement } from './plot'

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const MIN_ZOOM = 0.05
const MAX_ZOOM = 12
/** レンダリングするキャンバスの最大辺（メモリ保護） */
const MAX_RENDER_DIM = 8192

const TOOL_HINTS: Record<TakeoffTool, string> = {
  pan: 'ドラッグ: 表示移動 ／ ホイール: ズーム ／ クリック: 図面上の測定を選択',
  scale:
    '既知の寸法（通り芯間・スケールバー等）の両端2点をクリック → 実寸(m)を入力 ／ Esc: 中止 ／ 中ボタンドラッグ: 移動',
  count:
    'クリック: マーカー追加 ／ ダブルクリック or「確定」ボタン: 保存（ダブルクリックの位置はカウントに含めません） ／ 右クリック: 1つ戻す ／ Esc: 中止',
  length:
    'クリック: 頂点追加 ／ ダブルクリック: 確定 ／ 右クリック: 1つ戻す ／ Esc: 中止 ／ 中ボタンドラッグ: 移動',
  area: 'クリック: 頂点追加 ／ ダブルクリック: 閉じて確定 ／ 右クリック: 1つ戻す ／ Esc: 中止 ／ 中ボタンドラッグ: 移動',
  plot: '右パネルで配置する機器を選択 → クリックで1台ずつ配置 ／ 右クリック: 1つ戻す',
}

const TOOL_KIND: Partial<Record<TakeoffTool, MeasureKind>> = {
  count: 'count',
  length: 'length',
  area: 'area',
}

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v))
}

/**
 * 指定ページに適用するスケール（m/描画ピクセル）。
 * scaleByPage を優先。旧データ互換: scaleByPage が無い場合は
 * スケール設定時のページ（pageIndex ?? 0）に限り scaleMPerUnit を有効とし、
 * 別縮尺のページへ黙って旧スケールが適用されるのを防ぐ。
 */
function scaleForPage(meta: DrawingMeta | undefined, pageIndex: number): number | undefined {
  if (!meta) return undefined
  if (meta.scaleByPage) return meta.scaleByPage[pageIndex]
  return pageIndex === (meta.pageIndex ?? 0) ? meta.scaleMPerUnit : undefined
}

function distToSegment(px: number, py: number, a: TakeoffPoint, b: TakeoffPoint): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const l2 = dx * dx + dy * dy
  if (l2 === 0) return Math.hypot(px - a.x, py - a.y)
  const t = clamp(((px - a.x) * dx + (py - a.y) * dy) / l2, 0, 1)
  return Math.hypot(px - (a.x + t * dx), py - (a.y + t * dy))
}

function pointInPolygon(px: number, py: number, pts: TakeoffPoint[]): boolean {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x
    const yi = pts[i].y
    const xj = pts[j].x
    const yj = pts[j].y
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

function centroid(pts: TakeoffPoint[]): TakeoffPoint {
  let x = 0
  let y = 0
  for (const p of pts) {
    x += p.x
    y += p.y
  }
  const n = Math.max(1, pts.length)
  return { x: x / n, y: y / n }
}

interface DragState {
  sx: number
  sy: number
  ox: number
  oy: number
  moved: boolean
}

/**
 * PDF 拾いビューア
 *  - Measurement.points は「scale=1 の PDF ビューポート座標（PDFユーザー空間）」で保存する
 *  - 表示ズーム・パンには依存しない
 */
export default function PdfTakeoff({ file, drawingId }: TakeoffViewProps) {
  const project = useActiveProject()
  const upsertDrawing = useStore((s) => s.upsertDrawing)
  const addMeasurement = useStore((s) => s.addMeasurement)
  const updateMeasurement = useStore((s) => s.updateMeasurement)
  const removeMeasurement = useStore((s) => s.removeMeasurement)
  const loadUnits = useStore((s) => s.loadUnits)
  const daikinModels = useStore((s) => s.daikinModels)

  const meta = project.drawings.find((d) => d.id === drawingId)

  // --- PDF ドキュメント / ページ ---
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [pageIndex, setPageIndex] = useState(0)
  const [page, setPage] = useState<PDFPageProxy | null>(null)
  const [pageSize, setPageSize] = useState({ w: 0, h: 0 })
  const [error, setError] = useState('')

  /** 現在ページのスケール（ページごとに管理） */
  const scale = scaleForPage(meta, pageIndex)

  // --- 表示（ズーム・パン・キャンバスサイズ） ---
  const [zoom, setZoom] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [renderVer, setRenderVer] = useState(0)
  const [dragging, setDragging] = useState(false)

  // --- 拾い操作 ---
  const [tool, setTool] = useState<TakeoffTool>('pan')
  const [draft, setDraft] = useState<TakeoffPoint[]>([])
  const [cursor, setCursor] = useState<TakeoffPoint | null>(null)
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)
  const [presetSel, setPresetSel] = useState('0')
  const [target, setTarget] = useState({
    label: TAKEOFF_PRESETS[0].label,
    category: TAKEOFF_PRESETS[0].category,
    unitName: TAKEOFF_PRESETS[0].unitName,
  })
  /** 機器プロットの配置対象キー（`${roomId}|${plotKind}`） */
  const [plotKey, setPlotKey] = useState<string | null>(null)

  const wrapRef = useRef<HTMLDivElement>(null)
  const baseRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  /** レンダリング済みページ画像（オフスクリーン） */
  const pageCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const renderTaskRef = useRef<RenderTask | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const movedRef = useRef(false)
  const fittedRef = useRef(false)

  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1

  const pageMeasurements = project.measurements.filter(
    (m) => m.drawingId === drawingId && m.pageIndex === pageIndex,
  )

  // ---------- 機器プロット ----------
  const plotTargets = buildPlotTargets(project, loadUnits, daikinModels)
  const activePlotTarget = plotTargets.find((t) => t.key === plotKey)
  const hasPlots = project.measurements.some((m) => m.kind === 'plot' && m.drawingId === drawingId)

  /** 現在のラベル（部屋名・機種変更に追従）。孤立プロットは保存済みラベルを使用 */
  function plotLabelOf(m: Measurement): string {
    const t = plotTargets.find((x) => x.roomId === m.roomId && x.plotKind === m.plotKind)
    return t?.label ?? m.label
  }

  /** クリック位置に選択中の機器を1台配置する */
  function placePlot(p: TakeoffPoint) {
    const t = activePlotTarget
    if (!t) {
      alert('右の「機器プロット（配置）」から配置する機器を選択してください。')
      return
    }
    const existing = findPlotMeasurement(project.measurements, drawingId, pageIndex, t)
    if (existing) {
      const points = [...existing.points, p]
      updateMeasurement(existing.id, {
        points,
        value: points.length,
        label: t.label,
        modelId: t.model.id,
        spec: t.model.modelNo,
      })
    } else {
      const m = newPlotMeasurement(genId('ms'), drawingId, pageIndex, t)
      addMeasurement({ ...m, points: [p], value: 1 })
    }
  }

  /** 選択中対象の配置を1つ戻す（このページ上） */
  function undoPlot() {
    const t = activePlotTarget
    if (!t) return
    const existing = findPlotMeasurement(project.measurements, drawingId, pageIndex, t)
    if (!existing || existing.points.length === 0) return
    if (existing.points.length === 1) {
      removeMeasurement(existing.id)
    } else {
      const points = existing.points.slice(0, -1)
      updateMeasurement(existing.id, { points, value: points.length })
    }
  }

  /** パネルで対象を選んだら plot ツールへ切替 */
  function selectPlotTarget(key: string) {
    setPlotKey(key)
    setTool('plot')
    setDraft([])
    setCursor(null)
  }

  // ---------- 座標変換 ----------
  // 画面(CSS px) = PDFユーザー座標 * zoom + offset
  function toScreen(p: TakeoffPoint): { x: number; y: number } {
    return { x: p.x * zoom + offset.x, y: p.y * zoom + offset.y }
  }
  function toUser(sx: number, sy: number): TakeoffPoint {
    return { x: (sx - offset.x) / zoom, y: (sy - offset.y) / zoom }
  }
  function eventPos(e: React.MouseEvent): { sx: number; sy: number } {
    const rect = wrapRef.current?.getBoundingClientRect()
    return { sx: e.clientX - (rect?.left ?? 0), sy: e.clientY - (rect?.top ?? 0) }
  }

  // ---------- PDF 読み込み ----------
  useEffect(() => {
    let cancelled = false
    let doc: PDFDocumentProxy | null = null
    setPdf(null)
    setPage(null)
    setError('')
    setPageIndex(0)
    fittedRef.current = false
    pageCanvasRef.current = null
    file
      .arrayBuffer()
      .then((buf) => pdfjsLib.getDocument({ data: new Uint8Array(buf) }).promise)
      .then((d) => {
        if (cancelled) {
          d.destroy()
          return
        }
        doc = d
        setPdf(d)
        setNumPages(d.numPages)
      })
      .catch((e) => {
        if (!cancelled) setError('PDFの読み込みに失敗しました: ' + String((e as Error)?.message ?? e))
      })
    return () => {
      cancelled = true
      try {
        renderTaskRef.current?.cancel()
      } catch {
        /* ignore */
      }
      doc?.destroy()
    }
  }, [file])

  // ---------- ページ取得 ----------
  useEffect(() => {
    if (!pdf) return
    let cancelled = false
    pageCanvasRef.current = null
    setRenderVer((v) => v + 1)
    pdf
      .getPage(pageIndex + 1)
      .then((pg) => {
        if (cancelled) return
        const vp = pg.getViewport({ scale: 1 })
        setPage(pg)
        setPageSize({ w: vp.width, h: vp.height })
      })
      .catch((e) => {
        if (!cancelled) setError('ページの取得に失敗しました: ' + String((e as Error)?.message ?? e))
      })
    return () => {
      cancelled = true
    }
  }, [pdf, pageIndex])

  // ---------- コンテナサイズ監視 ----------
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    const ro = new ResizeObserver(update)
    ro.observe(el)
    update()
    return () => ro.disconnect()
  }, [])

  // ---------- 初回フィット ----------
  useEffect(() => {
    if (!pageSize.w || !size.w || fittedRef.current) return
    fittedRef.current = true
    const z = clamp(
      Math.min((size.w - 30) / pageSize.w, (size.h - 30) / pageSize.h),
      MIN_ZOOM,
      MAX_ZOOM,
    )
    setZoom(z)
    setOffset({ x: (size.w - pageSize.w * z) / 2, y: (size.h - pageSize.h * z) / 2 })
  }, [pageSize, size])

  // ---------- ページをオフスクリーンへレンダリング ----------
  useEffect(() => {
    if (!page || !pageSize.w) return
    let cancelled = false
    const cap = MAX_RENDER_DIM / Math.max(pageSize.w, pageSize.h)
    const rscale = Math.min(Math.max(zoom, 0.1) * dpr, cap)
    const timer = setTimeout(() => {
      const vp = page.getViewport({ scale: rscale })
      const off = document.createElement('canvas')
      off.width = Math.max(1, Math.floor(vp.width))
      off.height = Math.max(1, Math.floor(vp.height))
      const ctx = off.getContext('2d')
      if (!ctx) return
      try {
        renderTaskRef.current?.cancel()
      } catch {
        /* ignore */
      }
      const task = page.render({ canvasContext: ctx, viewport: vp })
      renderTaskRef.current = task
      task.promise.then(
        () => {
          if (cancelled) return
          pageCanvasRef.current = off
          setRenderVer((v) => v + 1)
        },
        () => {
          /* キャンセル時は無視 */
        },
      )
    }, 80)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [page, zoom, pageSize, dpr])

  // ---------- ベースキャンバス描画（ページ画像＋パン/ズーム反映） ----------
  useEffect(() => {
    const canvas = baseRef.current
    if (!canvas || !size.w) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)
    if (!pageSize.w) return
    const w = pageSize.w * zoom
    const h = pageSize.h * zoom
    ctx.save()
    ctx.shadowColor = 'rgba(0,0,0,0.25)'
    ctx.shadowBlur = 8
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(offset.x, offset.y, w, h)
    ctx.restore()
    const off = pageCanvasRef.current
    if (off && off.width > 0) {
      ctx.drawImage(off, 0, 0, off.width, off.height, offset.x, offset.y, w, h)
    }
  }, [renderVer, zoom, offset, size, pageSize, dpr])

  // ---------- オーバーレイ描画（測定＋作図プレビュー） ----------
  useEffect(() => {
    const canvas = overlayRef.current
    if (!canvas || !size.w) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)
    if (!pageSize.w) return

    ctx.font = 'bold 11px sans-serif'
    ctx.textBaseline = 'bottom'

    const drawLabel = (text: string, x: number, y: number, color: string) => {
      ctx.lineWidth = 3
      ctx.strokeStyle = 'rgba(255,255,255,0.92)'
      ctx.strokeText(text, x, y)
      ctx.fillStyle = color
      ctx.fillText(text, x, y)
    }
    const drawVertex = (x: number, y: number, color: string, r = 4) => {
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      ctx.lineWidth = 1.5
      ctx.strokeStyle = '#fff'
      ctx.stroke()
    }

    // --- 確定済み測定 ---
    for (const m of pageMeasurements) {
      const pts = m.points.map(toScreen)
      if (pts.length === 0) continue
      const sel = m.id === selectedId
      ctx.lineWidth = sel ? 3.5 : 2
      ctx.strokeStyle = m.color
      ctx.setLineDash([])

      if (m.kind === 'count') {
        for (const p of pts) drawVertex(p.x, p.y, m.color, sel ? 8 : 6)
        const c = toScreen(centroid(m.points))
        drawLabel(`${m.label} ${num(m.value)}${m.unitName}`, c.x + 8, c.y - 8, m.color)
      } else if (m.kind === 'plot') {
        // 機器プロット: 四角マーカー＋対角線（機器シンボル風）
        for (const p of pts) drawPlotMarker(ctx, p.x, p.y, m.color, sel)
        const c = toScreen(centroid(m.points))
        drawLabel(`${plotLabelOf(m)} ${num(m.value)}${m.unitName}`, c.x + 9, c.y - 9, m.color)
      } else if (m.kind === 'length') {
        ctx.beginPath()
        pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
        ctx.stroke()
        for (const p of pts) drawVertex(p.x, p.y, m.color, sel ? 4.5 : 3)
        const mid = pts[Math.floor(pts.length / 2)]
        drawLabel(`${m.label} ${num(m.value, 2)}${m.unitName}`, mid.x + 6, mid.y - 4, m.color)
      } else {
        ctx.beginPath()
        pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
        ctx.closePath()
        ctx.globalAlpha = sel ? 0.3 : 0.18
        ctx.fillStyle = m.color
        ctx.fill()
        ctx.globalAlpha = 1
        ctx.stroke()
        const c = toScreen(centroid(m.points))
        drawLabel(`${m.label} ${num(m.value, 2)}${m.unitName}`, c.x, c.y, m.color)
      }
    }

    // --- 機器プロットのカーソルプレビュー ---
    if (tool === 'plot' && cursor && activePlotTarget) {
      const s = toScreen(cursor)
      ctx.globalAlpha = 0.6
      drawPlotMarker(ctx, s.x, s.y, activePlotTarget.color, false)
      ctx.globalAlpha = 1
      drawLabel(activePlotTarget.label, s.x + 12, s.y - 10, activePlotTarget.color)
    }

    // --- 作図中プレビュー ---
    if (tool !== 'pan' && tool !== 'plot' && draft.length > 0) {
      const color = tool === 'scale' ? '#0b62c4' : colorForLabel(target.label)
      const pts = draft.map(toScreen)
      const cur = cursor ? toScreen(cursor) : null
      ctx.lineWidth = 2
      ctx.strokeStyle = color
      ctx.setLineDash([6, 4])

      if (tool === 'count') {
        for (const p of pts) drawVertex(p.x, p.y, color, 6)
        if (cur) drawLabel(`${target.label} ${draft.length}${target.unitName}`, cur.x + 10, cur.y - 10, color)
      } else {
        ctx.beginPath()
        pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
        if (cur) ctx.lineTo(cur.x, cur.y)
        if (tool === 'area' && pts.length >= 2) {
          // 始点まで閉じるプレビュー
          ctx.lineTo(pts[0].x, pts[0].y)
        }
        ctx.stroke()
        for (const p of pts) drawVertex(p.x, p.y, color, 3.5)

        const previewPts = cursor ? [...draft, cursor] : draft
        let text = ''
        if (tool === 'scale') {
          const u = polylineLength(previewPts)
          text = scale ? `${num(u * scale, 2)} m（現在のスケール）` : `${num(u, 1)} 図面単位`
        } else if (tool === 'length') {
          text = scale ? `${num(polylineLength(previewPts) * scale, 2)} m` : 'スケール未設定'
        } else if (tool === 'area') {
          text = scale ? `${num(polygonArea(previewPts) * scale * scale, 2)} m2` : 'スケール未設定'
        }
        if (cur && text) drawLabel(text, cur.x + 10, cur.y - 10, color)
      }
      ctx.setLineDash([])
    }
  })

  // ---------- ホイールズーム（passive:false で登録） ----------
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const sx = e.clientX - rect.left
      const sy = e.clientY - rect.top
      const nz = clamp(zoom * (e.deltaY < 0 ? 1.2 : 1 / 1.2), MIN_ZOOM, MAX_ZOOM)
      if (nz === zoom) return
      setOffset({
        x: sx - ((sx - offset.x) / zoom) * nz,
        y: sy - ((sy - offset.y) / zoom) * nz,
      })
      setZoom(nz)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoom, offset])

  // ---------- Esc で作図キャンセル ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDraft([])
        setCursor(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // ---------- 色（同一ラベルは同色を再利用） ----------
  function colorForLabel(label: string): string {
    const seen: string[] = []
    for (const m of project.measurements) {
      if (m.drawingId !== drawingId) continue
      if (m.label === label) return m.color
      if (!seen.includes(m.label)) seen.push(m.label)
    }
    return colorForIndex(seen.length)
  }

  // ---------- ツール・対象選択 ----------
  function selectTool(t: TakeoffTool) {
    if ((t === 'length' || t === 'area') && !scale) {
      alert(
        'このページのスケールが未設定です。\n長さ・面積を拾う前に「スケール設定」ツールで既知の寸法（通り芯間など）から基準を設定してください。\n（スケールはページごとに設定します）',
      )
    }
    if (t === 'plot') {
      if (plotTargets.length === 0) {
        alert(
          '配置できる機器がありません。\n先に「機器選定」タブで部屋（用途・面積）を登録してください。選定された機種が配置対象になります。',
        )
        return
      }
      // 未選択なら先頭の未完了対象を自動選択
      if (!plotTargets.some((x) => x.key === plotKey)) {
        setPlotKey(plotTargets[0].key)
      }
    }
    setTool(t)
    setDraft([])
    setCursor(null)
  }

  function onPresetChange(v: string) {
    setPresetSel(v)
    if (v === '') return // 自由入力: 現在の入力値を維持
    const p = TAKEOFF_PRESETS[Number(v)]
    if (p) {
      setTarget({ label: p.label, category: p.category, unitName: p.unitName })
      selectTool(p.kind)
    }
  }

  // ---------- ズーム操作 ----------
  function zoomBy(f: number) {
    const cx = size.w / 2
    const cy = size.h / 2
    const nz = clamp(zoom * f, MIN_ZOOM, MAX_ZOOM)
    if (nz === zoom) return
    setOffset({
      x: cx - ((cx - offset.x) / zoom) * nz,
      y: cy - ((cy - offset.y) / zoom) * nz,
    })
    setZoom(nz)
  }
  function fitToView() {
    if (!pageSize.w || !size.w) return
    const z = clamp(
      Math.min((size.w - 30) / pageSize.w, (size.h - 30) / pageSize.h),
      MIN_ZOOM,
      MAX_ZOOM,
    )
    setZoom(z)
    setOffset({ x: (size.w - pageSize.w * z) / 2, y: (size.h - pageSize.h * z) / 2 })
  }

  // ---------- 測定の確定 ----------
  function saveMeasurement(kind: MeasureKind, points: TakeoffPoint[]) {
    if ((kind === 'length' || kind === 'area') && !scale) {
      alert(
        'このページのスケールが未設定のため確定できません。「スケール設定」で基準寸法を設定してください。',
      )
      return
    }
    const label = target.label.trim() || TOOL_LABELS[tool]
    const m: Measurement = {
      id: genId('ms'),
      drawingId,
      pageIndex,
      kind,
      label,
      category: target.category.trim() || 'その他',
      unitName:
        target.unitName.trim() || (kind === 'count' ? '個' : kind === 'length' ? 'm' : 'm2'),
      points: [...points],
      value: measurementValue(kind, points, scale),
      color: colorForLabel(label),
    }
    addMeasurement(m)
    setDraft([])
    setCursor(null)
    setSelectedId(m.id)
  }

  function finalizeDraft() {
    const kind = TOOL_KIND[tool]
    if (!kind || draft.length === 0) return
    if (kind === 'length' && draft.length < 2) {
      alert('長さ拾いは2点以上クリックしてください。')
      return
    }
    if (kind === 'area' && draft.length < 3) {
      alert('面積拾いは3点以上クリックしてください。')
      return
    }
    saveMeasurement(kind, draft)
  }

  // ---------- クリックによる測定選択（panツール） ----------
  function hitSelect(sx: number, sy: number) {
    const tol = 8
    let best: { id: string; d: number } | null = null
    for (const m of pageMeasurements) {
      const pts = m.points.map(toScreen)
      let d = Infinity
      if (m.kind === 'count' || m.kind === 'plot') {
        for (const q of pts) d = Math.min(d, Math.hypot(q.x - sx, q.y - sy))
      } else {
        for (let i = 1; i < pts.length; i++) d = Math.min(d, distToSegment(sx, sy, pts[i - 1], pts[i]))
        if (m.kind === 'area' && pts.length >= 3) {
          d = Math.min(d, distToSegment(sx, sy, pts[pts.length - 1], pts[0]))
          if (pointInPolygon(sx, sy, pts)) d = Math.min(d, tol - 1)
        }
      }
      if (d < tol && (!best || d < best.d)) best = { id: m.id, d }
    }
    setSelectedId(best ? best.id : undefined)
  }

  // ---------- マウスイベント ----------
  function onMouseDown(e: React.MouseEvent) {
    if (e.button === 1 || (e.button === 0 && tool === 'pan')) {
      e.preventDefault()
      const { sx, sy } = eventPos(e)
      dragRef.current = { sx, sy, ox: offset.x, oy: offset.y, moved: false }
      setDragging(true)
    }
  }
  function onMouseMove(e: React.MouseEvent) {
    const { sx, sy } = eventPos(e)
    const d = dragRef.current
    if (d) {
      if (Math.abs(sx - d.sx) + Math.abs(sy - d.sy) > 2) d.moved = true
      setOffset({ x: d.ox + (sx - d.sx), y: d.oy + (sy - d.sy) })
      return
    }
    if (tool !== 'pan') setCursor(toUser(sx, sy))
  }
  function endDrag() {
    if (dragRef.current) {
      movedRef.current = dragRef.current.moved
      dragRef.current = null
      setDragging(false)
    }
  }
  function onClick(e: React.MouseEvent) {
    if (movedRef.current) {
      movedRef.current = false
      return
    }
    if (e.detail > 1) return // ダブルクリックの2回目は無視
    if (!page) return
    const { sx, sy } = eventPos(e)
    if (tool === 'pan') {
      hitSelect(sx, sy)
      return
    }
    const p = toUser(sx, sy)
    if (tool === 'scale') {
      const next = [...draft, p]
      if (next.length < 2) {
        setDraft(next)
        return
      }
      setDraft([])
      setCursor(null)
      const units = dist(next[0], next[1])
      if (units <= 0) return
      const input = prompt(
        'クリックした2点間の実際の長さを入力してください（m）\n例: 柱スパン 6.4 → 「6.4」',
      )
      if (input === null) return
      const realM = parseNumber(input)
      if (!Number.isFinite(realM) || realM <= 0) {
        alert('正の数値（m）を入力してください。')
        return
      }
      const newScale = realM / units
      const base = meta ?? { id: drawingId, kind: 'pdf' as const, fileName: file.name }
      // ページ単位でスケールを保持。旧データの scaleMPerUnit は設定時ページの値として引き継ぐ
      const scaleByPage: Record<number, number> = {
        ...(meta?.scaleByPage ??
          (meta?.scaleMPerUnit !== undefined
            ? { [meta.pageIndex ?? 0]: meta.scaleMPerUnit }
            : {})),
        [pageIndex]: newScale,
      }
      upsertDrawing({ ...base, scaleMPerUnit: newScale, pageIndex, scaleByPage })
      // このページの既存測定を新スケールで再計算（数量を手修正した測定は除く）
      for (const m of project.measurements) {
        if (
          m.drawingId !== drawingId ||
          m.pageIndex !== pageIndex ||
          m.kind === 'count' ||
          m.kind === 'plot' ||
          m.points.length === 0 ||
          m.valueOverridden === true
        )
          continue
        updateMeasurement(m.id, { value: measurementValue(m.kind, m.points, newScale) })
      }
      return
    }
    if (tool === 'plot') {
      placePlot(p)
      return
    }
    // count / length / area
    setDraft((d) => [...d, p])
  }
  function onDoubleClick(e: React.MouseEvent) {
    e.preventDefault()
    if (tool === 'count') {
      // ダブルクリックの1回目の click で draft に点が追加されているため、
      // 末尾1点（ダブルクリック位置）を除いて確定する（+1 防止）
      const pts = draft.slice(0, -1)
      if (pts.length === 0) {
        setDraft([])
        setCursor(null)
        return
      }
      saveMeasurement('count', pts)
      return
    }
    finalizeDraft()
  }
  function onContextMenu(e: React.MouseEvent) {
    e.preventDefault()
    if (tool === 'plot') {
      undoPlot()
      return
    }
    if (draft.length > 0) setDraft(draft.slice(0, -1))
  }

  // ---------- サイドパネルからの選択 ----------
  function onSelectFromPanel(id: string) {
    setSelectedId(id)
    const m = project.measurements.find((x) => x.id === id)
    if (!m) return
    if (m.pageIndex !== pageIndex) setPageIndex(m.pageIndex)
    // 画面外なら中央へ移動
    const c = centroid(m.points)
    const s = { x: c.x * zoom + offset.x, y: c.y * zoom + offset.y }
    if (m.pageIndex !== pageIndex || s.x < 0 || s.y < 0 || s.x > size.w || s.y > size.h) {
      setOffset({ x: size.w / 2 - c.x * zoom, y: size.h / 2 - c.y * zoom })
    }
  }

  function changePage(delta: number) {
    const next = clamp(pageIndex + delta, 0, Math.max(0, numPages - 1))
    if (next === pageIndex) return
    setPageIndex(next)
    setDraft([])
    setCursor(null)
  }

  const cursorStyle = dragging ? 'grabbing' : tool === 'pan' ? 'grab' : 'crosshair'
  const canvasW = Math.max(1, Math.floor(size.w * dpr))
  const canvasH = Math.max(1, Math.floor(size.h * dpr))

  return (
    <div>
      {/* ツール・表示操作 */}
      <div className="toolbar">
        {(Object.keys(TOOL_LABELS) as TakeoffTool[]).map((t) => (
          <button
            key={t}
            className={'btn' + (tool === t ? ' active' : '')}
            onClick={() => selectTool(t)}
          >
            {TOOL_LABELS[t]}
          </button>
        ))}
        {tool === 'count' && (
          <button className="btn primary" disabled={draft.length === 0} onClick={finalizeDraft}>
            確定（{draft.length}点）
          </button>
        )}
        <span className="spacer" />
        <button className="btn small" disabled={pageIndex <= 0} onClick={() => changePage(-1)}>
          ◀ 前
        </button>
        <span className="small" style={{ minWidth: 70, textAlign: 'center' }}>
          {numPages > 0 ? `${pageIndex + 1} / ${numPages} ページ` : '- / -'}
        </span>
        <button
          className="btn small"
          disabled={pageIndex >= numPages - 1}
          onClick={() => changePage(1)}
        >
          次 ▶
        </button>
        <button className="btn small" onClick={() => zoomBy(1 / 1.25)}>
          −
        </button>
        <span className="small" style={{ minWidth: 44, textAlign: 'center' }}>
          {Math.round(zoom * 100)}%
        </span>
        <button className="btn small" onClick={() => zoomBy(1.25)}>
          ＋
        </button>
        <button className="btn small" onClick={fitToView}>
          全体表示
        </button>
      </div>

      {/* 拾い対象・スケール表示（機器プロット中は拾い対象入力の代わりに配置対象を表示） */}
      <div className="toolbar">
        {tool === 'plot' ? (
          <span className="small">
            配置対象:{' '}
            {activePlotTarget ? (
              <>
                <span
                  style={{
                    display: 'inline-block',
                    width: 12,
                    height: 12,
                    background: activePlotTarget.color,
                    border: '1px solid rgba(0,0,0,0.2)',
                    verticalAlign: 'middle',
                    marginRight: 4,
                  }}
                />
                <b>{activePlotTarget.label}</b>（クリックで1台ずつ配置）
              </>
            ) : (
              '右の「機器プロット（配置）」から機器を選択してください'
            )}
          </span>
        ) : (
          <>
        <label className="field">
          <span>拾い対象プリセット</span>
          <select value={presetSel} onChange={(e) => onPresetChange(e.target.value)}>
            {TAKEOFF_PRESETS.map((p, i) => (
              <option key={p.label} value={String(i)}>
                {p.label}（{p.unitName}）
              </option>
            ))}
            <option value="">自由入力</option>
          </select>
        </label>
        <label className="field">
          <span>ラベル</span>
          <input
            type="text"
            style={{ width: 130 }}
            value={target.label}
            onChange={(e) => {
              setPresetSel('')
              setTarget({ ...target, label: e.target.value })
            }}
          />
        </label>
        <label className="field">
          <span>分類</span>
          <input
            type="text"
            style={{ width: 90 }}
            value={target.category}
            onChange={(e) => {
              setPresetSel('')
              setTarget({ ...target, category: e.target.value })
            }}
          />
        </label>
        <label className="field">
          <span>単位</span>
          <input
            type="text"
            style={{ width: 48 }}
            value={target.unitName}
            onChange={(e) => {
              setPresetSel('')
              setTarget({ ...target, unitName: e.target.value })
            }}
          />
        </label>
        <span
          style={{
            display: 'inline-block',
            width: 12,
            height: 12,
            borderRadius: 6,
            background: colorForLabel(target.label),
            border: '1px solid rgba(0,0,0,0.2)',
          }}
          title="この対象の表示色"
        />
          </>
        )}
        <span className="spacer" />
        {scale ? (
          <span className="badge green" title={`1図面単位 = ${scale} m（ページごとに設定）`}>
            {numPages > 1 ? `P${pageIndex + 1}: ` : ''}スケール設定済（100px ≒ {num(scale * 100, 2)} m）
          </span>
        ) : (
          <span className="badge orange">
            {numPages > 1 ? `P${pageIndex + 1}: ` : ''}スケール未設定 — 長さ・面積は拾えません
          </span>
        )}
      </div>

      <div className="takeoff-layout">
        <div
          ref={wrapRef}
          className="takeoff-canvas-wrap"
          style={{ cursor: cursorStyle }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={endDrag}
          onMouseLeave={endDrag}
          onClick={onClick}
          onDoubleClick={onDoubleClick}
          onContextMenu={onContextMenu}
        >
          <canvas
            ref={baseRef}
            width={canvasW}
            height={canvasH}
            style={{ width: size.w, height: size.h }}
          />
          <canvas
            ref={overlayRef}
            width={canvasW}
            height={canvasH}
            style={{ width: size.w, height: size.h }}
          />
          <div className="takeoff-hint">
            {error
              ? error
              : !pdf
                ? 'PDFを読み込んでいます…'
                : `【${TOOL_LABELS[tool]}】${TOOL_HINTS[tool]}`}
          </div>
        </div>
        <div className="takeoff-side">
          {(tool === 'plot' || hasPlots || plotTargets.length > 0) && (
            <EquipmentPlotPanel
              drawingId={drawingId}
              activeKey={plotKey}
              onSelectTarget={selectPlotTarget}
            />
          )}
          <MeasurementPanel
            drawingId={drawingId}
            pageIndex={pageIndex}
            selectedId={selectedId}
            onSelect={onSelectFromPanel}
          />
        </div>
      </div>
    </div>
  )
}
