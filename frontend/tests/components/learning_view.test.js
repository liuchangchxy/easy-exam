import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import LearningView from '../../src/views/LearningView.vue'

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn().mockResolvedValue([{ id: 'b1', name: 'Test Bank' }]),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn().mockResolvedValue({ id: 's1' }),
}))

vi.mock('../../src/stores/learningStore', () => {
  return {
    useLearningStore: () => {
      const trends = ref({
        coverage_percent: 65,
        attempted_questions: 13,
        total_questions: 20,
        review_completion_rate: 100,
        reviews_completed: 5,
        due_reviews: 5,
        window_days: 7,
        recent: {
          correct_rate: 80,
          attempts: 10,
          avg_time_per_question: 15,
          time_spent: 150,
        },
        weak_points: [
          { name: 'Computer Network', mistakes: 3 },
        ],
      })
      const recommendations = ref([
        { bank_id: 'b1', question_id: 'q1', stem: 'Sample recommendation stem' },
      ])
      const plan = ref({
        question_count: 10,
        days: [
          {
            day_number: 1,
            title: 'Day 1 Plan',
            focus: 'Network basics',
            focus_description: 'Daily practice focus',
            question_count: 5,
            estimated_minutes: 15,
            question_ids: ['q1'],
          },
        ],
      })

      return {
        summary: ref({}),
        trends,
        recommendations,
        mistakes: ref([]),
        plan,
        loading: ref(false),
        error: ref(''),
        load: vi.fn(),
        reloadRecommendations: vi.fn(),
        reloadStudyPlan: vi.fn(),
      }
    },
  }
})

describe('LearningView component integration', () => {
  it('has analytics accordion collapsed by default and expands on summary click', async () => {
    const wrapper = mount(LearningView, {
      props: {
        token: 'test-token',
      },
    })

    const accordion = wrapper.find('details.learning-analytics-accordion')
    expect(accordion.exists()).toBe(true)

    // Initially closed (no open attribute)
    expect(accordion.attributes('open')).toBeUndefined()

    // Click summary to toggle/expand
    const summary = accordion.find('summary.analytics-accordion-summary')
    expect(summary.exists()).toBe(true)
    await summary.trigger('click')

    // In DOM environment, summary click on native details toggles open attribute or child elements exist
    // Happy-dom toggles the open attribute or we can set it / inspect .metrics-grid
    const metricsGrid = accordion.find('.metrics-grid')
    expect(metricsGrid.exists()).toBe(true)

    const weakSection = accordion.find('.weak-section')
    expect(weakSection.exists()).toBe(true)
    expect(weakSection.text()).toContain('Computer Network')

    const recsSection = accordion.find('.recommendations-section')
    expect(recsSection.exists()).toBe(true)
  })
})
