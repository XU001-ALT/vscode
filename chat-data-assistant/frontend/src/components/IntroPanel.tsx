import type { Lang } from '../types'
import { t } from '../i18n'
import platformIntro from '../assets/platform-intro.png'

export default function IntroPanel({ lang }: { lang: Lang }) {
  return (
    <div className="intro">
      <span className="intro-badge">Chat Data</span>
      <div className="intro-head">{t('intro_title', lang)}</div>
      <p>{t('intro_p1', lang)}</p>
      <p>{t('intro_p2', lang)}</p>
      <p>{t('intro_p3', lang)}</p>
      <img
        src={platformIntro}
        alt="Chat Data platform"
        style={{
          width: '100%',
          borderRadius: 12,
          border: '1px solid var(--border)',
          marginTop: 6,
          display: 'block',
        }}
      />
    </div>
  )
}
