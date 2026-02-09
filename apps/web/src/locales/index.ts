import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN.json'
import enUS from './en-US.json'
import zhTW from './zh-TW.json'
import jaJP from './ja-JP.json'

export type MessageSchema = typeof zhCN

const i18n = createI18n<[MessageSchema], 'zh-CN' | 'en-US' | 'zh-TW' | 'ja-JP'>({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
    'zh-TW': zhTW,
    'ja-JP': jaJP,
  },
})

export default i18n
