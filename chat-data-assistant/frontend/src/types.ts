export interface ChartRecommendation {
  chart_type: 'line' | 'bar' | 'scatter' | 'pie'
  x_col: string
  y_col: string
  reason: string
}

export interface QueryResult {
  ok: boolean
  session_id?: string
  sql: string | null
  error: string | null
  columns: string[]
  rows: unknown[][]
  row_count: number
  recommendation: ChartRecommendation | null
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
