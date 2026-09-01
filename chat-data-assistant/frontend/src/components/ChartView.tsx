import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { ChartRecommendation, ChartType, Lang } from '../types'
import { t } from '../i18n'

interface Props {
  columns: string[]
  rows: unknown[][]
  recommendation: ChartRecommendation | null
  lang: Lang
}

// 品牌色板：科技蓝 → 青 → 紫，与界面深蓝主题呼应
const PALETTE = [
  '#4f8ef7', '#2dd4bf', '#a78bfa', '#fbbf24',
  '#fb7185', '#34d399', '#60a5fa', '#f472b6',
]

const FONT = 'Microsoft YaHei'

// 气泡/平行坐标用渐变色带（紫 → 蓝 → 青 → 绿 → 黄 → 橙）
const BUBBLE_COLORSCALE = [
  [0, '#30123b'], [0.18, '#4668d8'], [0.4, '#2fc6c4'],
  [0.62, '#7be141'], [0.82, '#f7d23e'], [1, '#f15a24'],
]

// 手动绘图器图型顺序（与甲方升级版要求一致，旧类型保留以不改变原功能）
const CHART_ORDER: ChartType[] = [
  'bubble', 'scatter3d', 'heatmap', 'parallel', 'box', 'radar',
  'line', 'bar', 'scatter', 'pie', 'area', 'histogram',
]

// 渲染时自动使用全部数值列、不需要显式 y 的图表
const AUTO_COL_CHARTS: ChartType[] = ['heatmap', 'parallel', 'radar']

function isNumericCol(rows: unknown[][], idx: number): boolean {
  return rows.some(r => r[idx] != null) &&
    rows.every(r => r[idx] == null || typeof r[idx] === 'number')
}

function toValues(rows: unknown[][], idx: number): (number | null)[] {
  return rows.map(r => (r[idx] == null ? null : Number(r[idx])))
}

function toNumber(v: unknown): number | null {
  return v == null || v === '' ? null : Number(v)
}

function buildLayout(lang: Lang, xTitle: string, yTitle: string): Record<string, unknown> {
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
      ...(xTitle ? { title: { text: xTitle, font: { size: 13 }, standoff: 10 } } : {}),
    },
    yaxis: {
      gridcolor: dark ? 'rgba(148,163,184,0.10)' : 'rgba(15,23,42,0.07)',
      linecolor: dark ? 'rgba(148,163,184,0.30)' : 'rgba(15,23,42,0.22)',
      zeroline: false,
      tickfont: { size: 11.5 },
      automargin: true,
      ...(yTitle ? { title: { text: yTitle, font: { size: 13 }, standoff: 8 } } : {}),
    },
    bargap: 0.35,
  }
}

interface PlotConfig {
  x: string
  ys: string[]
  z: string
  size: string
  color: string
}

