// ============================================================
// 機器プロット（図面への機器配置）の共通ロジック
//  - 配置対象のリストは「機器選定」ページで登録した部屋と
//    その選定機種（手動選択があれば優先）から生成する
//  - プロットは Measurement(kind='plot') として保存する。
//    数量は機器選定→数量表転記が正のため、plot は数量表へ転記しない
// ============================================================

import type { DaikinModel, LoadUnit, Measurement, Project, Room } from '../types'
import { calcRoom, ventUnitCount } from '../logic/selection'
import { colorForIndex } from './geometry'

export interface PlotTarget {
  /** `${roomId}|${plotKind}` */
  key: string
  roomId: string
  plotKind: 'ac' | 'vent'
  room: Room
  /** 実際に使う機種（手動選択 > 推奨）。未確定の部屋は対象に含めない */
  model: DaikinModel
  /** 計画台数（機器選定の台数） */
  planned: number
  /** 表示ラベル 例: 事務室1 SZRC112BF */
  label: string
  /** 部屋ごとの色（空調・換気で同色） */
  color: string
}

export function plotTargetKey(roomId: string, plotKind: 'ac' | 'vent'): string {
  return `${roomId}|${plotKind}`
}

/**
 * 機器選定の部屋一覧からプロット対象を生成する。
 * 機種が確定している（推奨または手動選択が解決できる）ものだけを返す。
 */
export function buildPlotTargets(
  project: Project,
  loadUnits: LoadUnit[],
  models: DaikinModel[],
): PlotTarget[] {
  const targets: PlotTarget[] = []
  project.rooms.forEach((room, i) => {
    const calc = calcRoom(room, loadUnits, models)
    const roomName = room.name || `(無名${i + 1})`
    const color = colorForIndex(i)

    const acModel = models.find((m) => m.id === room.selectedModelId) ?? calc.recommendedModel
    if (calc.requiredCoolingKw > 0 && acModel) {
      targets.push({
        key: plotTargetKey(room.id, 'ac'),
        roomId: room.id,
        plotKind: 'ac',
        room,
        model: acModel,
        planned: calc.unitCount,
        label: `${roomName} ${acModel.modelNo}`,
        color,
      })
    }

    if (room.useErv && calc.requiredVentilationM3h > 0) {
      const ventModel =
        models.find((m) => m.id === room.selectedVentModelId) ?? calc.recommendedVentModel
      if (ventModel) {
        targets.push({
          key: plotTargetKey(room.id, 'vent'),
          roomId: room.id,
          plotKind: 'vent',
          room,
          model: ventModel,
          planned: ventUnitCount(calc.requiredVentilationM3h, ventModel),
          label: `${roomName} ${ventModel.modelNo}（換気）`,
          color,
        })
      }
    }
  })
  return targets
}

/** プロット測定のみ抽出 */
export function plotMeasurements(measurements: Measurement[]): Measurement[] {
  return measurements.filter((m) => m.kind === 'plot')
}

/** 対象キーごとの配置済み台数（プロジェクト全図面の合計） */
export function plottedCountByKey(measurements: Measurement[]): Map<string, number> {
  const map = new Map<string, number>()
  for (const m of plotMeasurements(measurements)) {
    if (!m.roomId || !m.plotKind) continue
    const key = plotTargetKey(m.roomId, m.plotKind)
    map.set(key, (map.get(key) ?? 0) + m.points.length)
  }
  return map
}

/** この図面・ページ上の対象キーのプロット測定を探す */
export function findPlotMeasurement(
  measurements: Measurement[],
  drawingId: string,
  pageIndex: number,
  target: Pick<PlotTarget, 'roomId' | 'plotKind'>,
): Measurement | undefined {
  return measurements.find(
    (m) =>
      m.kind === 'plot' &&
      m.drawingId === drawingId &&
      m.pageIndex === pageIndex &&
      m.roomId === target.roomId &&
      m.plotKind === target.plotKind,
  )
}

/**
 * プロットマーカーの描画（画面座標）。四角＋対角線の機器シンボル風。
 * PDF / DXF 両ビューアのオーバーレイ描画から共用する。
 */
export function drawPlotMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  color: string,
  selected: boolean,
): void {
  const r = selected ? 9 : 7
  ctx.beginPath()
  ctx.rect(x - r, y - r, r * 2, r * 2)
  ctx.fillStyle = color + '3a'
  ctx.fill()
  ctx.lineWidth = selected ? 2.5 : 1.8
  ctx.strokeStyle = color
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(x - r, y - r)
  ctx.lineTo(x + r, y + r)
  ctx.moveTo(x + r, y - r)
  ctx.lineTo(x - r, y + r)
  ctx.lineWidth = 1
  ctx.stroke()
}

/** 新規プロット測定の雛形（points は空。呼び出し側で id を設定して点を追加する） */
export function newPlotMeasurement(
  id: string,
  drawingId: string,
  pageIndex: number,
  target: PlotTarget,
): Measurement {
  return {
    id,
    drawingId,
    pageIndex,
    kind: 'plot',
    label: target.label,
    category: target.plotKind === 'ac' ? '機器' : '換気工事',
    unitName: '台',
    points: [],
    value: 0,
    color: target.color,
    spec: target.model.modelNo,
    roomId: target.roomId,
    modelId: target.model.id,
    plotKind: target.plotKind,
  }
}
