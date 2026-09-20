import type { Lang } from '../types'
import { t } from '../i18n'

export default function IntroPanel({ lang }: { lang: Lang }) {
  const isEn = lang === 'en'
  return (
    <div className="intro">
      <div className="panel-title">{t('intro_area', lang)}</div>
      <div className="intro-body">
        <p><span className="intro-brand">{t('intro_brand', lang)}</span>{t('intro_p1_rest', lang)}</p>
        <p>{t('intro_p2', lang)}</p>
        <p>{t('intro_p3', lang)}</p>
        <p>{t('intro_p4', lang)}</p>
        <p>{t('intro_p5', lang)}</p>
        <video
          src={isEn ? '/demo-en.mp4' : '/demo.mp4'}
          poster={isEn ? '/demo-poster-en.jpg' : '/demo-poster.jpg'}
          className="intro-img"
          loop
          playsInline
          controls
        />
      </div>
    </div>
  )
}
