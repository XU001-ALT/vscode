import type { BootstrapState, LlmConfig, QueryResult } from './types'

// API 基础地址：通过 VITE_API_BASE_URL 环境变量配置
// - 开发模式（Vite dev server）：留空，由 vite.config.ts 的 proxy 转发到后端
// - 生产部署：设置为后端地址，如 "http://your-server:8000"
const API_BASE: string = (import.meta as any).env?.VITE_API_BASE_URL ?? ''

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export function createSession(): Promise<{ session_id: string }> {
  return request('/api/session', { method: 'POST' })
}

export function getBootstrapState(): Promise<BootstrapState> {
  return request('/api/bootstrap')
}

export function getSchemaDescriptions(): Promise<Record<string, string>> {
  return request('/api/schema/descriptions')
}

export function runQuery(sessionId: string | null, question: string, lang: string = 'zh'): Promise<QueryResult> {
  return request('/api/query', { method: 'POST', body: JSON.stringify({ session_id: sessionId, question, lang }) })
}

export function getLlmConfig(sessionId: string): Promise<LlmConfig> {
  return request(`/api/config/llm/${sessionId}`)
}

export function setLlmConfig(sessionId: string, cfg: Partial<{ provider: string; base_url: string; model: string; api_key: string }>): Promise<LlmConfig> {
  return request('/api/config/llm', { method: 'PUT', body: JSON.stringify({ session_id: sessionId, ...cfg }) })
}

export function clearLlmConfig(sessionId: string): Promise<{ ok: boolean }> {
  return request(`/api/config/llm/${sessionId}`, { method: 'DELETE' })
}
