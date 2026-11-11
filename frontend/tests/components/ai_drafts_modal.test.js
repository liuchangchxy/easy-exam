import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import AiDraftsModal from '../../src/components/AiDraftsModal.vue'

vi.mock('../../src/api/ai', () => ({
  listDrafts: vi.fn(),
  acceptDraft: vi.fn(),
  discardDraft: vi.fn(),
}))

import { listDrafts, acceptDraft } from '../../src/api/ai'

function draft(overrides = {}) {
  return {
    id: 'd1',
    type: 'SINGLE',
    difficulty: 3,
    stem: '变式题题干',
    options: [{ key: 'A', text: '选项一' }, { key: 'B', text: '选项二' }],
    answer: 'A',
    explanation: '解析',
    created_at: '2026-11-11 10:00',
    target_bank_name: '管理题库',
    can_manage: true,
    ...overrides,
  }
}

async function flush() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('AiDraftsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the target bank and only enables acceptance for editable banks', async () => {
    listDrafts.mockResolvedValue([
      draft(),
      draft({ id: 'd2', stem: '只读题库草稿', target_bank_name: '只读题库', can_manage: false }),
    ])

    const wrapper = mount(AiDraftsModal, { props: { token: 't1' } })
    await flush()

    expect(listDrafts).toHaveBeenCalledWith('t1', 'DRAFT', '')
    const rows = wrapper.findAll('.draft-row')
    expect(rows).toHaveLength(2)
    expect(wrapper.text()).toContain('管理题库')
    expect(wrapper.text()).toContain('只读题库')

    const acceptButtons = rows.map(row => row.find('.draft-actions .btn-primary'))
    expect(acceptButtons[0].attributes('disabled')).toBeUndefined()
    expect(acceptButtons[1].attributes('disabled')).toBeDefined()
    expect(rows[1].find('.draft-locked').exists()).toBe(true)
  })

  it('accepts a draft and emits the created question', async () => {
    listDrafts.mockResolvedValue([draft()])
    acceptDraft.mockResolvedValue({ status: 'ACCEPTED', question: { id: 'q-new' } })

    const wrapper = mount(AiDraftsModal, { props: { token: 't1', bankId: 'b1' } })
    await flush()
    expect(listDrafts).toHaveBeenCalledWith('t1', 'DRAFT', 'b1')

    await wrapper.find('.draft-actions .btn-primary').trigger('click')
    await flush()

    expect(acceptDraft).toHaveBeenCalledWith('t1', 'd1', {
      stem: '变式题题干',
      options: [{ key: 'A', text: '选项一' }, { key: 'B', text: '选项二' }],
      answer: 'A',
      explanation: '解析',
    })
    expect(wrapper.emitted('accepted')).toBeTruthy()
    expect(wrapper.emitted('accepted')[0][0]).toEqual({ id: 'q-new' })
    expect(wrapper.findAll('.draft-row')).toHaveLength(0)
  })

  it('renders a localized error state with retry when loading fails', async () => {
    listDrafts.mockRejectedValueOnce(new Error('network down'))
    const wrapper = mount(AiDraftsModal, { props: { token: 't1' } })
    await flush()

    expect(wrapper.find('.drafts-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('network down')

    listDrafts.mockResolvedValue([draft()])
    await wrapper.find('.drafts-error button').trigger('click')
    await flush()
    expect(wrapper.findAll('.draft-row')).toHaveLength(1)
  })
})
