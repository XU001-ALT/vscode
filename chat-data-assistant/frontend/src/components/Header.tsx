import type { Lang } from '../types'
import { t } from '../i18n'

interface Props {
  lang: Lang
  onToggleLang: () => void
}

export default function Header({ lang, onToggleLang }: Props) {
  return (
    <header className="header">
      <div className="title">{t('app_title', lang)}</div>
      <button className="lang-btn" onClick={onToggleLang}>
        {t('lang_btn', lang)}
      </button>
    </header>
  )
}
