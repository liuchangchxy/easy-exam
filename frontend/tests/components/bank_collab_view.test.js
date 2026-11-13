// Collaboration surfaces: the member picker must search registered users and
// work from the keyboard, while role management stays owner-only and every
// membership change reaches the app shell.
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import BankManageView from '../../src/views/BankManageView.vue'
import {
  getBank,
  listBanks,
  listBankQuestionsContent,
  listChapters,
  listBankMembers,
  addBankMember,
  removeBankMember,
  updateBankMemberRole,
  leaveBank,
  transferBankOwnership,
  listTags,
  listBankImports,
  listBankAudit,
} from '../../src/api/banks'
import { searchUsers } from '../../src/api/users'
import { BANKS_CHANGED_EVENT } from '../../src/utils/shellEvents.js'

const push = vi.fn()
const replace = vi.fn()
const routeState = reactive({ params: { bankId: 'b1' }, query: { tab: 'members' } })

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
  searchUsers: vi.fn(),
}))

vi.mock('../../src/api/users', () => ({
  searchUsers: vi.fn(),
}))

vi.mock('../../src/api/questions', () => ({
  updateQuestion: vi.fn(),
  getQuestion: vi.fn(),
  getQuestionConflict: vi.fn(),
  listQuestionVersions: vi.fn(),
  deleteQuestionVersion: vi.fn(),
}))

vi.mock('../../src/api/ai', () => ({
  listDrafts: vi.fn().mockResolvedValue([]),
  acceptDraft: vi.fn(),
  discardDraft: vi.fn(),
}))

