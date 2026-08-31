import { useEffect, useMemo, useState } from 'react'
import type { ManualTable, QueryResult } from '../types'
import { getManualRows, getManualTables } from '../api'
import { t, type TKey } from '../i18n'
import ChartView from './ChartView'

interface Props {
  lang: 'zh' | 'en'
}

function errorKey(err: string): TKey {
  if (/unreachable/i.test(err)) return 'err_db_unreachable'
  if (/schema|就绪|表结构/.test(err)) return 'err_no_schema'
  return 'err_unknown'
}

/** 甲方式手动绘图器：选表 → 选列绑轴 → 筛选，生成有限 8 类图（无 LLM、无 Key） */
export default function ManualPlotter({ lang }: Props) {
  const [tables, setTables] = useState<ManualTable[]>([])
  const [selTable, setSelTable] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<QueryResult | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    getManualTables().then(r => {
      setTables(r.tables ?? [])
      if (!r.ok && r.error) setLoadError(r.error)
    }).catch(e => setLoadError(String(e)))
  }, [])

  const selCols = useMemo(
    () => tables.find(tb => tb.name === selTable)?.columns ?? [],
    [tables, selTable],
  )

  async function loadTable(name: string) {
    if (!name) return
    setSelTable(name)
    setLoading(true)
    setLoadError(null)
    try {
      const r = await getManualRows(name)
      if (!r.ok) {
        setLoadError(r.error)
        setData(null)
      } else {
        setData({ ...r, recommendation: null, answer: null })
      }
    } catch (e) {
      setLoadError(String(e))
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="manual-plot">
      <div className="manual-plot-bar">
        <label className="field manual-table-field">
          <span>{t('manual_table', lang)}</span>
          <select
            value={selTable}
            onChange={e => loadTable(e.target.value)}
            disabled={loading}
          >
            <option value="">{t('manual_table_ph', lang)}</option>
            {tables.map(tb => <option key={tb.name} value={tb.name}>{tb.name}</option>)}
          </select>
        </label>
        <span className="manual-colcount">
          {selCols.length ? `${t('manual_cols', lang)}: ${selCols.length}` : ''}
        </span>
      </div>

      {loadError && (
        <div className="msg error">
          <div>{t(errorKey(loadError), lang)}</div>
          <div className="err-detail">{loadError}</div>
        </div>
      )}

      {loading && (
        <div className="loading-block"><span className="spinner" /><span>{t('manual_loading', lang)}</span></div>
      )}

      {!loading && selTable && data && data.columns.length > 0 && (
        <ChartView
          columns={data.columns}
          rows={data.rows}
          recommendation={null}
          lang={lang}
        />
      )}

      {!loading && selTable && data && data.columns.length === 0 && (
        <div className="msg info">{t('no_chart', lang)}</div>
      )}
    </div>
  )
}
