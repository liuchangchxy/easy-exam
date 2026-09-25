import { authHeaders, request } from './client'

export const getLearningSummary = token => request('/learning/summary', { headers: authHeaders(token) })
export const getLearningTrends = (token, params = {}) => {
  const query = new URLSearchParams(params).toString()
  return request(`/learning/trends${query ? `?${query}` : ''}`, { headers: authHeaders(token) })
}
export const getRecommendations = (token, params = {}) => {
  const query = new URLSearchParams(params).toString()
  return request(`/learning/recommendations${query ? `?${query}` : ''}`, { headers: authHeaders(token) })
}
export const getStudyPlan = (token, params = {}) => {
  const query = new URLSearchParams(params).toString()
  return request(`/learning/plan${query ? `?${query}` : ''}`, { headers: authHeaders(token) })
}

export const markWeak = (token, questionId) => request(`/learning/weak/${encodeURIComponent(questionId)}`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const unmarkWeak = (token, questionId) => request(`/learning/weak/${encodeURIComponent(questionId)}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})

