import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ExamCenterView from '../../src/views/ExamCenterView.vue'
import { t } from '../../src/composables/useLocale.js'
import { listBanks } from '../../src/api/banks'
import { listProfiles, getBlueprint, saveBlueprint } from '../../src/api/exams'
import { listActiveSessions } from '../../src/api/practice'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn(),
}))

vi.mock('../../src/api/exams', () => ({
  listProfiles: vi.fn(),
  createProfile: vi.fn(),
  getBlueprint: vi.fn(),
  saveBlueprint: vi.fn(),
  startExam: vi.fn(),
}))

vi.mock('../../src/api/practice', () => ({
  listActiveSessions: vi.fn(),
  abandonSession: vi.fn(),
}))

const bank = { id: 'b1', name: 'Bank One', question_count: 10 }
const blueprint = {
  negative_mark: 0,
  sections: [{ name: '单选', type: 'SINGLE', count: 5, difficulty: null, chapter_id: '', tags: '' }],
}
const profile = {
  id: 'p1',
  name: 'Paper One',
  latest_blueprint: { version_number: 1, blueprint },
}

function mountView() {
  return mount(ExamCenterView, {
    props: { token: 'token' },
    attachTo: document.body,
    // AppDialog teleports to <body>; stubbing Teleport keeps the markup inside
    // the wrapper so focus and dialog assertion stay queryable.
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

function pressTabFromBody() {
  document.body.tabIndex = -1
  document.body.focus()
  document.body.dispatchEvent(new KeyboardEvent('keydown', {
    key: 'Tab',
    bubbles: true,
    cancelable: true,
  }))
}

describe('ExamCenterView dialogs', () => {
  let wrapper

  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    listBanks.mockResolvedValue([bank])
    listProfiles.mockResolvedValue([profile])
    listActiveSessions.mockResolvedValue([])
    getBlueprint.mockResolvedValue({ blueprint })
    saveBlueprint.mockResolvedValue({ id: 'bp1' })
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    wrapper = null
    document.body.innerHTML = ''
    document.body.style.overflow = ''
  })

  it('moves focus into the create-paper dialog, traps Tab and closes on Escape from body', async () => {
    wrapper = mountView()
    await flushPromises()

    const trigger = wrapper.find('.page-actions .btn')
    trigger.element.focus()
    await trigger.trigger('click')
    await flushPromises()

    const panel = wrapper.find('.exam-setup-dialog')
    expect(panel.exists()).toBe(true)
    expect(panel.element.contains(document.activeElement)).toBe(true)
    expect(document.activeElement.id).toBe('paper-name')

    pressTabFromBody()
    expect(panel.element.contains(document.activeElement)).toBe(true)

    pressEscapeFromBody()
    await flushPromises()

    expect(wrapper.find('.exam-setup-dialog').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('moves focus into the exam setup dialog and closes on Escape from body', async () => {
    wrapper = mountView()
    await flushPromises()

    const trigger = wrapper.find('.page-actions .btn-primary')
    trigger.element.focus()
    await trigger.trigger('click')
    await flushPromises()

    const panel = wrapper.find('.exam-setup-dialog')
    expect(panel.exists()).toBe(true)
    expect(document.activeElement.id).toBe('setup-bank')

    pressEscapeFromBody()
    await flushPromises()

    expect(wrapper.find('.exam-setup-dialog').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('opens the blueprint editor with focus inside and closes it cleanly from body Escape', async () => {
    wrapper = mountView()
    await flushPromises()

    const trigger = wrapper.find('.exam-paper-row .btn-quiet')
    trigger.element.focus()
    await trigger.trigger('click')
    await flushPromises()

    const panel = wrapper.find('.drawer')
    expect(panel.exists()).toBe(true)
    expect(panel.element.contains(document.activeElement)).toBe(true)
    expect(document.activeElement.id).toBe('bp-negative')

    pressEscapeFromBody()
    await flushPromises()

    expect(wrapper.find('.drawer').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('asks before dropping blueprint edits from the cancel button', async () => {
    wrapper = mountView()
    await flushPromises()

    await wrapper.find('.exam-paper-row .btn-quiet').trigger('click')
    await flushPromises()
    await wrapper.find('.drawer-body > .btn.btn-sm').trigger('click')

    await wrapper.find('.drawer-foot .btn-quiet').trigger('click')

    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(true)
    expect(wrapper.find('.drawer').exists()).toBe(true)

    await wrapper.find('.discard-discard').trigger('click')
    await flushPromises()

    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(false)
    expect(wrapper.find('.drawer').exists()).toBe(false)
  })

  it('asks on Escape while dirty, and saving resets the dirty baseline', async () => {
    wrapper = mountView()
    await flushPromises()

    await wrapper.find('.exam-paper-row .btn-quiet').trigger('click')
    await flushPromises()
    await wrapper.find('.drawer-body > .btn.btn-sm').trigger('click')

    pressEscapeFromBody()
    await flushPromises()
    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(true)
    expect(wrapper.find('.drawer').exists()).toBe(true)

    await wrapper.find('.discard-save').trigger('click')
    await flushPromises()

    expect(saveBlueprint).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(false)
    expect(wrapper.find('.drawer').exists()).toBe(true)

    pressEscapeFromBody()
    await flushPromises()
    expect(wrapper.find('.discard-prompt-dialog').exists()).toBe(false)
    expect(wrapper.find('.drawer').exists()).toBe(false)
  })

  it('explains why starting an exam is disabled when no bank exists', async () => {
    listBanks.mockResolvedValue([])
    wrapper = mountView()
    await flushPromises()

    const reason = wrapper.find('.action-reason')
    expect(reason.exists()).toBe(true)
    expect(reason.text()).toBe(t('ep.exam.start_requires_bank'))
    expect(wrapper.find('.page-actions .btn-primary').attributes('disabled')).toBeDefined()
  })

  it('does not show the no-bank explanation while a bank is available', async () => {
    wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.action-reason').exists()).toBe(false)
    expect(wrapper.find('.page-actions .btn-primary').attributes('disabled')).toBeUndefined()
  })

  it('shows a retry control instead of the empty state when a request rejects', async () => {
    listBanks.mockRejectedValueOnce(new Error('boom'))
    wrapper = mountView()
    await flushPromises()

    const error = wrapper.find('.exam-load-error')
    expect(error.exists()).toBe(true)
    expect(error.text()).toContain(t('ep.common.load_failed'))

    const retry = error.find('.btn')
    expect(retry.exists()).toBe(true)
    expect(retry.text()).toBe(t('ep.common.retry'))

    expect(wrapper.text()).not.toContain(t('ep.exam.papers_empty'))
    expect(wrapper.text()).not.toContain(t('ep.exam.no_banks'))
  })

  it('re-runs the loader when retry is clicked', async () => {
    listBanks.mockRejectedValueOnce(new Error('boom'))
    wrapper = mountView()
    await flushPromises()
    expect(listBanks).toHaveBeenCalledTimes(1)

    await wrapper.find('.exam-load-error .btn').trigger('click')
    await flushPromises()

    expect(listBanks).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.exam-load-error').exists()).toBe(false)
  })
})
