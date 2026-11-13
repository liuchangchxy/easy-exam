import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import QuestionPageView from '../../src/views/QuestionPageView.vue'
import { t } from '../../src/composables/useLocale.js'
import { questionCode } from '../../src/domain/bankManage.js'
import {
  getBank,
  listBanks,
  listChapters,
  copyQuestionToBank,
  batchBankQuestions,
} from '../../src/api/banks'
import { getQuestion, listQuestionVersions } from '../../src/api/questions'
import { startSession } from '../../src/api/practice'

const push = vi.fn()
const replace = vi.fn()
const routeState = reactive({ params: {}, query: {} })

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push, replace }),
}))

vi.mock('../../src/api/banks', () => ({
  getBank: vi.fn(),
  listBanks: vi.fn(),
  listChapters: vi.fn(),
  copyQuestionToBank: vi.fn(),
  batchBankQuestions: vi.fn(),
}))

vi.mock('../../src/api/questions', () => ({
  getQuestion: vi.fn(),
  listQuestionVersions: vi.fn(),
  updateQuestion: vi.fn(),
  getQuestionConflict: vi.fn(),
  deleteQuestionVersion: vi.fn(),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn(),
  // useStartStudy asks for unfinished sessions before it starts another one.
  listActiveSessions: vi.fn().mockResolvedValue([]),
  abandonSession: vi.fn(),
  abandonAllSessions: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

function makeQuestion(overrides = {}) {
  return {
    id: 'q1',
    type: 'SINGLE',
    stem: 'Which letter is the answer?',
    options: [
      { key: 'A', text: 'Alpha' },
      { key: 'B', text: 'Beta' },
    ],
    answer: 'B',
    explanation: 'Beta is the correct choice.',
    difficulty: 2,
    version_number: 1,
    chapter_id: 'c1',
    tags: [],
    archived: false,
    ...overrides,
  }
}

let wrapper = null

async function mountView(props = {}) {
  wrapper = mount(QuestionPageView, {
    props: { token: 't1', bankId: 'b1', questionId: 'q1', ...props },
    attachTo: document.body,
  })
  await flush()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  routeState.params = {}
  routeState.query = {}
  getBank.mockResolvedValue({ id: 'b1', name: 'Bank One', role: 'ADMIN' })
  getQuestion.mockResolvedValue(makeQuestion())
  listChapters.mockResolvedValue([{ id: 'c1', name: 'Chapter One' }])
  listBanks.mockResolvedValue([{ id: 'b2', name: 'Bank Two', role: 'ADMIN' }])
  listQuestionVersions.mockResolvedValue([])
  startSession.mockResolvedValue({ id: 's1' })
  copyQuestionToBank.mockResolvedValue({})
  batchBankQuestions.mockResolvedValue({ updated: 1 })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  document.body.style.overflow = ''
})

describe('QuestionPageView question rendering', () => {
  it('renders the stem, marks the correct option, and shows the answer with its explanation', async () => {
    await mountView()

    expect(wrapper.find('.page-eyebrow').text()).toBe('Bank One')
    expect(wrapper.find('.page-title').text()).toBe(
      t('ep.questions.crumb_one', { code: questionCode('q1') })
    )
    expect(wrapper.find('.qp-stem').text()).toBe('Which letter is the answer?')

    const options = wrapper.findAll('.opt')
    expect(options).toHaveLength(2)
    expect(options[0].classes()).not.toContain('is-correct')
    expect(options[1].classes()).toContain('is-correct')
    expect(options[1].find('.opt-mark').exists()).toBe(true)

    expect(wrapper.find('.answer-line .ans').text()).toBe('B')
    expect(wrapper.find('.explain-body').text()).toBe('Beta is the correct choice.')
  })
})

describe('QuestionPageView version history', () => {
  it('lists versions newest-first, previews an older one, and returns to the current version', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ id: 'q3', version_number: 3, stem: 'Current stem' }))
    listQuestionVersions.mockResolvedValue([
      { id: 'v1', version_number: 1, stem: 'Oldest stem' },
      { id: 'v3', version_number: 3, stem: 'Current stem' },
      { id: 'v2', version_number: 2, stem: 'Middle stem' },
    ])

    await mountView({ questionId: 'q3' })

    const items = wrapper.findAll('.version-item')
    expect(items.map(item => item.find('.mono').text())).toEqual(['v3', 'v2', 'v1'])
    expect(wrapper.find('.practice-one-btn').exists()).toBe(true)

    await items[2].trigger('click')

    expect(wrapper.find('.qp-stem').text()).toBe('Oldest stem')
    expect(wrapper.find('.practice-one-btn').exists()).toBe(false)
    expect(wrapper.find('.qp-preview-note').exists()).toBe(true)

    await wrapper.find('.qp-preview-note button').trigger('click')

    expect(wrapper.find('.qp-stem').text()).toBe('Current stem')
    expect(wrapper.find('.practice-one-btn').exists()).toBe(true)
    expect(wrapper.find('.qp-preview-note').exists()).toBe(false)
  })
})