function buildPlotData(
  chart: ChartType,
  columns: string[],
  rows: unknown[][],
  numericCols: string[],
  cfg: PlotConfig,
  lang: Lang,
): { data: unknown[]; layout: Record<string, unknown> } {
  const xi = columns.indexOf(cfg.x)
  const dark = lang === 'zh'
  const xTitle = cfg.x || ''
  const yTitle = cfg.ys.join(' / ') || (chart === 'histogram' ? t('hist_y_axis', lang) : '')
  const layout: Record<string, unknown> = { ...buildLayout(lang, xTitle, yTitle) }
  const data: unknown[] = []
  let legend = false

  if (!rows.length) return { data: [], layout }

  if (chart === 'pie') {
    const vi = cfg.ys.length ? columns.indexOf(cfg.ys[0]) : -1
    const rawLabels: string[] = rows.map(r => String(r[xi] ?? ''))
    const rawValues: (number | null)[] = vi >= 0 ? toValues(rows, vi) : rows.map(() => 0)
    const pairs = rawLabels.map((l, i) => ({ label: l || '(空)', value: rawValues[i] ?? 0 }))
    pairs.sort((a, b) => b.value - a.value)
    const MAX_SLICES = 7
    let slices: { label: string; value: number }[]
    if (pairs.length > MAX_SLICES) {
      const main = pairs.slice(0, MAX_SLICES - 1)
      const otherSum = pairs.slice(MAX_SLICES - 1).reduce((s, p) => s + p.value, 0)
      slices = [...main, { label: '其他', value: otherSum }]
    } else {
      slices = pairs
    }
    const total = slices.reduce((s, p) => s + p.value, 0) || 1
    data.push({
      type: 'pie',
      labels: slices.map(s => s.label),
      values: slices.map(s => s.value),
      hole: 0.48,
      sort: false,
      marker: { colors: PALETTE, line: { color: 'rgba(0,0,0,0)', width: 0 } },
      textinfo: 'label+percent',
      textposition: slices.length <= 5 ? 'inside' : 'outside',
      textfont: { family: FONT, size: slices.length <= 5 ? 13 : 11 },
      insidetextorientation: 'horizontal',
      automargin: true,
      pull: slices.map(s => s.value / total < 0.05 ? 0.06 : 0),
      hovertemplate: '%{label}<br>%{value} (%{percent})<extra></extra>',
    })
    layout.showlegend = true
    return { data, layout }
  }

  if (chart === 'histogram') {
    data.push({
      type: 'hist',
      x: rows.map(r => r[xi]),
      name: cfg.x,
      marker: { color: PALETTE[0] },
      hovertemplate: `${cfg.x}: %{x}<br>${t('hist_y_axis', lang)}: %{y}<extra></extra>`,
    })
    return { data, layout }
  }

  if (chart === 'bubble') {
    const yi = cfg.ys.length ? columns.indexOf(cfg.ys[0]) : -1
    const si = cfg.size ? columns.indexOf(cfg.size) : -1
    const ci = cfg.color ? columns.indexOf(cfg.color) : -1
    const sizes = si >= 0 ? toValues(rows, si).map(v => v ?? 0) : []
    const smin = sizes.length ? Math.min(...sizes) : 0
    const smax = sizes.length ? Math.max(...sizes) : 1
    data.push({
      type: 'scatter',
      mode: 'markers',
      x: toValues(rows, xi),
      y: yi >= 0 ? toValues(rows, yi) : [],
      marker: {
        size: si >= 0 ? sizes.map(v => 8 + 34 * (smax - smin ? (v - smin) / (smax - smin) : 0.5)) : 20,
        color: ci >= 0 ? toValues(rows, ci) : PALETTE[1],
        colorscale: ci >= 0 ? BUBBLE_COLORSCALE : undefined,
        showscale: ci >= 0,
        colorbar: ci >= 0 ? { title: cfg.color, thickness: 13 } : undefined,
        line: { color: 'rgba(255,255,255,0.55)', width: 1 },
        opacity: 0.86,
      },
      hovertemplate: `${cfg.x}: %{x}<br>${cfg.ys[0] ?? ''}: %{y}<extra></extra>`,
    })
    return { data, layout }
  }

  if (chart === 'scatter3d') {
    const yi = cfg.ys.length ? columns.indexOf(cfg.ys[0]) : -1
    const otherCols = numericCols.filter(c => c !== cfg.x && (yi < 0 || c !== cfg.ys[0]))
    const zh = cfg.z || otherCols[0] || ''
    const zi = zh ? columns.indexOf(zh) : -1
    layout.scene = {
      xaxis: { title: cfg.x, gridcolor: dark ? 'rgba(148,163,184,0.12)' : 'rgba(15,23,42,0.08)' },
      yaxis: { title: cfg.ys[0] ?? '', gridcolor: dark ? 'rgba(148,163,184,0.12)' : 'rgba(15,23,42,0.08)' },
      zaxis: { title: zh, gridcolor: dark ? 'rgba(148,163,184,0.12)' : 'rgba(15,23,42,0.08)' },
      bgcolor: 'rgba(0,0,0,0)',
    }
    layout.margin = { l: 10, r: 10, t: 34, b: 10 }
    data.push({
      type: 'scatter3d',
      mode: 'markers',
      x: toValues(rows, xi),
      y: yi >= 0 ? toValues(rows, yi) : [],
      z: zi >= 0 ? toValues(rows, zi) : [],
      marker: { size: 6, color: PALETTE[0], opacity: 0.88 },
      hovertemplate: `${cfg.x}: %{x}<br>${cfg.ys[0] ?? ''}: %{y}<br>${zh}: %{z}<extra></extra>`,
    })
    return { data, layout }
  }

  if (chart === 'heatmap') {
    const idxA = numericCols.map(c => columns.indexOf(c))
    const corr = (a: number, b: number) => {
      const av = rows.reduce((n, r) => n + (toNumber(r[a]) ?? 0), 0) / rows.length
      const bv = rows.reduce((n, r) => n + (toNumber(r[b]) ?? 0), 0) / rows.length
      const num = rows.reduce((n, r) => n + (toNumber(r[a]) ?? 0 - av) * (toNumber(r[b]) ?? 0 - bv), 0)
      const da = Math.sqrt(rows.reduce((n, r) => n + ((toNumber(r[a]) ?? 0) - av) ** 2, 0))
      const db = Math.sqrt(rows.reduce((n, r) => n + ((toNumber(r[b]) ?? 0) - bv) ** 2, 0))
      return +(num / (da * db || 1)).toFixed(2)
    }
    const z = numericCols.map((_, i) => numericCols.map((_, j) => corr(idxA[i], idxA[j])))
    data.push({
      type: 'heatmap',
      z,
      x: numericCols,
      y: numericCols,
      zmin: -1,
      zmax: 1,
      colorscale: [[0, '#4456a6'], [0.5, '#f4f6fb'], [1, '#e05750']],
      colorbar: { thickness: 13 },
      texttemplate: '%{z:.2f}',
      hovertemplate: '%{y} × %{x}: %{z:.2f}<extra></extra>',
    })
    layout.margin = { l: 120, r: 24, t: 40, b: 120 }
    layout.xaxis = { ...(layout.xaxis as Record<string, unknown>), tickangle: -30 }
    layout.yaxis = { ...(layout.yaxis as Record<string, unknown>) }
    return { data, layout }
  }

  if (chart === 'parallel') {
    const dimensions = numericCols.map(c => ({
      label: c,
      values: rows.map(r => toNumber(r[columns.indexOf(c)])),
    }))
    const lineVals = numericCols.length ? rows.map(r => toNumber(r[columns.indexOf(numericCols[0])]) ?? 0) : []
    data.push({
      type: 'parcoords',
      line: {
        color: lineVals,
        colorscale: BUBBLE_COLORSCALE,
        showscale: true,
        colorbar: { title: numericCols[0] ?? '', thickness: 13 },
      },
      dimensions,
    })
    layout.margin = { l: 70, r: 46, t: 40, b: 30 }
    return { data, layout }
  }

  if (chart === 'box') {
    const yi = cfg.ys.length ? columns.indexOf(cfg.ys[0]) : -1
    const groups: { name: string; rows: unknown[][] }[] = []
    const seen = new Set<string>()
    for (const r of rows) {
      const g = String(r[xi] ?? '(空)')
      if (!seen.has(g)) {
        seen.add(g)
        groups.push({ name: g, rows: [] })
      }
      groups[groups.length - 1].rows.push(r)
    }
    for (const g of groups) {
      data.push({
        type: 'box',
        name: g.name,
        y: g.rows.map(r => toNumber(r[yi])),
        boxpoints: 'all',
        jitter: 0.35,
        pointpos: 0,
        marker: { size: 4.5, opacity: 0.75 },
        line: { width: 1.6 },
      })
    }
    layout.showlegend = true
    layout.xaxis = { ...(layout.xaxis as Record<string, unknown>), title: { text: cfg.x, font: { size: 13 } } }
    layout.yaxis = { ...(layout.yaxis as Record<string, unknown>), title: { text: cfg.ys[0] ?? '', font: { size: 13 } } }
    layout.margin = { l: 52, r: 24, t: 34, b: 44 }
    return { data, layout }
  }

  if (chart === 'radar') {
    const nameCol = columns.find(c => !numericCols.includes(c))
    const nameIdx = nameCol ? columns.indexOf(nameCol) : -1
    const entries = rows.slice(0, Math.min(6, rows.length))
    const norm = (vals: number[]) => {
      const lo = Math.min(...vals)
      const hi = Math.max(...vals)
      return vals.map(v => (hi - lo ? ((v - lo) / (hi - lo)) * 100 : 50))
    }
    const perRow: number[][] = entries.map(r => numericCols.map(c => toNumber(r[columns.indexOf(c)]) ?? 0))
    const normalized = numericCols.map((_, i) => norm(perRow.map(vals => vals[i])))
    for (let ei = 0; ei < entries.length; ei++) {
      const label = nameIdx >= 0 ? String(entries[ei][nameIdx] ?? '') : `#${ei + 1}`
      data.push({
        type: 'scatterpolar',
        mode: 'lines+markers',
        fill: 'toself',
        name: label || `#${ei + 1}`,
        r: numericCols.map((_, i) => normalized[i][ei]),
        theta: numericCols,
        line: { width: 1.6 },
        marker: { size: 4 },
        hovertemplate: `%{theta}: %{r:.1f}<extra>${label || ''}</extra>`,
      })
    }
    layout.showlegend = true
    layout.polar = {
      radialaxis: { visible: true, range: [0, 100], gridcolor: dark ? 'rgba(148,163,184,0.18)' : 'rgba(15,23,42,0.10)' },
      bgcolor: 'rgba(0,0,0,0)',
    }
    layout.margin = { l: 70, r: 70, t: 40, b: 46 }
    return { data, layout }
  }

  // line / bar / scatter / area：多 Y 数值列
  const multiYs = (cfg.ys.length ? cfg.ys : numericCols.slice(0, 1))
  for (const y of multiYs) {
    const yi = columns.indexOf(y)
    if (yi < 0) continue
    data.push({
      type: chart === 'bar' ? 'bar' : 'scatter',
      mode: chart === 'scatter' ? 'markers' : 'lines+markers',
      x: rows.map(r => r[xi]),
      y: toValues(rows, yi),
      name: y,
      ...((chart === 'line' || chart === 'area')
        ? {
            line: { shape: 'spline', smoothing: 0.75, width: 2.5 },
            marker: { size: 6 },
          }
        : chart === 'scatter'
          ? { marker: { size: 7, opacity: 0.85 } }
          : chart === 'bar'
            ? { marker: { line: { width: 0 } } }
            : {}),
      ...(chart === 'area'
        ? { fill: 'tozeroy', fillcolor: 'rgba(79,142,247,0.18)' }
        : {}),
      hovertemplate: `${cfg.x}: %{x}<br>${y}: %{y}<extra></extra>`,
    })
  }
  layout.showlegend = multiYs.length > 1 || legend
  return { data, layout }
}

