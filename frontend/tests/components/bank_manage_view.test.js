import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import BankManageView from '../../src/views/BankManageView.vue'
import {
  getBank,
  listBankQuestionsContent,
  listChapters,
  listBankMembers,
  listTags,
  listBankImports,
  listBankAudit,
  listBanks,
  updateBank,
  updateBankMemberRole,
  reorderChapters,
  createChapter,
  createTag,
  updateTag,
  deleteTag,
  batchBankQuestions,
  downloadBankExport,
} from '../../src/api/banks'
import { listDrafts } from '../../src/api/ai'

const push = vi.fn()
const replace = vi.fn()
const routeState = reactive({ params: { bankId: 'b1' }, query: {} })

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push, replace }),
}))

vi.mock('../../src/api/banks', () => ({
  getBank: vi.fn(),
  listBanks: vi.fn(),
  listBankQuestionsContent: vi.fn(),
  listChapters: vi.fn(),
  listBankMembers: vi.fn(),
  addBankMember: vi.fn(),
  removeBankMember: vi.fn(),
  updateBankMemberRole: vi.fn(),
  leaveBank: vi.fn(),
  transferBankOwnership: vi.fn(),
  createChapter: vi.fn(),
  updateChapter: vi.fn(),
  deleteChapter: vi.fn(),
  reorderChapters: vi.fn(),
  createQuestion: vi.fn(),
  batchBankQuestions: vi.fn(),
  updateBank: vi.fn(),
  deleteBank: vi.fn(),
  listBankAudit: vi.fn(),
  listBankImports: vi.fn(),
  listTags: vi.fn(),
  createTag: vi.fn(),
  updateTag: vi.fn(),
  deleteTag: vi.fn(),
  downloadBankExport: vi.fn(),
}))

vi.mock('../../src/api/questions', () => ({
  updateQuestion: vi.fn(),
  getQuestion: vi.fn(),
  getQuestionConflict: vi.fn(),
  listQuestionVersions: vi.fn(),
  deleteQuestionVersion: vi.fn(),
}))

