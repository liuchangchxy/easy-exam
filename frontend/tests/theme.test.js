import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DEFAULT_MODE,
  DEFAULT_PALETTE,
  THEME_PALETTES,
  applyAccentPreference,
  applyFullTheme,
  applyPalettePreference,
  applyThemePreference,
  calculateRelativeLuminance,
  getContrastTextColor,
  isValidHexColor,
  normalizeHexColor,
  normalizeModePreference,
  normalizePalettePreference,
  normalizeThemePreference,
  readAccentPreference,
  readModePreference,
  readPalettePreference,
  readThemePreference,
  resolveEffectiveTheme,
  writeAccentPreference,
  writeModePreference,
  writePalettePreference,
  writeThemePreference,
} from '../src/design/themePreference.js'

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  }
}

function createMockRoot() {
  const attributes = {}
  const properties = new Map()
  return {
    attributes,
    style: {
      colorScheme: '',
      setProperty(prop, val) {
        properties.set(prop, val)
      },
      removeProperty(prop) {
        properties.delete(prop)
      },
      getPropertyValue(prop) {
        return properties.get(prop) || ''
      },
    },
    setAttribute(key, val) {
      attributes[key] = val
    },
    getAttribute(key) {
      return attributes[key] ?? null
    },
  }
}

test('theme preference defaults to light when nothing has been saved', () => {
  assert.equal(readThemePreference(createStorage()), 'light')
})

test('theme preference restores a saved dark choice', () => {
  const storage = createStorage({ 'easyexam-theme': 'dark' })
  assert.equal(readThemePreference(storage), 'dark')
})

test('theme preference rejects unknown persisted values', () => {
  assert.equal(normalizeThemePreference('sepia'), 'light')
  assert.equal(readThemePreference(createStorage({ 'easyexam-theme': 'sepia' })), 'light')
})

test('theme preference remains usable when browser storage throws', () => {
  const storage = {
    getItem() { throw new Error('storage disabled') },
    setItem() { throw new Error('storage disabled') },
    removeItem() { throw new Error('storage disabled') },
  }

  assert.equal(readThemePreference(storage), 'light')
  assert.equal(writeThemePreference(storage, 'dark'), 'dark')
  assert.equal(readPalettePreference(storage), DEFAULT_PALETTE)
  assert.equal(writePalettePreference(storage, 'ocean'), 'ocean')
  assert.equal(readModePreference(storage), DEFAULT_MODE)
  assert.equal(writeModePreference(storage, 'system'), 'system')
  assert.equal(readAccentPreference(storage), '')
  assert.equal(writeAccentPreference(storage, '#2563eb'), '#2563eb')
})

test('theme preference applies to the document root and is saved', () => {
  const storage = createStorage()
  const root = createMockRoot()

  const applied = applyThemePreference(root, 'dark')
  writeThemePreference(storage, applied)

  assert.equal(root.attributes['data-theme'], 'dark')
  assert.equal(root.style.colorScheme, 'dark')
  assert.equal(readThemePreference(storage), 'dark')
})

test('palette preference defaults to neutral blue-grey', () => {
  const storage = createStorage()
  assert.equal(readPalettePreference(storage), 'blue-grey')
  assert.equal(normalizePalettePreference('unknown-color'), 'blue-grey')
})

test('all 8 theme palettes are recognized and persistable', () => {
  assert.equal(THEME_PALETTES.length, 8)
  const expected = ['blue-grey', 'mist', 'ocean', 'amethyst', 'rose', 'amber', 'forest', 'mocha']
  for (const p of expected) {
    assert.ok(THEME_PALETTES.includes(p), `Missing palette: ${p}`)
    const storage = createStorage()
    writePalettePreference(storage, p)
    assert.equal(readPalettePreference(storage), p)
  }
})

test('applyPalettePreference sets data-theme-palette on root', () => {
  const root = createMockRoot()
  applyPalettePreference(root, 'forest')
  assert.equal(root.getAttribute('data-theme-palette'), 'forest')

  applyPalettePreference(root, 'invalid')
  assert.equal(root.getAttribute('data-theme-palette'), 'blue-grey')
})

test('mode preference supports light, dark, and system', () => {
  const storage = createStorage()
  assert.equal(readModePreference(storage), 'light')

  writeModePreference(storage, 'dark')
  assert.equal(readModePreference(storage), 'dark')
  assert.equal(readThemePreference(storage), 'dark')

  writeModePreference(storage, 'system')
  assert.equal(readModePreference(storage), 'system')

  // Resolve effective theme
  assert.equal(resolveEffectiveTheme('system', false), 'light')
  assert.equal(resolveEffectiveTheme('system', true), 'dark')
  assert.equal(resolveEffectiveTheme('light', true), 'light')
  assert.equal(resolveEffectiveTheme('dark', false), 'dark')
})

test('custom accent color validation and normalization', () => {
  assert.equal(isValidHexColor('#fff'), true)
  assert.equal(isValidHexColor('#2563EB'), true)
  assert.equal(isValidHexColor('blue'), false)
  assert.equal(isValidHexColor('#12'), false)
  assert.equal(isValidHexColor('#1234567'), false)
  assert.equal(isValidHexColor(null), false)

  assert.equal(normalizeHexColor('#fff'), '#ffffff')
  assert.equal(normalizeHexColor('#3B82F6'), '#3b82f6')
  assert.equal(normalizeHexColor('invalid'), null)
})

test('custom accent relative luminance and WCAG text contrast calculation', () => {
  // Pure white has high luminance -> dark text
  assert.equal(getContrastTextColor('#ffffff'), '#0f172a')
  // Pure black has low luminance -> white text
  assert.equal(getContrastTextColor('#000000'), '#ffffff')
  // Deep blue (#1d4ed8) -> white text
  assert.equal(getContrastTextColor('#1d4ed8'), '#ffffff')
  // Pale yellow (#fef08a) -> dark text
  assert.equal(getContrastTextColor('#fef08a'), '#0f172a')
})

test('applyAccentPreference sets inline variables on root and cleans up on reset', () => {
  const root = createMockRoot()

  applyAccentPreference(root, '#2563eb')
  assert.equal(root.style.getPropertyValue('--primary'), '#2563eb')
  assert.equal(root.style.getPropertyValue('--on-primary'), '#ffffff')
  assert.ok(root.style.getPropertyValue('--primary-hover').includes('color-mix'))

  // Reset or invalid removes the custom properties
  applyAccentPreference(root, '')
  assert.equal(root.style.getPropertyValue('--primary'), '')
  assert.equal(root.style.getPropertyValue('--on-primary'), '')

  applyAccentPreference(root, 'invalid-hex')
  assert.equal(root.style.getPropertyValue('--primary'), '')
})

test('applyFullTheme coordinates theme, palette, and custom accent', () => {
  const root = createMockRoot()
  const result = applyFullTheme({
    root,
    mode: 'system',
    palette: 'ocean',
    customAccent: '#0891b2',
    isSystemDark: true,
  })

  assert.equal(result.effectiveTheme, 'dark')
  assert.equal(result.palette, 'ocean')
  assert.equal(result.customAccent, '#0891b2')
  assert.equal(root.getAttribute('data-theme'), 'dark')
  assert.equal(root.getAttribute('data-theme-palette'), 'ocean')
  assert.equal(root.style.getPropertyValue('--primary'), '#0891b2')
})
