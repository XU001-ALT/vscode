import { useState } from 'react'
import type { ErrorCode, Lang, QueryResult } from '../types'
import { runQuery } from '../api'
import { t, type TKey } from '../i18n'
import ChartView from './ChartView'
import DataResultView from './DataResultView'
import ManualPlotter from './ManualPlotter'

function errKey(code?: string | null): TKey {
  const known: ErrorCode[] = [
    'empty_question', 'no_schema', 'db_unreachable', 'llm_auth',
    'llm_timeout', 'llm_conn', 'sql_failed', 'no_valid_sql', 'server_busy',
  ]
  return known.includes(code as ErrorCode) ? (`err_${code}` as TKey) : 'err_unknown'
}

interface Props {
  lang: Lang
  sessionId: string | null
  schemaLoaded: boolean
}

export default function QueryPanel({ lang, sessionId, schemaLoaded }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QueryResult | null>(null)

  // 手动绘图模式：两种模式下均可展开
  const [showManual, setShowManual] = useState(false)

  async function submit() {
    const q = question.trim()
    if (!q || loading) return
    setLoading(true)
    try {
      const r = await runQuery(sessionId, q, lang)
      setResult(r)
    } catch (e) {
      setResult({
        ok: false, sql: null, error: String(e), error_code: null,
        columns: [], rows: [], row_count: 0, recommendation: null,
        answer: null, intent: null,
      })
    } finally {
      setLoading(false)
      setQuestion('')
    }
  }

  return (
    <div className="fill">
      <div className="panel-title">{t('chat_plot_area', lang)}</div>

      <div className="query-box">
        <textarea
          value={question}
          rows={2}
          placeholder={t('query_ph', lang)}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          disabled={loading}
        />
        <button onClick={submit} disabled={loading || !question.trim()}>
          {loading ? t('querying', lang) : t('send', lang)}
        </button>
      </div>

      <div className={`result-area${showManual && schemaLoaded ? ' manual-open' : ''}`}>
        <div className="panel-title result-title">
          <span>{t('result_area', lang)}</span>
          <button
            className="btn-outline mode-toggle"
            onClick={() => setShowManual(s => !s)}
            disabled={!schemaLoaded}
          >
            {showManual ? t('close_manual', lang) : t('open_manual', lang)}
          </button>
        </div>

        {/* 手动绘图：占满整个结果展示区，绘制图表但不展示明细数据/SQL */}
        {showManual && schemaLoaded && (
          <div className="manual-sql-box">
            <ManualPlotter lang={lang} />
          </div>
        )}

        {/* 手动绘图打开时隐藏 AI 结果区（正在查询时保留 loading 提示），让绘图器占满整个结果区 */}
        {(showManual && schemaLoaded && !loading) ? null : (
        <div className="result-body">
          {loading && (
            <div className="loading-block">
              <span className="spinner" />
              <span>{t('querying_hint', lang)}</span>
            </div>
          )}

          {!loading && !schemaLoaded && (
            <div className="msg info">{t('load_schema_first', lang)}</div>
          )}

          {!loading && schemaLoaded && !result && (
            <div className="msg info">
              <div>{t('result_tips', lang)}</div>
            </div>
          )}

          {result?.error && !loading && (
            <div className="msg error">
              <div>{t(errKey(result.error_code), lang)}</div>
              <div className="err-detail">{result.error}</div>
            </div>
          )}

          {result?.answer && !result.error && !loading && (
            <div className="ai-answer ai-answer-chat">
              <div className="ai-answer-body">{result.answer}</div>
            </div>
          )}

          {/* 问数模式：仅展示单行聚合结论（文字），不展示明细数据 */}
          {result && result.intent === 'data' && result.columns.length > 0 &&
            result.rows.length === 1 && !result.error && !loading && (
            <DataResultView columns={result.columns} rows={result.rows} lang={lang} />
          )}

          {/* 绘图模式：渲染图表，不展示明细数据表与 SQL */}
          {result && result.columns.length > 0 && result.intent === 'chart' && (
            <ChartView
              columns={result.columns}
              rows={result.rows}
              recommendation={result.recommendation}
              lang={lang}
            />
          )}
        </div>
        )}
      </div>
    </div>
  )
}
