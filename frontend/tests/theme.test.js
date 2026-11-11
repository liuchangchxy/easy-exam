import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  DEFAULT_MODE,
  DEFAULT_PALETTE,
  LEGACY_PALETTE_ALIASES,
  PALETTE_LABELS,
  PALETTE_SURFACES,
  THEME_PALETTES,
  applyAccentPreference,
  applyFullTheme,
  applyPalettePreference,
  applyThemePreference,
  calculateContrastRatio,
  calculateRelativeLuminance,
  getAccessibleForeground,
  getContrastTextColor,
  getPaletteSurface,
  isValidHexColor,
  mixHex,
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

function readCssBlock(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\n\\}`))
  assert.ok(match, `${selector} token block must exist in style.css`)
  return match[1]
}

function readToken(block, name) {
  const match = block.match(new RegExp(`--${name}:\\s*([^;]+);`))
  assert.ok(match, `--${name} must be defined`)
  return match[1].trim()
}

function assertHexToken(block, name) {
  const value = readToken(block, name)
  assert.match(value, /^#[0-9a-f]{6}$/i, `--${name} must be a literal hex token, got ${value}`)
  return value
}

const paletteBlocks = () => [
  { label: 'editorial light', selector: ':root' },
  { label: 'editorial dark', selector: '[data-theme="dark"]' },
  ...THEME_PALETTES.filter(p => p !== 'editorial').flatMap(palette => [
    { label: `${palette} light`, selector: `[data-theme-palette="${palette}"]` },
    { label: `${palette} dark`, selector: `[data-theme="dark"][data-theme-palette="${palette}"]` },
  ]),
]

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
  assert.equal(writePalettePreference(storage, 'gruvbox'), 'gruvbox')
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

test('palette default is the editorial family', () => {
  assert.equal(DEFAULT_PALETTE, 'editorial')
  assert.equal(readPalettePreference(createStorage()), 'editorial')
  assert.equal(normalizePalettePreference('unknown-color'), 'editorial')
  assert.equal(normalizePalettePreference(null), 'editorial')
})

test('four canonical palette families are recognized, labelled and persistable', () => {
  assert.deepEqual([...THEME_PALETTES], ['editorial', 'gruvbox', 'everforest', 'catppuccin'])
  for (const palette of THEME_PALETTES) {
    assert.ok(PALETTE_LABELS[palette], `Missing label for palette: ${palette}`)
    const storage = createStorage()
    writePalettePreference(storage, palette)
    assert.equal(readPalettePreference(storage), palette)
  }
})

test('legacy palette preferences are aliased instead of lost', () => {
  const expected = {
    'blue-grey': 'editorial',
    mist: 'editorial',
    ocean: 'catppuccin',
    amethyst: 'catppuccin',
    rose: 'gruvbox',
    amber: 'gruvbox',
    forest: 'everforest',
    mocha: 'catppuccin',
  }
  assert.deepEqual({ ...LEGACY_PALETTE_ALIASES }, expected)
  for (const [legacy, palette] of Object.entries(expected)) {
    assert.equal(normalizePalettePreference(legacy), palette, `${legacy} must resolve to ${palette}`)
    assert.equal(normalizePalettePreference(` ${legacy.toUpperCase()} `), palette)
    const storage = createStorage({ 'easyexam-theme-palette': legacy })
    assert.equal(readPalettePreference(storage), palette)
  }
})

test('palette and mode are independent preferences', () => {
  const storage = createStorage()
  writePalettePreference(storage, 'gruvbox')
  writeModePreference(storage, 'dark')

  assert.equal(readPalettePreference(storage), 'gruvbox')
  assert.equal(readModePreference(storage), 'dark')
  assert.equal(readThemePreference(storage), 'dark')

  writeModePreference(storage, 'light')
  assert.equal(readPalettePreference(storage), 'gruvbox', 'changing mode must not reset the palette')

  writePalettePreference(storage, 'catppuccin')
  assert.equal(readModePreference(storage), 'light', 'changing palette must not reset the mode')
})

test('applyPalettePreference sets data-theme-palette on root', () => {
  const root = createMockRoot()
  applyPalettePreference(root, 'everforest')
  assert.equal(root.getAttribute('data-theme-palette'), 'everforest')

  applyPalettePreference(root, 'forest')
  assert.equal(root.getAttribute('data-theme-palette'), 'everforest', 'legacy forest aliases to everforest')

  applyPalettePreference(root, 'invalid')
  assert.equal(root.getAttribute('data-theme-palette'), 'editorial')
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

  // #0891b2 (legacy ocean primary)
  const oceanText = getContrastTextColor('#0891b2')
  assert.equal(oceanText, '#0f172a')
  assert.ok(calculateContrastRatio('#0891b2', oceanText) >= 4.5)
})

test('WCAG AA contrast is mathematically guaranteed (>= 4.5:1) across palette primaries, boundaries, and 200 random legal hex colors', () => {
  // 1. All four palette primary colors
  const palettePrimaries = [
    '#23554b', // editorial
    '#af3a03', // gruvbox
    '#4e6b3f', // everforest
    '#8432e8', // catppuccin
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

test('mixHex correctly blends colors across weights', () => {
  assert.equal(mixHex('#000000', '#ffffff', 0), '#000000')
  assert.equal(mixHex('#000000', '#ffffff', 1), '#ffffff')
  assert.equal(mixHex('#000000', '#ffffff', 0.5), '#808080')
  assert.equal(mixHex('#ff0000', '#0000ff', 0.5), '#800080')
})

test('editorial tokens keep AAA-contrast ink on both light and dark paper', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css'),
    'utf-8'
  )
  const rootBlock = readCssBlock(css, ':root')
  const darkBlock = readCssBlock(css, '[data-theme="dark"]')

  for (const [mode, block] of [['light', rootBlock], ['dark', darkBlock]]) {
    const paper = assertHexToken(block, 'paper')
    const surface = assertHexToken(block, 'surface')
    const ink = assertHexToken(block, 'ink')
    const ink2 = assertHexToken(block, 'ink-2')
    const ink3 = assertHexToken(block, 'ink-3')

    assert.ok(calculateContrastRatio(ink, paper) >= 7, `${mode} ink on paper must reach AAA`)
    assert.ok(calculateContrastRatio(ink2, paper) >= 4.5, `${mode} ink-2 on paper must reach AA`)
    assert.ok(calculateContrastRatio(ink3, paper) >= 4.5, `${mode} ink-3 on paper must reach AA`)
    assert.ok(calculateContrastRatio(ink3, surface) >= 4.5, `${mode} ink-3 on surface must reach AA`)
  }
})

test('every palette family exposes the semantic token contract with AA text, 3:1 boundaries and readable statuses', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css'),
    'utf-8'
  )

  for (const { label, selector } of paletteBlocks()) {
    const block = readCssBlock(css, selector)
    const tokens = {}
    for (const name of [
      'paper', 'surface', 'surface-2', 'ink', 'ink-2', 'ink-3', 'ink-4',
      'line', 'line-strong', 'brand', 'brand-hover', 'brand-active', 'brand-ink',
      'brand-contrast', 'on-brand-hover', 'on-brand-active',
      'ok', 'bad', 'warn', 'on-bad',
    ]) {
      tokens[name] = assertHexToken(block, name)
    }

    assert.ok(calculateContrastRatio(tokens.ink, tokens.paper) >= 7, `${label}: ink on paper must reach AAA`)
    assert.ok(calculateContrastRatio(tokens.ink, tokens.surface) >= 7, `${label}: ink on surface must reach AAA`)

    for (const surfaceName of ['paper', 'surface', 'surface-2']) {
      for (const textName of ['ink-2', 'ink-3', 'ink-4']) {
        assert.ok(
          calculateContrastRatio(tokens[textName], tokens[surfaceName]) >= 4.5,
          `${label}: --${textName} on --${surfaceName} is ${calculateContrastRatio(tokens[textName], tokens[surfaceName]).toFixed(2)}:1 (must be >= 4.5:1)`
        )
      }
      for (const statusName of ['brand', 'ok', 'bad', 'warn']) {
        assert.ok(
          calculateContrastRatio(tokens[statusName], tokens[surfaceName]) >= 4.5,
          `${label}: --${statusName} on --${surfaceName} is ${calculateContrastRatio(tokens[statusName], tokens[surfaceName]).toFixed(2)}:1 (must be >= 4.5:1)`
        )
      }
    }

    for (const surfaceName of ['paper', 'surface']) {
      assert.ok(
        calculateContrastRatio(tokens['line-strong'], tokens[surfaceName]) >= 3,
        `${label}: --line-strong on --${surfaceName} must reach 3:1 for control boundaries`
      )
      assert.ok(
        calculateContrastRatio(tokens.line, tokens[surfaceName]) >= 1.5,
        `${label}: --line on --${surfaceName} must stay visible (>= 1.5:1)`
      )
    }

    // Filled brand controls: base, hover and active each pair with the
    // foreground computed for that exact shade.
    assert.ok(calculateContrastRatio(tokens['brand-contrast'], tokens.brand) >= 4.5, `${label}: brand base contrast`)
    assert.ok(calculateContrastRatio(tokens['on-brand-hover'], tokens['brand-hover']) >= 4.5, `${label}: brand hover contrast`)
    assert.ok(calculateContrastRatio(tokens['on-brand-active'], tokens['brand-active']) >= 4.5, `${label}: brand active contrast`)
    assert.ok(calculateContrastRatio(tokens['on-bad'], tokens.bad) >= 4.5, `${label}: --on-bad on --bad must reach AA`)
    assert.ok(
      calculateContrastRatio(tokens['brand-ink'], mixHex(tokens.surface, tokens.brand, 0.10)) >= 4.5,
      `${label}: --brand-ink on --brand-soft must reach AA`
    )

    // Status text sits on an 8% tint of its own hue in chips and options.
    for (const statusName of ['ok', 'bad', 'warn']) {
      const soft = mixHex(tokens.surface, tokens[statusName], 0.08)
      assert.ok(
        calculateContrastRatio(tokens[statusName], soft) >= 4.5,
        `${label}: --${statusName} on its soft tint ${soft} must reach AA`
      )
    }
  }
})

test('style.css defines a light and dark block for every palette family', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css'),
    'utf-8'
  )
  for (const palette of THEME_PALETTES.filter(p => p !== 'editorial')) {
    assert.ok(css.includes(`[data-theme-palette="${palette}"]`), `Missing light block for ${palette}`)
    assert.ok(
      css.includes(`[data-theme="dark"][data-theme-palette="${palette}"]`),
      `Missing dark block for ${palette}`
    )
  }
  for (const name of ['text-quiet', 'divider-strong', 'accent', 'state-success', 'state-danger', 'state-warning']) {
    assert.ok(css.includes(`--${name}:`), `Semantic token --${name} must be defined`)
  }
})

test('PALETTE_SURFACES stays in sync with the palette token blocks in style.css', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css'),
    'utf-8'
  )

  for (const palette of THEME_PALETTES) {
    const lightSelector = palette === 'editorial' ? ':root' : `[data-theme-palette="${palette}"]`
    const darkSelector = palette === 'editorial'
      ? '[data-theme="dark"]'
      : `[data-theme="dark"][data-theme-palette="${palette}"]`
    const light = readCssBlock(css, lightSelector)
    const dark = readCssBlock(css, darkSelector)
    const surfaces = getPaletteSurface(palette)

    assert.equal(assertHexToken(light, 'paper'), surfaces.lightPage, `${palette}: light page mismatch`)
    assert.equal(assertHexToken(light, 'surface'), surfaces.light, `${palette}: light card mismatch`)
    assert.equal(assertHexToken(light, 'surface-2'), surfaces.lightSubtle, `${palette}: light subtle mismatch`)
    assert.equal(assertHexToken(dark, 'paper'), surfaces.darkPage, `${palette}: dark page mismatch`)
    assert.equal(assertHexToken(dark, 'surface'), surfaces.dark, `${palette}: dark card mismatch`)
    assert.equal(assertHexToken(dark, 'surface-2'), surfaces.darkSubtle, `${palette}: dark subtle mismatch`)
  }
})

test('style.css never declares text smaller than 10px', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css'),
    'utf-8'
  )
  const sizes = [...css.matchAll(/font-size:\s*([\d.]+)px/g)].map(match => Number(match[1]))
  assert.ok(sizes.length > 0)
  const smallest = Math.min(...sizes)
  assert.ok(smallest >= 10, `style.css declares an unreadably small font-size of ${smallest}px`)
})

test('getAccessibleForeground guarantees WCAG AA contrast against surfaces across all four palettes and translucent accents', () => {
  const testAccents = ['#ffffff', '#000000', '#fbbf24', '#0891b2', '#d97706', '#60a5fa', '#2563eb', '#ffff00', '#777777']
  for (const pal of THEME_PALETTES) {
    const surfaces = getPaletteSurface(pal)
    for (const isDark of [false, true]) {
      const page = isDark ? surfaces.darkPage : surfaces.lightPage
      const card = isDark ? surfaces.dark : surfaces.light
      const subtle = isDark ? surfaces.darkSubtle : surfaces.lightSubtle
      for (const hex of testAccents) {
        const fg = getAccessibleForeground(hex, isDark, pal)
        const transCard = mixHex(card, hex, isDark ? 0.16 : 0.14)
        const transSubtle = mixHex(subtle, hex, isDark ? 0.16 : 0.14)
        const transPage = mixHex(page, hex, isDark ? 0.16 : 0.14)
        assert.ok(
          calculateContrastRatio(fg, card) >= 4.5,
          `Foreground ${fg} on card ${card} (${pal} dark=${isDark}) contrast is below 4.5:1 for accent ${hex}`
        )
        assert.ok(
          calculateContrastRatio(fg, subtle) >= 4.5,
          `Foreground ${fg} on subtle ${subtle} (${pal} dark=${isDark}) contrast is below 4.5:1 for accent ${hex}`
        )
        assert.ok(
          calculateContrastRatio(fg, page) >= 4.5,
          `Foreground ${fg} on page ${page} (${pal} dark=${isDark}) contrast is below 4.5:1 for accent ${hex}`
        )
        assert.ok(
          calculateContrastRatio(fg, transCard) >= 4.5,
          `Foreground ${fg} on translucent card ${transCard} (${pal} dark=${isDark}) contrast is below 4.5:1 for accent ${hex}`
        )
        assert.ok(
          calculateContrastRatio(fg, transSubtle) >= 4.5,
          `Foreground ${fg} on translucent subtle ${transSubtle} (${pal} dark=${isDark}) contrast is below 4.5:1 for accent ${hex}`
        )
        assert.ok(
          calculateContrastRatio(fg, transPage) >= 4.5,
          `Foreground ${fg} on translucent page ${transPage} (${pal} dark=${isDark}) contrast is below 4.5:1 for accent ${hex}`
        )
      }
    }
  }
})

test('confirmed reviewer counterexamples guarantee WCAG AA >= 4.5:1 across actual surfaces and composite primary-light', () => {
  const counterexamples = [
    { palette: 'everforest', isDark: false, accent: '#ffff00', desc: 'Everforest light + custom #ffff00' },
    { palette: 'catppuccin', isDark: false, accent: '#cccc66', desc: 'Catppuccin light + custom #cccc66' },
    { palette: 'gruvbox', isDark: true, accent: '#338833', desc: 'Gruvbox dark + custom #338833' },
    { palette: 'editorial', isDark: false, accent: '#ffffff', desc: 'Editorial light + custom #ffffff' },
    { palette: 'editorial', isDark: true, accent: '#000000', desc: 'Editorial dark + custom #000000' },
  ]

  for (const { palette, isDark, accent, desc } of counterexamples) {
    const fg = getAccessibleForeground(accent, isDark, palette)
    const s = getPaletteSurface(palette)
    const card = isDark ? s.dark : s.light
    const subtle = isDark ? s.darkSubtle : s.lightSubtle
    const page = isDark ? s.darkPage : s.lightPage
    const alpha = isDark ? 0.16 : 0.14
    const transCard = mixHex(card, accent, alpha)
    const transSubtle = mixHex(subtle, accent, alpha)
    const transPage = mixHex(page, accent, alpha)

    const surfaces = [
      { name: 'card', color: card },
      { name: 'subtle', color: subtle },
      { name: 'page', color: page },
      { name: 'transCard', color: transCard },
      { name: 'transSubtle', color: transSubtle },
      { name: 'transPage', color: transPage },
    ]

    for (const surf of surfaces) {
      const ratio = calculateContrastRatio(fg, surf.color)
      assert.ok(
        ratio >= 4.5,
        `${desc}: fg ${fg} against ${surf.name} ${surf.color} is ${ratio.toFixed(2)}:1 (must be >= 4.5:1)`
      )
    }
  }
})

test('custom accent applies readable brand + primary tokens for base, hover and active in every palette and mode', () => {
  const accents = ['#ffffff', '#000000', '#fbbf24', '#0891b2', '#d97706', '#60a5fa', '#2563eb', '#ffff00', '#777777', '#1d4ed8']

  for (const palette of THEME_PALETTES) {
    const surfaces = getPaletteSurface(palette)
    for (const isDark of [false, true]) {
      const page = isDark ? surfaces.darkPage : surfaces.lightPage
      const card = isDark ? surfaces.dark : surfaces.light
      const subtle = isDark ? surfaces.darkSubtle : surfaces.lightSubtle

      for (const accent of accents) {
        const root = createMockRoot()
        applyAccentPreference(root, accent, isDark ? 'dark' : 'light', palette)
        const get = prop => root.style.getPropertyValue(prop)

        const brand = get('--brand')
        const brandHover = get('--brand-hover')
        const brandActive = get('--brand-active')
        assert.match(brand, /^#[0-9a-f]{6}$/i)
        assert.match(brandHover, /^#[0-9a-f]{6}$/i)
        assert.match(brandActive, /^#[0-9a-f]{6}$/i)

        const brandSurfaces = [
          page,
          card,
          subtle,
          mixHex(card, accent, isDark ? 0.16 : 0.14),
          mixHex(subtle, accent, isDark ? 0.16 : 0.14),
          mixHex(page, accent, isDark ? 0.16 : 0.14),
          // --brand-soft is a 10% tint of the raw accent over the card surface.
          mixHex(card, accent, 0.10),
        ]
        for (const surface of brandSurfaces) {
          assert.ok(
            calculateContrastRatio(brand, surface) >= 4.5,
            `${palette} ${isDark ? 'dark' : 'light'} accent ${accent}: --brand ${brand} on ${surface} must reach AA`
          )
        }

        assert.ok(calculateContrastRatio(get('--brand-contrast'), brand) >= 4.5, 'brand base foreground')
        assert.ok(calculateContrastRatio(get('--on-brand-hover'), brandHover) >= 4.5, 'brand hover foreground')
        assert.ok(calculateContrastRatio(get('--on-brand-active'), brandActive) >= 4.5, 'brand active foreground')
        assert.ok(calculateContrastRatio(get('--on-primary'), get('--primary')) >= 4.5, 'primary base foreground')
        assert.ok(calculateContrastRatio(get('--on-primary-hover'), get('--primary-hover')) >= 4.5, 'primary hover foreground')
        assert.ok(calculateContrastRatio(get('--on-primary-active'), get('--primary-active')) >= 4.5, 'primary active foreground')
      }
    }
  }
})

test('custom accent cleanup removes every applied brand and primary token', () => {
  const root = createMockRoot()
  applyAccentPreference(root, '#ffffff', 'light', 'editorial')
  assert.ok(root.style.getPropertyValue('--brand'))
  assert.ok(root.style.getPropertyValue('--on-brand-hover'))
  assert.ok(root.style.getPropertyValue('--brand-active'))

  applyAccentPreference(root, '')
  for (const prop of [
    '--primary', '--primary-fg', '--on-primary', '--on-primary-hover', '--on-primary-active',
    '--primary-hover', '--primary-active', '--primary-light', '--primary-border',
    '--brand', '--brand-hover', '--brand-active', '--brand-ink', '--brand-soft',
    '--brand-line', '--brand-contrast', '--on-brand-hover', '--on-brand-active',
  ]) {
    assert.equal(root.style.getPropertyValue(prop), '', `${prop} must be removed on reset`)
  }

  applyAccentPreference(root, 'invalid-hex')
  assert.equal(root.style.getPropertyValue('--primary'), '')
})

test('applyFullTheme coordinates palette, mode and custom accent, including legacy palette ids', () => {
  const root = createMockRoot()
  const result = applyFullTheme({
    root,
    mode: 'system',
    palette: 'forest',
    customAccent: '#0891b2',
    isSystemDark: true,
  })

  assert.equal(result.effectiveTheme, 'dark')
  assert.equal(result.palette, 'everforest')
  assert.equal(result.customAccent, '#0891b2')
  assert.equal(root.getAttribute('data-theme'), 'dark')
  assert.equal(root.getAttribute('data-theme-palette'), 'everforest')
  assert.equal(root.style.getPropertyValue('--primary'), '#0891b2')
  assert.ok(root.style.getPropertyValue('--brand'))
})
