// ============================================================
// DXF 描画ヘルパー
//  - dxf-parser の解析結果を Canvas 描画用プリミティブへ変換する
//  - 座標はすべて DXF モデル空間（Y軸上向き）のまま保持し、
//    drawScene() で画面座標（Y軸下向き）へ変換して描画する
// ============================================================

import DxfParser from 'dxf-parser'
import type {
  IArcEntity,
  IBlock,
  ICircleEntity,
  IDxf,
  IEntity,
  IInsertEntity,
  ILineEntity,
  ILwpolylineEntity,
  IMtextEntity,
  IPolylineEntity,
  ITextEntity,
} from 'dxf-parser'

// ---------- 公開型 ----------

/** 描画プリミティブ（座標はすべて DXF モデル空間・Y軸上向き） */
export type DxfPrimitive =
  | { type: 'polyline'; points: { x: number; y: number }[]; closed: boolean }
  | { type: 'circle'; cx: number; cy: number; r: number }
  /** 角度はラジアン・反時計回り（DXF準拠） */
  | { type: 'arc'; cx: number; cy: number; r: number; startAngle: number; endAngle: number }
  | { type: 'text'; x: number; y: number; text: string; height: number; rotationDeg: number }

export interface DxfBounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export interface DxfScene {
  entities: DxfPrimitive[]
  bounds: DxfBounds
  /** INSERT のブロック名ごとの個数（'*' で始まる無名ブロック＝寸法等は除外） */
  insertCounts: Record<string, number>
  /** INSERT のブロック名ごとの挿入点（モデル空間座標）。insertCounts と同キー */
  insertPoints: Record<string, { x: number; y: number }[]>
}

/** 画面変換: screenX = x*scale + offsetX / screenY = offsetY - y*scale（Y反転） */
export interface SceneTransform {
  scale: number
  offsetX: number
  offsetY: number
}

// ---------- アフィン変換 ----------

/** x' = a*x + c*y + e, y' = b*x + d*y + f */
interface Mat {
  a: number
  b: number
  c: number
  d: number
  e: number
  f: number
}

const IDENTITY: Mat = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }

function isIdentity(m: Mat): boolean {
  return m.a === 1 && m.b === 0 && m.c === 0 && m.d === 1 && m.e === 0 && m.f === 0
}

/** m∘n（n を先に適用） */
function mul(m: Mat, n: Mat): Mat {
  return {
    a: m.a * n.a + m.c * n.b,
    b: m.b * n.a + m.d * n.b,
    c: m.a * n.c + m.c * n.d,
    d: m.b * n.c + m.d * n.d,
    e: m.a * n.e + m.c * n.f + m.e,
    f: m.b * n.e + m.d * n.f + m.f,
  }
}

function apply(m: Mat, x: number, y: number): { x: number; y: number } {
  return { x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f }
}

/** 変換行列の平均スケール倍率（文字高さ等の変換用） */
function scaleMag(m: Mat): number {
  return (Math.hypot(m.a, m.b) + Math.hypot(m.c, m.d)) / 2
}

/** 変換行列の回転角（度） */
function rotationDegOf(m: Mat): number {
  return (Math.atan2(m.b, m.a) * 180) / Math.PI
}

// ---------- パース本体 ----------

interface WalkCtx {
  prims: DxfPrimitive[]
  counts: Record<string, number>
  insertPts: Record<string, { x: number; y: number }[]>
  blocks: Record<string, IBlock>
  b: { minX: number; minY: number; maxX: number; maxY: number; has: boolean }
}

function extend(ctx: WalkCtx, x: number, y: number): void {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return
  const b = ctx.b
  if (!b.has) {
    b.minX = b.maxX = x
    b.minY = b.maxY = y
    b.has = true
    return
  }
  if (x < b.minX) b.minX = x
  if (x > b.maxX) b.maxX = x
  if (y < b.minY) b.minY = y
  if (y > b.maxY) b.maxY = y
}

