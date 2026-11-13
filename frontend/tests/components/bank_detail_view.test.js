import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BankDetailView from '../../src/views/BankDetailView.vue'
import { t } from '../../src/composables/useLocale.js'
import {
  getBank,
  listBanks,
  listBankQuestionsContent,
  listChapters,
  listBankMembers,
} from '../../src/api/banks'
import { startSession } from '../../src/api/practice'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('../../src/api/banks', () => ({
  getBank: vi.fn(),
  listBanks: vi.fn(),
  listBankQuestionsContent: vi.fn(),
  listChapters: vi.fn(),
  listBankMembers: vi.fn(),
  copyQuestionToBank: vi.fn(),
}))

vi.mock('../../src/api/questions', () => ({
  listQuestionVersions: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const question = {
  id: 'q1',
  type: 'SINGLE',
  stem: 'Sample?',
  options: [{ key: 'A', content: 'A', text: 'A' }],
  answer: 'A',
  explanation: '',
  difficulty: 2,
  version_number: 1,
}

function mountView() {
  return mount(BankDetailView, { props: { token: 't1', bankId: 'b1' } })
}

describe('BankDetailView practice affordances', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getBank.mockResolvedValue({ id: 'b1', name: 'Bank One', role: 'ADMIN' })
    listBanks.mockResolvedValue([])
    listChapters.mockResolvedValue([])
    listBankMembers.mockResolvedValue([])
  })

  it('explains why practice is disabled when the bank has no questions', async () => {
    listBankQuestionsContent.mockResolvedValue([])
    const wrapper = mountView()
    await flush()

    expect(wrapper.find('.practice-empty-note').text()).toBe(t('ep.banks.practice_empty'))
    expect(wrapper.find('.page-actions .btn-primary').element.disabled).toBe(true)
  })

  it('surfaces a failed practice start in the page', async () => {
    listBankQuestionsContent.mockResolvedValue([question])
    startSession.mockRejectedValue({ detail: 'start failed' })
    const wrapper = mountView()
    await flush()

    const button = wrapper.find('.page-actions .btn-primary')
    expect(button.element.disabled).toBe(false)
    await button.trigger('click')
    await flush()

    const notice = wrapper.find('.notice.bad')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain(t('ep.banks.practice_start_failed', { message: 'start failed' }))
    expect(push).not.toHaveBeenCalled()
  })

  it('labels the import action with the import glyph, not the upload glyph', async () => {
    listBankQuestionsContent.mockResolvedValue([question])
    const wrapper = mountView()
    await flush()

    const importButton = wrapper
      .findAll('.page-actions .btn')
      .find(btn => btn.text() === t('ep.common.import'))
    expect(importButton).toBeTruthy()
    expect(importButton.find('[data-icon="import"]').exists()).toBe(true)
    expect(importButton.find('[data-icon="upload"]').exists()).toBe(false)
  })
})
