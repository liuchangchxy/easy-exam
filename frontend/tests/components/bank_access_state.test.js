// The bank workspace is the one page per bank, so it is also the one page that
// has to distinguish "you are not a member" from "this bank is gone" from
// "the request failed". A retry banner on a 403 teaches the user to retry a
// permission answer; that is the bug these tests keep out.
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BankManageView from '../../src/views/BankManageView.vue'
import { t } from '../../src/composables/useLocale.js'
import {
  getBank,
  listBanks,
  listBankQuestionsContent,
  listChapters,
  listBankMembers,
  listTags,
  listBankImports,
  listBankAudit,
} from '../../src/api/banks'
import { BANK_LIST_QUERY_KEY } from '../../src/utils/bankListQuery.js'

const { push, replace, routeState } = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  routeState: { params: { bankId: 'b1' }, query: {} },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push, replace }),
  useRoute: () => routeState,
}))

vi.mock('../../src/api/banks', () => ({
  getBank: vi.fn(),
  listBanks: vi.fn(),
  listBankQuestionsContent: vi.fn(),
  listChapters: vi.fn(),
  listBankMembers: vi.fn(),
  listTags: vi.fn(),
  listBankImports: vi.fn(),
  listBankAudit: vi.fn(),
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
vi.mock('../../src/api/ai', () => ({ listDrafts: vi.fn().mockResolvedValue([]), acceptDraft: vi.fn(), discardDraft: vi.fn() }))
vi.mock('../../src/api/practice', () => ({ startSession: vi.fn() }))

const flush = () => new Promise(resolve => setTimeout(resolve, 20))

function apiError(status) {
  const error = new Error(`HTTP ${status}`)
  error.status = status
  return error
}

async function mountView() {
  const wrapper = mount(BankManageView, {
    props: { token: 't1' },
    attachTo: document.body,
  })
  await flush()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  routeState.params.bankId = 'b1'
  routeState.query = {}
  listBanks.mockResolvedValue([])
  listBankQuestionsContent.mockResolvedValue([])
  listChapters.mockResolvedValue([])
  listBankMembers.mockResolvedValue([])
  listTags.mockResolvedValue([])
  listBankImports.mockResolvedValue([])
  listBankAudit.mockResolvedValue([])
  sessionStorage.removeItem(BANK_LIST_QUERY_KEY)
})

describe('bank workspace access states', () => {
  it('explains a 403 as "not a member" instead of a failed load with retry', async () => {
    getBank.mockRejectedValueOnce(apiError(403))
    const wrapper = await mountView()

    const denied = wrapper.find('[data-testid="access-denied"]')
    expect(denied.exists()).toBe(true)
    expect(denied.attributes('data-kind')).toBe('forbidden')
    expect(denied.text()).toContain(t('ep.access.forbidden_title'))
    expect(denied.text()).toContain(t('ep.common.back_to_banks'))

    // The bank UI never renders, and a permission answer is not retryable.
    expect(wrapper.find('.manage-page').exists()).toBe(false)
    expect(wrapper.find('[data-testid="load-error"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('explains a 404 as a missing bank and returns to the list with its stored filters', async () => {
    const stored = { q: 'algebra', view: 'recycle' }
    sessionStorage.setItem(BANK_LIST_QUERY_KEY, JSON.stringify(stored))
    getBank.mockRejectedValueOnce(apiError(404))
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="access-denied"]').attributes('data-kind')).toBe('missing')

    await wrapper.find('[data-testid="access-denied-back"]').trigger('click')
    expect(push).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith({ name: 'banks', query: stored })

    wrapper.unmount()
  })

  it('keeps the generic retry state for failures that are not about access', async () => {
    getBank.mockRejectedValueOnce(new Error('network down'))
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="access-denied"]').exists()).toBe(false)
    const errorState = wrapper.find('[data-testid="load-error"]')
    expect(errorState.exists()).toBe(true)
    expect(errorState.text()).toContain(t('ep.common.load_failed'))
    expect(errorState.text()).toContain('network down')

    wrapper.unmount()
  })
})