export default function ChartView({ columns, rows, recommendation, lang }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [useRec, setUseRec] = useState(true)
  const [chartType, setChartType] = useState<ChartType>('bubble')
  const [xCol, setXCol] = useState('')
  const [yCols, setYCols] = useState<string[]>([])
  const [zCol, setZCol] = useState('')
  const [sizeCol, setSizeCol] = useState('')
  const [colorCol, setColorCol] = useState('')
  const [pieName, setPieName] = useState('')
  const [pieValue, setPieValue] = useState('')
  const [histCol, setHistCol] = useState('')

  // 通用筛选：数值列范围 + 类别列多选（"所有图形均可继续筛选"）
  const [filterCol, setFilterCol] = useState('')
  const [rangeMin, setRangeMin] = useState<number | null>(null)
  const [rangeMax, setRangeMax] = useState<number | null>(null)
  const [catSel, setCatSel] = useState<string[]>([])

  const numericCols = useMemo(
    () => columns.filter((_, i) => isNumericCol(rows, i)),
    [columns, rows],
  )
  const catCols = useMemo(
    () => columns.filter(c => !numericCols.includes(c)),
    [columns, numericCols],
  )

  // 手动绘图数据表导出功能
  const downloadPng = useCallback(() => {
    const el = chartRef.current
    if (!el) return
    // plotly.js-dist-min 类型未暴露 downloadImage，这里运行时方法存在
    ;(Plotly as unknown as { downloadImage: (el: HTMLElement, opts: {
      format: string; height: number; width: number; scale: number; filename: string
    }) => void }).downloadImage(el, {
      format: 'png', height: 750, width: 1300, scale: 1, filename: 'chat-data-chart',
    })
  }, [])

  // 重置所有坐标/筛选控件到默认值（columns 变化时 + 工具栏重置按钮复用）
  const resetControls = useCallback(() => {
    setChartType('bubble')
    setXCol(columns[0] ?? '')
    setYCols(numericCols.slice(0, 1))
    setZCol(numericCols[2] ?? numericCols[1] ?? columns[0] ?? '')
    setSizeCol(numericCols[1] ?? numericCols[0] ?? '')
    setColorCol(numericCols[0] ?? '')
    setPieName(columns[0] ?? '')
    setPieValue(numericCols[0] ?? '')
    setHistCol(numericCols[0] ?? '')
    setFilterCol('')
    setRangeMin(null)
    setRangeMax(null)
    setCatSel([])
    setUseRec(true)
  }, [columns, numericCols])

  // 数据集变化时重置默认坐标选择
  useEffect(() => {
    resetControls()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columns])

  const catOptions = useMemo(() => {
    if (!columns.length || !filterCol || numericCols.includes(filterCol)) return []
    const i = columns.indexOf(filterCol)
    return [...new Set(rows.map(r => String(r[i] ?? '')))]
  }, [columns, rows, filterCol, numericCols])

  // 数据集变化时重置默认坐标选择
  useEffect(() => {
    if (recommendation) setUseRec(true)
  }, [recommendation])

  // 按筛选列过滤数据
  const filteredRows = useMemo(() => {
    if (!filterCol) return rows
    const i = columns.indexOf(filterCol)
    if (i < 0) return rows
    if (numericCols.includes(filterCol)) {
      const lo = rangeMin ?? -Infinity
      const hi = rangeMax ?? Infinity
      return rows.filter(r => {
        const v = toNumber(r[i])
        return v == null || (v >= lo && v <= hi)
      })
    }
    if (!catSel.length) return rows
    const set = new Set(catSel)
    return rows.filter(r => set.has(String(r[i] ?? '')))
  }, [rows, columns, filterCol, rangeMin, rangeMax, catSel, numericCols])

  const recValid = recommendation && (
    recommendation.chart_type === 'histogram'
      ? columns.includes(recommendation.x_col)
      : AUTO_COL_CHARTS.includes(recommendation.chart_type)
        ? columns.includes(recommendation.x_col)
        : columns.includes(recommendation.x_col) && columns.includes(recommendation.y_col)
  )

  useEffect(() => {
    const el = chartRef.current
    if (!el || !columns.length) return

    let chart: ChartType
    let cfg: PlotConfig
    if (recValid && useRec && recommendation) {
      chart = recommendation.chart_type
      cfg = {
        x: recommendation.x_col,
        ys: recommendation.y_col ? [recommendation.y_col] : [],
        z: recommendation.z_col || '',
        size: recommendation.y_col || sizeCol,
        color: colorCol,
      }
    } else {
      chart = chartType
      if (chart === 'pie') {
        cfg = { x: pieName, ys: [pieValue], z: '', size: '', color: '' }
      } else if (chart === 'histogram') {
        cfg = { x: histCol, ys: [], z: '', size: '', color: '' }
      } else {
        cfg = { x: xCol, ys: yCols, z: zCol, size: sizeCol, color: colorCol }
      }
    }

    // 必要坐标缺失时跳过渲染
    const needX = chart !== 'pie' || !!cfg.x
    if (!needX || (xiMissing(cfg, chart, columns))) return

    const { data, layout } = buildPlotData(chart, columns, filteredRows, numericCols, cfg, lang)
    if (!data.length) return

    Plotly.react(el, data, layout, {
      responsive: true,
      displayModeBar: 'hover',
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
      toImageButtonOptions: { format: 'png', scale: 2, filename: 'chat-data-chart' },
    })
    return () => Plotly.purge(el)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columns, rows, filteredRows, recommendation, useRec, chartType, xCol, yCols, zCol, sizeCol, colorCol, pieName, pieValue, histCol, filterCol, rangeMin, rangeMax, catSel, lang])

  if (!columns.length) {
    return <div className="msg info">{t('no_chart', lang)}</div>
  }

  const showManual = !(recValid && useRec)
  const filterIsNumeric = !!(filterCol && numericCols.includes(filterCol))

  return (
    <div className="chart-view">
      {/* 工具栏：重置 / 导出 PNG */}
      <div className="result-actions">
        <button className="btn-outline" onClick={resetControls}>{t('reset', lang)}</button>
        <button className="btn-outline" onClick={downloadPng}>{t('export_png', lang)}</button>
      </div>

      <div className="chart-view-body">
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

      {/* 通用筛选：所有图型共用 */}
      <div className="chart-controls filter-row">
        <label>
          {t('filter_by', lang)}
          <select
            value={filterCol}
            onChange={e => {
              const v = e.target.value
              setFilterCol(v)
              setRangeMin(null)
              setRangeMax(null)
              setCatSel([])
            }}
          >
            <option value="">{t('filter_range_all', lang)}</option>
            {numericCols.map(c => <option key={c} value={c}>{c}</option>)}
            {catCols.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        {filterIsNumeric && (() => {
          const i = columns.indexOf(filterCol)
          const vals = rows.map(r => toNumber(r[i])).filter((v): v is number => v != null)
          const lo = rangeMin ?? (vals.length ? Math.min(...vals) : 0)
          const hi = rangeMax ?? (vals.length ? Math.max(...vals) : 0)
          return (
            <>
              <label>
                {t('filter_range', lang)}
                <input
                  type="number"
                  value={lo}
                  onChange={e => setRangeMin(e.target.value === '' ? null : Number(e.target.value))}
                />
              </label>
              <span className="filter-sep">~</span>
              <input
                type="number"
                value={hi}
                onChange={e => setRangeMax(e.target.value === '' ? null : Number(e.target.value))}
              />
            </>
          )
        })()}

        {filterCol && !filterIsNumeric && catOptions.length > 0 && (
          <label>
            {t('value', lang)}
            <select
              multiple
              value={catSel}
              onChange={e => setCatSel(Array.from(e.target.selectedOptions, o => o.value))}
            >
              {catOptions.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
        )}

        {filterCol && (
          <button className="filter-clear" onClick={() => { setFilterCol(''); setRangeMin(null); setRangeMax(null); setCatSel([]) }}>
            {t('filter_clear', lang)}
          </button>
        )}
      </div>

      {showManual && (
        <div className="chart-controls">
          <label>
            {t('chart_type_manual', lang)}
            <select value={chartType} onChange={e => setChartType(e.target.value as ChartType)}>
              {CHART_ORDER.map(ct => (
                <option key={ct} value={ct}>{t(ct, lang)}</option>
              ))}
            </select>
          </label>

          {chartType === 'pie' && (
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
          )}

          {chartType === 'histogram' && (
            <>
              <label>
                {t('value', lang)}
                <select value={histCol} onChange={e => setHistCol(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              {!numericCols.length && <span className="hint-err">{t('no_numeric', lang)}</span>}
            </>
          )}

          {/* 自动多列型：heatmap / parallel / radar 自动使用全部数值列 */}
          {AUTO_COL_CHARTS.includes(chartType) && (
            <span className="hint-ok">
              {chartType === 'heatmap'
                ? t('heatmap_hint', lang)
                : chartType === 'parallel'
                  ? t('parallel_hint', lang)
                  : t('radar_hint', lang)}
            </span>
          )}

          {/* 双轴型 */}
          {(chartType === 'line' || chartType === 'bar' || chartType === 'scatter' || chartType === 'area') && (
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

          {chartType === 'box' && (
            <>
              <label>
                {t('x_axis', lang)}
                <select value={xCol} onChange={e => setXCol(e.target.value)}>
                  {columns.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('y_axis_multi', lang)}
                <select value={yCols[0] ?? ''} onChange={e => setYCols([e.target.value])}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
            </>
          )}

          {chartType === 'bubble' && (
            <>
              <label>
                {t('x_axis', lang)}
                <select value={xCol} onChange={e => setXCol(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('y_axis_multi', lang)}
                <select value={yCols[0] ?? ''} onChange={e => setYCols([e.target.value])}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('size_field', lang)}
                <select value={sizeCol} onChange={e => setSizeCol(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('color_field', lang)}
                <select value={colorCol} onChange={e => setColorCol(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
            </>
          )}

          {chartType === 'scatter3d' && (
            <>
              <label>
                {t('x_axis', lang)}
                <select value={xCol} onChange={e => setXCol(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('y_axis_multi', lang)}
                <select value={yCols[0] ?? ''} onChange={e => setYCols([e.target.value])}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>
                {t('z_axis', lang)}
                <select value={zCol} onChange={e => setZCol(e.target.value)}>
                  {numericCols.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
            </>
          )}
        </div>
      )}

      <div ref={chartRef} style={{ width: '100%', flex: 1, minHeight: 320 }} />
      </div>
    </div>
  )
}

function xiMissing(cfg: PlotConfig, chart: ChartType, columns: string[]): boolean {
  const xOk = !cfg.x || columns.includes(cfg.x)
  if (!xOk || chart === 'heatmap' || chart === 'parallel' || chart === 'radar' || chart === 'histogram') return !xOk
  if (chart === 'pie') return false
  const ysOk = cfg.ys.length > 0 && cfg.ys.every(y => columns.includes(y))
  if (!ysOk) return true
  if (chart === 'scatter3d') {
    const z = cfg.z || columns[0] || ''
    return !columns.includes(z)
  }
  return false
}