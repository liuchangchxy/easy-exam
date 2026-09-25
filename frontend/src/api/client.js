const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `API request failed: ${status}`)
    this.status = status
    this.detail = detail
  }
}

export async function request(path, options = {}) {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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
