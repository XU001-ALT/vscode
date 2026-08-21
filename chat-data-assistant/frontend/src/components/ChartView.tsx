import { useEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { ChartRecommendation, Lang } from '../types'
import { t } from '../i18n'

interface Props {
  columns: string[]
  rows: unknown[][]
  recommendation: ChartRecommendation | null
  lang: Lang
}

type ChartType = 'line' | 'bar' | 'scatter' | 'pie'

function isNumericCol(rows: unknown[][], idx: number): boolean {
  return rows.some(r => r[idx] != null) &&
    rows.every(r => r[idx] == null || typeof r[idx] === 'number')
}

function toValues(rows: unknown[][], idx: number): (number | null)[] {
  return rows.map(r => (r[idx] == null ? null : Number(r[idx])))
}

const DARK_LAYOUT = {
  template: 'plotly_dark' as const,
  font: { family: 'Microsoft YaHei' },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(20,30,60,0.6)',
  legend: { orientation: 'h' as const, y: 1.12, x: 0.02 },
  margin: { l: 46, r: 20, t: 30, b: 40 },
}

const LIGHT_LAYOUT = {
  font: { family: 'Microsoft YaHei', color: '#1a2437' },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  legend: { orientation: 'h' as const, y: 1.12, x: 0.02 },
  margin: { l: 46, r: 20, t: 30, b: 40 },
}

export default function ChartView({ columns, rows, recommendation, lang }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [useRec, setUseRec] = useState(true)
  const [chartType, setChartType] = useState<ChartType>('line')
  const [xCol, setXCol] = useState('')
  const [yCols, setYCols] = useState<string[]>([])
  const [pieName, setPieName] = useState('')
  const [pieValue, setPieValue] = useState('')

  const numericCols = useMemo(
    () => columns.filter((_, i) => isNumericCol(rows, i)),
    [columns, rows],
  )

  useEffect(() => {
    if (recommendation) setUseRec(true)
  }, [recommendation])

  useEffect(() => {
    if (!xCol && columns.length) setXCol(columns[0])
    if (!yCols.length && numericCols.length) {
      setYCols(numericCols.filter(c => c !== xCol).slice(0, 1))
    }
    if (!pieName && columns.length) setPieName(columns[0])
    if (!pieValue && numericCols.length) setPieValue(numericCols[0])
  }, [columns, numericCols, xCol, yCols.length, pieName, pieValue])

  useEffect(() => {
    const el = chartRef.current
    if (!el || !columns.length) return

    let chart: ChartType
    let x: string
    let ys: string[]
    if (recommendation && useRec) {
      chart = recommendation.chart_type
      x = recommendation.x_col
      ys = [recommendation.y_col]
    } else if (chartType === 'pie') {
      chart = 'pie'
      x = pieName
      ys = [pieValue]
    } else {
      chart = chartType
      x = xCol
      ys = yCols
    }
    if (!x || !ys.length || !ys.every(c => columns.includes(c)) || !columns.includes(x)) return

    const xi = columns.indexOf(x)
    const layout: Record<string, unknown> = {
      ...(lang === 'zh' ? DARK_LAYOUT : LIGHT_LAYOUT),
      showlegend: ys.length > 1 || chart === 'pie',
    }
    let data: unknown[]

    if (chart === 'pie') {
      const vi = columns.indexOf(ys[0])
      data = [{
        type: 'pie',
        labels: rows.map(r => String(r[xi] ?? '')),
        values: toValues(rows, vi),
        textinfo: 'label+percent',
      }]
    } else {
      data = ys.map(y => ({
        type: chart === 'scatter' ? 'scatter' : chart,
        mode: chart === 'line' ? 'lines+markers' : 'markers',
        x: rows.map(r => r[xi]),
        y: toValues(rows, columns.indexOf(y)),
        name: y,
      }))
    }

    Plotly.react(el, data, layout, { responsive: true, displayModeBar: false })
    return () => Plotly.purge(el)
  }, [columns, rows, recommendation, useRec, chartType, xCol, yCols, pieName, pieValue, lang])

  if (!columns.length) {
    return <div className="msg info">{t('no_chart', lang)}</div>
  }

  const recValid = recommendation &&
    columns.includes(recommendation.x_col) && columns.includes(recommendation.y_col)

  return (
    <div>
      {recValid && (
        <>
          <label className="chart-controls">
            <input type="checkbox" checked={useRec} onChange={e => setUseRec(e.target.checked)} />
            {t('use_ai_rec', lang)}
          </label>
          {useRec && recommendation.reason && (
            <div className="rec-reason">{t('ai_reason', lang)}{recommendation.reason}</div>
          )}
        </>
      )}

      {!(recValid && useRec) && (
        <div className="chart-controls">
          <label>
            {t('chart_type_manual', lang)}
            <select value={chartType} onChange={e => setChartType(e.target.value as ChartType)}>
              {(['line', 'bar', 'scatter', 'pie'] as ChartType[]).map(ct => (
                <option key={ct} value={ct}>{t(ct, lang)}</option>
              ))}
            </select>
          </label>

          {chartType === 'pie' ? (
            <>
              <label>
                {t('category', lang)}
                <select value={pieName} onChange={e => setPieName(e.target.value)}>
                  {columns.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('value', lang)}
                <select value={pieValue} onChange={e => setPieValue(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              {!numericCols.length && <span className="hint-err">{t('no_numeric_pie', lang)}</span>}
            </>
          ) : (
            <>
              <label>
                {t('x_axis', lang)}
                <select value={xCol} onChange={e => setXCol(e.target.value)}>
                  {columns.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('y_axis_multi', lang)}
                <select
                  multiple
                  value={yCols}
                  onChange={e => setYCols(Array.from(e.target.selectedOptions, o => o.value))}
                >
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              {!numericCols.length && <span className="hint-err">{t('no_numeric', lang)}</span>}
            </>
          )}
        </div>
      )}

      <div ref={chartRef} style={{ width: '100%', minHeight: 320 }} />
    </div>
  )
}