/** MTEXT/TEXT の書式コードを除去して表示用文字列にする */
function cleanText(s: string): string {
  return s
    .replace(/\\P/g, ' ')
    .replace(/\\~/g, ' ')
    .replace(/\\[LlOoKk]/g, '') // 下線・取消線等の単独コード
    .replace(/\\[A-Za-z][^;{}\\]*;/g, '') // \f...; \H...; \C...; 等の書式コード
    .replace(/\\([\\{}])/g, '$1')
    .replace(/[{}]/g, '')
    .replace(/%%[cC]/g, 'φ')
    .replace(/%%[dD]/g, '°')
    .replace(/%%[pP]/g, '±')
    .trim()
}

function pushPolyline(
  ctx: WalkCtx,
  raw: { x: number; y: number }[],
  closed: boolean,
  m: Mat,
): void {
  if (raw.length < 2) return
  const points = raw.map((p) => {
    const q = apply(m, p.x, p.y)
    extend(ctx, q.x, q.y)
    return q
  })
  ctx.prims.push({ type: 'polyline', points, closed })
}

/** 円弧/円を折れ線としてテッセレーション（非等方変換・回転INSERT内で使用） */
function tessellateArc(
  ctx: WalkCtx,
  cx: number,
  cy: number,
  r: number,
  start: number,
  end: number,
  m: Mat,
  closed: boolean,
): void {
  let sweep = end - start
  if (sweep <= 0) sweep += Math.PI * 2
  const n = Math.min(64, Math.max(8, Math.ceil((Math.abs(sweep) / (Math.PI * 2)) * 48)))
  const pts: { x: number; y: number }[] = []
  for (let i = 0; i <= n; i++) {
    const t = start + (sweep * i) / n
    pts.push({ x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) })
  }
  pushPolyline(ctx, pts, closed, m)
}

