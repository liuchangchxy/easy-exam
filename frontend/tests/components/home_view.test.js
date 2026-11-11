import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import HomeView from '../../src/views/HomeView.vue'
import { t } from '../../src/composables/useLocale.js'
import { startSession, listActiveSessions } from '../../src/api/practice'
import { getBlueprint } from '../../src/api/exams'

const routerPush = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: routerPush, replace: vi.fn(), back: vi.fn() }),
}))

const mockState = vi.hoisted(() => ({
  plan: null,
  banks: [{ id: 'b1', name: 'Bank One', question_count: 5 }],
}))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn(async () => mockState.banks),
  createBank: vi.fn(),
  createQuestion: vi.fn(),
  addBankMember: vi.fn(),
  listBankMembers: vi.fn().mockResolvedValue([]),
  removeBankMember: vi.fn(),
  copyQuestionToBank: vi.fn(),
}))

vi.mock('../../src/api/exams', () => ({
  startExam: vi.fn(),
  listProfiles: vi.fn().mockResolvedValue([]),
  getBlueprint: vi.fn().mockResolvedValue(null),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn().mockResolvedValue({ id: 's-plan' }),
  listActiveSessions: vi.fn().mockResolvedValue([]),
  getSession: vi.fn(),
  abandonSession: vi.fn(),
  abandonAllSessions: vi.fn(),
}))

vi.mock('../../src/api/mistakes', () => ({
  listDueMistakes: vi.fn().mockResolvedValue([]),
  listMistakes: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../src/api/learning', () => ({
  getLearningSummary: vi.fn().mockResolvedValue({}),
  getLearningTrends: vi.fn().mockResolvedValue(null),
  getStudyPlan: vi.fn(async () => mockState.plan),
}))

vi.mock('../../src/api/ai', () => ({
  getAiBatchStatus: vi.fn().mockResolvedValue({}),
  startAiBatchGenerate: vi.fn(),
  stopAiBatchGenerate: vi.fn(),
}))

vi.mock('../../src/api/sync', () => ({
  triggerSyncEvent: vi.fn(),
}))

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 50))

describe('HomeView today plan across banks', () => {
  beforeEach(() => {
    mockState.banks = [{ id: 'b1', name: 'Bank One', question_count: 5 }]
    mockState.plan = {
      days: [
        {
          day_number: 1,
          bank_tasks: [
            { bank_id: 'b1', question_ids: ['q1', 'q2'] },
            { bank_id: 'b2', question_ids: ['q3'] },
            { bank_id: 'b1', question_ids: ['q2'] },
          ],
        },
      ],
    }
    vi.clearAllMocks()
    startSession.mockResolvedValue({ id: 's-plan' })
    listActiveSessions.mockResolvedValue([])
  })

  it('starts today with a multi-bank plan instead of the first bank only', async () => {
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()

    await wrapper.find('.masthead-actions .btn-primary').trigger('click')
    await flushPromises()

    expect(startSession).toHaveBeenCalledTimes(1)
    const payload = startSession.mock.calls[0][1]
    expect(payload.bank_id).toBe('b1')
    expect(payload.bank_ids).toEqual(['b1', 'b2'])
    expect(payload.mode).toBe('PRACTICE')
    expect(payload.question_ids.sort()).toEqual(['q1', 'q2', 'q3'])
    expect(wrapper.emitted('start')).toBeFalsy()

    wrapper.unmount()
  })

  it('omits bank_ids when the plan belongs to a single bank', async () => {
    mockState.plan = {
      days: [{ day_number: 1, bank_tasks: [{ bank_id: 'b1', question_ids: ['q1'] }] }],
    }
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()

    await wrapper.find('.masthead-actions .btn-primary').trigger('click')
    await flushPromises()

    const payload = startSession.mock.calls[0][1]
    expect(payload.bank_id).toBe('b1')
    expect(payload.bank_ids).toBeUndefined()

    wrapper.unmount()
  })

  it('labels the primary action by the real session state', async () => {
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()
    expect(wrapper.find('.masthead-actions .btn-primary').text()).toContain(t('ep.today.start_practice'))

    listActiveSessions.mockResolvedValue([{
      id: 's1',
      bank_name: 'Bank One',
      mode: 'PRACTICE',
      answered_count: 1,
      total_questions: 5,
      created_at: '2026-11-11T08:00:00Z',
    }])
    const resumed = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()
    expect(resumed.find('.masthead-actions .btn-primary').text()).toContain(t('ep.today.continue'))

    wrapper.unmount()
    resumed.unmount()
  })

  it('offers separately focusable controls for opening a bank and starting practice', async () => {
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()

    const row = wrapper.find('.today-bank-row')
    expect(row.element.tagName).toBe('DIV')
    expect(row.element.querySelector('button button')).toBeNull()
    expect(row.findAll('button').length).toBe(2)
    expect(row.find('.today-bank-open').element.tagName).toBe('BUTTON')
    expect(row.find('.bank-row-actions .btn').element.tagName).toBe('BUTTON')

    wrapper.unmount()
  })

  it('does not advertise shortcuts that are not implemented', async () => {
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()

    expect(wrapper.find('.rail-keys').exists()).toBe(false)
    expect(wrapper.find('.kbd').exists()).toBe(false)

    wrapper.unmount()
  })

  it('routes blueprint and AI entries to their single editors instead of modal events', async () => {
    const openDialog = vi.fn()
    window.addEventListener('easyexam:open-dialog', openDialog)
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()

    window.dispatchEvent(new CustomEvent('easyexam:action', { detail: 'blueprint' }))
    expect(routerPush).toHaveBeenCalledWith('/exams')
    window.dispatchEvent(new CustomEvent('easyexam:action', { detail: 'ai' }))
    expect(routerPush).toHaveBeenCalledWith({ path: '/settings', query: { section: 'ai' } })
    expect(openDialog).not.toHaveBeenCalled()

    wrapper.unmount()
    window.removeEventListener('easyexam:open-dialog', openDialog)
  })

  it('opens the create-bank dialog with focus inside and closes it on Escape', async () => {
    const wrapper = mount(HomeView, { props: { token: 'test-token' }, attachTo: document.body })
    await flushPromises()

    wrapper.vm.openCreateBankDialog()
    await flushPromises()

    const panel = document.querySelector('[data-testid="home-create-bank-dialog"]')
    expect(panel).not.toBeNull()
    expect(panel.contains(document.activeElement)).toBe(true)
    expect(document.activeElement).toBe(document.querySelector('#home-create-bank-name'))

    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flushPromises()

    expect(document.querySelector('[data-testid="home-create-bank-dialog"]')).toBeNull()

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('reads the exam profile blueprint summary from the wrapped blueprint payload', async () => {
    getBlueprint.mockResolvedValue({
      id: 'bp1',
      profile_id: 'p1',
      version_number: 3,
      blueprint: {
        negative_mark: 0.5,
        sections: [
          { type: 'SINGLE', count: 10 },
          { type: 'MULTI', count: 5 },
        ],
      },
    })
    const wrapper = mount(HomeView, { props: { token: 'test-token' } })
    await flushPromises()

    wrapper.vm.selectedProfileId = 'p1'
    await wrapper.vm.onExamProfileChange()

    expect(getBlueprint).toHaveBeenCalledWith('test-token', 'p1')
    expect(wrapper.vm.selectedProfileBlueprintSummary).toEqual({
      sectionsCount: 2,
      totalQuestions: 15,
      negativeMark: 0.5,
    })

    wrapper.unmount()
  })
})
