import { useState } from 'react'
import type { ErrorCode, Lang, QueryResult } from '../types'
import { runQuery } from '../api'
import { t, type TKey } from '../i18n'
import ChartView from './ChartView'

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
        <input
          value={question}
          placeholder={t('query_ph', lang)}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          disabled={loading}
        />
        <button onClick={submit} disabled={loading || !question.trim()}>
          {loading ? t('querying', lang) : t('send', lang)}
        </button>
      </div>

      <div className="result-area">
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
            <div className="msg info">{t('no_chart', lang)}</div>
          )}

          {result?.error && !loading && (
            <div className="msg error">
              <div>{t(errKey(result.error_code), lang)}</div>
              <div className="err-detail">{result.error}</div>
            </div>
          )}
          {result && !result.error && !result.answer && result.row_count === 0 && !loading && (
            <div className="msg info">{t('rows_returned', lang)}0{t('rows_unit', lang)}</div>
          )}

          {result?.answer && !result.error && !loading && (
            <div className={`ai-answer${result.intent === 'chat' ? ' ai-answer-chat' : ''}`}>
              <div className="ai-answer-title">{t('ans_title', lang)}</div>
              <div className="ai-answer-body">{result.answer}</div>
            </div>
          )}

          {result && result.columns.length > 0 && (
            <ChartView
              columns={result.columns}
              rows={result.rows}
              recommendation={result.recommendation}
              lang={lang}
            />
          )}
        </div>

        {result && result.columns.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>
              {t('rows_returned', lang)}{result.row_count}{t('rows_unit', lang)}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