function walkEntities(entities: IEntity[], m: Mat, depth: number, ctx: WalkCtx): void {
  const ident = isIdentity(m)
  for (const e of entities) {
    if (!e || !e.type) continue
    switch (e.type) {
      case 'LINE': {
        const le = e as ILineEntity
        if (Array.isArray(le.vertices)) pushPolyline(ctx, le.vertices, false, m)
        break
      }
      case 'LWPOLYLINE': {
        const pe = e as ILwpolylineEntity
        if (Array.isArray(pe.vertices)) pushPolyline(ctx, pe.vertices, !!pe.shape, m)
        break
      }
      case 'POLYLINE': {
        const pe = e as IPolylineEntity
        if (Array.isArray(pe.vertices)) pushPolyline(ctx, pe.vertices, !!pe.shape, m)
        break
      }
      case 'CIRCLE': {
        const ce = e as ICircleEntity
        if (!ce.center || !(ce.radius > 0)) break
        if (ident) {
          ctx.prims.push({ type: 'circle', cx: ce.center.x, cy: ce.center.y, r: ce.radius })
          extend(ctx, ce.center.x - ce.radius, ce.center.y - ce.radius)
          extend(ctx, ce.center.x + ce.radius, ce.center.y + ce.radius)
        } else {
          tessellateArc(ctx, ce.center.x, ce.center.y, ce.radius, 0, Math.PI * 2, m, true)
        }
        break
      }
      case 'ARC': {
        const ae = e as IArcEntity
        if (!ae.center || !(ae.radius > 0)) break
        const sa = ae.startAngle ?? 0
        const ea = ae.endAngle ?? Math.PI * 2
        if (ident) {
          ctx.prims.push({
            type: 'arc',
            cx: ae.center.x,
            cy: ae.center.y,
            r: ae.radius,
            startAngle: sa,
            endAngle: ea,
          })
          // 概算バウンディング（円全体）
          extend(ctx, ae.center.x - ae.radius, ae.center.y - ae.radius)
          extend(ctx, ae.center.x + ae.radius, ae.center.y + ae.radius)
        } else {
          tessellateArc(ctx, ae.center.x, ae.center.y, ae.radius, sa, ea, m, false)
        }
        break
      }
      case 'TEXT': {
        const te = e as ITextEntity
        const pos = te.startPoint ?? te.endPoint
        const raw = te.text
        if (!pos || !raw) break
        const text = cleanText(String(raw))
        if (!text) break
        const q = apply(m, pos.x, pos.y)
        const h = (te.textHeight > 0 ? te.textHeight : 2.5) * scaleMag(m)
        ctx.prims.push({
          type: 'text',
          x: q.x,
          y: q.y,
          text,
          height: h,
          rotationDeg: (te.rotation ?? 0) + rotationDegOf(m), // TEXT の group 50 は度
        })
        extend(ctx, q.x, q.y)
        extend(ctx, q.x, q.y + h)
        break
      }
      case 'MTEXT': {
        const me = e as IMtextEntity
        const raw = me.text
        if (!me.position || !raw) break
        const text = cleanText(String(raw))
        if (!text) break
        const q = apply(m, me.position.x, me.position.y)
        const h = (me.height > 0 ? me.height : 2.5) * scaleMag(m)
        // MTEXT の回転: 方向ベクトル(group 11)優先。group 50 は仕様上ラジアンだが
        // 度で書き出す CAD もあるため大きさで判別する
        let rot: number
        if (me.directionVector && (me.directionVector.x !== 0 || me.directionVector.y !== 0)) {
          rot = (Math.atan2(me.directionVector.y, me.directionVector.x) * 180) / Math.PI
        } else {
          const r0 = me.rotation ?? 0
          rot = Math.abs(r0) <= Math.PI * 2 ? (r0 * 180) / Math.PI : r0
        }
        ctx.prims.push({ type: 'text', x: q.x, y: q.y, text, height: h, rotationDeg: rot + rotationDegOf(m) })
        extend(ctx, q.x, q.y)
        extend(ctx, q.x, q.y + h)
        break
      }
      case 'INSERT': {
        const ie = e as IInsertEntity
        const name = ie.name
        if (!name) break
        const pos = ie.position ?? { x: 0, y: 0, z: 0 }
        const q = apply(m, pos.x, pos.y)
        extend(ctx, q.x, q.y)
        // 無名ブロック（寸法・ハッチング等の内部ブロック）は集計から除外
        if (!name.startsWith('*')) {
          ctx.counts[name] = (ctx.counts[name] ?? 0) + 1
          ;(ctx.insertPts[name] ??= []).push(q)
        }
        const block = ctx.blocks[name]
        if (block && Array.isArray(block.entities) && depth < 2) {
          const rad = ((ie.rotation ?? 0) * Math.PI) / 180
          const cos = Math.cos(rad)
          const sin = Math.sin(rad)
          const sx = ie.xScale ?? 1
          const sy = ie.yScale ?? 1
          // T(pos) ∘ R(rot) ∘ S(sx,sy)
          let local: Mat = {
            a: sx * cos,
            b: sx * sin,
            c: -sy * sin,
            d: sy * cos,
            e: pos.x,
            f: pos.y,
          }
          // ∘ T(-basePoint)
          const base = block.position
          if (base && (base.x !== 0 || base.y !== 0)) {
            local = mul(local, { a: 1, b: 0, c: 0, d: 1, e: -base.x, f: -base.y })
          }
          walkEntities(block.entities, mul(m, local), depth + 1, ctx)
        }
        break
      }
      default:
        break
    }
  }
}

/**
 * DXF テキストをパースして描画用シーンへ変換する。
 * LINE / LWPOLYLINE / POLYLINE / CIRCLE / ARC / TEXT / MTEXT / INSERT
 * （ブロック展開は2階層まで）に対応。
 * パースエラー・図形なしの場合は Error を throw する（呼び出し側で表示）。
 */
