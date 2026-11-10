import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ExamView from '../../src/features/exam/ExamView.vue'
import { setLocale } from '../../src/composables/useLocale.js'
import { useAuthStore } from '../../src/stores/authStore.js'

const api = vi.hoisted(() => ({
  getSession: vi.fn(),
  getSessionQuestions: vi.fn(),
  syncDraft: vi.fn(),
  completeSession: vi.fn(),
  toggleFlag: vi.fn(),
  submitAttempt: vi.fn(),
}))

vi.mock('../../src/api/practice', () => api)
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), replace: vi.fn(), push: vi.fn() }),
}))

const questions = [
  {
    id: 'q1',
    stem: '会做的题',
    type: 'SINGLE',
    options: [{ key: 'A', content: '选项 A' }, { key: 'B', content: '选项 B' }],
  },
  {
    id: 'q2',
    stem: '空着的题',
    type: 'SINGLE',
    options: [{ key: 'A', content: '选项 A' }, { key: 'B', content: '选项 B' }],
  },
]

function mountExam() {
  return mount(ExamView, { props: { token: 'test-token', sessionId: 's1' } })
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

const reportFixture = {
  session_id: 's1',
  mode: 'EXAM',
  total_questions: 2,
  answered_count: 1,
  correct_count: 1,
  partial_count: 0,
  incorrect_count: 0,
  unanswered_count: 1,
  score: 1,
  accuracy: 100,
  type_stats: {},
  tag_stats: {},
  answers: {
    q1: { user_answer: 'A', correct_answer: 'A', correctness: 'CORRECT', explanation: '解析 1' },
    q2: { user_answer: null, correct_answer: 'B', correctness: 'UNANSWERED', explanation: '解析 2' },
  },
}

describe('ExamView runner', () => {
  beforeEach(() => {
    setLocale('zh-CN')
    localStorage.clear()
    useAuthStore().user.value = { id: 'u1', username: 'tester' }
    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: {},
      flags: [],
      time_limit: 0,
      is_completed: false,
    })
    api.getSessionQuestions.mockResolvedValue(questions)
    api.syncDraft.mockResolvedValue({ has_conflict: false, conflicts: [] })
    api.toggleFlag.mockResolvedValue({ flags: [] })
  })

  afterEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('reports a cross-device draft conflict and can keep this device answer', async () => {
    api.syncDraft.mockResolvedValueOnce({
      has_conflict: true,
      conflicts: [{ question_id: 'q2', existing_answer: 'B', incoming_answer: 'A' }],
      answers: { q2: { user_answer: 'B' } },
    }).mockResolvedValue({ has_conflict: false, conflicts: [], answers: { q2: { user_answer: 'A' } } })
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.findAll('.exam-option input')[0].setValue(true)
    await wait(500)
    await flushPromises()

    const notice = wrapper.find('[data-testid="exam-draft-conflicts"]')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('2')
    expect(notice.text()).toContain('B')
    const firstPayload = api.syncDraft.mock.calls[0][2]
    expect(firstPayload.answers).toEqual({ q1: 'A' })

    await notice.find('.exam-conflict-actions .btn').trigger('click')
    await wait(500)
    await flushPromises()
    expect(wrapper.find('[data-testid="exam-draft-conflicts"]').exists()).toBe(false)
    const restorePayload = api.syncDraft.mock.calls.at(-1)[2]
    expect(restorePayload.answers).toEqual({ q1: 'A', q2: 'A' })
    expect(restorePayload.base_answers).toEqual({ q2: 'B' })
    wrapper.unmount()
  })

  it('refuses to submit while a draft conflict is unresolved', async () => {
    api.syncDraft.mockResolvedValue({
      has_conflict: true,
      conflicts: [{ question_id: 'q2', existing_answer: 'B', incoming_answer: 'A' }],
      answers: { q2: { user_answer: 'B' } },
    })
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.findAll('.exam-option input')[0].setValue(true)
    await wait(500)
    await flushPromises()
    expect(wrapper.find('[data-testid="exam-draft-conflicts"]').exists()).toBe(true)

    await wrapper.find('.exam-submit').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="exam-submit-confirm"] .btn-primary').trigger('click')
    await flushPromises()

    expect(api.completeSession).not.toHaveBeenCalled()
    expect(wrapper.find('.exam-report').exists()).toBe(false)
    expect(wrapper.find('.exam-error').text()).toContain('草稿冲突')
    wrapper.unmount()
  })

  it('reports wrong and blank questions after submission and hides fully correct ones', async () => {
    api.completeSession.mockResolvedValue({
      session_id: 's1',
      mode: 'EXAM',
      total_questions: 2,
      answered_count: 1,
      correct_count: 1,
      partial_count: 0,
      incorrect_count: 0,
      unanswered_count: 1,
      score: 1,
      accuracy: 100,
      type_stats: {},
      tag_stats: {},
      answers: {
        q1: { user_answer: 'A', correct_answer: 'A', correctness: 'CORRECT', explanation: '解析 1' },
        q2: { user_answer: null, correct_answer: 'B', correctness: 'UNANSWERED', explanation: '解析 2' },
      },
    })
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.find('.exam-submit').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="exam-submit-confirm"] .btn-primary').trigger('click')
    await flushPromises()

    expect(wrapper.find('.exam-report').exists()).toBe(true)
    const review = wrapper.find('.exam-review')
    expect(review.exists()).toBe(true)
    expect(review.text()).toContain('空着的题')
    expect(review.text()).not.toContain('会做的题')
    expect(review.text()).toContain('未作答')
    expect(review.text()).toContain('解析 2')
    wrapper.unmount()
  })

  it('keeps offline answers on this device and restores them after a reload', async () => {
    api.syncDraft.mockRejectedValue({ status: 0, code: 'NETWORK_ERROR' })
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.findAll('.exam-option input')[0].setValue(true)
    await wait(500)
    await flushPromises()

    expect(wrapper.find('[data-testid="exam-offline-banner"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="exam-offline-banner"]').attributes('data-pending')).toBe('false')
    const stored = JSON.parse(localStorage.getItem('easyexam_exam_draft_u1_s1'))
    expect(stored.answers).toEqual({ q1: 'A' })
    expect(stored.currentIndex).toBe(0)
    expect(stored.pendingSubmit).toBe(false)
    wrapper.unmount()

    // A reload must repaint the paper from the device backup before the
    // network is available again, then push the restored answer to the server.
    const reloaded = mountExam()
    await flushPromises()
    expect(reloaded.findAll('.exam-option.selected').length).toBe(1)
    expect(reloaded.find('.sheet-count').text()).toContain('1 / 2')
    const recovery = api.syncDraft.mock.calls.at(-1)[2]
    expect(recovery.answers).toEqual({ q1: 'A' })
    // The baseline is the empty value this device originally observed, not the
    // freshly fetched server copy, so a cross-device write is still detectable.
    expect(recovery.base_answers).toEqual({ q1: '' })
    reloaded.unmount()
  })

  it('surfaces a cross-device conflict when replaying a restored offline answer', async () => {
    // This device edited q1 offline against an empty server baseline; another
    // device has since answered B.
    localStorage.setItem('easyexam_exam_draft_u1_s1', JSON.stringify({
      version: 1,
      answers: { q1: 'A' },
      base: { q1: '' },
      flags: [],
      currentIndex: 0,
      timeSpent: 5,
      pendingSubmit: false,
      updatedAt: Date.now(),
    }))
    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: { q1: { user_answer: 'B' } },
      flags: [],
      time_limit: 0,
      is_completed: false,
    })
    api.syncDraft.mockResolvedValue({
      has_conflict: true,
      conflicts: [{ question_id: 'q1', existing_answer: 'B', incoming_answer: 'A' }],
      answers: { q1: { user_answer: 'B' } },
    })
    const wrapper = mountExam()
    await flushPromises()

    const recovery = api.syncDraft.mock.calls.at(-1)[2]
    expect(recovery.answers).toEqual({ q1: 'A' })
    expect(recovery.base_answers).toEqual({ q1: '' })
    const notice = wrapper.find('[data-testid="exam-draft-conflicts"]')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('B')
    // The server keeps its value and the device backup follows it, so a second
    // reload cannot replay the rejected answer as if it were still pending.
    const stored = JSON.parse(localStorage.getItem('easyexam_exam_draft_u1_s1'))
    expect(stored.answers).toEqual({ q1: 'B' })
    expect(stored.base).toEqual({ q1: 'B' })
    wrapper.unmount()
  })

  it('adopts the server report when a pending paper was already finalised', async () => {
    // The device believes the time-up submission never landed, but the server
    // already completed it (lost response / another device).
    localStorage.setItem('easyexam_exam_draft_u1_s1', JSON.stringify({
      version: 1,
      answers: { q1: 'A' },
      base: { q1: '' },
      flags: [],
      currentIndex: 0,
      timeSpent: 2,
      pendingSubmit: true,
      updatedAt: Date.now(),
    }))
    api.syncDraft.mockRejectedValue({ status: 0, code: 'NETWORK_ERROR' })
    const wrapper = mountExam()
    await flushPromises()
    expect(api.completeSession).not.toHaveBeenCalled()

    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: { q1: { user_answer: 'A' } },
      flags: [],
      time_limit: 0,
      is_completed: true,
    })
    api.completeSession.mockResolvedValue(reportFixture)
    window.dispatchEvent(new Event('online'))
    await flushPromises()

    expect(api.completeSession).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.exam-report').exists()).toBe(true)
    expect(localStorage.getItem('easyexam_exam_draft_u1_s1')).toBeNull()
    expect(wrapper.find('[data-testid="exam-offline-banner"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('holds a time-up submission offline and completes safely once back online', async () => {
    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: {},
      flags: [],
      time_limit: 0.02,
      time_spent: 0,
      is_completed: false,
    })
    api.syncDraft.mockRejectedValue({ status: 0, code: 'NETWORK_ERROR' })
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.findAll('.exam-option input')[0].setValue(true)
    await wait(2300)
    await flushPromises()

    // The draft never reached the server: completing now would score the
    // server's older copy, so nothing may be submitted.
    expect(api.completeSession).not.toHaveBeenCalled()
    const banner = wrapper.find('[data-testid="exam-offline-banner"]')
    expect(banner.exists()).toBe(true)
    expect(banner.attributes('data-pending')).toBe('true')
    expect(wrapper.find('.exam-timer').text()).toContain('00:00')
    expect(wrapper.findAll('.exam-option input')[0].attributes('disabled')).toBeDefined()
    const stored = JSON.parse(localStorage.getItem('easyexam_exam_draft_u1_s1'))
    expect(stored.pendingSubmit).toBe(true)
    expect(stored.answers).toEqual({ q1: 'A' })

    api.syncDraft.mockResolvedValue({
      has_conflict: false,
      conflicts: [],
      answers: { q1: { user_answer: 'A' } },
    })
    api.completeSession.mockResolvedValue(reportFixture)
    window.dispatchEvent(new Event('online'))
    await flushPromises()

    expect(api.completeSession).toHaveBeenCalledTimes(1)
    const payload = api.syncDraft.mock.calls.at(-1)[2]
    expect(payload.answers).toEqual({ q1: 'A' })
    expect(wrapper.find('.exam-report').exists()).toBe(true)
    expect(localStorage.getItem('easyexam_exam_draft_u1_s1')).toBeNull()
    wrapper.unmount()
  })

  it('does not auto-submit over an unresolved conflict when time runs out', async () => {
    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: {},
      flags: [],
      time_limit: 0.02,
      time_spent: 0,
      is_completed: false,
    })
    api.syncDraft.mockResolvedValue({
      has_conflict: true,
      conflicts: [{ question_id: 'q2', existing_answer: 'B', incoming_answer: 'A' }],
      answers: { q2: { user_answer: 'B' } },
    })
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.findAll('.exam-option input')[0].setValue(true)
    await wait(2300)
    await flushPromises()

    expect(api.completeSession).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="exam-draft-conflicts"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="exam-offline-banner"]').attributes('data-pending')).toBe('true')

    // The user decides to keep this device's answer; only then is the paper
    // finalised, with the conflict resolved against the observed baseline.
    api.syncDraft.mockResolvedValue({
      has_conflict: false,
      conflicts: [],
      answers: { q1: { user_answer: 'A' }, q2: { user_answer: 'A' } },
    })
    api.completeSession.mockResolvedValue(reportFixture)
    await wrapper.find('[data-testid="exam-draft-conflicts"] .exam-conflict-actions .btn').trigger('click')
    await flushPromises()

    expect(api.completeSession).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="exam-draft-conflicts"]').exists()).toBe(false)
    expect(wrapper.find('.exam-report').exists()).toBe(true)
    wrapper.unmount()
  })

  it('never loads another account exam draft', async () => {
    localStorage.setItem('easyexam_exam_draft_u2_s1', JSON.stringify({
      version: 1,
      answers: { q1: 'B' },
      base: { q1: '' },
      flags: [],
      currentIndex: 0,
      timeSpent: 1,
      pendingSubmit: false,
      updatedAt: Date.now(),
    }))
    const wrapper = mountExam()
    await flushPromises()

    expect(wrapper.findAll('.exam-option.selected').length).toBe(0)
    expect(wrapper.find('.sheet-count').text()).toContain('0 / 2')
    expect(JSON.parse(localStorage.getItem('easyexam_exam_draft_u2_s1')).answers).toEqual({ q1: 'B' })
    expect(localStorage.getItem('easyexam_exam_draft_u1_s1') || '').not.toContain('"q1":"B"')
    wrapper.unmount()
  })

  it('stops retrying and never silently submits when the server rejects a late sync', async () => {
    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: {},
      flags: [],
      time_limit: 0.02,
      time_spent: 0,
      is_completed: false,
    })
    api.syncDraft.mockRejectedValue({
      status: 409,
      code: 'HTTP_409',
      detail: '模考时间已到，已超时，请交卷 [EXAM_TIME_EXPIRED]',
    })
    api.completeSession.mockResolvedValue(reportFixture)
    const wrapper = mountExam()
    await flushPromises()

    await wrapper.findAll('.exam-option input')[0].setValue(true)
    await wait(2300)
    await flushPromises()

    // The deadline rejection is terminal: no automatic completion and no retry loop.
    expect(api.completeSession).not.toHaveBeenCalled()
    const banner = wrapper.find('[data-testid="exam-expired-banner"]')
    expect(banner.exists()).toBe(true)
    const unsubmitted = wrapper.find('[data-testid="exam-expired-unsubmitted"]')
    expect(unsubmitted.exists()).toBe(true)
    expect(unsubmitted.text()).toContain('1')
    const stored = JSON.parse(localStorage.getItem('easyexam_exam_draft_u1_s1'))
    expect(stored.answers).toEqual({ q1: 'A' })
    expect(stored.pendingSubmit).toBe(false)

    const syncCalls = api.syncDraft.mock.calls.length
    window.dispatchEvent(new Event('online'))
    await wait(600)
    await flushPromises()
    expect(api.syncDraft.mock.calls.length).toBe(syncCalls)
    expect(api.completeSession).not.toHaveBeenCalled()

    // The server-answer submission is an explicit, confirmed user choice.
    await wrapper.find('[data-testid="exam-expired-submit-server"]').trigger('click')
    await flushPromises()
    expect(api.completeSession).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="exam-expired-confirm"]').exists()).toBe(true)
    await wrapper.find('[data-testid="exam-expired-confirm-submit"]').trigger('click')
    await flushPromises()

    expect(api.completeSession).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.exam-report').exists()).toBe(true)
    expect(localStorage.getItem('easyexam_exam_draft_u1_s1')).toBeNull()
    wrapper.unmount()
  })

  it('recognises a server-expired session on reload without replaying the draft', async () => {
    api.getSession.mockResolvedValue({
      id: 's1',
      mode: 'EXAM',
      bank_id: 'b1',
      current_index: 0,
      answers: { q1: { user_answer: 'B' } },
      flags: [],
      time_limit: 1,
      time_spent: 120,
      is_expired: true,
      is_completed: false,
    })
    localStorage.setItem('easyexam_exam_draft_u1_s1', JSON.stringify({
      version: 1,
      answers: { q1: 'A' },
      base: { q1: '' },
      flags: [],
      currentIndex: 0,
      timeSpent: 120,
      pendingSubmit: true,
      updatedAt: Date.now(),
    }))
    const wrapper = mountExam()
    await flushPromises()

    expect(wrapper.find('[data-testid="exam-expired-banner"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="exam-expired-unsubmitted"]').text()).toContain('1')
    expect(api.syncDraft).not.toHaveBeenCalled()
    expect(api.completeSession).not.toHaveBeenCalled()
    const stored = JSON.parse(localStorage.getItem('easyexam_exam_draft_u1_s1'))
    expect(stored.answers).toEqual({ q1: 'A' })
    expect(stored.pendingSubmit).toBe(false)
    wrapper.unmount()
  })
})
