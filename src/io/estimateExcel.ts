// ============================================================
// 見積書 Excel 出力
//  - 「御見積書」シート: 表紙（宛名 / 件名 / 現場 / 見積金額(税込) /
//    内訳サマリ / 有効期限 / 支払条件 / 会社情報）
//  - 「内訳明細」シート: 分類・名称・規格・数量・単位・単価・金額と
//    小計 / 諸経費 / 法定福利費 / 出精値引 / 消費税 の集計行
//  金額セルは数値のまま出力する（Excel 側で再計算・書式設定できるように）
// ============================================================

import type { EstimateSettings, Project } from '../types'
import type { EstimateComputed } from '../logic/estimate'
import { itemAmountYen } from '../logic/estimate'
import { downloadXlsx } from './excel'
import { jpDate } from '../utils/format'

type Row = (string | number)[]

/** 集計行（直接工事費計〜税込合計）を生成する。pad: 金額列の手前に入れる空セル数 */
function summaryRows(computed: EstimateComputed, est: EstimateSettings, pad: number): Row[] {
  const blank = Array<string>(pad).fill('')
  const line = (label: string, value: number): Row => [label, ...blank, value]
  const rows: Row[] = [line('直接工事費 計', computed.directCost)]
  rows.push(line(`諸経費（直接工事費の${est.overheadRatePct}%）`, computed.overhead))
  if (computed.welfare !== 0) {
    rows.push(line(`法定福利費（直接工事費の${est.welfareRatePct}%）`, computed.welfare))
  }
  if (computed.rounding !== 0) {
    rows.push(line('出精値引（端数調整）', computed.rounding))
  }
  rows.push(line('税抜合計', computed.total))
  rows.push(line(`消費税（${est.taxRatePct}%）`, computed.tax))
  rows.push(line('御見積金額（税込）', computed.grandTotal))
  return rows
}

/** 表紙シート「御見積書」の行データ */
function coverRows(project: Project, computed: EstimateComputed, est: EstimateSettings): Row[] {
  const rows: Row[] = []
  rows.push(['御　見　積　書'])
  rows.push(['', '', '', `見積日：${jpDate()}`])
  rows.push([])
  rows.push([`${est.clientName}　${est.honorific}`.trim(), '', '', est.companyName])
  rows.push(['', '', '', est.companyAddress])
  rows.push(['', '', '', est.companyTel ? `TEL：${est.companyTel}` : ''])
  rows.push(['', '', '', est.personInCharge ? `担当：${est.personInCharge}` : ''])
  rows.push([])
  rows.push(['下記のとおり御見積り申し上げます。'])
  rows.push([])
  rows.push(['御見積金額（税込）', computed.grandTotal, '円'])
  rows.push([])
  rows.push(['件名', est.title])
  rows.push(['現場', project.siteName])
  rows.push(['工期', est.workPeriod])
  rows.push(['見積有効期限', est.validity])
  rows.push(['支払条件', est.paymentTerms])
  rows.push([])
  rows.push(['【内訳サマリ】'])
  rows.push(['分類', '金額（円）'])
  for (const sec of computed.sections) {
    rows.push([sec.category, sec.subtotal])
  }
  rows.push(...summaryRows(computed, est, 0))
  if (est.notes.trim() !== '') {
    rows.push([])
    rows.push(['備考', est.notes])
  }
  return rows
}

/** 内訳明細シートの行データ */
function detailRows(computed: EstimateComputed, est: EstimateSettings): Row[] {
  const rows: Row[] = []
  rows.push(['内訳明細'])
  rows.push(['分類', '名称', '規格', '数量', '単位', '単価（円）', '金額（円）'])
  for (const sec of computed.sections) {
    sec.items.forEach((q, i) => {
      rows.push([
        i === 0 ? sec.category : '',
        q.name,
        q.spec,
        q.quantity,
        q.unit,
        q.unitPriceYen ?? '',
        itemAmountYen(q),
      ])
    })
    rows.push([`【${sec.category}　小計】`, '', '', '', '', '', sec.subtotal])
  }
  rows.push(...summaryRows(computed, est, 5))
  return rows
}

/**
 * 「御見積書」（表紙）＋「内訳明細」の2シート構成でブックを生成し、
 * ブラウザからダウンロードする（完全クライアントサイド）。
 */
export function exportEstimateXlsx(
  project: Project,
  computed: EstimateComputed,
  est: EstimateSettings,
): void {
  downloadXlsx(`御見積書_${project.name || '無題'}.xlsx`, [
    {
      name: '御見積書',
      rows: coverRows(project, computed, est),
      colWidths: [24, 34, 8, 34],
    },
    {
      name: '内訳明細',
      rows: detailRows(computed, est),
      colWidths: [16, 34, 24, 10, 8, 14, 16],
    },
  ])
}
