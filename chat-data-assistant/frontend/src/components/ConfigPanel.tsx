import { useEffect, useState } from 'react'
import type { BootstrapState, Lang, LlmConfig } from '../types'
import { clearLlmConfig, getLlmConfig, getSchemaDescriptions, setLlmConfig } from '../api'
import { t } from '../i18n'

interface Props {
  lang: Lang
  sessionId: string | null
  boot: BootstrapState | null
}

const MODEL_PRESETS = [
  { label: 'DeepSeek V4 Flash', model: 'deepseek-v4-flash', url: 'https://api.deepseek.com' },
  { label: 'DeepSeek V4 Pro', model: 'deepseek-v4-pro', url: 'https://api.deepseek.com' },
  { label: 'GPT-4o Mini', model: 'gpt-4o-mini', url: 'https://api.openai.com' },
  { label: 'GPT-4o', model: 'gpt-4o', url: 'https://api.openai.com' },
  { label: '通义千问 Qwen-Plus', model: 'qwen-plus', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { label: '通义千问 Qwen-Max', model: 'qwen-max', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { label: 'Moonshot Kimi', model: 'moonshot-v1-8k', url: 'https://api.moonshot.cn/v1' },
  { label: '百川 Baichuan 4', model: 'Baichuan4', url: 'https://api.baichuan-ai.com/v1' },
  { label: '', model: '', url: '' },
]

function Section({ title, children, defaultOpen = false }: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details className="config-section" open={defaultOpen}>
      <summary>
        <span>{title}</span>
        <span className="arrow">▶</span>
      </summary>
      <div className="section-body">{children}</div>
    </details>
  )
}

export default function ConfigPanel({ lang, sessionId, boot }: Props) {
  const [llm, setLlm] = useState<LlmConfig | null>(null)
  const [preset, setPreset] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [savedFlash, setSavedFlash] = useState(false)
  const [descs, setDescs] = useState<Record<string, string>>({})

  useEffect(() => {
    getSchemaDescriptions().then(setDescs).catch(console.error)
  }, [])

  useEffect(() => {
    if (!sessionId) return
    getLlmConfig(sessionId).then(cfg => {
      setLlm(cfg)
      setBaseUrl(cfg.base_url)
      setModel(cfg.model)
    }).catch(console.error)
  }, [sessionId])

  function applyPreset(label: string) {
    setPreset(label)
    const p = MODEL_PRESETS.find(x => x.label === label)
    if (p?.model) setModel(p.model)
    if (p?.url) setBaseUrl(p.url)
  }

  async function saveLlm() {
    if (!sessionId) return
    const cfg = await setLlmConfig(sessionId, {
      base_url: baseUrl,
      model,
      ...(apiKey ? { api_key: apiKey } : {}),
    })
    setLlm(cfg)
    setApiKey('')
    setSavedFlash(true)
    setTimeout(() => setSavedFlash(false), 2000)
  }

  async function removeKey() {
    if (!sessionId) return
    await clearLlmConfig(sessionId)
    const cfg = await getLlmConfig(sessionId)
    setLlm(cfg)
  }

  const db = boot?.db

  return (
    <div className="fill">
      <div className="panel-title">{t('config_area', lang)}</div>

        <Section title={t('db_status', lang)} defaultOpen>
          {db?.connected && (
            <span className="hint-ok">
              <span className="status-dot ok" />{t('db_connected', lang)}
              {db.info && ` — ${db.info.database} (PostgreSQL ${String(db.info.version).split(' ').slice(0, 2).join(' ')})`}
            </span>
          )}
          {!db?.connected && !db?.last_error && (
            <span><span className="status-dot pending" />{t('db_connecting', lang)}</span>
          )}
          {db?.last_error && (
            <span className="hint-err">
              <span className="status-dot err" />{t('db_failed', lang)}：{db.last_error}
            </span>
          )}
        </Section>

        <Section title={t('api_config', lang)}>
          <div style={{ marginBottom: 10 }}>{t('api_config_hint', lang)}</div>
          <div className="field">
            <label>{t('model_select', lang)}</label>
            <select value={preset} onChange={e => applyPreset(e.target.value)}>
              <option value="">--</option>
              {MODEL_PRESETS.filter(p => p.label).map(p => (
                <option key={p.label} value={p.label}>{p.label}</option>
              ))}
              <option value={t('custom', lang)}>{t('custom', lang)}</option>
            </select>
          </div>
          <div className="field">
            <label>{t('base_url', lang)}</label>
            <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)}
              placeholder="https://api.deepseek.com" />
          </div>
          <div className="field">
            <label>{t('api_key', lang)}</label>
            <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
              placeholder={llm?.has_custom_key ? `••••••（${t('key_set', lang)}）` : 'sk-...'} />
          </div>
          <div className="field">
            <label>{t('model_name', lang)}</label>
            <input value={model} onChange={e => setModel(e.target.value)}
              placeholder={t('model_name_ph', lang)} />
          </div>
          <div className="btn-row">
            <button className="btn primary" onClick={saveLlm} disabled={!sessionId}>
              {savedFlash ? t('saved', lang) : t('save', lang)}
            </button>
            {llm?.has_custom_key && (
              <button className="btn" onClick={removeKey}>{t('clear', lang)}</button>
            )}
          </div>
          {llm?.key_masked && (
            <div style={{ marginTop: 8 }}>
              {t('current_key', lang)}：<span className="key-masked">{llm.key_masked}</span>
            </div>
          )}
        </Section>

        <Section title={t('data_guide', lang)}>
          {Object.entries(descs).map(([tbl, d]) => (
            <div key={tbl} style={{ marginBottom: 8 }}>
              <b style={{ color: 'var(--text)' }}>{tbl}</b>
              {d ? ` — ${d}` : ''}
            </div>
          ))}
        </Section>
    </div>
  )
}
