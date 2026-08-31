import { useEffect, useState } from 'react'
import type { ErrorCode, Lang, QueryResult } from '../types'
import { getLlmConfig, runQuery, runSql } from '../api'
import { t, type TKey } from '../i18n'
import ChartView from './ChartView'
import DataResultView from './DataResultView'

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
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null)

  // 探测当前会话是否已配置 API Key（服务端内存 Key 或全局配置）
  useEffect(() => {
    if (!sessionId) return
    let alive = true
    getLlmConfig(sessionId)
      .then(cfg => { if (alive) setHasApiKey(!!cfg.key_masked) })
      // 探测失败时视为无 Key，走手动模式（可少一次对 LLM 的依赖判断）
      .catch(() => { if (alive) setHasApiKey(false) })
    return () => { alive = false }
  }, [sessionId])

  // 手动绘图模式：SQL 输入 + 执行
  const [sql, setSql] = useState('')
  const [manualLoading, setManualLoading] = useState(false)
  const [manualError, setManualError] = useState<string | null>(null)

  async function runManualSql() {
    const q = sql.trim()
    if (!q || manualLoading || loading) return
    setManualLoading(true)
    setManualError(null)
    // 手动模式无需任何 Key 依赖；复用同一结果区渲染
    try {
      const r = await runSql(q)
      if (!r.ok) {
        setManualError(r.error)
        setResult(null)
      } else {
        setResult({ ...r, intent: 'chart' as const, recommendation: null, answer: null })
      }
    } catch (e) {
      setManualError(String(e))
      setResult(null)
    } finally {
      setManualLoading(false)
    }
  }

  async function submit() {
    const q = question.trim()
    if (!q || loading) return
    setLoading(true)
    // 清除手动模式残留错误 / 数据
    setManualError(null)
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

      <div className="result-area">
        <div className="panel-title result-title">{t('result_area', lang)}</div>

        {/* 模式指示条：无 Key → 手动绘图模式；有 Key → AI 增强绘图模式 */}
        {hasApiKey !== null && (
          <div className={`mode-bar ${hasApiKey ? '' : 'manual'}`}>
            <span className="mode-dot" />
            <span>{hasApiKey ? t('ai_mode', lang) : t('manual_mode', lang)}</span>
          </div>
        )}

        {/* 手动绘图输入：未配置 API Key 时高亮展示；有 Key 时也可展开使用 */}
        {hasApiKey === false && schemaLoaded && (
          <div className="manual-sql-box">
            <div className="manual-sql-row">
              <textarea
                value={sql}
                rows={2}
                placeholder={t('sql_ph', lang)}
                onChange={e => setSql(e.target.value)}
                className="sql-textarea"
              />
              <button onClick={runManualSql} disabled={manualLoading || !sql.trim() || loading}>
                {manualLoading ? t('querying', lang) : t('run_sql', lang)}
              </button>
            </div>
            <div className="hint-ok hint-manual">{t('manual_hint', lang)}</div>
          </div>
        )}

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

          {!loading && schemaLoaded && !result && !manualLoading && (
            <div className="msg info">
              <div>{t('result_tips', lang)}</div>
            </div>
          )}

          {manualError && !loading && (
            <div className="msg error">
              <div>{t('manual_error_title', lang)}</div>
              <div className="err-detail">{manualError}</div>
            </div>
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
            <div className="ai-answer ai-answer-chat">
              <div className="ai-answer-body">{result.answer}</div>
            </div>
          )}

          {/* 问数模式：聚合结果以回答框/表格直接展示（不返回明细数据，也不展示绘图界面） */}
          {result && result.intent === 'data' && result.columns.length > 0 && !result.error && !loading && (
            <DataResultView columns={result.columns} rows={result.rows} lang={lang} />
          )}

          {/* 绘图模式：表格 + 图表（AI 推荐或手动 SQL 共享同一渲染） */}
          {result && result.columns.length > 0 && result.intent === 'chart' && (
            <ChartView
              columns={result.columns}
              rows={result.rows}
              recommendation={result.recommendation}
              lang={lang}
              sql={result.sql}
              corrections={result.corrections}
            />
          )}
        </div>

        {result && result.columns.length > 0 && (
          <div style={{ padding: '8px 18px 12px' }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>
              {t('rows_returned', lang)}{result.row_count}{t('rows_unit', lang)}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
