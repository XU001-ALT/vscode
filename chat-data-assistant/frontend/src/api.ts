import type { BootstrapState, LlmConfig, QueryResult } from './types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
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

export function fetchSchemaFromDb(): Promise<{ ok: boolean; error: string; tables: string[] }> {
  return request('/api/schema/fetch', { method: 'POST' })
}

export function uploadSchema(content: string): Promise<{ ok: boolean; error: string; tables: string[] }> {
  return request('/api/schema/upload', { method: 'POST', body: JSON.stringify({ content }) })
}

export function getSchemaDescriptions(): Promise<Record<string, string>> {
  return request('/api/schema/descriptions')
}

export function runQuery(sessionId: string | null, question: string): Promise<QueryResult> {
  return request('/api/query', { method: 'POST', body: JSON.stringify({ session_id: sessionId, question }) })
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
