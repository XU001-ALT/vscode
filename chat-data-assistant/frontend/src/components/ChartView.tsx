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

// 品牌色板：科技蓝 → 青 → 紫，与界面深蓝主题呼应
const PALETTE = [
  '#4f8ef7', '#2dd4bf', '#a78bfa', '#fbbf24',
  '#fb7185', '#34d399', '#60a5fa', '#f472b6',
]

const FONT = 'Microsoft YaHei'

function isNumericCol(rows: unknown[][], idx: number): boolean {
  return rows.some(r => r[idx] != null) &&
    rows.every(r => r[idx] == null || typeof r[idx] === 'number')
}

function toValues(rows: unknown[][], idx: number): (number | null)[] {
  return rows.map(r => (r[idx] == null ? null : Number(r[idx])))
}

function buildLayout(lang: Lang): Record<string, unknown> {
  const dark = lang === 'zh'
  return {
    colorway: PALETTE,
    font: { family: FONT, color: dark ? '#dbe4ff' : '#1a2437', size: 12.5 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: dark ? 'rgba(20,30,60,0.45)' : 'rgba(0,0,0,0)',
    legend: { orientation: 'h', y: 1.14, x: 0, font: { size: 12 } },
    margin: { l: 52, r: 24, t: 34, b: 44 },
    transition: { duration: 350, easing: 'cubic-in-out' },
    hoverlabel: {
      bgcolor: dark ? 'rgba(17,24,48,0.94)' : 'rgba(255,255,255,0.97)',
      bordercolor: dark ? 'rgba(148,163,184,0.45)' : '#cbd5e1',
      font: { family: FONT, size: 12.5, color: dark ? '#e5ecff' : '#1a2437' },
    },
    xaxis: {
      gridcolor: dark ? 'rgba(148,163,184,0.10)' : 'rgba(15,23,42,0.07)',
      linecolor: dark ? 'rgba(148,163,184,0.30)' : 'rgba(15,23,42,0.22)',
      zeroline: false,
      tickfont: { size: 11.5 },
      automargin: true,
    },
    yaxis: {
      gridcolor: dark ? 'rgba(148,163,184,0.10)' : 'rgba(15,23,42,0.07)',
      linecolor: dark ? 'rgba(148,163,184,0.30)' : 'rgba(15,23,42,0.22)',
      zeroline: false,
      tickfont: { size: 11.5 },
      automargin: true,
    },
    bargap: 0.35,
  }
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
      ...buildLayout(lang),
      showlegend: ys.length > 1 || chart === 'pie',
    }
    let data: unknown[]

    if (chart === 'pie') {
      const vi = columns.indexOf(ys[0])
      data = [{
        type: 'pie',
        labels: rows.map(r => String(r[xi] ?? '')),
        values: toValues(rows, vi),
        hole: 0.55,
        marker: { colors: PALETTE, line: { color: 'rgba(0,0,0,0)', width: 0 } },
        textinfo: 'label+percent',
        textposition: 'outside',
        textfont: { family: FONT, size: 11.5 },
        automargin: true,
        hovertemplate: '%{label}<br>%{value} (%{percent})<extra></extra>',
      }]
    } else {
      data = ys.map(y => ({
        type: chart === 'scatter' ? 'scatter' : chart,
        mode: chart === 'line' ? 'lines+markers' : 'markers',
        x: rows.map(r => r[xi]),
        y: toValues(rows, columns.indexOf(y)),
        name: y,
        ...(chart === 'line'
          ? {
              line: { shape: 'spline', smoothing: 0.75, width: 2.5 },
              marker: { size: 6 },
            }
          : chart === 'scatter'
            ? { marker: { size: 7, opacity: 0.85 } }
            : {}),
        hovertemplate: `%{x} · ${y}: %{y}<extra></extra>`,
      }))
    }

    Plotly.react(el, data, layout, {
      responsive: true,
      displayModeBar: 'hover',
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
      toImageButtonOptions: { format: 'png', scale: 2, filename: 'chat-data-chart' },
    })
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

      <div ref={chartRef} style={{ width: '100%', height: 'clamp(320px, 56vh, 600px)' }} />
    </div>
  )
}
