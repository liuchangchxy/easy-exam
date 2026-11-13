import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ReviewView from '../../src/views/ReviewView.vue'
import { setLocale } from '../../src/composables/useLocale.js'

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn().mockResolvedValue([
    { id: 'b1', name: 'Bank One' },
    { id: 'b2', name: 'Bank Two' },
  ]),
}))

vi.mock('../../src/api/mistakes', () => ({
  listDueMistakes: vi.fn().mockResolvedValue([]),
  listMistakes: vi.fn().mockResolvedValue([
    { question_id: 'q1', bank_id: 'b1', stem: 'Photosynthesis basics', type: 'SINGLE', mistake_count: 1 },
    { question_id: 'q2', bank_id: 'b2', stem: 'Cell division stages', type: 'SINGLE', mistake_count: 2 },
  ]),
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

const settle = () => new Promise(resolve => setTimeout(resolve, 30))

async function routerAt(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/review', name: 'review', component: { template: '<div />' } }],
  })
  await router.push(path)
  await router.isReady()
  return router
}

async function mountAt(path) {
  const router = await routerAt(path)
  const wrapper = mount(ReviewView, { props: { token: 't1' }, global: { plugins: [router] } })
  await settle()
  return { wrapper, router }
}

function rowKeys(wrapper) {
  return wrapper.findAll('.review-queue-row').map(row => row.attributes('data-key'))
}

afterEach(() => {
  setLocale('zh-CN')
})

describe('ReviewView ?q= and ?scope= contract', () => {
  it('restores both filters from the address on mount', async () => {
    setLocale('zh-CN')
    const { wrapper } = await mountAt('/review?q=cell&scope=b2')
    await settle()

    expect(wrapper.find('[data-testid="review-queue-search"]').element.value).toBe('cell')
    expect(wrapper.find('[data-testid="review-queue-scope"]').element.value).toBe('b2')
    expect(rowKeys(wrapper)).toEqual(['b2::q2'])

    wrapper.unmount()
  })

  it('writes q into the address with replace after the debounce and clears it when emptied', async () => {
    const { wrapper, router } = await mountAt('/review')
    await settle()

    const search = wrapper.find('[data-testid="review-queue-search"]')
    await search.setValue('photo')
    await new Promise(resolve => setTimeout(resolve, 300))
    await settle()

    expect(router.currentRoute.value.query.q).toBe('photo')
    expect(rowKeys(wrapper)).toEqual(['b1::q1'])

    await search.setValue('')
    await new Promise(resolve => setTimeout(resolve, 300))
    await settle()

    expect(router.currentRoute.value.query.q).toBeUndefined()
    expect(rowKeys(wrapper)).toHaveLength(2)

    wrapper.unmount()
  })

  it('writes the picked bank into scope and drops it for all banks', async () => {
    const { wrapper, router } = await mountAt('/review')
    await settle()

    await wrapper.find('[data-testid="review-queue-scope"]').setValue('b1')
    await settle()
    expect(router.currentRoute.value.query.scope).toBe('b1')
    expect(rowKeys(wrapper)).toEqual(['b1::q1'])

    await wrapper.find('[data-testid="review-queue-scope"]').setValue('all')
    await settle()
    expect(router.currentRoute.value.query.scope).toBeUndefined()
    expect(rowKeys(wrapper)).toHaveLength(2)

    wrapper.unmount()
  })

  it('falls back to every bank for an unknown scope id without crashing', async () => {
    const { wrapper, router } = await mountAt('/review?scope=b-missing')
    await settle()

    expect(wrapper.find('[data-testid="review-queue-scope"]').element.value).toBe('all')
    expect(rowKeys(wrapper)).toHaveLength(2)
    // The dead id is repaired out of the address rather than kept forever.
    expect(router.currentRoute.value.query.scope).toBeUndefined()

    wrapper.unmount()
  })
})