describe('QuestionPageView access states', () => {
  it('renders the access-denied state for a forbidden and a missing question', async () => {
    getQuestion.mockRejectedValueOnce({ status: 403 })
    let view = await mountView()

    let denied = view.find('[data-testid="access-denied"]')
    expect(denied.exists()).toBe(true)
    expect(denied.attributes('data-kind')).toBe('forbidden')
    expect(denied.find('.page-title').text()).toBe(t('ep.access.forbidden_title'))
    view.unmount()

    getQuestion.mockRejectedValueOnce({ status: 404 })
    view = await mountView()

    denied = view.find('[data-testid="access-denied"]')
    expect(denied.exists()).toBe(true)
    expect(denied.attributes('data-kind')).toBe('missing')
    expect(denied.find('.page-title').text()).toBe(t('ep.access.missing_title'))
  })
})

describe('QuestionPageView role gating', () => {
  it('hides edit and archive from members while showing them to admins', async () => {
    getBank.mockResolvedValueOnce({ id: 'b1', name: 'Bank One', role: 'MEMBER' })
    let view = await mountView()

    expect(view.find('[data-testid="question-edit"]').exists()).toBe(false)
    expect(view.find('[data-testid="question-archive"]').exists()).toBe(false)
    view.unmount()

    getBank.mockResolvedValueOnce({ id: 'b1', name: 'Bank One', role: 'ADMIN' })
    view = await mountView()

    expect(view.find('[data-testid="question-edit"]').exists()).toBe(true)
    expect(view.find('[data-testid="question-archive"]').exists()).toBe(true)
  })
})

describe('QuestionPageView archive toggle', () => {
  it('archives then restores the question through the batch endpoint', async () => {
    await mountView()

    let button = wrapper.find('[data-testid="question-archive"]')
    expect(button.text()).toContain(t('ep.manage.archive'))

    await button.trigger('click')
    await flush()

    expect(batchBankQuestions).toHaveBeenCalledWith('t1', 'b1', {
      operation: 'archive',
      question_ids: ['q1'],
    })
    expect(wrapper.find('.page-sub .tag.bad').text()).toBe(t('ep.manage.archived_badge'))
    button = wrapper.find('[data-testid="question-archive"]')
    expect(button.text()).toContain(t('ep.manage.restore'))

    await button.trigger('click')
    await flush()

    expect(batchBankQuestions).toHaveBeenLastCalledWith('t1', 'b1', {
      operation: 'restore',
      question_ids: ['q1'],
    })
    expect(wrapper.find('.page-sub .tag.bad').exists()).toBe(false)
    button = wrapper.find('[data-testid="question-archive"]')
    expect(button.text()).toContain(t('ep.manage.archive'))
  })
})

describe('QuestionPageView copy to another bank', () => {
  it('offers only other banks the user may edit and copies the question there', async () => {
    listBanks.mockResolvedValue([
      { id: 'b1', name: 'Bank One', role: 'ADMIN' },
      { id: 'b2', name: 'Bank Two', role: 'ADMIN' },
      { id: 'b3', name: 'Bank Three', role: 'EDITOR' },
      { id: 'b4', name: 'Bank Four', role: 'MEMBER' },
    ])

    await mountView()

    const values = wrapper.findAll('.copy-select option').map(option => option.element.value)
    expect(values).toEqual(['', 'b2', 'b3'])

    await wrapper.find('.copy-select').setValue('b2')
    await wrapper.find('.copy-form .btn').trigger('click')
    await flush()

    expect(copyQuestionToBank).toHaveBeenCalledWith('t1', 'b1', 'q1', 'b2')
  })
})

