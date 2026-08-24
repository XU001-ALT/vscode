import type { Lang } from '../types'
import { t } from '../i18n'
import platformIntroZh from '../assets/platform-intro.png'
import platformIntroEn from '../assets/platform-intro-light.png'

// 图片配色跟随语言主题：中文=深蓝暗色版，英文=浅色版（色相一致、明度翻转）
const INTRO_IMG: Record<Lang, string> = {
  zh: platformIntroZh,
  en: platformIntroEn,
}

export default function IntroPanel({ lang }: { lang: Lang }) {
  return (
    <div className="intro">
      <div className="panel-title">{t('intro_area', lang)}</div>
      <div className="intro-body">
        <p><span className="intro-brand">{t('intro_brand', lang)}</span>{t('intro_p1_rest', lang)}</p>
        <p>{t('intro_p2', lang)}</p>
        <p>{t('intro_p3', lang)}</p>
        <p>{t('intro_p4', lang)}</p>
        <p>{t('intro_p5', lang)}</p>
        <img
          key={lang}
          src={INTRO_IMG[lang]}
          alt="Chat Data platform"
          className="intro-img"
        />
      </div>
    </div>
  )
}