vi.mock('../../src/api/practice', () => ({
  listActiveSessions: vi.fn(),
  startSession: vi.fn(),
  abandonSession: vi.fn(),
  abandonAllSessions: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const baseMembers = () => [
  { user_id: 'u1', username: 'owner', role: 'ADMIN', joined_at: '2026-11-01T10:00:00Z', is_self: true },
  { user_id: 'u2', username: 'editor', role: 'EDITOR', joined_at: '2026-11-02T10:00:00Z', is_self: false },
  { user_id: 'u3', username: 'reader', role: 'MEMBER', joined_at: '2026-11-03T10:00:00Z', is_self: false },
]

function mountView(role = 'ADMIN', options = {}) {
  listBanks.mockResolvedValue([])
  getBank.mockResolvedValue({
    id: 'b1', name: 'Bank One', category: 'Alpha', description: 'desc', role,
  })
  listBankQuestionsContent.mockResolvedValue([])
  listChapters.mockResolvedValue([])
  listBankMembers.mockResolvedValue(options.members || baseMembers())
  listTags.mockResolvedValue([])
  listBankImports.mockResolvedValue([])
  listBankAudit.mockResolvedValue([])
  return mount(BankManageView, {
    props: { token: 't1', user: { id: 'u1', username: 'owner' } },
    attachTo: document.body,
    global: { stubs: { teleport: true } },
  })
}

function trackBanksChanged() {
  const listener = vi.fn()
  window.addEventListener(BANKS_CHANGED_EVENT, listener)
  return listener
}

describe('BankManageView collaboration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    localStorage.clear()
    routeState.params.bankId = 'b1'
    routeState.query = { tab: 'members' }
    document.body.innerHTML = ''
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('debounces the user prefix search by 250ms', async () => {
    const wrapper = mountView('ADMIN')
    await flush()
    vi.useFakeTimers()
    searchUsers.mockResolvedValue([{ id: 'u9', username: 'alice' }])

    const input = wrapper.find('[data-testid="member-search-input"]')
    await input.setValue('al')
    expect(searchUsers).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(249)
    expect(searchUsers).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(searchUsers).toHaveBeenCalledTimes(1)
    expect(searchUsers).toHaveBeenCalledWith('t1', 'al')
    expect(wrapper.find('#member-search-listbox').exists()).toBe(true)
    expect(wrapper.find('[role="option"]').text()).toBe('alice')
    wrapper.unmount()
  })

  it('moves through candidates with the keyboard and picks one for adding', async () => {
    const wrapper = mountView('ADMIN')
    await flush()
    vi.useFakeTimers()
    searchUsers.mockResolvedValue([
      { id: 'u8', username: 'eddie' },
      { id: 'u9', username: 'edna' },
    ])
    addBankMember.mockResolvedValue({ user_id: 'u9', role: 'MEMBER' })

    const input = wrapper.find('[data-testid="member-search-input"]')
    await input.setValue('ed')
    await vi.advanceTimersByTimeAsync(250)

    expect(input.attributes('aria-expanded')).toBe('true')
    expect(input.attributes('aria-activedescendant')).toBe('member-option-u8')

    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe('member-option-u9')
    expect(wrapper.findAll('[role="option"]')[1].attributes('aria-selected')).toBe('true')

    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe('member-option-u8')

    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'Enter' })

    expect(wrapper.find('#member-search-listbox').exists()).toBe(false)
    expect(wrapper.find('[data-testid="member-selected"]').text()).toContain('edna')

    vi.useRealTimers()
    await wrapper.find('[data-testid="member-add-role"]').setValue('MEMBER')
    await wrapper.find('.member-form').trigger('submit')
    await flush()

    expect(addBankMember).toHaveBeenCalledWith('t1', 'b1', 'edna', 'MEMBER')
    expect(listBankMembers).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('shows an inline no-match message instead of an empty dropdown', async () => {
    const wrapper = mountView('ADMIN')
    await flush()
    vi.useFakeTimers()
    searchUsers.mockResolvedValue([])

    await wrapper.find('[data-testid="member-search-input"]').setValue('zzz')
    await vi.advanceTimersByTimeAsync(250)

    expect(wrapper.find('[data-testid="member-search-empty"]').text()).toBe('No matching users')
    expect(wrapper.find('#member-search-listbox').exists()).toBe(false)
    expect(wrapper.find('[data-testid="member-search-input"]').attributes('aria-expanded')).toBe('true')
    wrapper.unmount()
  })

  it('shows search failures inline and never as an empty dropdown', async () => {
    const wrapper = mountView('ADMIN')
    await flush()
    vi.useFakeTimers()
    searchUsers.mockRejectedValue({ detail: 'search down' })

    await wrapper.find('[data-testid="member-search-input"]').setValue('al')
    await vi.advanceTimersByTimeAsync(250)

    const error = wrapper.find('[data-testid="member-search-error"]')
    expect(error.text()).toContain('search down')
    expect(wrapper.find('#member-search-listbox').exists()).toBe(false)
    wrapper.unmount()
  })

  it('closes the candidate list on Escape without clearing the query', async () => {
    const wrapper = mountView('ADMIN')
    await flush()
    vi.useFakeTimers()
    searchUsers.mockResolvedValue([{ id: 'u9', username: 'alice' }])

    const input = wrapper.find('[data-testid="member-search-input"]')
    await input.setValue('al')
    await vi.advanceTimersByTimeAsync(250)
    expect(wrapper.find('#member-search-listbox').exists()).toBe(true)

    await input.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('#member-search-listbox').exists()).toBe(false)
    expect(input.element.value).toBe('al')
    wrapper.unmount()
  })

  it('shows the member list in server order with joined time and the self marker', async () => {
    const wrapper = mountView('MEMBER')
    await flush()

    const rows = wrapper.findAll('.member-row')
    expect(rows.map(row => row.attributes('data-user-id'))).toEqual(['u1', 'u2', 'u3'])
    expect(rows[0].find('[data-testid="member-self-badge"]').exists()).toBe(true)
    expect(rows[1].find('[data-testid="member-self-badge"]').exists()).toBe(false)
    expect(rows[2].find('[data-testid="member-role"]').text()).toBe('Member')
    expect(rows[0].find('[data-testid="member-joined-at"]').text()).toContain('2026')
    expect(rows[0].find('[data-testid="member-joined-at"]').text()).not.toContain('2026-11-01T')
    wrapper.unmount()
  })

  it('gives the owner row controls and a member none, while members can leave', async () => {
    const ownerWrapper = mountView('ADMIN')
    await flush()
    expect(ownerWrapper.findAll('[data-testid="member-remove"]')).toHaveLength(2)
    expect(ownerWrapper.findAll('[data-testid="member-transfer"]')).toHaveLength(2)
    expect(ownerWrapper.find('.member-add').exists()).toBe(true)
    expect(ownerWrapper.find('[data-testid="member-leave"]').exists()).toBe(false)
    ownerWrapper.unmount()

    const memberWrapper = mountView('MEMBER')
    await flush()
    expect(memberWrapper.find('[data-testid="member-remove"]').exists()).toBe(false)
    expect(memberWrapper.find('[data-testid="member-transfer"]').exists()).toBe(false)
    expect(memberWrapper.findAll('.member-actions').length).toBe(0)
    expect(memberWrapper.find('.member-add').exists()).toBe(false)
    expect(memberWrapper.find('[data-testid="member-leave"]').exists()).toBe(true)
    expect(memberWrapper.find('.member-row [data-testid="member-role"]').exists()).toBe(true)
    memberWrapper.unmount()
  })

  it('removes a member only after a dialog that names the person', async () => {
    const banksChanged = trackBanksChanged()
    removeBankMember.mockResolvedValue(null)
    const wrapper = mountView('ADMIN')
    await flush()

    await wrapper.find('[data-testid="member-remove"]').trigger('click')
    await flush()

    const dialog = wrapper.find('.member-remove-dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('editor')
    expect(removeBankMember).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="member-remove-confirm"]').trigger('click')
    await flush()

    expect(removeBankMember).toHaveBeenCalledWith('t1', 'b1', 'u2')
    expect(listBankMembers).toHaveBeenCalledTimes(2)
    expect(banksChanged).toHaveBeenCalled()
    wrapper.unmount()
    window.removeEventListener(BANKS_CHANGED_EVENT, banksChanged)
  })

  it('changes a member role and tells the shell', async () => {
    const banksChanged = trackBanksChanged()
    updateBankMemberRole.mockResolvedValue({ user_id: 'u2', role: 'MEMBER' })
    const wrapper = mountView('ADMIN')
    await flush()

    await wrapper.find('[data-testid="member-role-select-u2"]').setValue('MEMBER')
    await flush()

    expect(updateBankMemberRole).toHaveBeenCalledWith('t1', 'b1', 'u2', 'MEMBER')
    expect(banksChanged).toHaveBeenCalled()
    wrapper.unmount()
    window.removeEventListener(BANKS_CHANGED_EVENT, banksChanged)
  })

  it('requires the bank name before ownership can be transferred', async () => {
    const banksChanged = trackBanksChanged()
    transferBankOwnership.mockResolvedValue({ ok: true })
    const wrapper = mountView('ADMIN')
    await flush()

    await wrapper.find('[data-testid="member-transfer"]').trigger('click')
    await flush()

    const confirm = wrapper.find('[data-testid="transfer-confirm"]')
    expect(confirm.exists()).toBe(true)
    expect(confirm.attributes('disabled')).toBeDefined()

    await wrapper.find('[data-testid="transfer-confirm-input"]').setValue('Wrong name')
    await flush()
    expect(confirm.attributes('disabled')).toBeDefined()
    expect(transferBankOwnership).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="transfer-confirm-input"]').setValue('Bank One')
    await flush()
    expect(wrapper.find('[data-testid="transfer-confirm-input"]').element.value).toBe('Bank One')
    expect(wrapper.find('[data-testid="transfer-confirm"]').attributes('disabled')).toBeUndefined()

    await wrapper.find('[data-testid="transfer-confirm"]').trigger('click')
    await flush()

    expect(transferBankOwnership).toHaveBeenCalledWith('t1', 'b1', 'editor')
    expect(banksChanged).toHaveBeenCalled()
    wrapper.unmount()
    window.removeEventListener(BANKS_CHANGED_EVENT, banksChanged)
  })

  it('lets a non-owner leave the bank after confirmation', async () => {
    const banksChanged = trackBanksChanged()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    leaveBank.mockResolvedValue(null)
    const wrapper = mountView('EDITOR')
    await flush()

    await wrapper.find('[data-testid="member-leave"]').trigger('click')
    await flush()

    expect(confirmSpy).toHaveBeenCalledWith('Leave bank “Bank One”?')
    expect(leaveBank).toHaveBeenCalledWith('t1', 'b1')
    expect(banksChanged).toHaveBeenCalled()
    expect(push).toHaveBeenCalledWith('/banks')
    wrapper.unmount()
    window.removeEventListener(BANKS_CHANGED_EVENT, banksChanged)
  })
})
