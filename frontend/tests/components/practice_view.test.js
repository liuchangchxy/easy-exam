import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PracticeViewV1 from '../../src/views/PracticeViewV1.vue'
import { getSession, getSessionQuestions, submitAttempt, syncDraft } from '../../src/api/practice'
import { updateQuestion } from '../../src/api/questions'
import { killQuestion } from '../../src/api/kills'

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('../../src/stores/authStore', () => ({
  useAuthStore: () => ({
    token: { value: 'test-token' },
    user: { value: { id: 'u1', username: 'testuser' } },
  }),
}))

const mockState = vi.hoisted(() => ({ bankRole: 'EDITOR' }))

vi.mock('../../src/api/banks', () => ({
  listBankMembers: vi.fn(async () => [{ user_id: 'u1', role: mockState.bankRole }]),
}))

vi.mock('../../src/api/practice', () => ({
  getSession: vi.fn().mockResolvedValue({
    id: 's1',
    mode: 'PRACTICE',
    bank_id: 'b1',
    current_index: 0,
    answers: {},
  }),
  getSessionQuestions: vi.fn().mockResolvedValue([
    {
      id: 'q1',
      bank_id: 'b1',
      stem: 'What is EasyExam?',
      type: 'SINGLE',
      options: [
        { key: 'A', content: 'An exam app' },
        { key: 'B', content: 'Other' },
      ],
      answer: 'A',
      explanation: 'Explanation for Q1',
    },
  ]),
  submitAttempt: vi.fn(),
  completeSession: vi.fn(),
  syncDraft: vi.fn().mockResolvedValue({ answers: {}, conflicts: [] }),
}))

vi.mock('../../src/api/questions', () => ({
  getQuestion: vi.fn(),
  listQuestionVersions: vi.fn().mockResolvedValue([]),
  updateQuestion: vi.fn(),
  getQuestionConflict: vi.fn().mockResolvedValue({ has_conflict: false }),
  resolveQuestionConflict: vi.fn(),
  regradeQuestion: vi.fn(),
}))

vi.mock('../../src/api/ai', () => ({
  generateAnswer: vi.fn(),
  listAnswerVersions: vi.fn().mockResolvedValue([]),
  adoptAnswer: vi.fn(),
  saveCandidate: vi.fn(),
  verifyWeb: vi.fn(),
  listQuestionConversations: vi.fn().mockResolvedValue([]),
  listConversationMessages: vi.fn().mockResolvedValue([]),
  sendChatMessage: vi.fn(),
  generateVariant: vi.fn(),
}))

vi.mock('../../src/api/learning', () => ({
  markWeak: vi.fn(),
  unmarkWeak: vi.fn(),
}))

vi.mock('../../src/api/kills', () => ({
  killQuestion: vi.fn(),
}))

vi.mock('../../src/api/sync', () => ({
  triggerSyncEvent: vi.fn(),
}))

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 50))
const waitForDraftFlush = () => new Promise(resolve => setTimeout(resolve, 750))

async function mountView() {
  const wrapper = mount(PracticeViewV1, {
    props: {
      token: 'test-token',
      sessionId: 's1',
    },
  })
  await flushPromises()
  return wrapper
}

