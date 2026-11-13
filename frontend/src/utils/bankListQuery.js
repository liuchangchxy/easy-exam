// The bank list keeps its view state in the URL so refresh and browser Back
// preserve filters. The in-app back control (AppLayout) cannot read the URL of
// a route it is leaving, so the same normalized state is also kept in
// sessionStorage and replayed when returning to /banks.
export const BANK_LIST_QUERY_KEY = 'easyexam.banks.query'

const ALLOWED_KEYS = ['q', 'category', 'sort', 'view']

export function normalizeBankListQuery(input) {
  const source = input && typeof input === 'object' ? input : {}
  const result = {}
  for (const key of ALLOWED_KEYS) {
    const value = source[key]
    if (typeof value === 'string' && value) result[key] = value
  }
  return result
}

export function readStoredBankListQuery() {
  try {
    const raw = sessionStorage.getItem(BANK_LIST_QUERY_KEY)
    if (!raw) return {}
    return normalizeBankListQuery(JSON.parse(raw))
  } catch {
    return {}
  }
}

export function storeBankListQuery(query) {
  try {
    const normalized = normalizeBankListQuery(query)
    if (Object.keys(normalized).length) {
      sessionStorage.setItem(BANK_LIST_QUERY_KEY, JSON.stringify(normalized))
    } else {
      sessionStorage.removeItem(BANK_LIST_QUERY_KEY)
    }
  } catch {
    // Storage can be unavailable (private mode); the URL remains the source of truth.
  }
}
