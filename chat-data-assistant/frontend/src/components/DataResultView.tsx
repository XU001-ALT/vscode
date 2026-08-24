import type { Lang } from '../types'

interface Props {
  columns: string[]
  rows: unknown[][]
  lang: Lang
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number' && Number.isFinite(v)) {
    return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  return String(v)
}

/** 问数模式结果展示：服务端保证单行，渲染为回答框（单列突出数值，多列逐行列出） */
export default function DataResultView({ columns, rows }: Props) {
  if (!columns.length || rows.length !== 1) return null

  const row = rows[0]

  // 单列 → 列名作标题、数值放大展示；多列 → 逐行"列名: 值"
  if (columns.length === 1) {
    return (
      <div className="ai-answer">
        <div className="ai-answer-title">{columns[0]}</div>
        <div className="ai-answer-body data-value">{formatCell(row[0])}</div>
      </div>
    )
  }

  return (
    <div className="ai-answer">
      {columns.map((c, i) => (
        <div key={c} className="data-kv">
          <span className="data-kv-label">{c}</span>
          <span className="data-kv-value">{formatCell(row[i])}</span>
        </div>
      ))}
    </div>
  )
}
