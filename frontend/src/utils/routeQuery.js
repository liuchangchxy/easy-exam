// Filter/sort/search state belongs in the URL: a refreshed tab, a bookmarked
// list or a link pasted to a teammate must show the same view. These helpers
// keep the encoding rules in one place so every page writes the same shapes:
// defaults are omitted, empty values are removed, and a replace only happens
// when something actually changed.

export function readQueryString(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw : ''
}

export function readQueryEnum(value, allowed, fallback) {
  const raw = readQueryString(value)
  return allowed.includes(raw) ? raw : fallback
}

export function readQueryNumber(value, fallback, { min = 1, max = 100000 } = {}) {
  const parsed = Number(readQueryString(value))
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(max, Math.max(min, Math.trunc(parsed)))
}

export function buildQuery(current, patch, defaults = {}) {
  const next = { ...(current && typeof current === 'object' ? current : {}) }
  for (const [key, value] of Object.entries(patch)) {
    const isDefault = Object.prototype.hasOwnProperty.call(defaults, key) && value === defaults[key]
    if (value === '' || value === null || value === undefined || isDefault) delete next[key]
    else next[key] = String(value)
  }
  return next
}

export function queriesEqual(a, b) {
  const left = a && typeof a === 'object' ? a : {}
  const right = b && typeof b === 'object' ? b : {}
  const keys = new Set([...Object.keys(left), ...Object.keys(right)])
  for (const key of keys) {
    if (String(left[key] ?? '') !== String(right[key] ?? '')) return false
  }
  return true
}

// Returns true when a navigation was issued. Views render without a router in
// some component tests, so a missing router is a no-op rather than a crash.
export function replaceQueryState(router, current, patch, defaults = {}) {
  const base = current && typeof current === 'object' ? current : {}
  // A value already equal to its default is not a change, even when the
  // address carries it redundantly (`?tab=due`).
  let changed = false
  for (const [key, value] of Object.entries(patch)) {
    const fallback = defaults[key] === undefined || defaults[key] === null ? '' : String(defaults[key])
    const before = readQueryString(base[key]) || fallback
    const after = value === '' || value === null || value === undefined ? fallback : String(value)
    if (before === after) continue
    changed = true
    break
  }
  if (!changed) return false
  if (!router || typeof router.replace !== 'function') return false
  router.replace({ query: buildQuery(base, patch, defaults) })
  return true
}
