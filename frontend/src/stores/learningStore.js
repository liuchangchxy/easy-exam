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

  async function load(token, bankId = '', minutesPerDay = 30, days = 7, questionsPerDay = null) {
    loading.value = true
    error.value = ''
    try {
      const params = bankId ? { bank_id: bankId } : {}
      const planParams = { ...params, days }
      if (questionsPerDay) {
        planParams.questions_per_day = questionsPerDay
      } else {
        planParams.minutes_per_day = minutesPerDay
      }
      ;[summary.value, trends.value, recommendations.value, mistakes.value, plan.value] = await Promise.all([
        getLearningSummary(token),
        getLearningTrends(token, params),
        getRecommendations(token, { ...params, limit: 20 }),
        listMistakes(token, bankId),
        getStudyPlan(token, planParams),
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

  async function reloadStudyPlan(token, bankId = '', minutesPerDay = 30, days = 7, questionsPerDay = null) {
    try {
      const params = { ...(bankId ? { bank_id: bankId } : {}), days }
      if (questionsPerDay) {
        params.questions_per_day = questionsPerDay
      } else {
        params.minutes_per_day = minutesPerDay
      }
      plan.value = await getStudyPlan(token, params)
    } catch (err) {
      error.value = err.detail || err.message
    }
  }

  return { summary, trends, recommendations, mistakes, plan, loading, error, load, reloadRecommendations, reloadStudyPlan }
}
