import { ref } from 'vue'
import {
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
  STORAGE_KEY,
  applyLocaleToDocument,
  isValidLocale,
  resolveInitialLocale,
} from '../design/localePreference.js'
import zhCN from '../locales/zh-CN.js'
import enUS from '../locales/en-US.js'

const dictionaries = {
  'zh-CN': zhCN,
  'en-US': enUS,
}

const currentLocale = ref(DEFAULT_LOCALE)
let initialized = false

function getBrowserStorage() {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

export function initializeLocale() {
  if (initialized) return currentLocale.value
  const resolved = resolveInitialLocale()
  currentLocale.value = resolved
  applyLocaleToDocument(resolved)
  initialized = true
  return currentLocale.value
}

export function setLocale(locale) {
  const safe = isValidLocale(locale) ? locale : DEFAULT_LOCALE
  currentLocale.value = safe
  const storage = getBrowserStorage()
  if (storage) {
    try {
      storage.setItem(STORAGE_KEY, safe)
    } catch {
      // 容错处理
    }
  }
  applyLocaleToDocument(safe)
  initialized = true
  return safe
}

export function toggleLocale() {
  const next = currentLocale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  return setLocale(next)
}

export function getCurrentLocale() {
  initializeLocale()
  return currentLocale.value
}

/**
 * 响应式国际化取值函数
 * @param {string} path 字典点分路径，如 'nav.practice'
 * @param {Record<string, any>} [params] 动态插值参数，如 { count: 5 }
 * @returns {string}
 */
export function t(path, params = {}) {
  initializeLocale()
  const activeDict = dictionaries[currentLocale.value] || dictionaries[DEFAULT_LOCALE]
  const fallbackDict = dictionaries[DEFAULT_LOCALE]

  let val = resolvePath(activeDict, path)
  if (val === undefined && activeDict !== fallbackDict) {
    val = resolvePath(fallbackDict, path)
  }

  if (val === undefined) {
    return path
  }

  if (typeof val === 'string' && params && typeof params === 'object') {
    return val.replace(/\{(\w+)\}/g, (match, key) => {
      return key in params ? String(params[key]) : match
    })
  }

  return String(val)
}

function resolvePath(obj, path) {
  if (!obj || typeof obj !== 'object') return undefined
  const parts = path.split('.')
  let current = obj
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part]
    } else {
      return undefined
    }
  }
  return current
}

export function useLocale() {
  initializeLocale()
  return {
    locale: currentLocale,
    supportedLocales: SUPPORTED_LOCALES,
    setLocale,
    toggleLocale,
    t,
  }
}
