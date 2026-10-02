import { getCurrentLocale, t } from '../composables/useLocale.js'

const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  constructor(status, code = 'REQUEST_FAILED', params = {}, structuredDetail = null) {
    super('')
    this.status = status
    this.code = code
    this.params = params
    this.structuredDetail = structuredDetail
    Object.defineProperty(this, 'message', { configurable: true, get: () => this.localizedMessage() })
  }

  localizedMessage() {
    const key = `api_errors.${this.code}`
    const translated = t(key, this.params)
    return translated === key ? t('api_errors.REQUEST_FAILED') : translated
  }

  get detail() {
    return this.structuredDetail ?? this.message
  }
}

export function localizedHeaders(headers = {}, form = false) {
  const currentLang = getCurrentLocale()
  return {
    ...(form ? {} : { 'Content-Type': 'application/json' }),
    'Accept-Language': currentLang === 'en-US' ? 'en-US,en;q=0.9' : 'zh-CN,zh;q=0.9',
    ...headers,
  }
}

async function localizedFetch(path, options) {
  try {
    return await fetch(`${API_PREFIX}${path}`, options)
  } catch (_) {
    throw new ApiError(0, 'NETWORK_ERROR')
  }
}

export async function parseApiResponse(response) {
  if (!response.ok) {
    let body = {}
    try { body = await response.json() } catch (_) {}
    const code = typeof body.error_code === 'string' ? body.error_code : `HTTP_${response.status}`
    const params = body.params && typeof body.params === 'object' && !Array.isArray(body.params) ? body.params : {}
    const structuredDetail = response.status === 409 && body.detail && typeof body.detail === 'object' && !Array.isArray(body.detail) ? body.detail : null
    throw new ApiError(response.status, code, params, structuredDetail)
  }
  if (response.status === 204) return null
  return response.json()
}

export async function request(path, options = {}) {
  const response = await localizedFetch(path, {
    ...options,
    headers: localizedHeaders(options.headers),
  })
  return parseApiResponse(response)
}

export async function requestForm(path, form, options = {}) {
  const response = await localizedFetch(path, {
    ...options,
    method: options.method || 'POST',
    headers: localizedHeaders(options.headers, true),
    body: form,
  })
  return parseApiResponse(response)
}

export function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}