describe('PracticeViewV1 component integration', () => {
  beforeEach(() => {
    mockState.bankRole = 'EDITOR'
    localStorage.clear()
    vi.clearAllMocks()
    submitAttempt.mockReset()
    // A fresh array per test: the view replaces entries in place when an offline
    // question edit syncs, and a shared fixture would leak that mutation.
    getSessionQuestions.mockResolvedValue([{
      id: 'q1',
      bank_id: 'b1',
      stem: 'What is EasyExam?',
      type: 'SINGLE',
      options: [
        { key: 'A', content: 'An exam app' },
        { key: 'B', content: 'Other' },
      ],
      answer: 'A',
      explanation: 'Explanation for Q1',
    }])
    syncDraft.mockResolvedValue({ answers: {}, conflicts: [] })
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('opens the exit confirmation focused on continue and restores the exit trigger on Escape', async () => {
    const wrapper = mount(PracticeViewV1, {
      props: { token: 'test-token', sessionId: 's1' },
      attachTo: document.body,
    })
    await flushPromises()

    const trigger = wrapper.find('.focus-exit').element
    trigger.focus()
    await wrapper.find('.focus-exit').trigger('click')
    await flushPromises()

    const panel = document.querySelector('[data-testid="exit-confirm-modal"]')
    expect(panel).not.toBeNull()
    expect(document.activeElement).toBe(panel.querySelector('.exit-continue'))

    // Escape from outside the dialog keeps the session and returns focus.
    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flushPromises()

    expect(document.querySelector('[data-testid="exit-confirm-modal"]')).toBeNull()
    expect(document.activeElement).toBe(trigger)
    expect(wrapper.emitted('back')).toBeFalsy()

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('toggles more menu on "⋯" click and renders key action items', async () => {
    const wrapper = await mountView()

    // 1. Initial state: dropdown menu is closed
    expect(wrapper.find('.focus-menu').exists()).toBe(false)

    // 2. Click "⋯" button
    const moreBtn = wrapper.find('.btn-more-menu')
    expect(moreBtn.exists()).toBe(true)
    await moreBtn.trigger('click')

    // 3. Dropdown menu appears
    const dropdown = wrapper.find('.focus-menu')
    expect(dropdown.exists()).toBe(true)

    // 4. Editor sees question edit plus kill actions
    const items = dropdown.findAll('.focus-menu-item')
    expect(items.length).toBe(2)
    expect(items[0].classes()).toContain('focus-menu-item')
    expect(dropdown.find('.is-danger').exists()).toBe(true)

    // Header complete button is accessible
    const completeBtn = wrapper.find('.focus-finish')
    expect(completeBtn.exists()).toBe(true)

    wrapper.unmount()
  })

  it('hides the edit action and regrade option for a bank MEMBER', async () => {
    mockState.bankRole = 'MEMBER'
    const wrapper = await mountView()

    await wrapper.find('.btn-more-menu').trigger('click')
    const items = wrapper.find('.focus-menu').findAll('.focus-menu-item')
    expect(items.length).toBe(1)
    expect(wrapper.find('.focus-menu').find('.is-danger').exists()).toBe(true)
    expect(wrapper.find('.focus-menu').find('.focus-menu-item:not(.is-danger)').exists()).toBe(false)

    wrapper.unmount()
  })

  it('flushes the selected draft answer to syncDraft with a base snapshot', async () => {
    syncDraft.mockResolvedValue({ answers: { q1: 'A' }, conflicts: [] })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await waitForDraftFlush()

    expect(syncDraft).toHaveBeenCalled()
    const payload = syncDraft.mock.calls.at(-1)[2]
    expect(payload.answers).toEqual({ q1: 'A' })
    expect(payload.base_answers).toEqual({ q1: '' })
    expect(typeof payload.time_spent).toBe('number')

    wrapper.unmount()
  })

  it('surfaces cross-device draft conflicts instead of silently keeping the local answer', async () => {
    syncDraft.mockResolvedValue({
      answers: { q1: 'B' },
      conflicts: [{ question_id: 'q1', existing_answer: 'B', incoming_answer: 'A' }],
    })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await waitForDraftFlush()

    const banner = wrapper.find('[data-testid="draft-conflict-banner"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('B')
    expect(banner.text()).toContain('A')
    expect(banner.findAll('button').length).toBe(2)

    wrapper.unmount()
  })

  it('keeps a conflicted answer out of later auto flushes, including after a reload', async () => {
    syncDraft.mockResolvedValueOnce({
      answers: { q1: 'B' },
      conflicts: [{ question_id: 'q1', existing_answer: 'B', incoming_answer: 'A' }],
    })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await waitForDraftFlush()
    expect(wrapper.find('[data-testid="draft-conflict-banner"]').exists()).toBe(true)

    // Re-selecting the option schedules another automatic flush; the unresolved
    // question must stay out of the payload so the server answer is not clobbered.
    await wrapper.findAll('.opt')[0].trigger('click')
    await waitForDraftFlush()
    for (const call of syncDraft.mock.calls.slice(1)) {
      expect(call[2].answers?.q1).toBeUndefined()
    }

    wrapper.unmount()
    const callsBeforeReload = syncDraft.mock.calls.length
    const remounted = await mountView()
    await waitForDraftFlush()
    expect(remounted.find('[data-testid="draft-conflict-banner"]').exists()).toBe(true)
    for (const call of syncDraft.mock.calls.slice(callsBeforeReload)) {
      expect(call[2].answers?.q1).toBeUndefined()
    }
    remounted.unmount()
  })

  it('sends an explicit overwrite only after the user chooses to use the local answer', async () => {
    syncDraft.mockResolvedValueOnce({
      answers: { q1: 'B' },
      conflicts: [{ question_id: 'q1', existing_answer: 'B', incoming_answer: 'A' }],
    })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await waitForDraftFlush()

    const banner = wrapper.find('[data-testid="draft-conflict-banner"]')
    await banner.findAll('button')[1].trigger('click')
    await waitForDraftFlush()

    const payload = syncDraft.mock.calls.at(-1)[2]
    expect(payload.answers).toEqual({ q1: 'A' })
    expect(payload.base_answers).toEqual({ q1: 'B' })
    expect(wrapper.find('[data-testid="draft-conflict-banner"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('adopts the server answer after the user chooses to keep it', async () => {
    syncDraft.mockResolvedValueOnce({
      answers: { q1: 'B' },
      conflicts: [{ question_id: 'q1', existing_answer: 'B', incoming_answer: 'A' }],
    })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await waitForDraftFlush()

    const banner = wrapper.find('[data-testid="draft-conflict-banner"]')
    await banner.findAll('button')[0].trigger('click')
    await waitForDraftFlush()

    const payload = syncDraft.mock.calls.at(-1)[2]
    expect(payload.answers).toEqual({ q1: 'B' })
    expect(payload.base_answers).toEqual({ q1: 'B' })
    expect(wrapper.find('[data-testid="draft-conflict-banner"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('clears the queued offline attempt once a manual online submit succeeds', async () => {
    submitAttempt.mockRejectedValue({ status: 0 })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    const submitButton = () => wrapper.find('[data-testid="practice-action-bar"] .btn-primary')
    await submitButton().trigger('click')
    await new Promise(resolve => setTimeout(resolve, 1200))

    const queued = () => JSON.parse(localStorage.getItem('easyexam_offline_attempts_u1') || 'null')
    expect(queued()).toHaveLength(1)
    expect(queued()[0].questionId).toBe('q1')
    const offlineCalls = submitAttempt.mock.calls.length

    submitAttempt.mockResolvedValue({ id: 'a1', correctness: 'CORRECT', score_ratio: 1, is_objective: true })
    await submitButton().trigger('click')
    await flushPromises()

    expect(queued()).toBeNull()
    expect(submitAttempt.mock.calls.length).toBe(offlineCalls + 1)

    // Reconnecting later must not replay the already-accepted attempt.
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    expect(submitAttempt.mock.calls.length).toBe(offlineCalls + 1)

    wrapper.unmount()
  })

  it('removes a killed question from the local draft and the pending queue', async () => {
    getSessionQuestions.mockResolvedValueOnce([
      {
        id: 'q1', bank_id: 'b1', stem: 'Question one', type: 'SINGLE',
        options: [{ key: 'A', content: 'A1' }, { key: 'B', content: 'B1' }], answer: 'A',
      },
      {
        id: 'q2', bank_id: 'b1', stem: 'Question two', type: 'SINGLE',
        options: [{ key: 'A', content: 'A2' }, { key: 'B', content: 'B2' }], answer: 'B',
      },
    ])
    submitAttempt.mockRejectedValue({ status: 0 })
    vi.stubGlobal('confirm', vi.fn(() => true))
    vi.stubGlobal('alert', vi.fn())
    killQuestion.mockResolvedValue({ status: 'killed' })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await wrapper.find('[data-testid="practice-action-bar"] .btn-primary').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 1200))

    expect(JSON.parse(localStorage.getItem('easyexam_offline_attempts_u1') || '[]')).toHaveLength(1)
    const draftBefore = JSON.parse(localStorage.getItem('easyexam_practice_draft_u1_s1') || 'null')
    expect(draftBefore.answers.q1).toBeTruthy()

    await wrapper.find('.btn-more-menu').trigger('click')
    await wrapper.find('.focus-menu .is-danger').trigger('click')
    await flushPromises()

    const remainingAttempts = JSON.parse(localStorage.getItem('easyexam_offline_attempts_u1') || '[]')
    expect(remainingAttempts.some(item => item.questionId === 'q1')).toBe(false)
    const draftAfter = JSON.parse(localStorage.getItem('easyexam_practice_draft_u1_s1') || 'null')
    expect(draftAfter?.answers?.q1).toBeUndefined()

    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('migrates only the current account legacy offline queue and never deletes another account entries', async () => {
    const mine = {
      userId: 'u1',
      questionId: 'q1',
      payload: { stem: 'Mine', type: 'SINGLE', answer: 'A', base_version_number: 1 },
    }
    const other = {
      userId: 'u2',
      questionId: 'q2',
      payload: { stem: 'Someone else', type: 'SINGLE', answer: 'B', base_version_number: 1 },
    }
    localStorage.setItem('easyexam_offline_question_edits', JSON.stringify([mine, other]))
    updateQuestion.mockResolvedValue({ id: 'q1', version_number: 2 })

    const wrapper = await mountView()
    await new Promise(resolve => setTimeout(resolve, 100))

    expect(updateQuestion).toHaveBeenCalledTimes(1)
    expect(updateQuestion.mock.calls[0][1]).toBe('q1')
    // The synced item is gone from the scoped queue...
    expect(localStorage.getItem('easyexam_offline_question_edits_u1')).toBeNull()
    // ...while the other account's item is still there for its own session.
    expect(JSON.parse(localStorage.getItem('easyexam_offline_question_edits'))).toEqual([other])

    wrapper.unmount()
  })

  it('reuses one stable client_attempt_id across network retries and the offline queue', async () => {
    submitAttempt.mockRejectedValue({ status: 0, code: 'NETWORK_ERROR' })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await wrapper.find('[data-testid="practice-action-bar"] .btn-primary').trigger('click')
    await new Promise(resolve => setTimeout(resolve, 1300))

    const ids = submitAttempt.mock.calls.map(call => call[2].client_attempt_id)
    expect(ids.length).toBeGreaterThan(1)
    expect(new Set(ids).size).toBe(1)
    expect(ids[0]).toBeTruthy()

    const queued = JSON.parse(localStorage.getItem('easyexam_offline_attempts_u1'))
    expect(queued).toHaveLength(1)
    expect(queued[0].clientAttemptId).toBe(ids[0])
    expect(queued[0].user_answer).toBe('A')

    // The same key is persisted with the draft, so a reload cannot mint a new one.
    expect(JSON.parse(localStorage.getItem('easyexam_practice_draft_u1_s1')).clientAttemptIds.q1).toBe(ids[0])

    wrapper.unmount()
  })

  it('queues a rating on the answer attempt key without overwriting the answer', async () => {
    getSession.mockResolvedValueOnce({
      id: 's1',
      mode: 'FSRS',
      bank_id: 'b1',
      current_index: 0,
      answers: {},
    })
    submitAttempt
      .mockResolvedValueOnce({ id: 'a1', correctness: 'CORRECT', score_ratio: 1, is_objective: true, user_answer: 'A' })
      .mockRejectedValue({ status: 0, code: 'NETWORK_ERROR' })
    const wrapper = await mountView()

    await wrapper.findAll('.opt')[0].trigger('click')
    await wrapper.find('[data-testid="practice-action-bar"] .btn-primary').trigger('click')
    await flushPromises()

    const answerCall = submitAttempt.mock.calls[0][2]
    expect(answerCall.client_attempt_id).toBeTruthy()
    expect(answerCall.user_answer).toBe('A')

    // Good (3) is enabled because the answer was correct.
    await wrapper.findAll('.fsrs-buttons .btn')[2].trigger('click')
    await new Promise(resolve => setTimeout(resolve, 1300))

    const ratingCalls = submitAttempt.mock.calls.slice(1)
    expect(ratingCalls.length).toBeGreaterThan(0)
    for (const call of ratingCalls) {
      expect(call[2].client_attempt_id).toBe(answerCall.client_attempt_id)
      expect(call[2].user_answer).toBe('A')
      expect(call[2].fsrs_rating).toBe(3)
    }

    // One merged queue entry: the answer is not replaced by the rating, and the
    // rating is not dropped when the answer is replayed.
    const queued = JSON.parse(localStorage.getItem('easyexam_offline_attempts_u1'))
    expect(queued).toHaveLength(1)
    expect(queued[0]).toMatchObject({
      questionId: 'q1',
      user_answer: 'A',
      fsrs_rating: 3,
      clientAttemptId: answerCall.client_attempt_id,
    })

    // Draining replays the combined payload with the same id.
    submitAttempt.mockResolvedValue({ id: 'a1', correctness: 'CORRECT', score_ratio: 1, is_objective: true, user_answer: 'A', fsrs_rating: 3 })
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    const drained = submitAttempt.mock.calls.at(-1)[2]
    expect(drained).toMatchObject({
      question_id: 'q1',
      user_answer: 'A',
      fsrs_rating: 3,
      client_attempt_id: answerCall.client_attempt_id,
    })
    expect(JSON.parse(localStorage.getItem('easyexam_offline_attempts_u1'))).toBeNull()

    wrapper.unmount()
  })

  it('reopens a completed practice session as its stored report, not a blank runner', async () => {
    getSession.mockResolvedValueOnce({
      id: 's1',
      mode: 'PRACTICE',
      bank_id: 'b1',
      status: 'completed',
      is_completed: true,
      report: {
        score: 8,
        accuracy: 80,
        answered_count: 4,
        total_questions: 5,
        time_spent: 120,
        correct_count: 4,
        partial_count: 0,
        incorrect_count: 0,
        unanswered_count: 1,
        type_stats: {},
        tag_stats: {},
        answers: {},
      },
    })

    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="practice-report-modal"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="practice-action-bar"]').exists()).toBe(false)
    expect(wrapper.find('.opt').exists()).toBe(false)
    expect(wrapper.find('.focus-empty').exists()).toBe(false)
    expect(getSessionQuestions).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('offers a retry when a completed practice session has no report', async () => {
    getSession.mockResolvedValueOnce({
      id: 's1',
      mode: 'PRACTICE',
      bank_id: 'b1',
      status: 'completed',
    })

    const wrapper = await mountView()

    const notice = wrapper.find('[data-testid="practice-report-load-failed"]')
    expect(notice.exists()).toBe(true)
    expect(wrapper.find('[data-testid="practice-report-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="practice-report-modal"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="practice-action-bar"]').exists()).toBe(false)

    wrapper.unmount()
  })
})
