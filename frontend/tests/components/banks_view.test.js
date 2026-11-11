import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BanksView from '../../src/views/BanksView.vue'
import { t } from '../../src/composables/useLocale.js'
import { listBanks } from '../../src/api/banks'
import { startSession } from '../../src/api/practice'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn(),
  createBank: vi.fn(),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn(),
}))

vi.mock('../../src/api/sync', () => ({
  triggerSyncEvent: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

describe('BanksView row semantics and practice failures', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listBanks.mockResolvedValue([
      { id: 'b1', name: 'Bank One', category: 'Test', question_count: 3, role: 'ADMIN' },
    ])
  })

  it('renders a plain row container with an explicit open control', async () => {
    const wrapper = mount(BanksView, { props: { token: 't1' } })
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
    listBanks.mockResolvedValue([
      { id: 'b1', name: 'Locked Bank', question_count: 3, role: 'ADMIN', has_active_exam: true },
    ])
    const wrapper = mount(BanksView, { props: { token: 't1' } })
    await flush()

    const lock = wrapper.find('.bank-manage-locked')
    expect(lock.exists()).toBe(true)
    expect(lock.attributes('title')).toBe(t('ep.manage.locked_desc'))
    expect(lock.find('button').element.disabled).toBe(true)
  })

  it('surfaces a failed practice start on the page', async () => {
    startSession.mockRejectedValue({ detail: 'start failed' })
    const wrapper = mount(BanksView, { props: { token: 't1' } })
    await flush()

    await wrapper.find('.bank-actions-cell .btn').trigger('click')
    await flush()

    const notice = wrapper.find('.notice.bad')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain(t('ep.banks.practice_start_failed', { message: 'start failed' }))
    expect(push).not.toHaveBeenCalled()
  })
})
