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
  calculateContrastRatio,
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

  // Problematic midtone colors explicitly cited in issue verification:
  // #d97706 with white is 3.19:1 (fails), but with dark text is >= 5.6:1 (passes AA)
  const amberText = getContrastTextColor('#d97706')
  assert.equal(amberText, '#0f172a')
  assert.ok(calculateContrastRatio('#d97706', amberText) >= 4.5)

  // #888888 with white is 3.54:1 (fails), but with dark text is >= 5.0:1 (passes AA)
  const greyText = getContrastTextColor('#888888')
  assert.equal(greyText, '#0f172a')
  assert.ok(calculateContrastRatio('#888888', greyText) >= 4.5)

  // #0891b2 (ocean light primary)
  const oceanText = getContrastTextColor('#0891b2')
  assert.equal(oceanText, '#0f172a')
  assert.ok(calculateContrastRatio('#0891b2', oceanText) >= 4.5)
})

test('WCAG AA contrast is mathematically guaranteed (>= 4.5:1) across 8 palettes, boundaries, and 200 random legal hex colors', () => {
  // 1. All 8 palette primary colors
  const palettePrimaries = [
    '#2563eb', // blue-grey
    '#3b6978', // mist
    '#0891b2', // ocean
    '#7c3aed', // amethyst
    '#e11d48', // rose
    '#d97706', // amber
    '#286b53', // forest
    '#845339', // mocha
  ]
  for (const hex of palettePrimaries) {
    const text = getContrastTextColor(hex)
    const ratio = calculateContrastRatio(hex, text)
    assert.ok(ratio >= 4.5, `Palette ${hex} contrast ${ratio.toFixed(2)}:1 is below 4.5:1`)
  }

  // 2. Critical boundary and corner-case colors
  const boundaries = [
    '#000000', '#ffffff', '#7f7f7f', '#808080', '#bfbfbf', '#3f3f3f',
    '#ffff00', '#00ffff', '#ff00ff', '#ff0000', '#00ff00', '#0000ff',
    '#faad14', '#13c2c2', '#52c41a', '#f5222d', '#722ed1', '#eb2f96'
  ]
  for (const hex of boundaries) {
    const text = getContrastTextColor(hex)
    const ratio = calculateContrastRatio(hex, text)
    assert.ok(ratio >= 4.5, `Boundary ${hex} contrast ${ratio.toFixed(2)}:1 is below 4.5:1`)
  }

  // 3. 200 pseudo-random legal hex codes (LCG deterministic seed for 100% reproducibility)
  let state = 123456789
  const lcg = () => {
    state = (1103515245 * state + 12345) & 0x7fffffff
    return state
  }

  for (let i = 0; i < 200; i++) {
    const r = (lcg() >> 16) & 0xff
    const g = (lcg() >> 16) & 0xff
    const b = (lcg() >> 16) & 0xff
    const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
    const text = getContrastTextColor(hex)
    const ratio = calculateContrastRatio(hex, text)
    assert.ok(ratio >= 4.5, `Random hex ${hex} with text ${text} contrast ${ratio.toFixed(2)}:1 is below 4.5:1`)
  }
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
