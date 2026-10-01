export const THEME_STORAGE_KEY = 'easyexam-theme'

export function normalizeThemePreference(value) {
  return value === 'dark' ? 'dark' : 'light'
}

export function readThemePreference(storage, key = THEME_STORAGE_KEY) {
  try {
    return normalizeThemePreference(storage?.getItem(key))
  } catch {
    return 'light'
  }
}

export function writeThemePreference(storage, value, key = THEME_STORAGE_KEY) {
  const theme = normalizeThemePreference(value)
  try {
    storage?.setItem(key, theme)
  } catch {
    // Keep the current page usable when private browsing disables storage.
  }
  return theme
}

export function applyThemePreference(root, value) {
  const theme = normalizeThemePreference(value)
  root?.setAttribute?.('data-theme', theme)
  if (root?.style) root.style.colorScheme = theme
  return theme
}