vi.mock('../../src/api/ai', () => ({
  listDrafts: vi.fn(),
  acceptDraft: vi.fn(),
  discardDraft: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

function question(index, overrides = {}) {
  return {
    id: `q-${String(index).padStart(4, '0')}`,
    stem: `Question ${index}`,
    type: index === 1 ? 'FILL' : 'SINGLE',
    options: [],
    answer: 'A',
    difficulty: 2,
    tags: ['alpha'],
    chapter_id: 'c1',
    version_number: 1,
    archived: false,
    locked_by_active_exam: false,
    ...overrides,
  }
}

function mountView(role = 'ADMIN', options = {}) {
  listBanks.mockResolvedValue(options.banks || [{ id: 'b2', name: 'Another Bank', role: 'ADMIN' }])
  if (options.rejectBank) {
    getBank.mockRejectedValue(new Error('bank unavailable'))
  } else {
    getBank.mockResolvedValue({
      id: 'b1', name: 'Bank One', category: 'Alpha', description: 'desc', role,
      question_count: 45, archived_question_count: 0,
    })
  }
  if (options.rejectQuestions) {
    listBankQuestionsContent.mockRejectedValue(new Error('questions unavailable'))
  } else {
    listBankQuestionsContent.mockResolvedValue(
      options.questions || Array.from({ length: 45 }, (_, i) => question(i + 1))
    )
  }
  listChapters.mockResolvedValue([
    { id: 'c1', name: 'Root', parent_id: null, sort_order: 0 },
    { id: 'c2', name: 'Child', parent_id: 'c1', sort_order: 0 },
    { id: 'c3', name: 'Second root', parent_id: null, sort_order: 1 },
  ])
  listBankMembers.mockResolvedValue([
    { user_id: 'u1', username: 'owner', role: 'ADMIN' },
    { user_id: 'u2', username: 'editor', role: 'EDITOR' },
  ])
  listTags.mockResolvedValue(options.tags || [{ id: 't1', name: 'alpha', question_count: 45 }])
  listBankImports.mockResolvedValue([
    {
      id: 'job1', filename: 'bank.txt', format: 'text', status: 'IMPORTED',
      imported_count: 3, reason: null, created_at: '2026-11-12T10:00:00Z',
      completed_at: '2026-11-12T10:00:05Z',
    },
  ])
  listBankAudit.mockResolvedValue([
    { id: 'a1', action: 'BANK_UPDATED', details: { fields: { name: 'Bank One' } }, created_at: '2026-11-12T10:00:00Z' },
  ])
  listDrafts.mockResolvedValue([])
  return mount(BankManageView, {
    props: { token: 't1', user: { id: 'u1', username: 'owner' } },
    attachTo: document.body,
    global: { stubs: { teleport: true } },
  })
}

async function openTab(wrapper, index) {
  await wrapper.findAll('.manage-tabs .tab')[index].trigger('click')
  await flush()
}

describe('BankManageView management surfaces', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params.bankId = 'b1'
    routeState.query = {}
    document.body.innerHTML = ''
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('paginates the question table and keeps FILL questions visible in filters', async () => {
    const wrapper = mountView()
    await flush()

    expect(wrapper.findAll('.mtable-row').length).toBe(25)
    expect(wrapper.find('.mtable-foot').text()).toContain('1 / 2')

    await wrapper.find('.mtable-foot .list-side .btn:last-child').trigger('click')
    await flush()
    expect(wrapper.findAll('.mtable-row').length).toBe(20)

    const typeSelect = wrapper.find('.manage-toolbar select')
    expect(typeSelect.text()).toContain('Fill in')
    wrapper.unmount()
  })

  it('changes page size, resets to page one and persists the choice', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('.mtable-foot .list-side .btn:last-child').trigger('click')
    await flush()
    expect(wrapper.findAll('.mtable-row').length).toBe(20)

    const pageSize = wrapper.find('[data-testid="page-size"]')
    expect(pageSize.exists()).toBe(true)
    expect(pageSize.findAll('option').map(option => option.element.value)).toEqual(['25', '50', '75', '100'])

    await pageSize.setValue('50')
    await flush()
    expect(wrapper.findAll('.mtable-row').length).toBe(45)
    expect(wrapper.find('.mtable-foot').text()).toContain('1 / 1')
    expect(localStorage.getItem('easyexam.bankManage.pageSize')).toBe('50')
    wrapper.unmount()

    const remount = mountView()
    await flush()
    expect(remount.find('[data-testid="page-size"]').element.value).toBe('50')
    expect(remount.findAll('.mtable-row').length).toBe(45)
    remount.unmount()
  })

  it('keeps a single bank header without a duplicate breadcrumb or role badge', async () => {
    routeState.query = { tab: 'members' }
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('.page-eyebrow').exists()).toBe(false)
    expect(wrapper.find('[data-testid="crumb-bank"]').exists()).toBe(false)
    expect(wrapper.find('.page-title').text()).toBe('Bank One')
    expect(wrapper.find('.page-sub').text()).toContain('Alpha')
    expect(wrapper.find('.page-sub').text()).not.toContain('Owner')
    expect(wrapper.find('.page-sub').text()).not.toContain('chapters')
    expect(wrapper.find('.page-actions').text()).not.toContain('Open')

    await openTab(wrapper, 1)
    expect(replace).toHaveBeenLastCalledWith({ query: { tab: 'structure' } })
    wrapper.unmount()
  })

  it('hides the import entry for a MEMBER and keeps the table read-only', async () => {
    const wrapper = mountView('MEMBER')
    await flush()

    expect(wrapper.find('[data-testid="manage-import"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="select-all"]').exists()).toBe(false)
    expect(wrapper.find('.manage-toolbar .search-box input').exists()).toBe(true)
    wrapper.unmount()
  })

  it('saves bank settings and shows audit and import history', async () => {
    updateBank.mockResolvedValue({ id: 'b1', name: 'Renamed Bank', category: 'Beta', description: 'new' })
    const wrapper = mountView()
    await flush()

    await openTab(wrapper, 5)

    const inputs = wrapper.findAll('.settings-form .input')
    expect(inputs[0].element.value).toBe('Bank One')
    await inputs[0].setValue('Renamed Bank')
    await inputs[1].setValue('Beta')
    await wrapper.find('.settings-form button[type="submit"]').trigger('click')
    await flush()

    expect(updateBank).toHaveBeenCalledWith('t1', 'b1', {
      name: 'Renamed Bank', category: 'Beta', description: 'desc',
    })
    const auditRow = wrapper.find('.audit-row')
    expect(auditRow.attributes('data-action')).toBe('BANK_UPDATED')
    expect(auditRow.text()).toContain('Bank updated')
    expect(auditRow.text()).not.toContain('BANK_UPDATED')
    expect(auditRow.text()).toContain('name')
    expect(auditRow.text()).not.toContain('{')
    expect(auditRow.find('.mono.small.dim').text()).toContain('2026')
    expect(auditRow.find('.mono.small.dim').text()).not.toContain('2026-11-12T')

    await openTab(wrapper, 3)
    expect(wrapper.find('.import-table').text()).toContain('bank.txt')
    const statusTag = wrapper.find('.import-table [data-status="IMPORTED"]')
    expect(statusTag.exists()).toBe(true)
    expect(statusTag.text()).toBe('Imported')
    // Timestamps go through the shared formatter, not raw API ISO strings.
    expect(wrapper.find('.import-row td:last-child').text()).toContain('2026')
    expect(wrapper.find('.import-row td:last-child').text()).not.toContain('2026-11-12T')
    wrapper.unmount()
  })

  it('clears stale bulk selections when filters, sort or a single-row archive hide rows', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('.mtable-row .row-select').setValue(true)
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    expect(wrapper.find('.batch-bar').text()).toContain('1 selected')

    await wrapper.find('.manage-toolbar .search-box input').setValue('Question 45')
    await flush()
    expect(wrapper.find('.mtable-row').exists()).toBe(true)
    expect(wrapper.find('.batch-bar').exists()).toBe(false)

    await wrapper.find('.manage-toolbar .search-box input').setValue('')
    await flush()
    await wrapper.find('.mtable-row .row-select').setValue(true)
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    await wrapper.find('[data-testid="question-sort"]').setValue('difficulty')
    await flush()
    expect(wrapper.find('.batch-bar').exists()).toBe(false)

    // Archiving the row while it disappears from the filtered list must prune
    // its id from the selection instead of leaving a ghost batch selection.
    const rowSelect = wrapper.find('.mtable-row .row-select')
    const hiddenId = rowSelect.attributes('data-question-id')
    await rowSelect.setValue(true)
    expect(wrapper.find('.batch-bar').text()).toContain('1 selected')
    listBankQuestionsContent.mockResolvedValue(
      Array.from({ length: 45 }, (_, i) => question(i + 1)).filter(q => q.id !== hiddenId)
    )
    await wrapper.find('.mtable-row [data-testid="row-archive"]').trigger('click')
    await flush()
    expect(wrapper.find('.batch-bar').exists()).toBe(false)
    wrapper.unmount()
  })

  it('requires an explicit chapter for batch apply and offers a separate clear action', async () => {
    batchBankQuestions.mockResolvedValue({ updated: 1 })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mountView()
    await flush()

    await wrapper.find('.mtable-row .row-select').setValue(true)
    const select = wrapper.find('[data-testid="batch-chapter"]')
    const placeholder = select.find('option')
    expect(placeholder.element.disabled).toBe(true)
    expect(placeholder.text()).toBe('Choose a chapter')
    expect(select.element.value).toBe('')

    const apply = wrapper.find('[data-testid="batch-apply-chapter"]')
    expect(apply.attributes('disabled')).toBeDefined()

    await select.setValue('c1')
    expect(apply.attributes('disabled')).toBeUndefined()

    await wrapper.find('[data-testid="batch-clear-chapter"]').trigger('click')
    await flush()

    expect(confirmSpy).toHaveBeenCalledWith('Clear the chapter for 1 selected questions?')
    expect(batchBankQuestions).toHaveBeenCalledWith('t1', 'b1', {
      question_ids: ['q-0001'],
      operation: 'chapter',
      chapter_id: null,
    })
    wrapper.unmount()
  })

  it('puts an explicit select-all in the toolbar with filtered/selected scope', async () => {
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('.mtable th.select-cell input').exists()).toBe(false)
    const checkbox = wrapper.find('[data-testid="select-all"]')
    expect(checkbox.element.closest('.manage-toolbar')).toBeTruthy()
    const label = checkbox.element.closest('label')
    expect(label.textContent).toContain('Select all filtered')
    expect(label.textContent).toContain('45 filtered, 0 selected')

    await checkbox.setValue(true)
    await flush()
    expect(label.textContent).toContain('45 filtered, 45 selected')
    expect(wrapper.findAll('.mtable-row').length).toBe(25)
    expect(wrapper.find('.batch-bar').text()).toContain('45 selected')
    wrapper.unmount()
  })

  it('guards the create dialog close path when the form has content', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="manage-create"]').trigger('click')
    await flush()
    expect(wrapper.find('.manage-create').exists()).toBe(true)
    expect(document.activeElement?.id).toBe('create-stem')

    await wrapper.find('#create-stem').setValue('Draft stem')
    await wrapper.find('.manage-create .app-dialog-close').trigger('click')
    await flush()
    expect(wrapper.find('.create-discard-dialog').exists()).toBe(true)

    await wrapper.find('.create-discard-keep').trigger('click')
    expect(wrapper.find('.create-discard-dialog').exists()).toBe(false)
    expect(wrapper.find('.manage-create').exists()).toBe(true)

    await wrapper.find('.manage-create .app-dialog-foot .btn-quiet').trigger('click')
    await flush()
    expect(wrapper.find('.create-discard-dialog').exists()).toBe(true)
    await wrapper.find('.create-discard-accept').trigger('click')
    await flush()
    expect(wrapper.find('.manage-create').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a dedicated load error instead of the empty bank state', async () => {
    const wrapper = mountView('ADMIN', { rejectBank: true })
    await flush()

    const errorPanel = wrapper.find('[data-testid="load-error"]')
    expect(errorPanel.exists()).toBe(true)
    expect(errorPanel.text()).toContain('Could not load')
    expect(wrapper.text()).not.toContain('No questions in this bank yet')

    getBank.mockResolvedValue({
      id: 'b1', name: 'Bank One', category: 'Alpha', description: 'desc', role: 'ADMIN',
    })
    listBankQuestionsContent.mockResolvedValue([question(1)])
    await wrapper.find('[data-testid="load-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="load-error"]').exists()).toBe(false)
    expect(wrapper.findAll('.mtable-row').length).toBe(1)
    wrapper.unmount()
  })

  it('reloads only the question list when archived visibility changes', async () => {
    const wrapper = mountView()
    await flush()
    const chapterCalls = listChapters.mock.calls.length
    const bankCalls = getBank.mock.calls.length

    listBankQuestionsContent.mockResolvedValue([question(1, { archived: true })])
    await wrapper.find('[data-testid="show-archived"]').setValue(true)
    await flush()

    expect(listBankQuestionsContent).toHaveBeenCalledTimes(2)
    expect(listBankQuestionsContent).toHaveBeenLastCalledWith('t1', 'b1', { includeArchived: true })
    expect(listChapters).toHaveBeenCalledTimes(chapterCalls)
    expect(getBank).toHaveBeenCalledTimes(bankCalls)
    expect(replace).toHaveBeenLastCalledWith({ query: { tab: 'questions', archived: '1' } })
    expect(wrapper.find('.archived-toggle').text()).toContain('Show archived')
    expect(wrapper.find('.manage-archived-note').exists()).toBe(true)
    wrapper.unmount()
  })

  it('limits archived batch actions to restore and selection', async () => {
    const wrapper = mountView()
    await flush()

    listBankQuestionsContent.mockResolvedValue([question(1, { archived: true })])
    await wrapper.find('[data-testid="show-archived"]').setValue(true)
    await flush()
    await wrapper.find('.mtable-row .row-select').setValue(true)

    const bar = wrapper.find('.batch-bar')
    expect(bar.exists()).toBe(true)
    expect(bar.find('[data-testid="batch-restore"]').exists()).toBe(true)
    expect(bar.find('[data-testid="batch-chapter"]').exists()).toBe(false)
    expect(bar.find('[data-testid="batch-clear-chapter"]').exists()).toBe(false)
    expect(bar.find('[data-testid="batch-add-tags"]').exists()).toBe(false)
    expect(bar.find('[data-testid="batch-target"]').exists()).toBe(false)
    expect(bar.find('[data-testid="batch-archive"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('gates owner-only panels and skips the owner-only audit request', async () => {
    const wrapper = mountView('MEMBER')
    await flush()

    expect(listBankAudit).not.toHaveBeenCalled()

    await openTab(wrapper, 2)
    expect(wrapper.find('[data-testid="owner-members-note"]').exists()).toBe(true)
    expect(wrapper.find('.member-add').exists()).toBe(false)

    await openTab(wrapper, 5)
    expect(wrapper.find('[data-testid="owner-settings-note"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="audit-owner-note"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('routes the header export entry to the single settings export panel', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="manage-export"]').trigger('click')
    await flush()

    expect(downloadBankExport).not.toHaveBeenCalled()
    const panel = wrapper.find('[data-testid="export-panel"]')
    expect(panel.exists()).toBe(true)
    expect(panel.attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(panel.element)
    expect(wrapper.findAll('.manage-tabs .tab')[5].attributes('aria-selected')).toBe('true')
    expect(panel.text()).toContain('JSON')
    expect(panel.find('[data-testid="export-include-archived"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('opens AI drafts locally for this bank instead of the global dialog', async () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = mountView()
    await flush()

    await openTab(wrapper, 4)
    await wrapper.find('[data-testid="open-local-drafts"]').trigger('click')
    await flush()

    expect(listDrafts).toHaveBeenCalledWith('t1', 'DRAFT', 'b1')
    expect(wrapper.find('.drafts-dialog').exists()).toBe(true)
    const dialogEvents = dispatchSpy.mock.calls.filter(([event]) => event?.type === 'easyexam:open-dialog')
    expect(dialogEvents).toHaveLength(0)
    wrapper.unmount()
  })

  it('confirms tag merges and edits one tag row at a time', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    updateTag.mockResolvedValue({ id: 't1', name: 'beta', question_count: 2 })
    const wrapper = mountView('ADMIN', {
      tags: [
        { id: 't1', name: 'alpha', question_count: 2 },
        { id: 't2', name: 'beta', question_count: 3 },
      ],
    })
    await flush()
    await openTab(wrapper, 1)

    let firstRow = wrapper.findAll('.tag-row')[0]
    expect(firstRow.find('input').exists()).toBe(false)
    await firstRow.find('.btn-quiet').trigger('click')
    await firstRow.find('.tag-row-input').setValue('beta')
    await firstRow.find('[data-testid="tag-save"]').trigger('click')
    await flush()

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('beta'))
    expect(updateTag).not.toHaveBeenCalled()

    // Esc cancels the inline edit without touching the server.
    await wrapper.findAll('.tag-row')[0].find('.tag-row-input').trigger('keydown', { key: 'Escape' })
    expect(wrapper.findAll('.tag-row')[0].find('.tag-row-input').exists()).toBe(false)
    expect(updateTag).not.toHaveBeenCalled()

    confirmSpy.mockReturnValue(true)
    firstRow = wrapper.findAll('.tag-row')[0]
    await firstRow.find('.btn-quiet').trigger('click')
    await firstRow.find('.tag-row-input').setValue('beta')
    await firstRow.find('.tag-row-input').trigger('keydown', { key: 'Enter' })
    await flush()

    expect(updateTag).toHaveBeenCalledWith('t1', 'b1', 't1', 'beta')
    const rows = wrapper.findAll('.tag-row')
    expect(rows.length).toBe(1)
    expect(rows[0].text()).toContain('beta')
    expect(rows[0].text()).toContain('5')
    wrapper.unmount()
  })

  it('shows an inline child chapter form under the clicked chapter', async () => {
    createChapter.mockResolvedValue({ id: 'c4', name: 'New child', parent_id: 'c1' })
    const wrapper = mountView()
    await flush()
    await openTab(wrapper, 1)

    const rootRow = wrapper.findAll('.chapter-row')[0]
    await rootRow.findAll('.list-side .btn')[0].trigger('click')
    await flush()

    const form = wrapper.find('.child-chapter-form')
    expect(form.exists()).toBe(true)
    expect(form.find('input').attributes('placeholder')).toBe('Child chapter name')

    await form.find('input').setValue('New child')
    await form.trigger('submit')
    await flush()

    expect(createChapter).toHaveBeenCalledWith('t1', 'b1', { name: 'New child', parent_id: 'c1' })
    expect(wrapper.find('.child-chapter-form').exists()).toBe(false)
    wrapper.unmount()
  })

  it('changes a member role and reorders sibling chapters', async () => {
    updateBankMemberRole.mockResolvedValue({ user_id: 'u2', role: 'MEMBER' })
    reorderChapters.mockResolvedValue([
      { id: 'c2', name: 'Child', parent_id: 'c1', sort_order: 0 },
      { id: 'c1', name: 'Root', parent_id: null, sort_order: 0 },
    ])
    const wrapper = mountView()
    await flush()

    await openTab(wrapper, 2)
    const roleSelect = wrapper.find('.member-actions select')
    await roleSelect.setValue('MEMBER')
    await flush()
    expect(updateBankMemberRole).toHaveBeenCalledWith('t1', 'b1', 'u2', 'MEMBER')

    await openTab(wrapper, 1)
    expect(wrapper.findAll('.chapter-row').length).toBe(3)
    const rootRow = wrapper.findAll('.chapter-row')[0]
    await rootRow.findAll('.list-side .btn')[2].trigger('click')
    await flush()
    expect(reorderChapters).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows a chapter load error with retry instead of an empty chapter state', async () => {
    listChapters.mockRejectedValueOnce(new Error('chapters unavailable'))
    const wrapper = mountView()
    await flush()
    await openTab(wrapper, 1)

    const panel = wrapper.find('[data-testid="chapters-error"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('chapters unavailable')
    expect(wrapper.text()).not.toContain('No chapters')
    expect(wrapper.findAll('.chapter-row').length).toBe(0)

    await wrapper.find('[data-testid="chapters-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="chapters-error"]').exists()).toBe(false)
    expect(wrapper.findAll('.chapter-row').length).toBe(3)
    wrapper.unmount()
  })

  it('shows a member load error with retry instead of the empty member state', async () => {
    listBankMembers.mockRejectedValueOnce(new Error('members unavailable'))
    const wrapper = mountView()
    await flush()
    await openTab(wrapper, 2)

    const panel = wrapper.find('[data-testid="members-error"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('members unavailable')
    expect(wrapper.findAll('.member-row').length).toBe(0)

    await wrapper.find('[data-testid="members-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="members-error"]').exists()).toBe(false)
    expect(wrapper.findAll('.member-row').length).toBe(2)
    wrapper.unmount()
  })

  it('shows a tag load error with retry instead of an empty tag list', async () => {
    listTags.mockRejectedValueOnce(new Error('tags unavailable'))
    const wrapper = mountView()
    await flush()
    await openTab(wrapper, 1)

    const panel = wrapper.find('[data-testid="tags-error"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('tags unavailable')
    expect(wrapper.find('.tag-list').text()).not.toContain('No tags yet')

    await wrapper.find('[data-testid="tags-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="tags-error"]').exists()).toBe(false)
    expect(wrapper.findAll('.tag-row').length).toBe(1)
    wrapper.unmount()
  })

  it('shows an import load error with retry instead of the empty import state', async () => {
    listBankImports.mockRejectedValueOnce(new Error('imports unavailable'))
    const wrapper = mountView()
    await flush()
    await openTab(wrapper, 3)

    const panel = wrapper.find('[data-testid="imports-error"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('imports unavailable')
    expect(wrapper.text()).not.toContain('No imports yet')

    await wrapper.find('[data-testid="imports-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="imports-error"]').exists()).toBe(false)
    expect(wrapper.find('.import-table').text()).toContain('bank.txt')
    wrapper.unmount()
  })

  it('shows a bank-list load error with retry in the batch target slot', async () => {
    listBanks.mockRejectedValueOnce(new Error('banks unavailable'))
    const wrapper = mountView()
    await flush()

    await wrapper.find('.mtable-row .row-select').setValue(true)
    const panel = wrapper.find('[data-testid="batch-targets-error"]')
    expect(panel.exists()).toBe(true)
    expect(wrapper.find('.batch-bar').text()).not.toContain('No other editable banks')

    await wrapper.find('[data-testid="batch-targets-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="batch-targets-error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="batch-target"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('moves tab focus and selection with arrow, Home and End keys', async () => {
    const wrapper = mountView()
    await flush()

    let tabs = wrapper.findAll('.manage-tabs .tab')
    expect(tabs[0].attributes('tabindex')).toBe('0')
    expect(tabs[1].attributes('tabindex')).toBe('-1')

    const tablist = wrapper.find('.manage-tabs')
    await tablist.trigger('keydown', { key: 'ArrowRight' })
    await flush()
    tabs = wrapper.findAll('.manage-tabs .tab')
    expect(tabs[1].attributes('aria-selected')).toBe('true')
    expect(tabs[1].attributes('tabindex')).toBe('0')
    expect(tabs[0].attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(tabs[1].element)

    await tablist.trigger('keydown', { key: 'End' })
    await flush()
    tabs = wrapper.findAll('.manage-tabs .tab')
    expect(tabs[5].attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(tabs[5].element)

    await tablist.trigger('keydown', { key: 'Home' })
    await flush()
    expect(wrapper.findAll('.manage-tabs .tab')[0].attributes('aria-selected')).toBe('true')

    await tablist.trigger('keydown', { key: 'ArrowLeft' })
    await flush()
    tabs = wrapper.findAll('.manage-tabs .tab')
    expect(tabs[5].attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(tabs[5].element)
    wrapper.unmount()
  })

  it('reverts the archived toggle and offers a retry when the reload fails', async () => {
    const wrapper = mountView()
    await flush()
    const initialRows = wrapper.findAll('.mtable-row').length

    listBankQuestionsContent.mockRejectedValueOnce(new Error('questions unavailable'))
    await wrapper.find('[data-testid="show-archived"]').setValue(true)
    await flush()

    expect(wrapper.find('[data-testid="show-archived"]').element.checked).toBe(false)
    const notice = wrapper.find('.notice.bad.manage-notice')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('questions unavailable')
    expect(notice.find('[data-testid="error-retry"]').exists()).toBe(true)
    expect(wrapper.findAll('.mtable-row').length).toBe(initialRows)

    listBankQuestionsContent.mockResolvedValue([question(1, { archived: true })])
    await wrapper.find('[data-testid="error-retry"]').trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="show-archived"]').element.checked).toBe(true)
    expect(wrapper.find('.notice.bad.manage-notice').exists()).toBe(false)
    expect(wrapper.findAll('.mtable-row').length).toBe(1)
    wrapper.unmount()
  })

  it('keeps the read-only explanation visible while archived rows are shown', async () => {
    routeState.query = { archived: '1' }
    const wrapper = mountView('MEMBER')
    await flush()

    const banner = wrapper.find('.notice.info.manage-notice')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('No edit permission')
    expect(wrapper.find('[data-testid="show-archived"]').element.checked).toBe(true)
    wrapper.unmount()
  })

  it('resets bank state and discards stale responses when the route bank changes', async () => {
    const wrapper = mountView()
    await flush()
    expect(getBank).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.page-title').text()).toBe('Bank One')

    // Leave a filter, page and selection behind before switching banks.
    await wrapper.find('.manage-toolbar .search-box input').setValue('Question')
    await wrapper.find('.mtable-foot .list-side .btn:last-child').trigger('click')
    await flush()
    await wrapper.find('.mtable-row .row-select').setValue(true)
    expect(wrapper.find('.batch-bar').exists()).toBe(true)

    const deferred = {}
    listBankQuestionsContent.mockImplementation((_token, id) => new Promise(resolve => {
      deferred[id] = resolve
    }))
    getBank.mockImplementation((_token, id) => Promise.resolve({
      id, name: id === 'b3' ? 'Bank Three' : 'Bank Two', category: '', description: '', role: 'ADMIN',
    }))

    routeState.params.bankId = 'b2'
    await flush()
    routeState.params.bankId = 'b3'
    await flush()

    deferred.b3([question(9, { stem: 'Question from B3' })])
    await flush()
    deferred.b2([question(8, { stem: 'Question from B2' })])
    await flush()

    expect(wrapper.find('.page-title').text()).toBe('Bank Three')
    expect(wrapper.find('.manage-toolbar .search-box input').element.value).toBe('')
    expect(wrapper.find('.batch-bar').exists()).toBe(false)
    expect(wrapper.text()).toContain('Question from B3')
    expect(wrapper.text()).not.toContain('Question from B2')
    expect(listBankQuestionsContent).toHaveBeenLastCalledWith('t1', 'b3', { includeArchived: false })
    expect(getBank).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('joins multi-answer picks with commas in the create form', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="manage-create"]').trigger('click')
    await flush()
    await wrapper.find('.manage-create .create-grid select').setValue('MULTI')
    await wrapper.find('#create-stem').setValue('Multi stem')

    const optionButtons = wrapper.findAll('.manage-create .opt-key-btn')
    await optionButtons[0].trigger('click')
    await optionButtons[1].trigger('click')
    await flush()

    const answerInput = wrapper.findAll('.manage-create .create-grid')[1].find('input')
    expect(answerInput.element.value).toBe('A,B')
    const submit = wrapper.find('.manage-create .app-dialog-foot .btn-primary')
    expect(submit.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('restores the workspace filters, sort and page from the URL', async () => {
    routeState.query = { q: 'Question 4', type: 'SINGLE', difficulty: '2', tag: 'alpha', chapter: 'c1', sort: 'difficulty' }
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('.manage-toolbar .search-box input').element.value).toBe('Question 4')
    const values = wrapper.findAll('.manage-toolbar select').map(select => select.element.value)
    expect(values).toContain('SINGLE')
    expect(values).toContain('2')
    expect(values).toContain('alpha')
    expect(values).toContain('c1')
    expect(wrapper.find('[data-testid="question-sort"]').element.value).toBe('difficulty')
    expect(wrapper.find('.mtable-row .stem-text').text()).toBe('Question 4')
    wrapper.unmount()
  })

  it('restores the workspace page from the URL', async () => {
    routeState.query = { page: '2' }
    const wrapper = mountView()
    await flush()
    expect(wrapper.findAll('.mtable-row').length).toBe(20)
    expect(wrapper.find('.mtable-row .stem-text').text()).toBe('Question 26')
    wrapper.unmount()
  })

  it('writes workspace filters and sort to the URL and drops defaults', async () => {
    const wrapper = mountView()
    await flush()
    expect(replace).not.toHaveBeenCalled()

    await wrapper.find('.manage-toolbar .search-box input').setValue('Question 4')
    await flush()
    expect(replace).toHaveBeenCalled()
    expect(replace.mock.calls.at(-1)[0].query.q).toBe('Question 4')
    expect('page' in replace.mock.calls.at(-1)[0].query).toBe(false)

    await wrapper.find('[data-testid="question-sort"]').setValue('id')
    await flush()
    expect(replace.mock.calls.at(-1)[0].query.sort).toBe('id')

    await wrapper.find('.manage-toolbar .search-box input').setValue('')
    await flush()
    expect('q' in replace.mock.calls.at(-1)[0].query).toBe(false)
    wrapper.unmount()
  })

  it('opens a bank switch on the filtered view the address asked for', async () => {
    routeState.query = { q: 'Question 3' }
    const wrapper = mountView()
    await flush()
    expect(wrapper.find('.manage-toolbar .search-box input').element.value).toBe('Question 3')

    routeState.params.bankId = 'b2'
    await flush()
    expect(wrapper.find('.manage-toolbar .search-box input').element.value).toBe('Question 3')
    wrapper.unmount()
  })

  it('restores page and filters together when the address changes', async () => {
    const wrapper = mountView()
    await flush()

    routeState.query = { tag: 'alpha', page: '2' }
    await flush()

    expect(wrapper.findAll('.mtable-row').length).toBe(20)
    expect(wrapper.find('.mtable-row .stem-text').text()).toBe('Question 26')
    wrapper.unmount()
  })
})
