export type ChartType =
  | 'line' | 'bar' | 'scatter' | 'pie' | 'area' | 'histogram'
  | 'bubble' | 'scatter3d' | 'heatmap' | 'parallel' | 'box' | 'radar'

export interface ChartRecommendation {
  chart_type: ChartType
  x_col: string
  y_col: string
  z_col?: string
  reason: string
}

export type ErrorCode =
  | 'empty_question' | 'no_schema' | 'db_unreachable' | 'llm_auth'
  | 'llm_timeout' | 'llm_conn' | 'sql_failed' | 'no_valid_sql' | 'server_busy'
  | 'unknown'

export type QueryIntent = 'chart' | 'data' | 'chat'

export interface SqlCorrection {
  attempt: number
  failed_sql: string
  error: string
  fixed_sql?: string
}

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
  corrections?: SqlCorrection[] | null
  answer?: string | null   // chat 回应或问数模式的批量数据拒绝提醒
  intent?: QueryIntent | null
}

export interface ManualColumn {
  name: string
  data_type: string
  numeric: boolean
  categorical: boolean
}

export interface ManualTable {
  name: string
  columns: ManualColumn[]
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
