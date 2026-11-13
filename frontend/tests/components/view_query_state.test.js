import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import {
  buildQuery,
  queriesEqual,
  readQueryEnum,
  readQueryNumber,
  readQueryString,
  replaceQueryState,
} from '../../src/utils/routeQuery.js'

describe('routeQuery helpers', () => {
  it('reads strings out of the array shape vue-router produces for repeated keys', () => {
    expect(readQueryString('abc')).toBe('abc')
    expect(readQueryString(['abc', 'def'])).toBe('abc')
    expect(readQueryString(undefined)).toBe('')
    expect(readQueryString(3)).toBe('')
  })

  it('falls back for values outside the allowed set', () => {
    expect(readQueryEnum('killed', ['due', 'killed'], 'due')).toBe('killed')
    expect(readQueryEnum('bogus', ['due', 'killed'], 'due')).toBe('due')
    expect(readQueryEnum(undefined, ['due', 'killed'], 'due')).toBe('due')
  })

  it('clamps numbers and rejects junk', () => {
    expect(readQueryNumber('3', 1)).toBe(3)
    expect(readQueryNumber('0', 1)).toBe(1)
    expect(readQueryNumber('999', 1, { max: 10 })).toBe(10)
    expect(readQueryNumber('abc', 2)).toBe(2)
  })

  it('drops empty values and defaults so the address stays short', () => {
    const next = buildQuery({ tab: 'killed', bank: 'b1' }, { tab: 'due', bank: '', cause: '审题遗漏' }, { tab: 'due' })
    expect(next).toEqual({ cause: '审题遗漏' })
  })

  it('compares query objects regardless of key order', () => {
    expect(queriesEqual({ a: '1', b: '2' }, { b: '2', a: '1' })).toBe(true)
    expect(queriesEqual({ a: '1' }, { a: '1', b: '2' })).toBe(false)
    expect(queriesEqual(undefined, {})).toBe(true)
  })

  it('skips the navigation when nothing changed and tolerates a missing router', () => {
    const router = { replace: vi.fn() }
    expect(replaceQueryState(router, { tab: 'due' }, { tab: 'due' }, { tab: 'due' })).toBe(false)
    expect(router.replace).not.toHaveBeenCalled()

    expect(replaceQueryState(router, { tab: 'due' }, { tab: 'killed' }, { tab: 'due' })).toBe(true)
    expect(router.replace).toHaveBeenCalledWith({ query: { tab: 'killed' } })

    expect(replaceQueryState(null, {}, { q: 'x' })).toBe(false)
  })
})

// --- Views -------------------------------------------------------------

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn().mockResolvedValue([{ id: 'b1', name: 'Bank One' }, { id: 'b2', name: 'Bank Two' }]),
}))
vi.mock('../../src/api/mistakes', () => ({
  listDueMistakes: vi.fn().mockResolvedValue([]),
  listMistakes: vi.fn().mockResolvedValue([
    { question_id: 'q1', bank_id: 'b1', stem: 'One', type: 'SINGLE', mistake_count: 1 },
    { question_id: 'q2', bank_id: 'b2', stem: 'Two', type: 'SINGLE', mistake_count: 2 },
  ]),
  listWeakMistakes: vi.fn().mockResolvedValue([]),
  updateMistakeCause: vi.fn(),
}))
vi.mock('../../src/api/kills', () => ({
  listKills: vi.fn().mockResolvedValue([
    { question_id: 'q3', bank_id: 'b2', stem: 'Killed', type: 'SINGLE' },
  ]),
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
vi.mock('../../src/api/assets', () => ({
  listAssets: vi.fn().mockResolvedValue([
    { id: 'a1', asset_type: 'NOTE', content: '原始笔记内容', file_name: null, created_at: '2026-11-11T08:00:00Z' },
    { id: 'a2', asset_type: 'SUMMARY', content: 'PDF 提取出的文本', file_name: '复习资料.pdf', created_at: '2026-11-11T09:00:00Z' },
  ]),
  createAsset: vi.fn(),
  uploadAssetFile: vi.fn(),
  updateAsset: vi.fn(),
  deleteAsset: vi.fn(),
  fetchAssetBlob: vi.fn(),
}))

import ReviewView from '../../src/views/ReviewView.vue'
import NotesView from '../../src/views/NotesView.vue'
import { t } from '../../src/composables/useLocale.js'

const Empty = { template: '<div />' }

async function routerAt(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/review', name: 'review', component: Empty },
      { path: '/notes', name: 'notes', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
  router.push(path)
  await router.isReady()
  return router
}

const settle = () => new Promise(resolve => setTimeout(resolve, 20))

afterEach(() => {
  vi.clearAllMocks()
})

describe('ReviewView URL state', () => {
  it('opens the tab and bank filter named in the address', async () => {
    const router = await routerAt('/review?tab=killed&bank=b2')
    const wrapper = mount(ReviewView, { props: { token: 't' }, global: { plugins: [router] } })
    await settle()

    // The killed section is the one on screen, and its bank filter is applied.
    expect(wrapper.find('.select').element.value).toBe('b2')
    expect(wrapper.findAll('.list-row.due-row')).toHaveLength(0)

    wrapper.unmount()
  })

  it('keeps the other filters when the tab changes', async () => {
    const router = await routerAt('/review?tab=killed&bank=b2')
    const wrapper = mount(ReviewView, { props: { token: 't' }, global: { plugins: [router] } })
    await settle()

    await wrapper.findAll('.tabs .tab').at(3).trigger('click')
    await settle()

    expect(router.currentRoute.value.query.tab).toBe('diagnosis')
    expect(router.currentRoute.value.query.bank).toBe('b2')

    wrapper.unmount()
  })

  it('writes the bank filter into the address and drops it when cleared', async () => {
    const router = await routerAt('/review?tab=killed')
    const wrapper = mount(ReviewView, { props: { token: 't' }, global: { plugins: [router] } })
    await settle()

    await wrapper.find('.select').setValue('b1')
    await settle()
    expect(router.currentRoute.value.query.bank).toBe('b1')

    await wrapper.find('.select').setValue('')
    await settle()
    expect(router.currentRoute.value.query.bank).toBeUndefined()

    wrapper.unmount()
  })
})

describe('NotesView URL state', () => {
  it('opens the type and keyword named in the address', async () => {
    const router = await routerAt('/notes?type=NOTE&q=%E5%8E%9F%E5%A7%8B')
    const wrapper = mount(NotesView, { props: { token: 't1' }, global: { plugins: [router] } })
    await settle()

    expect(wrapper.find('input.input').element.value).toBe('原始')
    const activeTab = wrapper.find('.tab.is-active')
    expect(activeTab.exists()).toBe(true)
    expect(activeTab.text()).toContain(t('ep.library.type_note'))

    wrapper.unmount()
  })

  it('mirrors typing and tab changes back into the address', async () => {
    const router = await routerAt('/notes')
    const wrapper = mount(NotesView, { props: { token: 't1' }, global: { plugins: [router] } })
    await settle()

    await wrapper.find('input.input').setValue('资料')
    await settle()
    expect(router.currentRoute.value.query.q).toBe('资料')

    const tabs = wrapper.findAll('.tab')
    await tabs.at(3).trigger('click')
    await settle()
    expect(router.currentRoute.value.query.type).toBe('KNOWLEDGE')

    wrapper.unmount()
  })
})
