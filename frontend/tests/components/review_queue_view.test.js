import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ReviewView from '../../src/views/ReviewView.vue'
import { t } from '../../src/composables/useLocale.js'

const mockQuery = vi.hoisted(() => ({ value: {} }))
const state = vi.hoisted(() => ({ due: [], mistakes: [], killed: [] }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mockQuery.value }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn().mockResolvedValue([
    { id: 'b1', name: 'Bank One' },
    { id: 'b2', name: 'Bank Two' },
  ]),
}))

vi.mock('../../src/api/mistakes', () => ({
  listDueMistakes: vi.fn(async () => state.due),
  listMistakes: vi.fn(async () => state.mistakes),
  listWeakMistakes: vi.fn(async () => state.weak || []),
  updateMistakeCause: vi.fn(),
}))

vi.mock('../../src/api/kills', () => ({
  listKills: vi.fn(async () => state.killed),
  killQuestion: vi.fn(),
  unkillQuestion: vi.fn(),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn().mockResolvedValue({ id: 's1' }),
  listActiveSessions: vi.fn().mockResolvedValue([]),
  abandonSession: vi.fn().mockResolvedValue({}),
  abandonAllSessions: vi.fn().mockResolvedValue({}),
}))

vi.mock('../../src/api/learning', () => ({
  getLearningTrends: vi.fn().mockResolvedValue(null),
  getStudyPlan: vi.fn().mockResolvedValue(null),
  getRecommendations: vi.fn().mockResolvedValue([]),
}))

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 50))

async function mountView(query = {}) {
  mockQuery.value = query
  const wrapper = mount(ReviewView, { props: { token: 'test-token' } })
  await flushPromises()
  return wrapper
}

function rowKeys(wrapper) {
  return wrapper.findAll('.review-queue-row').map(row => row.attributes('data-key'))
}

describe('ReviewView unified review queue', () => {
  beforeEach(() => {
    state.due = [
      { question_id: 'q1', bank_id: 'b1', stem: 'One', type: 'SINGLE', due_at: '2026-11-13T08:00:00Z', mistake_count: 3, is_weak_flagged: true },
      { question_id: 'q2', bank_id: 'b2', stem: 'Two', type: 'SINGLE', due_at: '2026-11-13T09:00:00Z', is_weak_flagged: false },
    ]
    state.mistakes = [
      { question_id: 'q1', bank_id: 'b1', stem: 'One', type: 'SINGLE', mistake_count: 3 },
      { question_id: 'q3', bank_id: 'b2', stem: 'Three', type: 'SINGLE', mistake_count: 1 },
    ]
    state.killed = [
      { question_id: 'q4', bank_id: 'b1', stem: 'Four', type: 'SINGLE', killed_at: '2026-11-12T08:00:00Z' },
    ]
  })

  it('opens on the merged 全部 view by default and deduplicates sources', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="review-tab-all"]').classes()).toContain('is-active')
    expect(wrapper.find('.review-queue').exists()).toBe(true)
    // q1 is both due and a mistake; it must appear once.
    expect(rowKeys(wrapper)).toEqual(['b1::q1', 'b2::q2', 'b2::q3', 'b1::q4'])

    wrapper.unmount()
  })

  it('shows every applicable reason as a tag on the row', async () => {
    const wrapper = await mountView()

    const row = wrapper.find('[data-key="b1::q1"]')
    const tags = row.findAll('.review-reason-tag').map(tag => tag.text())
    expect(tags).toContain(t('ep.review.tab_due'))
    expect(tags).toContain(t('ep.review.tab_mistakes'))
    expect(tags).toContain(t('ep.review.weak'))

    wrapper.unmount()
  })

  it('keeps the 错题 tab showing only mistakes', async () => {
    const wrapper = await mountView()

    await wrapper.findAll('.tabs .tab').at(1).trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="review-tab-mistakes"]').classes()).toContain('is-active')
    expect(wrapper.findAll('.review-queue-row')).toHaveLength(0)
    expect(wrapper.findAll('.mistake-row')).toHaveLength(2)

    wrapper.unmount()
  })

  it('lands on the killed tab when ?source=killed is in the address', async () => {
    const wrapper = await mountView({ source: 'killed' })

    expect(wrapper.find('[data-testid="review-tab-killed"]').classes()).toContain('is-active')
    expect(wrapper.find('.review-queue').exists()).toBe(false)
    expect(wrapper.findAll('.review-single').length).toBeGreaterThan(0)

    wrapper.unmount()
  })

  it('opens the unified queue with the weak filter for ?source=weak', async () => {
    const wrapper = await mountView({ source: 'weak' })

    expect(wrapper.find('[data-testid="review-tab-all"]').classes()).toContain('is-active')
    expect(wrapper.find('[data-testid="review-reason-weak"]').classes()).toContain('is-on')
    expect(rowKeys(wrapper)).toEqual(['b1::q1'])

    wrapper.unmount()
  })

  it('falls back to the unified queue for an unknown source', async () => {
    const wrapper = await mountView({ source: 'bogus' })

    expect(wrapper.find('[data-testid="review-tab-all"]').classes()).toContain('is-active')
    expect(wrapper.find('[data-testid="review-reason-all"]').classes()).toContain('is-on')
    expect(wrapper.findAll('.review-queue-row')).toHaveLength(4)

    wrapper.unmount()
  })

  it('narrows the merged list with the reason filter', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('.review-queue-row')).toHaveLength(4)

    await wrapper.find('[data-testid="review-reason-mistakes"]').trigger('click')
    expect(rowKeys(wrapper)).toEqual(['b1::q1', 'b2::q3'])

    await wrapper.find('[data-testid="review-reason-weak"]').trigger('click')
    expect(rowKeys(wrapper)).toEqual(['b1::q1'])

    await wrapper.find('[data-testid="review-reason-all"]').trigger('click')
    expect(wrapper.findAll('.review-queue-row')).toHaveLength(4)

    wrapper.unmount()
  })

  it('names the empty source instead of saying no data', async () => {
    state.due = []
    state.mistakes = []
    state.killed = []

    const wrapper = await mountView()
    expect(wrapper.find('.review-queue-empty .empty-title').text()).toBe(t('ep.review.queue_empty'))

    await wrapper.find('[data-testid="review-reason-weak"]').trigger('click')
    expect(wrapper.find('.review-queue-empty .empty-title').text()).toBe(t('ep.review.weak_empty'))

    await wrapper.find('[data-testid="review-reason-due"]').trigger('click')
    expect(wrapper.find('.review-queue-empty .empty-title').text()).toBe(t('ep.review.due_empty'))

    wrapper.unmount()
  })
})
