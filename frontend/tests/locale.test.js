import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse as parseTemplate } from '@vue/compiler-dom'
import { parse as parseVueSfc } from '@vue/compiler-sfc'
import {
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
  STORAGE_KEY,
  isValidLocale,
  applyLocaleToDocument,
} from '../src/design/localePreference.js'
import { t, setLocale, useLocale } from '../src/composables/useLocale.js'
import zhDict from '../src/locales/zh-CN.js'
import enDict from '../src/locales/en-US.js'
import { request, ApiError } from '../src/api/client.js'
import { inspectVueSource } from '../scripts/scan_localized_templates.js'
import { validateLocalizationConfig } from '../scripts/check_localization_config.js'

function extractKeyPaths(obj, prefix = '') {
  let paths = []
  for (const [k, v] of Object.entries(obj)) {
    const keyPath = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      paths.push(...extractKeyPaths(v, keyPath))
    } else {
      paths.push(keyPath)
    }
  }
  return paths
}

function extractPlaceholders(str) {
  if (typeof str !== 'string') return []
  const matches = str.match(/\{(\w+)\}/g) || []
  return matches.map(m => m.slice(1, -1)).sort()
}

function getValue(obj, pathStr) {
  const parts = pathStr.split('.')
  let curr = obj
  for (const p of parts) {
    if (curr && typeof curr === 'object' && p in curr) {
      curr = curr[p]
    } else {
      return undefined
    }
  }
  return curr
}

test('locale preference helpers validate locales', () => {
  assert.equal(isValidLocale('zh-CN'), true)
  assert.equal(isValidLocale('en-US'), true)
  assert.equal(isValidLocale('fr-FR'), false)
  assert.equal(isValidLocale(null), false)
  assert.equal(isValidLocale(undefined), false)
})

test('applyLocaleToDocument updates the root lang attribute', () => {
  const mockDoc = {
    documentElement: {
      attributes: {},
      setAttribute(k, v) { this.attributes[k] = v },
    },
  }
  globalThis.document = mockDoc

  applyLocaleToDocument('en-US')
  assert.equal(mockDoc.documentElement.attributes.lang, 'en-US')

  applyLocaleToDocument('invalid')
  assert.equal(mockDoc.documentElement.attributes.lang, DEFAULT_LOCALE)
})

test('dictionary parity: zh-CN and en-US have 100% matching keys', () => {
  const zhKeys = extractKeyPaths(zhDict)
  const enKeys = extractKeyPaths(enDict)

  const zhKeySet = new Set(zhKeys)
  const enKeySet = new Set(enKeys)

  const missingInEn = zhKeys.filter(k => !enKeySet.has(k))
  const missingInZh = enKeys.filter(k => !zhKeySet.has(k))

  assert.deepEqual(missingInEn, [], `Missing in en-US: ${missingInEn.join(', ')}`)
  assert.deepEqual(missingInZh, [], `Missing in zh-CN: ${missingInZh.join(', ')}`)
  assert.equal(zhKeys.length, enKeys.length)
  assert.ok(zhKeys.length >= 40, `Dictionary should have substantial entries, found ${zhKeys.length}`)
})

