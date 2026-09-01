import { useEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'

type Material = {
  id: string
  formula: string
  family: string
  capacity: number
  desorptionTemp: number
  absorptionTemp: number
  plateauPressure: number
  retention: number
  kinetics: number
  year: number
  catalyst: string
  pressure: number
  [key: string]: string | number
}

// 课题演示数据集（压缩包对标）：固体系储氢材料示意记录（非线上真实数据库）
const MATERIALS: Material[] = [
  { id: 'M001', formula: 'MgH₂', family: '镁基氢化物', capacity: 7.60, desorptionTemp: 365, absorptionTemp: 310, plateauPressure: 1.1, retention: 82.0, kinetics: 38, year: 2018, catalyst: '无', pressure: 5 },
  { id: 'M002', formula: 'MgH₂–5TiH₂', family: '镁基氢化物', capacity: 7.10, desorptionTemp: 248, absorptionTemp: 220, plateauPressure: 1.6, retention: 93.6, kinetics: 9, year: 2024, catalyst: '5 wt% TiH₂', pressure: 5 },
  { id: 'M003', formula: 'MgH₂–10Ni', family: '镁基氢化物', capacity: 6.45, desorptionTemp: 275, absorptionTemp: 235, plateauPressure: 1.8, retention: 90.8, kinetics: 12, year: 2022, catalyst: '10 wt% Ni', pressure: 5 },
  { id: 'M004', formula: 'MgH₂–Nb₂O₅', family: '镁基氢化物', capacity: 6.72, desorptionTemp: 238, absorptionTemp: 215, plateauPressure: 1.7, retention: 92.1, kinetics: 8, year: 2023, catalyst: '5 wt% Nb₂O₅', pressure: 5 },
  { id: 'M005', formula: 'MgH₂–VCl₃', family: '镁基氢化物', capacity: 6.38, desorptionTemp: 228, absorptionTemp: 205, plateauPressure: 1.9, retention: 89.7, kinetics: 7, year: 2021, catalyst: '3 wt% VCl₃', pressure: 5 },
  { id: 'M006', formula: 'Mg₂NiH₄', family: '镁基氢化物', capacity: 3.62, desorptionTemp: 285, absorptionTemp: 250, plateauPressure: 2.2, retention: 91.0, kinetics: 15, year: 2020, catalyst: 'Ni', pressure: 8 },
  { id: 'M007', formula: 'MgH₂–CNT', family: '镁基氢化物', capacity: 6.85, desorptionTemp: 252, absorptionTemp: 225, plateauPressure: 1.5, retention: 94.2, kinetics: 10, year: 2025, catalyst: '碳纳米管', pressure: 5 },
  { id: 'M008', formula: 'MgH₂–Ti₃C₂', family: '镁基氢化物', capacity: 6.91, desorptionTemp: 218, absorptionTemp: 198, plateauPressure: 2.0, retention: 95.1, kinetics: 6, year: 2025, catalyst: 'MXene', pressure: 5 },
  { id: 'M009', formula: 'LiBH₄', family: '复杂氢化物', capacity: 13.80, desorptionTemp: 410, absorptionTemp: 390, plateauPressure: 3.8, retention: 61.4, kinetics: 75, year: 2017, catalyst: '无', pressure: 10 },
  { id: 'M010', formula: 'LiBH₄/MgH₂', family: '复杂氢化物', capacity: 9.20, desorptionTemp: 178, absorptionTemp: 160, plateauPressure: 4.2, retention: 86.5, kinetics: 18, year: 2024, catalyst: '反应复合', pressure: 10 },
  { id: 'M011', formula: 'NaAlH₄–TiCl₃', family: '复杂氢化物', capacity: 5.10, desorptionTemp: 185, absorptionTemp: 145, plateauPressure: 4.8, retention: 84.0, kinetics: 14, year: 2019, catalyst: '4 mol% TiCl₃', pressure: 10 },
  { id: 'M012', formula: 'LiAlH₄', family: '复杂氢化物', capacity: 10.50, desorptionTemp: 205, absorptionTemp: 180, plateauPressure: 5.1, retention: 52.0, kinetics: 21, year: 2018, catalyst: '无', pressure: 8 },
  { id: 'M013', formula: 'KBH₄', family: '复杂氢化物', capacity: 7.40, desorptionTemp: 425, absorptionTemp: 400, plateauPressure: 3.4, retention: 66.5, kinetics: 90, year: 2016, catalyst: '无', pressure: 10 },
  { id: 'M014', formula: 'Ca(BH₄)₂', family: '复杂氢化物', capacity: 11.50, desorptionTemp: 360, absorptionTemp: 325, plateauPressure: 4.6, retention: 69.8, kinetics: 58, year: 2020, catalyst: 'TiF₃', pressure: 10 },
  { id: 'M015', formula: 'NH₃BH₃/SiO₂', family: '复杂氢化物', capacity: 9.60, desorptionTemp: 112, absorptionTemp: 95, plateauPressure: 1.2, retention: 58.0, kinetics: 4, year: 2023, catalyst: '介孔 SiO₂', pressure: 1 },
  { id: 'M016', formula: 'LiNH₂–LiH', family: '复杂氢化物', capacity: 6.50, desorptionTemp: 245, absorptionTemp: 210, plateauPressure: 3.2, retention: 80.2, kinetics: 20, year: 2021, catalyst: 'KH', pressure: 8 },
  { id: 'M017', formula: 'LaNi₅H₆', family: '储氢合金', capacity: 1.42, desorptionTemp: 85, absorptionTemp: 45, plateauPressure: 2.1, retention: 97.8, kinetics: 2, year: 2016, catalyst: '无', pressure: 3 },
  { id: 'M018', formula: 'TiFeH₁.₉', family: '储氢合金', capacity: 1.86, desorptionTemp: 92, absorptionTemp: 55, plateauPressure: 6.4, retention: 96.2, kinetics: 3, year: 2022, catalyst: 'Mn 调控', pressure: 10 },
  { id: 'M019', formula: 'ZrV₂H₅.₅', family: '储氢合金', capacity: 3.02, desorptionTemp: 138, absorptionTemp: 85, plateauPressure: 4.0, retention: 94.5, kinetics: 4, year: 2020, catalyst: '无', pressure: 8 },
  { id: 'M020', formula: 'TiCrMnH₂', family: '储氢合金', capacity: 1.92, desorptionTemp: 118, absorptionTemp: 70, plateauPressure: 7.2, retention: 95.8, kinetics: 3, year: 2024, catalyst: '多元合金', pressure: 10 },
  { id: 'M021', formula: 'MmNi₄.₅Al₀.₅', family: '储氢合金', capacity: 1.28, desorptionTemp: 78, absorptionTemp: 40, plateauPressure: 1.7, retention: 98.1, kinetics: 2, year: 2019, catalyst: 'Al 调控', pressure: 3 },
  { id: 'M022', formula: 'V₀.₆Ti₀.₂Cr₀.₂', family: '储氢合金', capacity: 3.60, desorptionTemp: 155, absorptionTemp: 95, plateauPressure: 5.8, retention: 93.0, kinetics: 5, year: 2023, catalyst: 'BCC 合金', pressure: 10 },
  { id: 'M023', formula: 'Mg₂FeH₆', family: '储氢合金', capacity: 5.45, desorptionTemp: 318, absorptionTemp: 280, plateauPressure: 2.8, retention: 87.5, kinetics: 24, year: 2021, catalyst: 'Fe', pressure: 8 },
  { id: 'M024', formula: 'Ti–V–Mn', family: '储氢合金', capacity: 2.48, desorptionTemp: 105, absorptionTemp: 65, plateauPressure: 8.1, retention: 96.7, kinetics: 3, year: 2025, catalyst: '高熵调控', pressure: 10 },
  { id: 'M025', formula: 'MOF-5', family: 'MOF/多孔材料', capacity: 4.50, desorptionTemp: 95, absorptionTemp: 25, plateauPressure: 35.0, retention: 88.0, kinetics: 1, year: 2017, catalyst: '无', pressure: 80 },
  { id: 'M026', formula: 'HKUST-1', family: 'MOF/多孔材料', capacity: 3.80, desorptionTemp: 88, absorptionTemp: 25, plateauPressure: 32.0, retention: 89.2, kinetics: 1, year: 2018, catalyst: 'Cu 节点', pressure: 80 },
  { id: 'M027', formula: 'MOF-177', family: 'MOF/多孔材料', capacity: 7.50, desorptionTemp: 82, absorptionTemp: 25, plateauPressure: 40.0, retention: 85.6, kinetics: 1, year: 2019, catalyst: '无', pressure: 100 },
  { id: 'M028', formula: 'UiO-66-NH₂', family: 'MOF/多孔材料', capacity: 2.90, desorptionTemp: 110, absorptionTemp: 30, plateauPressure: 28.0, retention: 92.4, kinetics: 2, year: 2023, catalyst: '氨基修饰', pressure: 80 },
  { id: 'M029', formula: 'MIL-101(Cr)', family: 'MOF/多孔材料', capacity: 5.10, desorptionTemp: 102, absorptionTemp: 25, plateauPressure: 36.0, retention: 91.3, kinetics: 1, year: 2022, catalyst: 'Cr 节点', pressure: 100 },
  { id: 'M030', formula: 'COF-301', family: 'MOF/多孔材料', capacity: 5.82, desorptionTemp: 98, absorptionTemp: 25, plateauPressure: 42.0, retention: 90.1, kinetics: 1, year: 2024, catalyst: '共价骨架', pressure: 100 },
  { id: 'M031', formula: 'Pd/AC', family: 'MOF/多孔材料', capacity: 2.15, desorptionTemp: 135, absorptionTemp: 40, plateauPressure: 12.0, retention: 94.0, kinetics: 2, year: 2021, catalyst: 'Pd 溢流', pressure: 30 },
  { id: 'M032', formula: 'B-doped graphene', family: 'MOF/多孔材料', capacity: 3.95, desorptionTemp: 125, absorptionTemp: 35, plateauPressure: 25.0, retention: 93.5, kinetics: 2, year: 2025, catalyst: 'B 掺杂', pressure: 50 },
]

const CYCLE_DATA = MATERIALS.flatMap((m, mi) => [1, 5, 10, 20, 40, 60, 80, 100].map(cycle => ({
  materialId: m.id,
  formula: m.formula,
  cycle,
  retention: Math.max(45, +(100 - (100 - m.retention) * (cycle / 100) - Math.sin(mi + cycle) * 0.35).toFixed(2)),
})))

const FIELDS: Record<string, string> = {
  capacity: '质量储氢密度 (wt%)',
  desorptionTemp: '放氢温度 (℃)',
  absorptionTemp: '吸氢温度 (℃)',
  plateauPressure: '平台压力 (bar)',
  retention: '100次循环保持率 (%)',
  kinetics: '吸氢动力学 t₉₀ (min)',
  year: '文献年份',
  pressure: '测试压力 (bar)',
}
const PALETTE = [[0, '#30123b'], [0.18, '#4668d8'], [0.4, '#2fc6c4'], [0.62, '#7be141'], [0.82, '#f7d23e'], [1, '#f15a24']]

const CHART_TYPES: { value: string; label: string }[] = [
  { value: 'bubble', label: '气泡散点图' },
  { value: 'scatter3d', label: '三维散点图' },
  { value: 'parallel', label: '平行坐标图' },
  { value: 'heatmap', label: '相关性热力图' },
  { value: 'box', label: '箱线分布图' },
  { value: 'radar', label: '材料雷达图' },
  { value: 'line', label: '循环保持率曲线' },
  { value: 'bar', label: '性能排名柱状图' },
]

const FIELD_KEYS = ['capacity', 'desorptionTemp', 'retention', 'kinetics', 'year', 'pressure'] as const
const FAMILIES = [...new Set(MATERIALS.map(d => d.family))]

function baseLayout(title: string): Record<string, unknown> {
  return {
    title: { text: title, font: { size: 15, color: '#263247' }, x: 0.03 },
    paper_bgcolor: '#f7f8fb', plot_bgcolor: '#f7f8fb',
    font: { family: 'Microsoft YaHei,Segoe UI', size: 11, color: '#4c5669' },
    margin: { l: 62, r: 32, t: 55, b: 58 },
    hoverlabel: { bgcolor: '#17213a', font: { color: '#fff' } },
    legend: { orientation: 'h', y: 1.12 },
    xaxis: { gridcolor: '#dce2ea', zerolinecolor: '#c5cdd9' },
    yaxis: { gridcolor: '#dce2ea', zerolinecolor: '#c5cdd9' },
  }
}

interface Props {
  lang: 'zh' | 'en'
}

export default function ManualPlotter(_props: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [chartType, setChartType] = useState('bubble')
  const [xField, setXField] = useState('desorptionTemp')
  const [yField, setYField] = useState('capacity')
  const [colorField, setColorField] = useState('year')
  const [sizeField, setSizeField] = useState('retention')
  const [family, setFamily] = useState('全部')
  const [tempMin, setTempMin] = useState(80)
  const [tempMax, setTempMax] = useState(430)

  const filtered = useMemo(() => {
    const lo = Math.min(tempMin, tempMax)
    const hi = Math.max(tempMin, tempMax)
    return MATERIALS.filter(d =>
      d.desorptionTemp >= lo && d.desorptionTemp <= hi &&
      (family === '全部' || d.family === family))
  }, [tempMin, tempMax, family])

  useEffect(() => {
    const el = chartRef.current
    if (!el) return
    const d = filtered
    const type = chartType
    const x = xField
    const y = yField
    const c = colorField
    const s = sizeField
    const nv = (v: Material, k: string): number => Number(v[k]) || 0

    const hover = (v: Material) => `<b>${v.formula}</b><br>${v.family}<br>储氢密度 ${v.capacity} wt%<br>放氢温度 ${v.desorptionTemp} ℃<br>循环保持率 ${v.retention}%`
    let traces: unknown[] = []
    let layout: Record<string, unknown> = baseLayout(`${FIELDS[y]} × ${FIELDS[x]}`)

    if (type === 'bubble') {
      const sizes = d.map(q => nv(q, s))
      const smin = Math.min(...sizes)
      const smax = Math.max(...sizes)
      traces = [{
        type: 'scatter', mode: 'markers',
        x: d.map(v => nv(v, x)), y: d.map(v => nv(v, y)),
        text: d.map(v => hover(v)), hovertemplate: '%{text}',
        marker: {
          size: d.map(v => 8 + 22 * (nv(v, s) - smin) / ((smax - smin) || 1)),
          color: d.map(v => nv(v, c)), colorscale: PALETTE, showscale: true,
          colorbar: { title: FIELDS[c], thickness: 13 },
          line: { color: '#fff', width: 1 }, opacity: 0.86,
        },
      }]
      layout = {
        ...layout,
        xaxis: { ...(layout.xaxis as Record<string, unknown>), title: { text: FIELDS[x], font: { size: 11 } } },
        yaxis: { ...(layout.yaxis as Record<string, unknown>), title: { text: FIELDS[y], font: { size: 11 } } },
      }
    }
    if (type === 'scatter3d') {
      traces = [{
        type: 'scatter3d', mode: 'markers',
        x: d.map(v => nv(v, x)), y: d.map(v => nv(v, y)), z: d.map(v => v.retention),
        text: d.map(v => hover(v)), hovertemplate: '%{text}',
        marker: { size: 7, color: d.map(v => nv(v, c)), colorscale: PALETTE, showscale: true, opacity: 0.88 },
      }]
      layout = { ...layout, scene: { xaxis: { title: FIELDS[x] }, yaxis: { title: FIELDS[y] }, zaxis: { title: FIELDS.retention }, bgcolor: '#f7f8fb' }, margin: { l: 10, r: 10, t: 55, b: 10 } }
    }
    if (type === 'parallel') {
      const dimensions = ['capacity', 'desorptionTemp', 'retention', 'kinetics', 'pressure'].map(k => ({ label: FIELDS[k], values: d.map(v => nv(v, k)) }))
      traces = [{ type: 'parcoords', line: { color: d.map(v => v.year), colorscale: PALETTE, showscale: true, colorbar: { title: '年份' } }, dimensions }]
      layout = { ...layout, title: { text: '多性能指标平行坐标对比', font: { size: 15, color: '#263247' }, x: 0.03 }, margin: { l: 55, r: 55, t: 65, b: 35 } }
    }
    if (type === 'heatmap') {
      const ks = ['capacity', 'desorptionTemp', 'retention', 'kinetics', 'pressure']
      const corr = (a: string, b: string) => {
        const av = d.reduce((n, v) => n + nv(v, a), 0) / d.length
        const bv = d.reduce((n, v) => n + nv(v, b), 0) / d.length
        const num = d.reduce((n, v) => n + (nv(v, a) - av) * (nv(v, b) - bv), 0)
        const da = Math.sqrt(d.reduce((n, v) => n + (nv(v, a) - av) ** 2, 0))
        const db = Math.sqrt(d.reduce((n, v) => n + (nv(v, b) - bv) ** 2, 0))
        return +(num / (da * db || 1)).toFixed(2)
      }
      traces = [{ type: 'heatmap', z: ks.map(a => ks.map(b => corr(a, b))), x: ks.map(k => FIELDS[k]), y: ks.map(k => FIELDS[k]), zmin: -1, zmax: 1, colorscale: [[0, '#4456a6'], [0.5, '#f6f8fb'], [1, '#e05750']], texttemplate: '%{z:.2f}', hovertemplate: '%{y} × %{x}: %{z:.2f}<extra></extra>' }]
      layout = { ...layout, title: { text: '关键性能参数相关性热力图', font: { size: 15, color: '#263247' }, x: 0.03 }, margin: { l: 125, r: 30, t: 55, b: 105 } }
    }
    if (type === 'box') {
      traces = [...new Set(d.map(v => v.family))].map(f => ({
        type: 'box', name: f, y: d.filter(v => v.family === f).map(v => nv(v, y)),
        boxpoints: 'all', jitter: 0.35, pointpos: 0, marker: { size: 5 },
        hovertext: d.filter(v => v.family === f).map(v => v.formula),
      }))
      layout = { ...layout, title: { text: `不同材料体系的${FIELDS[y]}分布`, font: { size: 15, color: '#263247' }, x: 0.03 }, xaxis: { gridcolor: '#dce2ea', title: '材料体系' }, yaxis: { gridcolor: '#dce2ea', title: FIELDS[y] } }
    }
    if (type === 'radar') {
      const top = [...d].sort((a, b) => (b.capacity * 10 + b.retention - a.desorptionTemp / 5) - (a.capacity * 10 + a.retention - b.desorptionTemp / 5)).slice(0, 5)
      traces = top.map(v => ({
        type: 'scatterpolar', fill: 'toself', name: v.formula,
        r: [v.capacity / 14 * 100, (430 - v.desorptionTemp) / 350 * 100, v.retention, (100 - v.kinetics) / 100 * 100, (50 - Math.min(v.pressure, 50)) / 50 * 100],
        theta: ['储氢密度', '低温放氢', '循环稳定性', '动力学', '低压性能'],
      }))
      layout = { ...layout, title: { text: '候选材料多维性能雷达图', font: { size: 15, color: '#263247' }, x: 0.03 }, polar: { radialaxis: { visible: true, range: [0, 100], gridcolor: '#cdd5e0' }, bgcolor: '#f7f8fb' }, margin: { l: 70, r: 70, t: 70, b: 50 } }
    }
    if (type === 'line') {
      const chosen = [...d].sort((a, b) => b.retention - a.retention).slice(0, 6)
      traces = chosen.map(v => {
        const rows = CYCLE_DATA.filter(r => r.materialId === v.id)
        return { type: 'scatter', mode: 'lines+markers', name: v.formula, x: rows.map(r => r.cycle), y: rows.map(r => r.retention) }
      })
      layout = { ...layout, title: { text: '高稳定性候选材料循环保持率', font: { size: 15, color: '#263247' }, x: 0.03 }, xaxis: { gridcolor: '#dce2ea', title: '循环次数' }, yaxis: { gridcolor: '#dce2ea', title: '容量保持率 (%)' } }
    }
    if (type === 'bar') {
      const score = (v: Material) => v.capacity / 14 * 40 + (430 - v.desorptionTemp) / 350 * 30 + v.retention / 100 * 30
      const top = [...d].sort((a, b) => score(b) - score(a)).slice(0, 12)
      traces = [{
        type: 'bar', orientation: 'h', y: top.map(v => v.formula).reverse(), x: top.map(score).reverse(),
        marker: { color: top.map(v => v.desorptionTemp).reverse(), colorscale: PALETTE, showscale: true, colorbar: { title: '放氢温度 ℃' } },
        customdata: top.map(v => [v.capacity, v.retention]).reverse(),
        hovertemplate: '%{y}<br>综合分 %{x:.1f}<br>储氢密度 %{customdata[0]} wt%<br>保持率 %{customdata[1]}%<extra></extra>',
      }]
      layout = { ...layout, title: { text: '候选材料综合性能排名', font: { size: 15, color: '#263247' }, x: 0.03 }, xaxis: { gridcolor: '#dce2ea', title: '综合评分' }, margin: { l: 95, r: 32, t: 55, b: 58 } }
    }

    Plotly.react(el, traces, layout, {
      responsive: true, displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d'],
      toImageButtonOptions: { format: 'png', filename: 'solid_hydrogen_materials_chart', scale: 2 },
    })
    return () => { Plotly.purge(el) }
  }, [filtered, chartType, xField, yField, colorField, sizeField])

  function reset() {
    setChartType('bubble')
    setXField('desorptionTemp')
    setYField('capacity')
    setColorField('year')
    setSizeField('retention')
    setFamily('全部')
    setTempMin(80)
    setTempMax(430)
  }

  function exportPng() {
    const el = chartRef.current
    if (!el) return
    ;(Plotly as unknown as { downloadImage: (el: HTMLElement, opts: { format: string; height: number; width: number; scale: number; filename: string }) => void }).downloadImage(el, {
      format: 'png', height: 900, width: 1500, scale: 1, filename: '固态储氢材料图表',
    })
  }

  const selOptions = () => (
    <div className="chart-builder">
      <label>图表类型<select value={chartType} onChange={e => setChartType(e.target.value)}>
        {CHART_TYPES.map(ct => <option key={ct.value} value={ct.value}>{ct.label}</option>)}
      </select></label>
      <label>横轴<select value={xField} onChange={e => setXField(e.target.value)}>
        {FIELD_KEYS.map(k => <option key={k} value={k}>{FIELDS[k]}</option>)}
      </select></label>
      <label>纵轴<select value={yField} onChange={e => setYField(e.target.value)}>
        {FIELD_KEYS.map(k => <option key={k} value={k}>{FIELDS[k]}</option>)}
      </select></label>
      <label>颜色<select value={colorField} onChange={e => setColorField(e.target.value)}>
        {FIELD_KEYS.map(k => <option key={k} value={k}>{FIELDS[k]}</option>)}
      </select></label>
      <label>气泡大小<select value={sizeField} onChange={e => setSizeField(e.target.value)}>
        {FIELD_KEYS.map(k => <option key={k} value={k}>{FIELDS[k]}</option>)}
      </select></label>
      <label>材料体系<select value={family} onChange={e => setFamily(e.target.value)}>
        <option value="全部">全部材料</option>
        {FAMILIES.map(f => <option key={f} value={f}>{f}</option>)}
      </select></label>
    </div>
  )

  return (
    <div className="manual-plot-demo">
      <div className="result-heading demo-heading">
        <span className="demo-title">手动绘图器</span>
        <div className="result-actions">
          <button onClick={reset}>重置</button>
          <button onClick={exportPng}>导出 PNG</button>
        </div>
      </div>

      {selOptions()}

      <div className="range-row">
        <span>放氢温度范围</span>
        <input type="range" min={80} max={430} value={tempMin}
          onChange={e => { setTempMin(Number(e.target.value)); if (Number(e.target.value) > tempMax) setTempMax(Number(e.target.value)) }} />
        <output>{tempMin}℃</output>
        <input type="range" min={80} max={430} value={tempMax}
          onChange={e => { setTempMax(Number(e.target.value)); if (Number(e.target.value) < tempMin) setTempMin(Number(e.target.value)) }} />
        <output>{tempMax}℃</output>
      </div>

      <div className="quality-strip">
        <span><i className="ok" />字段校验</span>
        <span><i className="ok" />单位统一</span>
        <span><i className="ok" />安全查询</span>
        <span><i className="ok" />结果试跑</span>
        <b>{filtered.length} 条材料记录</b>
      </div>

      <div ref={chartRef} className="demo-chart" role="img" aria-label="固态储氢材料交互式图表" />
    </div>
  )
}
