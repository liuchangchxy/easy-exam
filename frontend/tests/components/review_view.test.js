import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ReviewView from '../../src/views/ReviewView.vue'
import { startSession } from '../../src/api/practice'
import { listBanks } from '../../src/api/banks'
import { t } from '../../src/composables/useLocale.js'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { tab: 'mistakes' } }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}))

const mockState = vi.hoisted(() => ({ mistakes: [] }))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn().mockResolvedValue([
    { id: 'b1', name: 'Bank One' },
    { id: 'b2', name: 'Bank Two' },
  ]),
}))

vi.mock('../../src/api/mistakes', () => ({
  listDueMistakes: vi.fn().mockResolvedValue([]),
  listMistakes: vi.fn(async () => mockState.mistakes),
  listWeakMistakes: vi.fn().mockResolvedValue([]),
  updateMistakeCause: vi.fn(),
}))

vi.mock('../../src/api/kills', () => ({
  listKills: vi.fn().mockResolvedValue([]),
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

async function mountView() {
  const wrapper = mount(ReviewView, { props: { token: 'test-token' } })
  await flushPromises()
  return wrapper
}

describe('ReviewView all-review sessions across banks', () => {
  beforeEach(() => {
    mockState.mistakes = [
      { question_id: 'q1', bank_id: 'b1', stem: 'One', type: 'SINGLE', mistake_count: 1 },
      { question_id: 'q2', bank_id: 'b2', stem: 'Two', type: 'SINGLE', mistake_count: 2 },
    ]
    vi.clearAllMocks()
    startSession.mockResolvedValue({ id: 's1' })
  })

  it('starts "all mistakes" with every bank represented in the list', async () => {
    const wrapper = await mountView()
    const startBtn = wrapper.find('.review-toolbar .btn-primary')
    expect(startBtn.exists()).toBe(true)
    await startBtn.trigger('click')
    await flushPromises()

    expect(startSession).toHaveBeenCalledTimes(1)
    const payload = startSession.mock.calls[0][1]
    expect(payload.mode).toBe('MISTAKE')
    expect(payload.bank_id).toBe('b1')
    expect(payload.question_ids.sort()).toEqual(['q1', 'q2'])
    expect(payload.bank_ids).toEqual(['b1', 'b2'])
    expect(wrapper.emitted('start-session')).toBeTruthy()

    wrapper.unmount()
  })

  it('omits bank_ids when the whole review set belongs to one bank', async () => {
    mockState.mistakes = [
      { question_id: 'q1', bank_id: 'b1', stem: 'One', type: 'SINGLE', mistake_count: 1 },
      { question_id: 'q2', bank_id: 'b1', stem: 'Two', type: 'SINGLE', mistake_count: 2 },
    ]
    const wrapper = await mountView()
    await wrapper.find('.review-toolbar .btn-primary').trigger('click')
    await flushPromises()

    const payload = startSession.mock.calls[0][1]
    expect(payload.bank_id).toBe('b1')
    expect(payload.question_ids.sort()).toEqual(['q1', 'q2'])
    expect(payload.bank_ids).toBeUndefined()

    wrapper.unmount()
  })
})

describe('ReviewView load failure', () => {
  beforeEach(() => {
    mockState.mistakes = []
    vi.clearAllMocks()
    startSession.mockResolvedValue({ id: 's1' })
  })

  it('shows a retry control instead of the empty state when a request rejects', async () => {
    listBanks.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await mountView()

    const error = wrapper.find('.review-load-error')
    expect(error.exists()).toBe(true)
    expect(error.text()).toContain(t('ep.common.load_failed'))

    const retry = error.find('.btn')
    expect(retry.exists()).toBe(true)
    expect(retry.text()).toBe(t('ep.common.retry'))

    expect(wrapper.find('.empty-title').exists()).toBe(false)

    wrapper.unmount()
  })

  it('re-runs the loader when retry is clicked', async () => {
    listBanks.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await mountView()
    expect(listBanks).toHaveBeenCalledTimes(1)

    await wrapper.find('.review-load-error .btn').trigger('click')
    await flushPromises()

    expect(listBanks).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.review-load-error').exists()).toBe(false)

    wrapper.unmount()
  })
})