test('JSON catalogs stay identical to the runtime dictionaries', () => {
  const zhSnapshot = JSON.parse(fs.readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
  const enSnapshot = JSON.parse(fs.readFileSync(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
  assert.deepEqual(zhSnapshot, zhDict)
  assert.deepEqual(enSnapshot, enDict)
})

test('English runtime catalog contains no untranslated Chinese copy', () => {
  const untranslated = []
  function walk(dictionary, prefix = '') {
    for (const [key, value] of Object.entries(dictionary)) {
      const keyPath = prefix ? `${prefix}.${key}` : key
      if (typeof value === 'string' && /[\u4e00-\u9fff]/u.test(value)
          && !['ui.k0645', 'ui.k0646'].includes(keyPath)) untranslated.push(`${keyPath}: ${value}`)
      else if (value && typeof value === 'object') walk(value, keyPath)
    }
  }
  walk(enDict)
  assert.deepEqual(untranslated, [])
})

test('localization config cannot disable bilingual support or replace required delivery stages', () => {
  const config = JSON.parse(fs.readFileSync(new URL('../../localization.config.json', import.meta.url), 'utf8'))
  const packageJson = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  assert.deepEqual(validateLocalizationConfig(config, packageJson), [])

  const weakened = structuredClone(config)
  weakened.applicable = false
  weakened.locales = ['fr-FR', 'de-DE']
  weakened.checks.browser[4] = 'test:e2e'
  const failures = validateLocalizationConfig(weakened, packageJson)
  assert.ok(failures.some(item => item.includes('applicable must remain true')))
  assert.ok(failures.some(item => item.includes('locales must include en-US')))
  assert.ok(failures.some(item => item.includes('must use the enforced script test:localization:e2e')))
})

test('placeholder token parity: dynamic tokens match across locales', () => {
  const zhKeys = extractKeyPaths(zhDict)
  for (const k of zhKeys) {
    const zhVal = getValue(zhDict, k)
    const enVal = getValue(enDict, k)

    const zhTokens = extractPlaceholders(zhVal)
    const enTokens = extractPlaceholders(enVal)

    assert.deepEqual(
      enTokens,
      zhTokens,
      `Placeholder token mismatch at "${k}": zh-CN has [${zhTokens}], en-US has [${enTokens}]`
    )
  }
})

test('t() helper interpolates dynamic variables and switches locales reactively', () => {
  setLocale('zh-CN')
  assert.equal(t('common.total', { count: 42 }), '共 42 项')

  setLocale('en-US')
  assert.equal(t('common.total', { count: 42 }), '42 total')

  // Fallback to key when path not found
  assert.equal(t('nonexistent.path.key'), 'nonexistent.path.key')
})

test('requests use the current in-memory locale even when storage is unavailable', async () => {
  const previousStorage = globalThis.localStorage
  const previousFetch = globalThis.fetch
  const headers = []
  globalThis.localStorage = { getItem: () => 'zh-CN', setItem: () => { throw new Error('storage unavailable') } }
  globalThis.fetch = async (_url, options) => {
    headers.push(options.headers['Accept-Language'])
    return { ok: true, status: 200, json: async () => ({ ok: true }) }
  }
  try {
    setLocale('en-US')
    await request('/health')
    assert.match(headers[0], /^en-US/)
  } finally {
    globalThis.localStorage = previousStorage
    globalThis.fetch = previousFetch
    setLocale('zh-CN')
  }
})

test('API errors render only catalog text and follow a later language switch', async () => {
  const previousFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    ok: false, status: 401, statusText: 'Unauthorized',
    json: async () => ({ error_code: 'AUTH_INVALID_CREDENTIALS', params: {}, detail: '私有原始错误' }),
  })
  try {
    setLocale('en-US')
    await assert.rejects(request('/auth/login'), err => {
      assert.ok(err instanceof ApiError)
      assert.match(err.message, /credential|password|sign in|log in/i)
      assert.doesNotMatch(err.message, /私有原始错误/)
      setLocale('zh-CN')
      assert.match(err.message, /账号|密码/)
      return true
    })
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('network failures use catalog text instead of the browser exception', async () => {
  const previousFetch = globalThis.fetch
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch') }
  try {
    setLocale('en-US')
    await assert.rejects(request('/health'), err => {
      assert.equal(err.code, 'NETWORK_ERROR')
      assert.match(err.message, /network|connection/i)
      setLocale('zh-CN')
      assert.match(err.message, /网络|连接/)
      return true
    })
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('critical session actions and mistakes launchpad keys are present and localized', () => {
  setLocale('en-US')
  assert.equal(t('home.resume_session'), 'Resume Practice')
  assert.equal(t('home.abandon_session'), 'Abandon Session')
  assert.equal(t('mistakes.select_bank_title'), 'Select Question Bank')
  assert.equal(t('mistakes.cause_oversight'), 'Careless Oversight')

  setLocale('zh-CN')
  assert.equal(t('home.resume_session'), '继续答题')
  assert.equal(t('home.abandon_session'), '放弃会话')
  assert.equal(t('mistakes.select_bank_title'), '请选择题库')
  assert.equal(t('mistakes.cause_oversight'), '审题遗漏')
})

test('no raw un-localized Chinese characters remain in Vue template markup', () => {
  const srcDir = path.resolve(fileURLToPath(import.meta.url), '../../src')
  const chineseRegex = /[\u4e00-\u9fa5]/
  const violations = []

  function scan(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true })
    for (const ent of entries) {
      const full = path.join(dir, ent.name)
      if (ent.isDirectory()) {
        scan(full)
      } else if (ent.name.endsWith('.vue')) {
        const text = fs.readFileSync(full, 'utf8')
        // Extract template portion
        const templateMatch = text.match(/<template>([\s\S]*?)<\/template>/)
        if (!templateMatch) continue
        const templateContent = templateMatch[1]
        // Strip HTML comments
        const noComments = templateContent.replace(/<!--[\s\S]*?-->/g, '')
        const lines = noComments.split('\n')
        lines.forEach((line, idx) => {
          if (chineseRegex.test(line)) {
            violations.push(`${ent.name}:${idx + 1} -> ${line.trim()}`)
          }
        })
      }
    }
  }

  scan(srcDir)
  assert.deepEqual(violations, [], `Found raw Chinese in Vue templates: \n${violations.join('\n')}`)
})

test('the delivery source scanner rejects raw English UI copy and accepts catalog-backed copy', () => {
  const raw = '<template><button title="Open settings">Settings</button></template>'
  const translated = `<template><button :title="t('ui.settings')">{{ t('ui.settings') }}</button></template>`
  assert.equal(inspectVueSource(raw).length, 2, 'visible text and accessible name must both be gated')
  assert.deepEqual(inspectVueSource(translated), [])
  assert.equal(
    inspectVueSource(`<script setup>function remove(){ window.confirm('Delete this bank?') }</script>`).length,
    1,
    'browser dialogs must also use the locale catalog'
  )
  assert.deepEqual(inspectVueSource(`<script setup>function remove(){ window.confirm(t('ui.confirm_delete')) }</script>`), [])
})
