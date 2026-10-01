import { resolveInitialLocale } from '../design/localePreference.js'

const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `API request failed: ${status}`)
    this.status = status
    this.detail = detail
  }
}

export async function request(path, options = {}) {
  const currentLang = resolveInitialLocale()
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Accept-Language': currentLang === 'en-US' ? 'en-US,en;q=0.9' : 'zh-CN,zh;q=0.9',
      ...(options.headers || {}),
    },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch (_) {
      // Keep the HTTP status when the server returned no JSON body.
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return null
  return response.json()
}

export function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}
