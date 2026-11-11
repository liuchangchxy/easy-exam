import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import QuestionEditModal from '../../src/components/QuestionEditModal.vue'
import { updateQuestion, getQuestion, getQuestionConflict, listQuestionVersions } from '../../src/api/questions'

vi.mock('../../src/api/questions', () => ({
  updateQuestion: vi.fn(),
  getQuestion: vi.fn(),
  getQuestionConflict: vi.fn(),
  listQuestionVersions: vi.fn(),
}))

function makeQuestion(overrides = {}) {
  return {
    id: 'q1',
    version_number: 1,
    stem: 'Original stem',
    type: 'SINGLE',
    options: [
      { key: 'A', content: 'Alpha' },
      { key: 'B', content: 'Beta' },
    ],
    answer: 'A',
    explanation: 'Original explanation',
    difficulty: 3,
    tags: ['math'],
    chapter_id: '',
    ...overrides,
  }
}

function mountModal(question = makeQuestion(), readOnly = false) {
  return mount(QuestionEditModal, {
    props: { show: true, question, chapters: [], readOnly, token: 'token' },
    attachTo: document.body,
    // AppDialog teleports to <body>; stubbing Teleport keeps the markup inside
    // the wrapper so the component contract stays queryable.
    global: { stubs: { teleport: true } },
  })
}

function pressEscapeFromBody() {
  document.body.tabIndex = -1
  document.body.focus()
  document.body.dispatchEvent(new KeyboardEvent('keydown', {
    key: 'Escape',
    bubbles: true,
    cancelable: true,
  }))
}

describe('QuestionEditModal', () => {
  let wrapper

  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    getQuestionConflict.mockResolvedValue({ has_conflict: false, conflict: null })
    listQuestionVersions.mockResolvedValue([])
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    wrapper = null
    document.body.innerHTML = ''
    document.body.style.overflow = ''
  })

  it('offers history and renders reachable versions', async () => {
    listQuestionVersions.mockResolvedValue([
      { id: 'v1', version_number: 1, stem: 'Original stem', options: [], answer: 'A', explanation: '' },
      { id: 'v2', version_number: 2, stem: 'Newer stem', options: [], answer: 'B', explanation: '' },
    ])

    wrapper = mountModal()
    await wrapper.find('.modal-head-right .btn').trigger('click')
    await flushPromises()

    expect(listQuestionVersions).toHaveBeenCalledWith('token', 'q1')
    const rows = wrapper.findAll('.version-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('v2')

    await rows[1].trigger('click')
    expect(wrapper.find('.version-preview').exists()).toBe(true)
    expect(wrapper.find('.version-stem').text()).toContain('Original stem')
  })

  it('asks about re-grading only when the answer changes and sends the choice', async () => {
    updateQuestion.mockResolvedValue(makeQuestion({ version_number: 2, answer: 'B' }))
    wrapper = mountModal()

    expect(wrapper.find('.regrade-choice').exists()).toBe(false)

    await wrapper.find('#edit-answer').setValue('B')
    expect(wrapper.find('.regrade-choice').exists()).toBe(true)
    expect(wrapper.find('.regrade-choice .check-row input').element.checked).toBe(false)

    await wrapper.find('#edit-stem').setValue('Edited stem')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const payload = updateQuestion.mock.calls[0][2]
    expect(payload.regrade_history).toBe(false)
    expect(payload.answer).toBe('B')
  })

  it('sends regrade_history when the user opts in', async () => {
    updateQuestion.mockResolvedValue(makeQuestion({ version_number: 2, answer: 'B' }))
    wrapper = mountModal()

    await wrapper.find('#edit-answer').setValue('B')
    await wrapper.find('.regrade-choice .check-row input').setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const payload = updateQuestion.mock.calls[0][2]
    expect(payload.regrade_history).toBe(true)
    expect(payload.apply_fsrs).toBe(true)
  })

  it('keeps the conflict draft and can save it as a new branch', async () => {
    const conflictError = { status: 409, detail: { error: 'version_conflict', current_version_number: 2 } }
    updateQuestion.mockRejectedValueOnce(conflictError)
    updateQuestion.mockResolvedValueOnce({ ...makeQuestion({ version_number: 3 }), conflict: { id: 'c1' } })

    wrapper = mountModal()
    await wrapper.find('#edit-stem').setValue('My local draft')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.conflict-actions').exists()).toBe(true)
    // The draft is still in the form; the conflict did not overwrite it.
    expect(wrapper.find('#edit-stem').element.value).toBe('My local draft')

    const branchButton = wrapper.find('.conflict-buttons .btn')
    await branchButton.trigger('click')
    await flushPromises()

    expect(updateQuestion).toHaveBeenCalledTimes(2)
    const branchPayload = updateQuestion.mock.calls[1][2]
    expect(branchPayload.allow_stale_branch).toBe(true)
    expect(branchPayload.reject_stale).toBe(false)
    expect(branchPayload.stem).toBe('My local draft')
    expect(wrapper.emitted('saved')?.[0]?.[0]?.conflict).toBeTruthy()
  })

  it('closes immediately when nothing changed', async () => {
    wrapper = mountModal()
    await flushPromises()

    await wrapper.find('.modal-footer .btn').trigger('click')

    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(false)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('closes a read-only viewer without a discard prompt', async () => {
    wrapper = mountModal(makeQuestion(), true)

    await wrapper.find('.modal-footer .btn').trigger('click')

    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(false)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('prompts before discarding an edited draft from the cancel button', async () => {
    wrapper = mountModal()
    await wrapper.find('#edit-stem').setValue('Edited stem')

    await wrapper.find('.modal-footer .btn').trigger('click')

    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(true)
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(wrapper.find('#edit-stem').element.value).toBe('Edited stem')

    await wrapper.find('.discard-discard').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('prompts on Escape and on the backdrop while dirty', async () => {
    wrapper = mountModal()
    await wrapper.find('#edit-stem').setValue('Edited stem')

    pressEscapeFromBody()
    await flushPromises()
    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(true)

    await wrapper.find('.discard-prompt-dialog .btn-quiet').trigger('click')
    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(false)
    expect(wrapper.emitted('close')).toBeUndefined()

    await wrapper.find('.app-dialog-scrim').trigger('click')
    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(true)
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('prompts from the header close control', async () => {
    wrapper = mountModal()
    await wrapper.find('#edit-stem').setValue('Edited stem')

    await wrapper.find('.app-dialog-close').trigger('click')

    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(true)
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('saves through the existing save path from the discard prompt', async () => {
    updateQuestion.mockResolvedValue(makeQuestion({ version_number: 2 }))
    wrapper = mountModal()
    await wrapper.find('#edit-stem').setValue('Edited stem')

    await wrapper.find('.app-dialog-close').trigger('click')
    await wrapper.find('.discard-save').trigger('click')
    await flushPromises()

    expect(updateQuestion).toHaveBeenCalledTimes(1)
    expect(updateQuestion.mock.calls[0][2].stem).toBe('Edited stem')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
