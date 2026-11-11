import { beforeEach, describe, expect, it, vi } from 'vitest'

// Boot-level regression: the density chosen in Settings must survive a refresh
// on any route, not only on the settings page that writes it.
vi.mock('../../src/App.vue', () => ({
  default: { name: 'AppStub', render: () => null },
}))
vi.mock('../../src/router/index.js', () => ({
  default: { install() {} },
}))

const DENSITY_KEY = 'easyexam-density'

async function bootWithSavedDensity(saved) {
  vi.resetModules()
  if (saved === undefined) localStorage.removeItem(DENSITY_KEY)
  else localStorage.setItem(DENSITY_KEY, saved)
  document.documentElement.removeAttribute('data-density')
  document.body.innerHTML = '<div id="app"></div>'
  await import('../../src/main.js')
  return document.documentElement.getAttribute('data-density')
}

describe('density preference restored at boot', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('applies a saved dense preference before any page renders', async () => {
    await expect(bootWithSavedDensity('dense')).resolves.toBe('dense')
  })

  it('applies a saved balanced preference', async () => {
    await expect(bootWithSavedDensity('balanced')).resolves.toBe('balanced')
  })

  it('defaults to balanced when nothing has been saved', async () => {
    await expect(bootWithSavedDensity(undefined)).resolves.toBe('balanced')
  })

  it('normalizes an unknown stored value to balanced', async () => {
    await expect(bootWithSavedDensity('compact')).resolves.toBe('balanced')
  })

  it('still boots with balanced when storage access throws', async () => {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('storage disabled')
      },
    })
    try {
      vi.resetModules()
      document.documentElement.removeAttribute('data-density')
      document.body.innerHTML = '<div id="app"></div>'
      await import('../../src/main.js')
      expect(document.documentElement.getAttribute('data-density')).toBe('balanced')
    } finally {
      if (descriptor) Object.defineProperty(globalThis, 'localStorage', descriptor)
    }
  })
})
