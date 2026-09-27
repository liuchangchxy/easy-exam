import { ref } from 'vue'
import { getLearningSummary, getLearningTrends, getRecommendations, getStudyPlan } from '../api/learning'
import { listMistakes } from '../api/mistakes'

export function useLearningStore() {
  const summary = ref(null)
  const trends = ref(null)
  const recommendations = ref([])
  const mistakes = ref([])
  const plan = ref(null)
  const loading = ref(false)
  const error = ref('')

  async function load(token, bankId = '', minutesPerDay = 30, days = 7) {
    loading.value = true
    error.value = ''
    try {
      const params = bankId ? { bank_id: bankId } : {}
      ;[summary.value, trends.value, recommendations.value, mistakes.value, plan.value] = await Promise.all([
        getLearningSummary(token),
        getLearningTrends(token, params),
        getRecommendations(token, { ...params, limit: 20 }),
        listMistakes(token, bankId),
        getStudyPlan(token, { ...params, minutes_per_day: minutesPerDay, days }),
      ])
    } catch (err) {
      error.value = err.detail || err.message
    } finally {
      loading.value = false
    }
  }

  async function reloadRecommendations(token, bankId = '', options = {}) {
    try {
      const params = { ...(bankId ? { bank_id: bankId } : {}), ...options }
      recommendations.value = await getRecommendations(token, params)
    } catch (err) {
      error.value = err.detail || err.message
    }
  }

  async function reloadStudyPlan(token, bankId = '', minutesPerDay = 30, days = 7) {
    try {
      const params = { ...(bankId ? { bank_id: bankId } : {}), minutes_per_day: minutesPerDay, days }
      plan.value = await getStudyPlan(token, params)
    } catch (err) {
      error.value = err.detail || err.message
    }
  }

  return { summary, trends, recommendations, mistakes, plan, loading, error, load, reloadRecommendations, reloadStudyPlan }
}
