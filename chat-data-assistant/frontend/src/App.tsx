import { useCallback, useEffect, useState } from 'react'
import type { BootstrapState, Lang } from './types'
import { createSession, getBootstrapState } from './api'
import Header from './components/Header'
import IntroPanel from './components/IntroPanel'
import QueryPanel from './components/QueryPanel'
import ConfigPanel from './components/ConfigPanel'

export default function App() {
  const [lang, setLang] = useState<Lang>('zh')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [boot, setBoot] = useState<BootstrapState | null>(null)

  useEffect(() => {
    document.documentElement.dataset.lang = lang
    document.title = 'Chat Data for Digital Hydrogen'
  }, [lang])

  useEffect(() => {
    createSession().then(r => setSessionId(r.session_id)).catch(console.error)
  }, [])

  const refreshBoot = useCallback(() => {
    getBootstrapState().then(setBoot).catch(console.error)
  }, [])

  useEffect(() => {
    refreshBoot()
    const timer = setInterval(refreshBoot, 4000)
    return () => clearInterval(timer)
  }, [refreshBoot])

  return (
    <div className="app" data-lang={lang}>
      <Header lang={lang} onToggleLang={() => setLang(l => (l === 'zh' ? 'en' : 'zh'))} />
      <div className="main">
        <section className="panel">
          <IntroPanel lang={lang} />
        </section>
        <section className="panel">
          <QueryPanel lang={lang} sessionId={sessionId} schemaLoaded={!!boot?.schema.tables.length} />
        </section>
        <section className="panel">
          <ConfigPanel
            lang={lang}
            sessionId={sessionId}
            boot={boot}
          />
        </section>
      </div>
    </div>
  )
}
