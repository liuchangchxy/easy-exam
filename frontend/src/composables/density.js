// Single source for the interface density preference. SettingsView writes it,
// main.js restores it before the first render, and both read the same key and
// normalization rules so the saved density survives a refresh on any route.

export const DENSITY_STORAGE_KEY = 'easyexam-density'

export function normalizeDensityPreference(value) {
  return value === 'dense' ? 'dense' : 'balanced'
}

export function readDensityPreference() {
  let saved = ''
  try {
    saved = globalThis.localStorage?.getItem(DENSITY_STORAGE_KEY) || ''
  } catch {
    saved = ''
  }
  return normalizeDensityPreference(saved)
}

export function restoreDensityPreference(root = globalThis.document?.documentElement) {
  const density = readDensityPreference()
  if (root) root.setAttribute('data-density', density)
  return density
}
