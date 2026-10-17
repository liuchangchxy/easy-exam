import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  DEFAULT_MODE,
  DEFAULT_PALETTE,
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

test('mixHex correctly blends colors across weights', () => {
  assert.equal(mixHex('#000000', '#ffffff', 0), '#000000')
  assert.equal(mixHex('#000000', '#ffffff', 1), '#ffffff')
  assert.equal(mixHex('#000000', '#ffffff', 0.5), '#808080')
  assert.equal(mixHex('#ff0000', '#0000ff', 0.5), '#800080')
})

test('anti-drift: PALETTE_SURFACES exactly matches actual CSS palette variables in style.css', () => {
  const __dirname = path.dirname(fileURLToPath(import.meta.url))
  const cssPath = path.resolve(__dirname, '../src/style.css')
  const css = fs.readFileSync(cssPath, 'utf-8')

  // Parse :root[data-theme-palette="..."] blocks from style.css
  const paletteBlocks = {}
  const lines = css.split('\n')
  let curPalette = null
  let curTheme = 'light'
  let inBlock = false

  for (const line of lines) {
    const trimmed = line.trim()
    const match = trimmed.match(/:root(?:\[data-theme-palette="([a-z-]+)"])?(?:\[data-theme="(dark)"])?\s*\{/)
    if (match) {
      if (match[1]) curPalette = match[1]
      else if (trimmed.includes(':root,')) curPalette = 'blue-grey'
      curTheme = match[2] === 'dark' || trimmed.includes('[data-theme="dark"]') ? 'dark' : 'light'
      inBlock = true
      if (curPalette) {
        if (!paletteBlocks[curPalette]) paletteBlocks[curPalette] = { light: {}, dark: {} }
      }
    } else if (trimmed === '}') {
      inBlock = false
    } else if (inBlock && curPalette) {
      const vMatch = trimmed.match(/^(--bg-[a-z]+):\s*([^;]+);/)
      if (vMatch) {
        paletteBlocks[curPalette][curTheme][vMatch[1]] = vMatch[2].trim().toLowerCase()
      }
    }
  }

  for (const pal of THEME_PALETTES) {
    const ps = PALETTE_SURFACES[pal]
    assert.ok(ps, `Missing PALETTE_SURFACES definition for ${pal}`)
    const parsed = paletteBlocks[pal]
    assert.ok(parsed, `Missing style.css definition for ${pal}`)

    // Light mode surfaces
    assert.equal(ps.lightPage, parsed.light['--bg-page'], `${pal} lightPage mismatch with style.css --bg-page`)
    assert.equal(ps.light, parsed.light['--bg-card'], `${pal} light card mismatch with style.css --bg-card`)
    assert.equal(ps.lightSubtle, parsed.light['--bg-subtle'], `${pal} lightSubtle mismatch with style.css --bg-subtle`)

    // Dark mode surfaces
    assert.equal(ps.darkPage, parsed.dark['--bg-page'], `${pal} darkPage mismatch with style.css --bg-page`)
    assert.equal(ps.dark, parsed.dark['--bg-card'], `${pal} dark card mismatch with style.css --bg-card`)
    assert.equal(ps.darkSubtle, parsed.dark['--bg-subtle'], `${pal} darkSubtle mismatch with style.css --bg-subtle`)
  }
})

test('getAccessibleForeground guarantees WCAG AA contrast against surfaces across all 8 palettes and translucent accents', () => {
  const testAccents = ['#ffffff', '#000000', '#fbbf24', '#0891b2', '#d97706', '#60a5fa', '#2563eb', '#ffff00', '#777777']
  for (const pal of THEME_PALETTES) {
    const surfaces = PALETTE_SURFACES[pal]
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
    { palette: 'forest', isDark: false, accent: '#ffff00', desc: 'Forest light + custom #ffff00' },
    { palette: 'mocha', isDark: false, accent: '#cccc66', desc: 'Mocha light + custom #cccc66' },
    { palette: 'amber', isDark: true, accent: '#338833', desc: 'Amber dark + custom #338833' },
    { palette: 'blue-grey', isDark: false, accent: '#ffffff', desc: 'Blue-grey light + custom #ffffff' },
    { palette: 'blue-grey', isDark: true, accent: '#000000', desc: 'Blue-grey dark + custom #000000' },
  ]

  for (const { palette, isDark, accent, desc } of counterexamples) {
    const fg = getAccessibleForeground(accent, isDark, palette)
    const s = PALETTE_SURFACES[palette]
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

test('status foreground/background pairs guarantee WCAG AA contrast across all modes', () => {
  // Light mode status pairs:
  // --success #15803d against --on-success #ffffff (>= 5.0:1) and --bg-card #ffffff (>= 5.0:1)
  assert.ok(calculateContrastRatio('#15803d', '#ffffff') >= 4.5, 'Light success #15803d on white must meet AA')
  assert.ok(calculateContrastRatio('#166534', '#ffffff') >= 4.5, 'Light success-hover #166534 on white must meet AA')
  // --danger #dc2626 against --on-danger #ffffff (>= 4.8:1)
  assert.ok(calculateContrastRatio('#dc2626', '#ffffff') >= 4.5, 'Light danger on white must meet AA')
  // --warning #d97706 against --on-warning #1c1408 (>= 5.7:1)
  assert.ok(calculateContrastRatio('#d97706', '#1c1408') >= 4.5, 'Light warning #d97706 on #1c1408 must meet AA')

  // Dark mode status pairs:
  assert.ok(calculateContrastRatio('#4ade80', '#090d16') >= 4.5, 'Dark success on dark on-success must meet AA')
  assert.ok(calculateContrastRatio('#f87171', '#090d16') >= 4.5, 'Dark danger on dark on-danger must meet AA')
  assert.ok(calculateContrastRatio('#fbbf24', '#090d16') >= 4.5, 'Dark warning on dark on-warning must meet AA')

  // Text-safe status token --warning-fg:
  // Must meet AA >= 4.5:1 against white card (#ffffff), subtle (#fef3c7 / #f1f5f9), page (#fffbeb / #f8fafc), and warning-light (#fffbeb)
  const warningFg = '#92400e'
  assert.ok(calculateContrastRatio(warningFg, '#ffffff') >= 4.5, 'Warning text --warning-fg on card #ffffff must meet AA')
  assert.ok(calculateContrastRatio(warningFg, '#fffbeb') >= 4.5, 'Warning text --warning-fg on warning-light #fffbeb must meet AA')
  assert.ok(calculateContrastRatio(warningFg, '#fef3c7') >= 4.5, 'Warning text --warning-fg on subtle #fef3c7 must meet AA')
  assert.ok(calculateContrastRatio(warningFg, '#f8fafc') >= 4.5, 'Warning text --warning-fg on page #f8fafc must meet AA')
  assert.ok(calculateContrastRatio('#fbbf24', '#131b2e') >= 4.5, 'Dark warning text on dark card #131b2e must meet AA')

  // Text-safe status token --danger-fg:
  const dangerFg = '#b91c1c'
  assert.ok(calculateContrastRatio(dangerFg, '#ffffff') >= 4.5, 'Danger text --danger-fg on card #ffffff must meet AA')
  assert.ok(calculateContrastRatio(dangerFg, '#fef2f2') >= 4.5, 'Danger text --danger-fg on danger-light #fef2f2 must meet AA')
  assert.ok(calculateContrastRatio(dangerFg, '#f8fafc') >= 4.5, 'Danger text --danger-fg on page #f8fafc must meet AA')
  assert.ok(calculateContrastRatio('#f87171', '#131b2e') >= 4.5, 'Dark danger text on dark card #131b2e must meet AA')

  // Text-safe status token --success-fg:
  const successFg = '#15803d'
  assert.ok(calculateContrastRatio(successFg, '#ffffff') >= 4.5, 'Success text --success-fg on card #ffffff must meet AA')
  assert.ok(calculateContrastRatio(successFg, '#f0fdf4') >= 4.5, 'Success text --success-fg on success-light #f0fdf4 must meet AA')
  assert.ok(calculateContrastRatio(successFg, '#f8fafc') >= 4.5, 'Success text --success-fg on page #f8fafc must meet AA')
  assert.ok(calculateContrastRatio('#4ade80', '#131b2e') >= 4.5, 'Dark success text on dark card #131b2e must meet AA')

  // Verify style.css definitions match without drift
  const cssPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css')
  const css = fs.readFileSync(cssPath, 'utf8')
  assert.ok(css.includes('--warning-fg: #92400e;'), 'style.css must define light --warning-fg')
  assert.ok(css.includes('--warning-fg: #fbbf24;'), 'style.css must define dark --warning-fg')
  assert.ok(css.includes('--danger-fg: #b91c1c;'), 'style.css must define light --danger-fg')
  assert.ok(css.includes('--danger-fg: #f87171;'), 'style.css must define dark --danger-fg')
  assert.ok(css.includes('--success-fg: #15803d;'), 'style.css must define light --success-fg')
  assert.ok(css.includes('--success-fg: #4ade80;'), 'style.css must define dark --success-fg')
})

test('preset --primary-fg tokens guarantee WCAG AA contrast against their respective card, page, subtle and translucent surfaces', () => {
  // Rose light preset (darkened to #be123c):
  const roseFg = '#be123c'
  const roseSurfaces = PALETTE_SURFACES['rose']
  assert.ok(calculateContrastRatio(roseFg, roseSurfaces.light) >= 4.5, 'Rose fg on card must meet AA')
  assert.ok(calculateContrastRatio(roseFg, roseSurfaces.lightPage) >= 4.5, 'Rose fg on page must meet AA')
  assert.ok(calculateContrastRatio(roseFg, roseSurfaces.lightSubtle) >= 4.5, 'Rose fg on subtle must meet AA')
  const roseTransCard = mixHex(roseSurfaces.light, '#e11d48', 0.14)
  assert.ok(calculateContrastRatio(roseFg, roseTransCard) >= 4.5, 'Rose fg on primary-light must meet AA')
})

test('tertiary text tokens guarantee WCAG AA >= 4.5:1 across all 8 light & dark palettes and surfaces (card, subtle, page)', () => {
  const cssPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/style.css')
  const css = fs.readFileSync(cssPath, 'utf8')

  for (const pal of THEME_PALETTES) {
    const s = PALETTE_SURFACES[pal]

    // Light mode block
    const escapedPal = pal.replace('-', '\\-')
    const palRegex = new RegExp(`:root\\[data-theme-palette="${escapedPal}"\\]\\s*\\{([\\s\\S]*?)\\}`, 'm')
    const lightBlockMatch = css.match(palRegex)
    assert.ok(lightBlockMatch, `Light CSS block for ${pal} must exist`)
    const lightTertMatch = lightBlockMatch[1].match(/--text-tertiary:\s*(#[0-9a-fA-F]{3,8});/)
    assert.ok(lightTertMatch, `Light --text-tertiary for ${pal} must be defined in style.css`)
    const lightTert = lightTertMatch[1]

    for (const [sName, sVal] of Object.entries({ page: s.lightPage, card: s.light, subtle: s.lightSubtle })) {
      const ratio = calculateContrastRatio(lightTert, sVal)
      assert.ok(
        ratio >= 4.5,
        `Light ${pal} --text-tertiary (${lightTert}) on ${sName} (${sVal}) is ${ratio.toFixed(2)}:1 (must be >= 4.5:1)`
      )
    }

    // Dark mode block
    let darkBlockMatch
    if (pal === 'blue-grey') {
      darkBlockMatch = css.match(/:root\[data-theme="dark"\],[^\{]*\{([\s\S]*?)\}/)
    } else {
      const escapedPal = pal.replace('-', '\\-')
      const darkRegex = new RegExp(`:root\\[data-theme-palette="${escapedPal}"\\]\\[data-theme="dark"\\]\\s*\\{([\\s\\S]*?)\\}`, 'm')
      darkBlockMatch = css.match(darkRegex)
    }
    assert.ok(darkBlockMatch, `Dark CSS block for ${pal} must exist`)
    const darkTertMatch = darkBlockMatch[1].match(/--text-tertiary:\s*(#[0-9a-fA-F]{3,8});/)
    const darkMutedMatch = darkBlockMatch[1].match(/--text-muted:\s*(#[0-9a-fA-F]{3,8});/)
    assert.ok(darkTertMatch, `Dark --text-tertiary for ${pal} must be defined in style.css`)
    assert.ok(darkMutedMatch, `Dark --text-muted for ${pal} must be defined in style.css`)
    const darkTert = darkTertMatch[1]
    const darkMuted = darkMutedMatch[1]

    for (const [sName, sVal] of Object.entries({ page: s.darkPage, card: s.dark, subtle: s.darkSubtle })) {
      const ratio = calculateContrastRatio(darkTert, sVal)
      assert.ok(
        ratio >= 4.5,
        `Dark ${pal} --text-tertiary (${darkTert}) on ${sName} (${sVal}) is ${ratio.toFixed(2)}:1 (must be >= 4.5:1)`
      )
    }

    // Dark hierarchy verification
    const mutedRatio = calculateContrastRatio(darkMuted, s.darkSubtle)
    const tertRatio = calculateContrastRatio(darkTert, s.darkSubtle)
    assert.ok(
      tertRatio < mutedRatio,
      `Dark ${pal} hierarchy preserved: tertiary contrast (${tertRatio.toFixed(2)}) must be below muted contrast (${mutedRatio.toFixed(2)})`
    )
  }
})

test('button base, hover, and active states guarantee WCAG AA contrast across presets and custom accents', () => {
  // Problematic preset palettes cited in review:
  // amber light hover #b45309 and active #92400e
  assert.ok(calculateContrastRatio('#b45309', '#ffffff') >= 4.5, 'Amber hover with white text must meet AA')
  assert.ok(calculateContrastRatio('#92400e', '#ffffff') >= 4.5, 'Amber active with white text must meet AA')
  // ocean light hover #0e7490
  assert.ok(calculateContrastRatio('#0e7490', '#ffffff') >= 4.5, 'Ocean hover with white text must meet AA')

  // Custom accents at base, hover, and active
  const accents = ['#d97706', '#0891b2', '#2563eb', '#ffffff', '#000000', '#fbbf24']
  for (const hex of accents) {
    const onPrimary = getContrastTextColor(hex)
    assert.ok(calculateContrastRatio(hex, onPrimary) >= 4.5)

    const hoverTarget = hex === '#000000' ? '#ffffff' : '#000000'
    const hover = mixHex(hex, hoverTarget, 0.12)
    const onHover = getContrastTextColor(hover)
    assert.ok(calculateContrastRatio(hover, onHover) >= 4.5)

    const active = mixHex(hex, hoverTarget, 0.24)
    const onActive = getContrastTextColor(active)
    assert.ok(calculateContrastRatio(active, onActive) >= 4.5)
  }
})

test('applyAccentPreference sets inline variables on root and cleans up on reset', () => {
  const root = createMockRoot()

  applyAccentPreference(root, '#ffffff', 'light')
  assert.equal(root.style.getPropertyValue('--primary'), '#ffffff')
  assert.equal(root.style.getPropertyValue('--on-primary'), '#0f172a')
  assert.ok(root.style.getPropertyValue('--primary-fg'))
  assert.ok(calculateContrastRatio(root.style.getPropertyValue('--primary-fg'), '#ffffff') >= 4.5)
  assert.ok(root.style.getPropertyValue('--on-primary-hover'))
  assert.ok(root.style.getPropertyValue('--on-primary-active'))

  // Reset or invalid removes the custom properties
  applyAccentPreference(root, '')
  assert.equal(root.style.getPropertyValue('--primary'), '')
  assert.equal(root.style.getPropertyValue('--primary-fg'), '')
  assert.equal(root.style.getPropertyValue('--on-primary'), '')
  assert.equal(root.style.getPropertyValue('--on-primary-hover'), '')
  assert.equal(root.style.getPropertyValue('--on-primary-active'), '')

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
  assert.ok(root.style.getPropertyValue('--primary-fg'))
})