export function parseDxf(text: string): DxfScene {
  const parser = new DxfParser()
  let dxf: IDxf | null = null
  try {
    dxf = parser.parseSync(text)
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    throw new Error(`DXFの解析に失敗しました: ${msg}`)
  }
  if (!dxf) throw new Error('DXFの解析結果が空です。ファイル形式を確認してください。')

  const ctx: WalkCtx = {
    prims: [],
    counts: {},
    insertPts: {},
    blocks: dxf.blocks ?? {},
    b: { minX: 0, minY: 0, maxX: 0, maxY: 0, has: false },
  }

  const modelEntities = (dxf.entities ?? []).filter((e) => !e.inPaperSpace)
  walkEntities(modelEntities, IDENTITY, 0, ctx)

  if (ctx.prims.length === 0 && Object.keys(ctx.counts).length === 0) {
    throw new Error(
      '描画可能な図形（LINE / POLYLINE / CIRCLE / ARC / TEXT / INSERT）が見つかりませんでした。',
    )
  }
  if (!ctx.b.has) {
    ctx.b = { minX: 0, minY: 0, maxX: 100, maxY: 100, has: true }
  }

  return {
    entities: ctx.prims,
    bounds: { minX: ctx.b.minX, minY: ctx.b.minY, maxX: ctx.b.maxX, maxY: ctx.b.maxY },
    insertCounts: ctx.counts,
    insertPoints: ctx.insertPts,
  }
}

// ---------- 描画 ----------

/**
 * シーンをキャンバスへ描画する。
 * DXF は Y軸上向きのため、screenY = offsetY - y*scale で反転して描画する。
 * ctx には devicePixelRatio 分の setTransform を済ませた状態で渡すこと
 * （transform.scale / offset は CSS ピクセル基準）。
 */
export function drawScene(
  ctx: CanvasRenderingContext2D,
  scene: DxfScene,
  transform: { scale: number; offsetX: number; offsetY: number },
): void {
  const { scale, offsetX, offsetY } = transform
  const sx = (x: number) => x * scale + offsetX
  const sy = (y: number) => offsetY - y * scale

  ctx.save()
  ctx.lineWidth = 0.8
  ctx.strokeStyle = '#3c4854'
  ctx.fillStyle = '#5b6b7b'
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'

  for (const p of scene.entities) {
    switch (p.type) {
      case 'polyline': {
        if (p.points.length < 2) break
        ctx.beginPath()
        ctx.moveTo(sx(p.points[0].x), sy(p.points[0].y))
        for (let i = 1; i < p.points.length; i++) {
          ctx.lineTo(sx(p.points[i].x), sy(p.points[i].y))
        }
        if (p.closed) ctx.closePath()
        ctx.stroke()
        break
      }
      case 'circle': {
        const r = p.r * scale
        if (r < 0.15) break
        ctx.beginPath()
        ctx.arc(sx(p.cx), sy(p.cy), r, 0, Math.PI * 2)
        ctx.stroke()
        break
      }
      case 'arc': {
        const r = p.r * scale
        if (r < 0.15) break
        ctx.beginPath()
        // モデル空間の反時計回りは、Y反転後の画面では anticlockwise=true・角度符号反転
        ctx.arc(sx(p.cx), sy(p.cy), r, -p.startAngle, -p.endAngle, true)
        ctx.stroke()
        break
      }
      case 'text': {
        const px = p.height * scale
        if (px < 2.5) break // 読めない大きさの文字は省略（ズームで表示される）
        const size = Math.min(px, 400)
        ctx.save()
        ctx.translate(sx(p.x), sy(p.y))
        if (p.rotationDeg) ctx.rotate((-p.rotationDeg * Math.PI) / 180)
        ctx.font = `${size}px sans-serif`
        ctx.textBaseline = 'alphabetic'
        ctx.fillText(p.text, 0, 0)
        ctx.restore()
        break
      }
    }
  }
  ctx.restore()
}
