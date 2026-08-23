export interface ChartRecommendation {
  chart_type: 'line' | 'bar' | 'scatter' | 'pie' | 'area' | 'histogram'
  x_col: string
  y_col: string
  reason: string
}

export type ErrorCode =
  | 'empty_question' | 'no_schema' | 'db_unreachable' | 'llm_auth'
  | 'llm_timeout' | 'llm_conn' | 'sql_failed' | 'no_valid_sql' | 'server_busy'
  | 'unknown'

export type QueryIntent = 'chart' | 'data' | 'chat'

export interface QueryResult {
  ok: boolean
  session_id?: string
  error_code?: string | null
  sql: string | null
  error: string | null
  columns: string[]
  rows: unknown[][]
  row_count: number
  recommendation: ChartRecommendation | null
  answer?: string | null   // chat 回应或 data 模式的 AI 文字解读
  intent?: QueryIntent | null
}

export interface DbStatus {
  connected: boolean
  done: boolean
  attempts: number
  last_error: string
  info: { version: string; database: string; user: string } | null
}

export interface BootstrapState {
  db: DbStatus
  schema: { text: string; tables: string[] }
}

export interface LlmConfig {
  provider: string
  base_url: string
  model: string
  has_custom_key: boolean
  key_masked: string
}

export type Lang = 'zh' | 'en'
