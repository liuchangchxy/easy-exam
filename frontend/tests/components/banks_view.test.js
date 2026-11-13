import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import BanksView from '../../src/views/BanksView.vue'
import { t } from '../../src/composables/useLocale.js'
import {
  listBanks,
  createBank,
  updateBank,
  batchBanks,
  deleteBank,
  restoreBank,
  listBankCategories,
  renameBankCategory,
  deleteBankCategory,
} from '../../src/api/banks'
import { startSession } from '../../src/api/practice'

const push = vi.fn()
const replace = vi.fn()
const routeState = reactive({ query: {} })

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push, replace }),
}))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn(),
  createBank: vi.fn(),
  updateBank: vi.fn(),
  deleteBank: vi.fn(),
  restoreBank: vi.fn(),
  batchBanks: vi.fn(),
  listBankCategories: vi.fn(),
  renameBankCategory: vi.fn(),
  deleteBankCategory: vi.fn(),
  downloadBankExport: vi.fn(),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn(),
  // useStartStudy asks for unfinished sessions before it starts another one.
  listActiveSessions: vi.fn().mockResolvedValue([]),
  abandonSession: vi.fn(),
  abandonAllSessions: vi.fn(),
}))

vi.mock('../../src/api/sync', () => ({
  triggerSyncEvent: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const adminBank = (overrides = {}) => ({
  id: 'b1', name: 'Bank One', category: 'Test', question_count: 3, role: 'ADMIN', ...overrides,
})

const lastReplaceQuery = () => replace.mock.calls.at(-1)?.[0]?.query

function mountView() {
  return mount(BanksView, { props: { token: 't1' } })
}

describe('BanksView row semantics and practice failures', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    sessionStorage.clear()
    listBanks.mockResolvedValue([adminBank()])
  })

  it('renders a plain row container with an explicit open control', async () => {
    const wrapper = mountView()
    await flush()

    const row = wrapper.find('.banks-row')
    expect(row.attributes('role')).toBeUndefined()
    expect(row.attributes('tabindex')).toBeUndefined()
    expect(row.find('.bank-open').element.tagName).toBe('BUTTON')
    expect(row.element.querySelector('button button')).toBeNull()
    expect(row.findAll('.bank-actions-cell button').length).toBe(2)

    await row.find('.bank-open').trigger('click')
    expect(push).toHaveBeenCalledWith('/banks/b1')
  })

  it('disables manage with a reason while an exam locks the bank', async () => {
    listBanks.mockResolvedValue([adminBank({ name: 'Locked Bank', has_active_exam: true })])
    const wrapper = mountView()
    await flush()

    const lock = wrapper.find('.bank-manage-locked')
    expect(lock.exists()).toBe(true)
    expect(lock.attributes('title')).toBe(t('ep.manage.locked_desc'))
    expect(lock.find('button').element.disabled).toBe(true)
  })

  it('opens the create-bank dialog with focus inside, traps Tab and restores the trigger on Escape', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    const trigger = wrapper.find('.page-actions .btn-primary').element
    trigger.focus()
    await wrapper.find('.page-actions .btn-primary').trigger('click')
    await flush()

    const panel = document.querySelector('[data-testid="bank-create-dialog"]')
    expect(panel).not.toBeNull()
    expect(document.activeElement).toBe(document.querySelector('#bank-create-name'))

    // Tab from the last focusable control wraps back into the dialog.
    const submit = panel.querySelector('button[type="submit"]')
    submit.focus()
    submit.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }))
    expect(document.activeElement).toBe(panel.querySelector('.app-dialog-close'))

    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flush()

    expect(document.querySelector('[data-testid="bank-create-dialog"]')).toBeNull()
    expect(document.activeElement).toBe(trigger)

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('surfaces a failed practice start on the page', async () => {
    startSession.mockRejectedValue({ detail: 'start failed' })
    const wrapper = mountView()
    await flush()

    await wrapper.find('.bank-actions-cell .btn').trigger('click')
    await flush()

    const notice = wrapper.find('.notice.bad')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain(t('ep.banks.practice_start_failed', { message: 'start failed' }))
    expect(push).not.toHaveBeenCalled()
  })

  it('exposes bank management in an overflow menu without nesting buttons', async () => {
    const wrapper = mountView()
    await flush()

    const row = wrapper.find('.banks-row')
    expect(row.findAll('.bank-actions-cell button').length).toBe(2)
    await row.find('[data-testid="bank-menu-trigger"]').trigger('click')

    const menu = row.find('[data-testid="bank-menu"]')
    expect(menu.exists()).toBe(true)
    expect(row.element.querySelector('button button')).toBeNull()
    expect(menu.text()).toContain(t('ep.banks.edit_meta'))
    expect(menu.text()).toContain(t('ep.banks.action_archive'))
  })

  it('keeps only non-redundant entries in the kebab menu', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-menu-trigger"]').trigger('click')
    const items = wrapper.find('[data-testid="bank-menu"]').findAll('button')
    expect(items.map(item => item.text())).toEqual([
      t('ep.banks.edit_meta'),
      t('ep.banks.export_json'),
      t('ep.banks.export_csv'),
      t('ep.banks.action_archive'),
    ])
    expect(items.some(item => item.text() === t('ep.banks.open'))).toBe(false)
    expect(items.some(item => item.text() === t('ep.banks.manage'))).toBe(false)
  })

  it('gates edit and archive to owners while exports stay available to members', async () => {
    listBanks.mockResolvedValue([adminBank({ role: 'MEMBER', name: 'Shared Bank' })])
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-menu-trigger"]').trigger('click')
    const items = wrapper.find('[data-testid="bank-menu"]').findAll('button')
    const edit = items.find(item => item.text() === t('ep.banks.edit_meta'))
    const archive = items.find(item => item.text() === t('ep.banks.action_archive'))
    const json = items.find(item => item.text() === t('ep.banks.export_json'))

    expect(edit.element.disabled).toBe(true)
    expect(edit.attributes('title')).toBe(t('ep.common.owner_only_action'))
    expect(archive.element.disabled).toBe(true)
    expect(archive.attributes('title')).toBe(t('ep.common.owner_only_action'))
    expect(json.element.disabled).toBe(false)
    expect(json.attributes('title')).toBeUndefined()
  })

  it('shows a role badge only for banks the user does not own', async () => {
    listBanks.mockResolvedValue([
      adminBank({ id: 'own', name: 'Owned', role: 'ADMIN' }),
      adminBank({ id: 'ed', name: 'Edited', role: 'EDITOR' }),
      adminBank({ id: 'mem', name: 'Shared', role: 'MEMBER' }),
    ])
    const wrapper = mountView()
    await flush()

    const rows = wrapper.findAll('.banks-row')
    expect(rows[0].find('.bank-name .tag').exists()).toBe(false)
    expect(rows[1].find('.bank-name .tag').text()).toBe(t('ep.banks.editor'))
    expect(rows[2].find('.bank-name .tag').text()).toBe(t('ep.banks.member'))
  })

  it('appends the bank name to row action aria-labels', async () => {
    const wrapper = mountView()
    await flush()

    const row = wrapper.find('.banks-row')
    expect(row.find('.bank-practice-btn').attributes('aria-label')).toBe(`${t('ep.banks.practice')} Bank One`)
    expect(row.findAll('.bank-actions-cell button')[1].attributes('aria-label')).toBe(`${t('ep.banks.manage')} Bank One`)
    expect(row.find('[data-testid="bank-menu-trigger"]').attributes('aria-label')).toBe(`${t('ep.banks.menu_label')} Bank One`)
  })

  it('groups the overflow trigger with row actions in one action cluster', async () => {
    const longName = 'A very long bank name that must truncate instead of pushing the row layout'
    listBanks.mockResolvedValue([adminBank({ name: longName, question_count: 12, role: 'EDITOR' })])
    const wrapper = mountView()
    await flush()

    const row = wrapper.find('.banks-row')
    const children = Array.from(row.element.children)
    const cluster = children.find(el => el.classList.contains('bank-action-cluster'))

    // The menu is no longer a standalone grid cell on the title row.
    expect(cluster).toBeTruthy()
    expect(children.some(el => el.classList.contains('bank-menu-wrap'))).toBe(false)
    expect(children).toHaveLength(4)

    // Actions and overflow trigger share one right-aligned container.
    expect(cluster.querySelector('.bank-actions-cell')).not.toBeNull()
    expect(cluster.querySelector('.bank-menu-wrap')).not.toBeNull()
    expect(cluster.querySelector('[data-testid="bank-menu-trigger"]')).not.toBeNull()
    expect(cluster.querySelectorAll('.bank-actions-cell button')).toHaveLength(2)
    expect(cluster.querySelector('.bank-actions-cell [data-testid="bank-menu-trigger"]')).toBeNull()

    // Long bank names live in a truncating span, keeping tags intact.
    expect(row.find('.bank-name-text').text()).toBe(longName)
    expect(row.find('.bank-name .tag').text()).toBe(t('ep.banks.editor'))

    const trigger = row.find('[data-testid="bank-menu-trigger"]')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(trigger.attributes('aria-controls')).toBeUndefined()

    await trigger.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(trigger.attributes('aria-controls')).toBe('bank-menu-b1')
    expect(cluster.querySelector('[data-testid="bank-menu"]')).not.toBeNull()
  })

  it('closes the overflow menu on Escape and restores trigger focus', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    const trigger = wrapper.find('[data-testid="bank-menu-trigger"]')
    await trigger.trigger('click')
    expect(wrapper.find('[data-testid="bank-menu"]').exists()).toBe(true)

    const firstItem = wrapper.find('[data-testid="bank-menu"] .bank-menu-item')
    firstItem.element.focus()
    await firstItem.trigger('keydown', { key: 'Escape' })

    expect(wrapper.find('[data-testid="bank-menu"]').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('batch-selects banks and sends the archive request', async () => {
    batchBanks.mockResolvedValue({ affected: 1 })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mountView()
    await flush()

    await wrapper.find('.bank-select-cell input').setValue(true)
    expect(wrapper.find('.bank-batch-bar').text()).toContain(t('ep.banks.batch_selected', { count: 1 }))

    await wrapper.find('[data-testid="bank-batch-archive"]').trigger('click')
    await flush()

    expect(confirmSpy).toHaveBeenCalledWith(t('ep.banks.batch_archive_confirm', { count: 1 }))
    expect(batchBanks).toHaveBeenCalledWith('t1', { bank_ids: ['b1'], operation: 'archive' })
    expect(listBanks).toHaveBeenCalledTimes(2)
    confirmSpy.mockRestore()
  })

  it('leaves banks untouched when the batch-archive confirmation is declined', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = mountView()
    await flush()

    await wrapper.find('.bank-select-cell input').setValue(true)
    await wrapper.find('[data-testid="bank-batch-archive"]').trigger('click')
    await flush()

    expect(confirmSpy).toHaveBeenCalledWith(t('ep.banks.batch_archive_confirm', { count: 1 }))
    expect(batchBanks).not.toHaveBeenCalled()
    expect(listBanks).toHaveBeenCalledTimes(1)
    confirmSpy.mockRestore()
  })

  it('disables batch actions when any selected bank is not owned by the user', async () => {
    listBanks.mockResolvedValue([
      adminBank({ id: 'own', name: 'Owned', role: 'ADMIN' }),
      adminBank({ id: 'mem', name: 'Shared', role: 'MEMBER' }),
    ])
    const wrapper = mountView()
    await flush()

    const checkboxes = wrapper.findAll('.bank-select-cell input')
    await checkboxes[1].setValue(true)

    const archive = wrapper.find('[data-testid="bank-batch-archive"]')
    expect(archive.element.disabled).toBe(true)
    expect(archive.attributes('title')).toBe(t('ep.common.owner_only_action'))
    const setCategory = wrapper.find('[data-testid="bank-batch-set-category"]')
    expect(setCategory.element.disabled).toBe(true)
    expect(setCategory.attributes('title')).toBe(t('ep.common.owner_only_action'))
  })

  it('styles the batch archive as a destructive action', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('.bank-select-cell input').setValue(true)
    const archive = wrapper.find('[data-testid="bank-batch-archive"]')
    expect(archive.classes()).toContain('btn-danger')
    expect(archive.classes()).not.toContain('btn-quiet')
    // The benign batch action stays neutral.
    expect(wrapper.find('[data-testid="bank-batch-set-category"]').classes()).not.toContain('btn-danger')
  })

  it('lets a failed batch archive be retried or dismissed', async () => {
    batchBanks.mockRejectedValueOnce({ detail: 'batch failed' })
    batchBanks.mockResolvedValueOnce({ affected: 1 })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mountView()
    await flush()

    await wrapper.find('.bank-select-cell input').setValue(true)
    await wrapper.find('[data-testid="bank-batch-archive"]').trigger('click')
    await flush()

    const notice = wrapper.find('.notice.bad')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('batch failed')
    const retry = wrapper.find('[data-testid="bank-error-retry"]')
    expect(retry.exists()).toBe(true)
    expect(retry.text()).toBe(t('ep.common.retry'))

    await retry.trigger('click')
    await flush()

    expect(batchBanks).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.notice.bad').exists()).toBe(false)
    confirmSpy.mockRestore()
  })

  it('offers a retry for a failed restore and re-runs it', async () => {
    restoreBank.mockRejectedValueOnce({ detail: 'restore failed' })
    restoreBank.mockResolvedValueOnce({ id: 'b1' })
    listBanks.mockImplementation((token, options) => Promise.resolve([
      adminBank({ deleted: Boolean(options?.deleted) }),
    ]))
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()

    await wrapper.find('[data-testid="row-restore"]').trigger('click')
    await flush()
    expect(wrapper.find('.notice.bad').text()).toContain('restore failed')

    await wrapper.find('[data-testid="bank-error-retry"]').trigger('click')
    await flush()
    expect(restoreBank).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.notice.bad').exists()).toBe(false)
  })

  it('dismisses a non-retryable action error with an accessible close button', async () => {
    startSession.mockRejectedValue({ detail: 'start failed' })
    const wrapper = mountView()
    await flush()

    await wrapper.find('.bank-actions-cell .btn').trigger('click')
    await flush()

    expect(wrapper.find('[data-testid="bank-error-retry"]').exists()).toBe(false)
    const dismiss = wrapper.find('[data-testid="bank-error-dismiss"]')
    expect(dismiss.attributes('aria-label')).toBe(t('ep.common.close'))

    await dismiss.trigger('click')
    expect(wrapper.find('.notice.bad').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('start failed')
  })

  it('prunes the batch selection to rows that stay visible when the filters change', async () => {
    listBanks.mockResolvedValue([
      adminBank({ id: 'b1', name: 'Bank One', category: 'Test' }),
      adminBank({ id: 'b2', name: 'Second Bank', category: 'Other' }),
    ])
    const wrapper = mountView()
    await flush()

    const checkboxes = wrapper.findAll('.bank-select-cell input')
    await checkboxes[0].setValue(true)
    await checkboxes[1].setValue(true)
    expect(wrapper.find('.bank-batch-bar').text()).toContain(t('ep.banks.batch_selected', { count: 2 }))

    // Refining the search keeps the still-visible row selected instead of
    // discarding the whole batch.
    await wrapper.find('.search-box input').setValue('one')
    await flush()
    expect(wrapper.find('.bank-batch-bar').text()).toContain(t('ep.banks.batch_selected', { count: 1 }))
    const rows = wrapper.findAll('.banks-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].find('input').element.checked).toBe(true)

    // When nothing remains visible, the selection has nothing left to keep.
    await wrapper.find('.search-box input').setValue('no such bank')
    await flush()
    expect(wrapper.find('.bank-batch-bar').exists()).toBe(false)
  })

  it('disables category management without an owned bank', async () => {
    listBanks.mockResolvedValue([adminBank({ role: 'EDITOR' })])
    const wrapper = mountView()
    await flush()

    const manage = wrapper.find('[data-testid="bank-category-manage"]')
    expect(manage.element.disabled).toBe(true)
    expect(manage.attributes('title')).toBe(t('ep.common.owner_only_action'))
  })

  it('keeps category management available in recycle for an owner with active banks', async () => {
    listBanks.mockImplementation((token, options) => Promise.resolve(
      options?.deleted
        ? [adminBank({ id: 'd1', name: 'Deleted Bank', role: 'MEMBER', deleted: true })]
        : [adminBank({ id: 'a1', name: 'Owned Bank', role: 'ADMIN' })],
    ))
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()

    // The recycle list itself holds no owned bank, but ownership is a property
    // of the user's active banks and survives the view switch.
    const manage = wrapper.find('[data-testid="bank-category-manage"]')
    expect(manage.element.disabled).toBe(false)
    expect(manage.attributes('title')).toBeUndefined()
  })

  it('does not claim ownership in recycle when no active list was ever loaded', async () => {
    routeState.query = { view: 'recycle' }
    listBanks.mockResolvedValue([adminBank({ role: 'MEMBER', deleted: true })])
    const wrapper = mountView()
    await flush()

    const manage = wrapper.find('[data-testid="bank-category-manage"]')
    expect(manage.element.disabled).toBe(true)
    expect(manage.attributes('title')).toBe(t('ep.common.owner_only_action'))
  })

  it('shows a filtered-empty state with a clear-filters action when nothing matches', async () => {
    const wrapper = mountView()
    await flush()

    const search = wrapper.find('.search-box input')
    await search.setValue('no such bank')

    expect(wrapper.find('.banks-row').exists()).toBe(false)
    const noMatch = wrapper.find('[data-testid="bank-no-match"]')
    expect(noMatch.exists()).toBe(true)
    expect(noMatch.text()).toContain(t('ep.banks.no_match'))
    expect(noMatch.text()).toContain(t('ep.banks.no_match_hint'))

    await wrapper.find('[data-testid="bank-clear-filters"]').trigger('click')
    expect(search.element.value).toBe('')
    expect(wrapper.find('.banks-row').exists()).toBe(true)
    expect(wrapper.find('[data-testid="bank-no-match"]').exists()).toBe(false)
  })

  it('keeps the first-run empty state when there are no banks at all', async () => {
    listBanks.mockResolvedValue([])
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('[data-testid="bank-no-match"]').exists()).toBe(false)
    expect(wrapper.find('.empty').text()).toContain(t('ep.banks.empty'))
    expect(wrapper.find('.empty').text()).toContain(t('ep.banks.empty_hint'))
    expect(wrapper.find('.empty-actions .btn-primary').exists()).toBe(true)
  })

  it('renders a dedicated retry panel when the list fails to load', async () => {
    listBanks.mockRejectedValueOnce({ detail: 'network down' })
    const wrapper = mountView()
    await flush()

    const panel = wrapper.find('[data-testid="bank-load-error"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain(t('ep.common.load_failed'))
    expect(panel.text()).toContain('network down')
    expect(wrapper.find('.empty').text()).not.toContain(t('ep.banks.empty'))

    listBanks.mockResolvedValue([adminBank()])
    await wrapper.find('[data-testid="bank-retry"]').trigger('click')
    await flush()

    expect(wrapper.find('[data-testid="bank-load-error"]').exists()).toBe(false)
    expect(wrapper.find('.banks-row').exists()).toBe(true)
  })

  it('guards the practice button against a second start while pending', async () => {
    let resolveStart
    startSession.mockImplementation(() => new Promise(resolve => { resolveStart = resolve }))
    const wrapper = mountView()
    await flush()

    const button = wrapper.find('.bank-practice-btn')
    await button.trigger('click')
    await flush()

    expect(button.element.disabled).toBe(true)
    expect(button.text()).toBe(t('ep.common.starting'))

    await button.trigger('click')
    expect(startSession).toHaveBeenCalledTimes(1)

    resolveStart({ id: 's1' })
    await flush()
    expect(push).toHaveBeenCalledWith('/practice/s1')
  })

  it('confirms before discarding a dirty create form', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('.page-actions .btn-primary').trigger('click')
    await flush()

    const nameInput = document.querySelector('#bank-create-name')
    nameInput.value = 'Draft name'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()

    // Escape on a dirty form opens the discard prompt instead of closing.
    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flush()
    expect(document.querySelector('[data-testid="bank-create-dialog"]')).not.toBeNull()
    const prompt = document.querySelector('.discard-prompt-dialog')
    expect(prompt).not.toBeNull()

    // Accepting the prompt discards and closes the dialog.
    prompt.querySelector('.discard-discard').click()
    await flush()
    expect(document.querySelector('[data-testid="bank-create-dialog"]')).toBeNull()

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('routes the create dialog footer cancel through the dirty guard', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('.page-actions .btn-primary').trigger('click')
    await flush()

    const nameInput = document.querySelector('#bank-create-name')
    nameInput.value = 'Draft name'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()

    document.querySelector('[data-testid="bank-create-dialog"] .app-dialog-foot .btn-quiet').click()
    await flush()

    const prompt = document.querySelector('.discard-prompt-dialog')
    expect(prompt).not.toBeNull()
    expect(prompt.textContent).toContain(t('ep.common.unsaved_title'))
    expect(prompt.textContent).toContain(t('ep.common.unsaved_desc'))
    expect(prompt.querySelector('.discard-cancel').textContent).toContain(t('ep.common.keep_editing'))
    expect(prompt.querySelector('.discard-discard').textContent).toContain(t('ep.common.discard'))
    expect(document.querySelector('[data-testid="bank-create-dialog"]')).not.toBeNull()

    // Keeping the draft leaves the dialog open with the typed name.
    prompt.querySelector('.discard-cancel').click()
    await flush()
    expect(document.querySelector('#bank-create-name').value).toBe('Draft name')

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('confirms before discarding a dirty edit form', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('[data-testid="bank-menu-trigger"]').trigger('click')
    const editItem = wrapper.find('[data-testid="bank-menu"]').findAll('button')
      .find(btn => btn.text() === t('ep.banks.edit_meta'))
    await editItem.trigger('click')
    await flush()

    const nameInput = document.querySelector('#bank-edit-name')
    nameInput.value = 'Renamed bank'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()

    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flush()

    const prompt = document.querySelector('.discard-prompt-dialog')
    expect(prompt).not.toBeNull()

    prompt.querySelector('.discard-cancel').click()
    await flush()
    // Keeping the draft leaves the edit dialog open with the typed name.
    expect(document.querySelector('#bank-edit-name')).not.toBeNull()
    expect(document.querySelector('#bank-edit-name').value).toBe('Renamed bank')

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('discards a dirty edit draft when the prompt is accepted', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('[data-testid="bank-menu-trigger"]').trigger('click')
    const editItem = wrapper.find('[data-testid="bank-menu"]').findAll('button')
      .find(btn => btn.text() === t('ep.banks.edit_meta'))
    await editItem.trigger('click')
    await flush()

    const nameInput = document.querySelector('#bank-edit-name')
    nameInput.value = 'Renamed bank'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()

    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flush()

    document.querySelector('.discard-prompt-dialog .discard-discard').click()
    await flush()
    expect(document.querySelector('#bank-edit-name')).toBeNull()

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('closes a clean create form without prompting', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('.page-actions .btn-primary').trigger('click')
    await flush()
    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flush()

    expect(document.querySelector('[data-testid="bank-create-dialog"]')).toBeNull()
    expect(document.querySelector('.discard-prompt-dialog')).toBeNull()

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('switches between the all-banks and recycle views with a segmented control', async () => {
    const wrapper = mountView()
    await flush()

    const group = wrapper.find('[role="group"]')
    expect(group.exists()).toBe(true)
    const all = wrapper.find('[data-testid="bank-view-all"]')
    const recycle = wrapper.find('[data-testid="bank-recycle-toggle"]')
    expect(all.attributes('aria-pressed')).toBe('true')
    expect(all.classes()).toContain('is-on')
    expect(recycle.attributes('aria-pressed')).toBe('false')
    expect(recycle.classes()).not.toContain('is-on')

    await recycle.trigger('click')
    await flush()

    expect(wrapper.find('[data-testid="bank-view-all"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.find('[data-testid="bank-recycle-toggle"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('[data-testid="bank-recycle-toggle"]').classes()).toContain('is-on')
    expect(wrapper.find('.banks-view-switch').element.closest('.banks-toolbar')).not.toBeNull()
    // The banner offers an honest way back instead of a fake history button.
    expect(wrapper.find('[data-testid="bank-back-to-active"]').text()).toBe(t('ep.banks.back_to_active'))
    const bareBack = wrapper.findAll('button')
      .some(btn => btn.text().trim() === t('ep.common.back'))
    expect(bareBack).toBe(false)
  })

  it('returns to the all-banks view from the recycle segment', async () => {
    const wrapper = mountView()
    await flush()

    const recycle = wrapper.find('[data-testid="bank-recycle-toggle"]')
    await recycle.trigger('click')
    await flush()
    expect(listBanks).toHaveBeenLastCalledWith('t1', { deleted: true })

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()
    expect(listBanks).toHaveBeenLastCalledWith('t1', { deleted: false })
    expect(wrapper.find('[data-testid="bank-view-all"]').attributes('aria-pressed')).toBe('true')
  })

  it('uses the recycle subtitle in recycle mode instead of the accessible count', async () => {
    listBanks.mockResolvedValue([adminBank({ deleted: true })])
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()

    const sub = wrapper.find('.page-sub').text()
    expect(sub).toContain(t('ep.banks.recycle_sub', { count: 1 }))
    expect(sub).not.toContain(t('ep.banks.sub', { count: 1 }))
  })

  it('renders recycle rows as static text with an inline restore action', async () => {
    restoreBank.mockResolvedValue({ id: 'b1', deleted: false })
    listBanks.mockImplementation((token, options) => Promise.resolve([
      adminBank({ deleted: Boolean(options?.deleted) }),
    ]))
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()
    expect(listBanks).toHaveBeenLastCalledWith('t1', { deleted: true })

    const row = wrapper.find('.banks-row')
    expect(row.find('.bank-static').exists()).toBe(true)
    expect(row.find('.bank-open').exists()).toBe(false)
    expect(row.find('a').exists()).toBe(false)
    expect(row.find('.bank-practice-btn').exists()).toBe(false)
    expect(row.find('[data-testid="bank-menu-trigger"]').exists()).toBe(false)
    expect(row.find('.bank-select-cell').exists()).toBe(false)
    expect(wrapper.find('.bank-batch-bar').exists()).toBe(false)
    expect(row.find('.bank-name-text').text()).toBe('Bank One')
    expect(row.find('.tag.bad').text()).toBe(t('ep.banks.deleted_badge'))

    const restore = row.find('[data-testid="row-restore"]')
    expect(restore.classes()).toContain('btn')
    expect(restore.classes()).toContain('btn-sm')
    await restore.trigger('click')
    await flush()

    expect(restoreBank).toHaveBeenCalledWith('t1', 'b1')
    expect(push).not.toHaveBeenCalled()
  })

  it('syncs search, category and sort to the URL and keeps category in recycle', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('.search-box input').setValue('one')
    await flush()
    expect(lastReplaceQuery()).toEqual({ q: 'one' })

    await wrapper.find('.select').setValue('Test')
    await flush()
    expect(lastReplaceQuery()).toEqual({ q: 'one', category: 'Test' })

    await wrapper.find('[data-testid="bank-sort"]').setValue('name')
    await flush()
    expect(lastReplaceQuery()).toEqual({ q: 'one', category: 'Test', sort: 'name' })

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()
    expect(lastReplaceQuery()).toEqual({ q: 'one', category: 'Test', sort: 'name', view: 'recycle' })
    expect(wrapper.find('.banks-toolbar select').element.value).toBe('Test')
  })

  it('seeds the list state from the URL and restores the view on history navigation', async () => {
    routeState.query = { q: 'one', sort: 'name' }
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('.search-box input').element.value).toBe('one')
    expect(wrapper.find('[data-testid="bank-sort"]').element.value).toBe('name')

    routeState.query = { q: 'one', sort: 'name', view: 'recycle' }
    await flush()

    expect(wrapper.find('[data-testid="bank-recycle-toggle"]').attributes('aria-pressed')).toBe('true')
    expect(listBanks).toHaveBeenLastCalledWith('t1', { deleted: true })

    routeState.query = { q: 'one', sort: 'name' }
    await flush()

    expect(wrapper.find('[data-testid="bank-view-all"]').attributes('aria-pressed')).toBe('true')
    expect(listBanks).toHaveBeenLastCalledWith('t1', { deleted: false })
  })

  it('stores the list state for the in-app back control', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('.search-box input').setValue('one')
    await flush()

    expect(JSON.parse(sessionStorage.getItem('easyexam.banks.query'))).toEqual({ q: 'one' })
  })

  it('seeds the category filter inside the recycle view from the URL', async () => {
    routeState.query = { view: 'recycle', category: 'Test' }
    listBanks.mockResolvedValue([adminBank({ category: 'Test', deleted: true })])
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('[data-testid="bank-recycle-toggle"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('.banks-toolbar select').element.value).toBe('Test')
    // The filter survives reloads because it stays in the URL and storage.
    expect(JSON.parse(sessionStorage.getItem('easyexam.banks.query'))).toEqual({
      view: 'recycle',
      category: 'Test',
    })
  })

  it('falls back to all categories when the stored one is gone in recycle', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.findAll('.banks-toolbar select')[0].setValue('Test')
    await flush()

    listBanks.mockImplementation((token, options) => Promise.resolve(
      options?.deleted
        ? [adminBank({ id: 'd1', category: 'Other', deleted: true })]
        : [adminBank({ category: 'Test' })],
    ))
    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()

    expect(wrapper.find('.banks-toolbar select').element.value).toBe('')
    expect(lastReplaceQuery()).toEqual({ view: 'recycle' })
  })

  it('moves the category filter to the renamed category and keeps the manager open', async () => {
    let banks = [adminBank({ category: 'Old' })]
    listBanks.mockImplementation(() => Promise.resolve(banks))
    listBankCategories.mockResolvedValue([{ name: 'Old', count: 1 }])
    renameBankCategory.mockImplementation(async () => {
      banks = [adminBank({ category: 'New' })]
      listBankCategories.mockResolvedValue([{ name: 'New', count: 1 }])
    })
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.findAll('.banks-toolbar select')[0].setValue('Old')
    await flush()

    await wrapper.find('[data-testid="bank-category-manage"]').trigger('click')
    await flush()

    const row = document.querySelector('.category-row')
    const input = row.querySelector('.input')
    input.value = 'New'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()
    row.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flush()

    expect(renameBankCategory).toHaveBeenCalledWith('t1', 'Old', 'New')
    expect(document.querySelector('.category-row')).not.toBeNull()
    expect(document.querySelector('.category-row .input').value).toBe('New')
    expect(wrapper.findAll('.banks-toolbar select')[0].element.value).toBe('New')

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('resets the category filter after deleting it and refetches the manager rows', async () => {
    let banks = [adminBank({ category: 'Old' })]
    listBanks.mockImplementation(() => Promise.resolve(banks))
    listBankCategories.mockResolvedValue([{ name: 'Old', count: 1 }])
    deleteBankCategory.mockImplementation(async () => {
      banks = [adminBank({ category: 'Default' })]
      listBankCategories.mockResolvedValue([])
    })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.findAll('.banks-toolbar select')[0].setValue('Old')
    await flush()

    await wrapper.find('[data-testid="bank-category-manage"]').trigger('click')
    await flush()

    const row = document.querySelector('.category-row')
    expect(row.querySelector('.btn-danger')).not.toBeNull()
    row.querySelector('.btn-danger').click()
    await flush()

    expect(deleteBankCategory).toHaveBeenCalledWith('t1', 'Old')
    expect(wrapper.findAll('.banks-toolbar select')[0].element.value).toBe('')
    expect(document.querySelector('.category-row')).toBeNull()
    expect(document.querySelector('.app-dialog-panel')).not.toBeNull()
    confirmSpy.mockRestore()

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('omits a blank category instead of persisting a localized label', async () => {
    createBank.mockResolvedValue({ id: 'b9', name: 'Fresh' })
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('.page-actions .btn-primary').trigger('click')
    await flush()

    const nameInput = document.querySelector('#bank-create-name')
    nameInput.value = 'Fresh'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()
    document.querySelector('#bank-create-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flush()

    expect(createBank).toHaveBeenCalledWith('t1', { name: 'Fresh', description: '' })
    expect(Object.keys(createBank.mock.calls[0][1])).not.toContain('category')

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('does not send a blank category when editing', async () => {
    updateBank.mockResolvedValue({ id: 'b1' })
    const wrapper = mount(BanksView, { props: { token: 't1' }, attachTo: document.body })
    await flush()

    await wrapper.find('[data-testid="bank-menu-trigger"]').trigger('click')
    const editItem = wrapper.find('[data-testid="bank-menu"]').findAll('button')
      .find(btn => btn.text() === t('ep.banks.edit_meta'))
    await editItem.trigger('click')
    await flush()

    const categoryInput = document.querySelectorAll('#bank-edit-form .input')[1]
    categoryInput.value = ''
    categoryInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()
    document.querySelector('#bank-edit-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flush()

    expect(updateBank).toHaveBeenCalledTimes(1)
    const payload = updateBank.mock.calls[0][2]
    expect(Object.keys(payload)).not.toContain('category')
    expect(payload.name).toBe('Bank One')

    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('shows a specific archive confirmation toast rather than a generic save', async () => {
    deleteBank.mockResolvedValue({ id: 'b1' })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-menu-trigger"]').trigger('click')
    const archive = wrapper.find('[data-testid="bank-menu"]').findAll('button')
      .find(btn => btn.text() === t('ep.banks.action_archive'))
    await archive.trigger('click')
    await flush()

    expect(deleteBank).toHaveBeenCalledWith('t1', 'b1')
    const toast = wrapper.find('.notice.ok')
    expect(toast.text()).toContain(t('ep.manage.audit_bank_deleted'))
    expect(toast.text()).not.toBe(t('ep.banks.saved'))
    confirmSpy.mockRestore()
  })
})