describe('QuestionPageView practice', () => {
  it('starts a single-question practice session and routes to it', async () => {
    startSession.mockResolvedValue({ id: 'session-9' })

    await mountView()

    await wrapper.find('.practice-one-btn').trigger('click')
    await flush()

    expect(startSession).toHaveBeenCalledWith('t1', {
      bank_id: 'b1',
      mode: 'PRACTICE',
      question_ids: ['q1'],
      total_questions: 1,
    })
    expect(push).toHaveBeenCalledWith('/practice/session-9')
  })
})

describe('QuestionPageView archived question', () => {
  it('shows the archived badge and disables practice', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ archived: true }))

    await mountView()

    expect(wrapper.find('.page-sub .tag.bad').text()).toBe(t('ep.manage.archived_badge'))
    const practice = wrapper.find('.practice-one-btn')
    expect(practice.exists()).toBe(true)
    expect(practice.element.disabled).toBe(true)

    await practice.trigger('click')
    await flush()
    expect(startSession).not.toHaveBeenCalled()
  })
})

describe('QuestionPageView load failures', () => {
  it('shows a retryable failure instead of the not-found copy when the question cannot load', async () => {
    getQuestion.mockRejectedValueOnce({ status: 500, detail: 'server exploded' })

    await mountView()

    const failure = wrapper.find('.question-missing')
    expect(failure.exists()).toBe(true)
    expect(wrapper.find('[data-testid="access-denied"]').exists()).toBe(false)
    expect(failure.find('.empty-title').text()).toBe(t('ep.common.load_failed'))
    expect(failure.text()).toContain('server exploded')
    expect(failure.text()).not.toContain(t('ep.questions.not_found_title'))

    await failure.find('.empty-actions .btn').trigger('click')
    await flush()

    expect(getQuestion).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.qp-stem').text()).toBe('Which letter is the answer?')
  })

  it('surfaces a bank load failure without denying access to the question', async () => {
    getBank.mockRejectedValueOnce({ status: 500, detail: 'bank down' })

    await mountView()

    expect(wrapper.find('[data-testid="access-denied"]').exists()).toBe(false)
    const notice = wrapper.find('.page-head .notice.bad')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain(t('ep.common.load_failed'))

    await notice.find('.btn').trigger('click')
    await flush()

    expect(getBank).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.page-eyebrow').text()).toBe('Bank One')
  })
})

describe('QuestionPageView access-denied exit', () => {
  it('sends the access-denied action to the bank list instead of the forbidden bank', async () => {
    getBank.mockRejectedValueOnce({ status: 403 })

    const view = await mountView()

    expect(view.find('[data-testid="access-denied"]').exists()).toBe(true)
    await view.find('[data-testid="access-denied-back"]').trigger('click')

    expect(push).toHaveBeenCalledWith({ name: 'banks' })
  })
})

describe('QuestionPageView bank mismatch', () => {
  it('redirects a question opened under the wrong bank to its real bank', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ bank_id: 'b9' }))

    await mountView()

    expect(replace).toHaveBeenCalledWith({
      name: 'question',
      params: { bankId: 'b9', questionId: 'q1' },
    })
    expect(wrapper.find('.qp-stem').exists()).toBe(false)
    expect(listQuestionVersions).not.toHaveBeenCalled()
  })
})

describe('QuestionPageView edit gating for archived and locked questions', () => {
  it('disables edit on an archived question but keeps restore available', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ archived: true }))

    await mountView()

    const edit = wrapper.find('[data-testid="question-edit"]')
    expect(edit.exists()).toBe(true)
    expect(edit.element.disabled).toBe(true)
    expect(edit.attributes('title')).toBe(t('ep.manage.archived_note'))

    const archive = wrapper.find('[data-testid="question-archive"]')
    expect(archive.text()).toContain(t('ep.manage.restore'))
    expect(archive.element.disabled).toBe(false)
  })

  it('disables edit and archive while an active exam locks the question', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ locked_by_active_exam: true }))

    await mountView()

    for (const testId of ['question-edit', 'question-archive']) {
      const button = wrapper.find(`[data-testid="${testId}"]`)
      expect(button.exists()).toBe(true)
      expect(button.element.disabled).toBe(true)
      expect(button.attributes('title')).toBe(t('ep.manage.locked_desc'))
    }

    await wrapper.find('[data-testid="question-archive"]').trigger('click')
    await flush()
    expect(batchBankQuestions).not.toHaveBeenCalled()
  })
})

