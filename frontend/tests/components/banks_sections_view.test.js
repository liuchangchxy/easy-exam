// The active bank list is two sections — owned and shared — but search,
// category, sort and batch selection still act on one combined list.
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
  downloadBankExport,
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
}))

vi.mock('../../src/api/sync', () => ({
  triggerSyncEvent: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const bank = (overrides = {}) => ({
  id: 'b1', name: 'Bank One', category: 'Test', question_count: 3, role: 'ADMIN', ...overrides,
})

function mountView() {
  return mount(BanksView, { props: { token: 't1' } })
}

describe('BanksView owned and shared sections', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    sessionStorage.clear()
  })

  it('splits owned and shared banks into labelled sections with their own counts', async () => {
    listBanks.mockResolvedValue([
      bank({ id: 'o1', name: 'Owned One', role: 'ADMIN' }),
      bank({ id: 'o2', name: 'Owned Two', role: 'ADMIN' }),
      bank({ id: 's1', name: 'Shared One', role: 'EDITOR' }),
      bank({ id: 's2', name: 'Shared Two', role: 'MEMBER' }),
    ])
    const wrapper = mountView()
    await flush()

    const owned = wrapper.find('[data-testid="banks-section-owned"]')
    const shared = wrapper.find('[data-testid="banks-section-shared"]')
    expect(owned.exists()).toBe(true)
    expect(shared.exists()).toBe(true)
    expect(owned.find('.bank-section-title').text()).toBe(t('ep.banks.owned_section'))
    expect(shared.find('.bank-section-title').text()).toBe(t('ep.banks.shared_section'))
    expect(owned.find('.bank-section-count').text()).toBe('2')
    expect(shared.find('.bank-section-count').text()).toBe('2')
    expect(owned.findAll('.banks-row')).toHaveLength(2)
    expect(shared.findAll('.banks-row')).toHaveLength(2)
    // Owned rows come first, shared rows follow in their original order.
    expect(wrapper.findAll('.banks-row').map(row => row.find('.bank-name-text').text()))
      .toEqual(['Owned One', 'Owned Two', 'Shared One', 'Shared Two'])
    wrapper.unmount()
  })

  it('omits a section that has no rows', async () => {
    listBanks.mockResolvedValue([bank({ id: 'o1', name: 'Owned Only', role: 'ADMIN' })])
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('[data-testid="banks-section-owned"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="banks-section-shared"]').exists()).toBe(false)
    wrapper.unmount()

    listBanks.mockResolvedValue([bank({ id: 's1', name: 'Shared Only', role: 'MEMBER' })])
    const sharedWrapper = mountView()
    await flush()
    expect(sharedWrapper.find('[data-testid="banks-section-owned"]').exists()).toBe(false)
    expect(sharedWrapper.find('[data-testid="banks-section-shared"]').exists()).toBe(true)
    sharedWrapper.unmount()
  })

  it('keeps search and sort operating across both sections', async () => {
    listBanks.mockResolvedValue([
      bank({ id: 'o1', name: 'Study Owned B', role: 'ADMIN' }),
      bank({ id: 'o2', name: 'Study Owned A', role: 'ADMIN' }),
      bank({ id: 's1', name: 'Study Shared B', role: 'EDITOR' }),
      bank({ id: 's2', name: 'Study Shared A', role: 'MEMBER' }),
    ])
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-sort"]').setValue('name')
    await flush()
    expect(wrapper.findAll('[data-testid="banks-section-owned"] .banks-row .bank-name-text')
      .map(node => node.text())).toEqual(['Study Owned A', 'Study Owned B'])
    expect(wrapper.findAll('[data-testid="banks-section-shared"] .banks-row .bank-name-text')
      .map(node => node.text())).toEqual(['Study Shared A', 'Study Shared B'])

    // A query that only matches one side collapses the other section entirely.
    await wrapper.find('.search-box input').setValue('owned')
    await flush()
    expect(wrapper.find('[data-testid="banks-section-owned"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="banks-section-shared"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="bank-filtered-count"]').text()).toContain('2')
    wrapper.unmount()
  })

  it('labels shared rows with the editor or member badge', async () => {
    listBanks.mockResolvedValue([
      bank({ id: 's1', name: 'Editable', role: 'EDITOR' }),
      bank({ id: 's2', name: 'Readable', role: 'MEMBER' }),
    ])
    const wrapper = mountView()
    await flush()

    const rows = wrapper.findAll('[data-testid="banks-section-shared"] .banks-row')
    expect(rows[0].find('.bank-name .tag').text()).toBe(t('ep.banks.role_badge_editor'))
    expect(rows[1].find('.bank-name .tag').text()).toBe(t('ep.banks.role_badge_member'))
    wrapper.unmount()
  })

  it('keeps the workspace entry available to a shared member', async () => {
    listBanks.mockResolvedValue([bank({ id: 's1', name: 'Shared Member', role: 'MEMBER' })])
    const wrapper = mountView()
    await flush()

    const row = wrapper.find('.banks-row')
    expect(row.find('.bank-manage-locked').exists()).toBe(false)
    const manage = row.findAll('.bank-actions-cell button')[1]
    expect(manage.text()).toBe(t('ep.banks.manage'))
    expect(manage.element.disabled).toBe(false)

    await manage.trigger('click')
    expect(push).toHaveBeenCalledWith({
      name: 'bank-detail',
      params: { bankId: 's1' },
      query: { tab: 'settings' },
    })
    wrapper.unmount()
  })

  it('keeps the recycle view as one unlabelled list with restore actions', async () => {
    listBanks.mockImplementation((_token, options) => Promise.resolve(
      options?.deleted ? [bank({ id: 'd1', name: 'Deleted', role: 'MEMBER', deleted: true })] : [],
    ))
    const wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="bank-recycle-toggle"]').trigger('click')
    await flush()

    expect(wrapper.findAll('.bank-section')).toHaveLength(1)
    expect(wrapper.find('[data-testid="banks-section-recycle"]').exists()).toBe(true)
    expect(wrapper.find('.bank-section-head').exists()).toBe(false)
    expect(wrapper.find('[data-testid="row-restore"]').exists()).toBe(true)
    expect(wrapper.find('.banks-row .bank-practice-btn').exists()).toBe(false)
    wrapper.unmount()
  })
})
