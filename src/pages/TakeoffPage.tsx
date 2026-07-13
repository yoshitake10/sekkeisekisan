import { useRef, useState } from 'react'
import { useActiveProject, useStore } from '../store'
import type { DrawingMeta } from '../types'
import { genId } from '../utils/id'
import { num } from '../utils/format'
import PdfTakeoff from '../takeoff/PdfTakeoff'
import DxfTakeoff from '../takeoff/DxfTakeoff'

/**
 * 開いた図面ファイルの実体（module スコープで保持）。
 * store には DrawingMeta のみ保存し、File はタブ切替でも消えないようここに持つ。
 * ページ再読込で消えた場合は、同名ファイルを開き直すと同じ drawingId に再関連付けされる。
 */
const drawingFiles = new Map<string, File>()

function detectKind(fileName: string): DrawingMeta['kind'] | null {
  const ext = fileName.toLowerCase().split('.').pop()
  if (ext === 'pdf') return 'pdf'
  if (ext === 'dxf') return 'dxf'
  return null
}

export default function TakeoffPage() {
  const project = useActiveProject()
  const upsertDrawing = useStore((s) => s.upsertDrawing)
  const removeDrawing = useStore((s) => s.removeDrawing)

  const [selectedId, setSelectedId] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const drawings = project.drawings
  const selected = drawings.find((d) => d.id === selectedId) ?? drawings[0]
  const selectedFile = selected ? drawingFiles.get(selected.id) : undefined

  function measureCount(drawingId: string): number {
    return project.measurements.filter((m) => m.drawingId === drawingId).length
  }

  function openFiles(files: ArrayLike<File> | null | undefined) {
    if (!files || files.length === 0) return
    let lastId = ''
    const skipped: string[] = []
    for (const f of Array.from(files)) {
      const kind = detectKind(f.name)
      if (!kind) {
        skipped.push(f.name)
        continue
      }
      // 同名・同種の既存図面があれば同じ drawingId に再関連付け（測定が復元される）
      const existing = drawings.find((d) => d.fileName === f.name && d.kind === kind)
      let meta: DrawingMeta
      if (existing) {
        if (existing.fileSize !== undefined && existing.fileSize !== f.size) {
          const relink = confirm(
            `「${f.name}」は同名ですがファイルサイズが異なります。図面が改訂されている場合、保存済みのスケール・測定が図面と合わない可能性があります。既存の測定に関連付けますか？\n（キャンセルすると新規図面として登録します）`,
          )
          meta = relink
            ? { ...existing, fileSize: f.size }
            : { id: genId('dwg'), kind, fileName: f.name, fileSize: f.size }
        } else {
          meta = { ...existing, fileSize: f.size }
        }
      } else {
        meta = { id: genId('dwg'), kind, fileName: f.name, fileSize: f.size }
      }
      drawingFiles.set(meta.id, f)
      upsertDrawing(meta)
      lastId = meta.id
    }
    if (lastId) setSelectedId(lastId)
    if (skipped.length > 0) {
      alert('対応していない形式のためスキップしました（PDF / DXF のみ対応）:\n' + skipped.join('\n'))
    }
  }

  function onRemoveDrawing(d: DrawingMeta) {
    const n = measureCount(d.id)
    if (
      confirm(
        `図面「${d.fileName}」を削除しますか？\nこの図面の測定 ${n} 件もすべて削除されます。この操作は元に戻せません。`,
      )
    ) {
      removeDrawing(d.id)
      drawingFiles.delete(d.id)
      if (selectedId === d.id) setSelectedId('')
    }
  }

  const dropHandlers = {
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(true)
    },
    onDragLeave: () => setDragOver(false),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      openFiles(e.dataTransfer.files)
    },
  }

  return (
    <div>
      <div className="page-header">
        <h1>図面拾い（PDF / DXF）</h1>
        <div className="sub">
          平面図から機器台数・ダクト/配管長さ・面積を拾って数量表へ転記します。機器が描かれていない図面には「機器プロット」で機器選定の結果を配置し、台数の照合と配置検討ができます。ファイルはブラウザ内でのみ処理され、外部へは送信されません。
        </div>
      </div>

      <div className="card no-print">
        <h2>図面ファイル</h2>
        <div className="toolbar">
          <button className="btn primary" onClick={() => fileRef.current?.click()}>
            ファイルを開く（PDF / DXF）
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.dxf"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => {
              openFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <span className="muted small">
            図面ファイルはメモリ上にのみ保持されます。ページ再読込後は同名ファイルを開き直すと測定が再関連付けされます。
          </span>
        </div>

        {drawings.length > 0 && (
          <div className="toolbar" style={{ marginBottom: 8 }}>
            {drawings.map((d) => {
              const hasFile = drawingFiles.has(d.id)
              const isSel = selected?.id === d.id
              return (
                <span
                  key={d.id}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
                >
                  <button
                    className={'btn' + (isSel ? ' active' : '')}
                    onClick={() => setSelectedId(d.id)}
                    title={d.fileName}
                  >
                    <span className={'badge ' + (d.kind === 'pdf' ? 'blue' : 'purple')}>
                      {d.kind.toUpperCase()}
                    </span>{' '}
                    {d.fileName}
                    <span className="small">（測定{num(measureCount(d.id))}件）</span>
                    {!hasFile && <span className="badge orange">ファイル未読込</span>}
                  </button>
                  <button
                    className="btn small danger"
                    title="この図面と測定を削除"
                    onClick={() => onRemoveDrawing(d)}
                  >
                    ×
                  </button>
                </span>
              )
            })}
          </div>
        )}

        <div
          className={'drop-zone' + (dragOver ? ' over' : '')}
          style={drawings.length > 0 ? { padding: '10px 16px' } : undefined}
          onClick={() => fileRef.current?.click()}
          {...dropHandlers}
        >
          {drawings.length === 0 ? (
            <>
              ここに PDF・DXF の図面ファイルをドラッグ＆ドロップ
              <br />
              またはクリックしてファイルを選択
            </>
          ) : (
            '図面を追加: ここにドラッグ＆ドロップ / クリックで選択'
          )}
        </div>
      </div>

      {selected &&
        (selectedFile ? (
          selected.kind === 'pdf' ? (
            <PdfTakeoff key={selected.id} file={selectedFile} drawingId={selected.id} />
          ) : (
            <DxfTakeoff key={selected.id} file={selectedFile} drawingId={selected.id} />
          )
        ) : (
          <div className="card">
            <div className="note">
              「{selected.fileName}」のファイルデータがメモリにありません（ページ再読込などのため）。
              <br />
              ファイルを再度開いてください。上の「ファイルを開く」から同名ファイル（{selected.fileName}
              ）を開くと、保存済みの測定 {num(measureCount(selected.id))} 件と自動的に再関連付けされます。
            </div>
          </div>
        ))}
    </div>
  )
}
