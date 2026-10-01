/**
 * localePreference.js
 * 语言首选项检测、规范化与 DOM 注入适配器
 * 严格遵照 standards/LOCALIZATION.md 根设计
 */

export const SUPPORTED_LOCALES = ['zh-CN', 'en-US']
export const DEFAULT_LOCALE = 'zh-CN'
export const STORAGE_KEY = 'easyexam_locale'

/**
 * 校验传入的 locale 是否合法
 * @param {string} locale
 * @returns {boolean}
 */
export function isValidLocale(locale) {
  return typeof locale === 'string' && SUPPORTED_LOCALES.includes(locale)
}

/**
 * 解析并确定初始语言
 * 优先级：localStorage -> navigator.language 探测 -> 默认语言 (zh-CN)
 * @returns {string}
 */
export function resolveInitialLocale() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const stored = window.localStorage.getItem(STORAGE_KEY)
      if (stored && isValidLocale(stored)) {
        return stored
      }
    }
  } catch {
    // 保护隐私模式或无权限环境
  }

  if (typeof navigator !== 'undefined' && navigator.language) {
    const navLang = navigator.language.toLowerCase()
    if (navLang.startsWith('en')) {
      return 'en-US'
    }
    if (navLang.startsWith('zh')) {
      return 'zh-CN'
    }
  }

  return DEFAULT_LOCALE
}

/**
 * 物理将语言注入到根元素，通知屏幕阅读器与浏览器排版引擎
 * @param {string} locale
 */
export function applyLocaleToDocument(locale) {
  if (typeof document === 'undefined') return
  const safeLocale = isValidLocale(locale) ? locale : DEFAULT_LOCALE
  document.documentElement.setAttribute('lang', safeLocale)
}
