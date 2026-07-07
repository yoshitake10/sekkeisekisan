// ============================================================
// 図面拾いモジュール間の契約
//  - PdfTakeoff.tsx / DxfTakeoff.tsx は TakeoffViewProps を受ける
//    default export の React コンポーネントとして実装する
//  - MeasurementPanel.tsx は MeasurementPanelProps を受ける
// ============================================================

export interface TakeoffViewProps {
  /** 開いたファイル（メモリ保持のみ。再読込時はユーザーが再度開く） */
  file: File
  /** store 上の DrawingMeta.id */
  drawingId: string
}

export interface MeasurementPanelProps {
  drawingId: string
  /** 表示中ページ（DXF は 0 固定） */
  pageIndex: number
  /** 選択中の測定ID（ハイライト表示用） */
  selectedId?: string
  onSelect?: (id: string) => void
}

/** 拾いツール種別（各ビューア内のツールバーで共通利用） */
export type TakeoffTool = 'pan' | 'scale' | 'count' | 'length' | 'area'

export const TOOL_LABELS: Record<TakeoffTool, string> = {
  pan: '移動/選択',
  scale: 'スケール設定',
  count: '個数カウント',
  length: '長さ拾い',
  area: '面積拾い',
}

/** 拾い対象の既定プリセット（label, category, unit） */
export const TAKEOFF_PRESETS: { label: string; category: string; unitName: string; kind: 'count' | 'length' | 'area' }[] = [
  { label: '室内機', category: '機器', unitName: '台', kind: 'count' },
  { label: '室外機', category: '機器', unitName: '台', kind: 'count' },
  { label: '換気扇・全熱交換器', category: '換気工事', unitName: '台', kind: 'count' },
  { label: '吹出口・吸込口', category: 'ダクト工事', unitName: '個', kind: 'count' },
  { label: '角ダクト', category: 'ダクト工事', unitName: 'm', kind: 'length' },
  { label: 'スパイラルダクト', category: 'ダクト工事', unitName: 'm', kind: 'length' },
  { label: '冷媒配管', category: '配管工事', unitName: 'm', kind: 'length' },
  { label: 'ドレン配管', category: '配管工事', unitName: 'm', kind: 'length' },
  { label: '部屋面積', category: 'その他', unitName: 'm2', kind: 'area' },
]
