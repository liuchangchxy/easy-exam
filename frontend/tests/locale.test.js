import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
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