describe('QuestionPageView copy for members', () => {
  it('lets a member copy the question into a bank they can edit', async () => {
    getBank.mockResolvedValue({ id: 'b1', name: 'Bank One', role: 'MEMBER' })
    listBanks.mockResolvedValue([
      { id: 'b1', name: 'Bank One', role: 'MEMBER' },
      { id: 'b2', name: 'Bank Two', role: 'EDITOR' },
      { id: 'b3', name: 'Bank Three', role: 'MEMBER' },
    ])

    await mountView()

    expect(wrapper.find('[data-testid="question-edit"]').exists()).toBe(false)
    const values = wrapper.findAll('.copy-select option').map(option => option.element.value)
    expect(values).toEqual(['', 'b2'])

    await wrapper.find('.copy-select').setValue('b2')
    await wrapper.find('.copy-form .btn').trigger('click')
    await flush()

    expect(copyQuestionToBank).toHaveBeenCalledWith('t1', 'b1', 'q1', 'b2')
  })

  it('keeps the copy panel hidden when the member has no editable target', async () => {
    getBank.mockResolvedValue({ id: 'b1', name: 'Bank One', role: 'MEMBER' })
    listBanks.mockResolvedValue([{ id: 'b1', name: 'Bank One', role: 'MEMBER' }])

    await mountView()

    expect(wrapper.find('.copy-form').exists()).toBe(false)
    expect(wrapper.text()).not.toContain(t('ep.banks.copy_to'))
  })
})

describe('QuestionPageView version preview in the URL', () => {
  const versionList = [
    { id: 'v1', version_number: 1, stem: 'Oldest stem' },
    { id: 'v3', version_number: 3, stem: 'Current stem' },
    { id: 'v2', version_number: 2, stem: 'Middle stem' },
  ]

  it('writes the selected version to ?v= and clears it when returning to the current version', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ id: 'q3', version_number: 3, stem: 'Current stem' }))
    listQuestionVersions.mockResolvedValue(versionList)

    await mountView({ questionId: 'q3' })

    const items = wrapper.findAll('.version-item')
    await items[1].trigger('click')

    expect(wrapper.find('.qp-stem').text()).toBe('Middle stem')
    expect(replace).toHaveBeenCalledWith({ query: { v: '2' } })

    // The router would have written the query; mirror it before returning.
    routeState.query = { v: '2' }
    await wrapper.find('.qp-preview-note button').trigger('click')

    expect(wrapper.find('.qp-stem').text()).toBe('Current stem')
    expect(replace).toHaveBeenLastCalledWith({ query: {} })
  })

  it('restores a version preview from the URL on a fresh load', async () => {
    getQuestion.mockResolvedValue(makeQuestion({ id: 'q3', version_number: 3, stem: 'Current stem' }))
    listQuestionVersions.mockResolvedValue(versionList)
    routeState.query = { v: '2' }

    await mountView({ questionId: 'q3' })

    expect(wrapper.find('.qp-stem').text()).toBe('Middle stem')
    expect(wrapper.find('.practice-one-btn').exists()).toBe(false)
    expect(wrapper.find('.qp-preview-note').exists()).toBe(true)
  })
})

describe('QuestionPageView version request race', () => {
  it('ignores versions that resolve after the reader switched questions', async () => {
    let resolveFirst
    listQuestionVersions
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockImplementationOnce(() => Promise.resolve([
        { id: 'v2', version_number: 2, stem: 'Second question' },
      ]))
    getQuestion
      .mockResolvedValueOnce(makeQuestion({ id: 'q1', version_number: 1, stem: 'First question' }))
      .mockResolvedValue(makeQuestion({ id: 'q2', version_number: 2, stem: 'Second question' }))

    await mountView({ questionId: 'q1' })
    expect(wrapper.find('.qp-stem').text()).toBe('First question')

    await wrapper.setProps({ questionId: 'q2' })
    await flush()
    await flush()
    expect(wrapper.find('.qp-stem').text()).toBe('Second question')

    resolveFirst([{ id: 'v1', version_number: 1, stem: 'Stale first question' }])
    await flush()
    await flush()

    const items = wrapper.findAll('.version-item')
    expect(items.map(item => item.find('.mono').text())).toEqual(['v2'])
    expect(wrapper.text()).not.toContain('Stale first question')
  })
})
