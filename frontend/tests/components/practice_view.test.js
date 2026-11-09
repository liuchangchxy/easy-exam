import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PracticeViewV1 from '../../src/views/PracticeViewV1.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('../../src/stores/authStore', () => ({
  useAuthStore: () => ({
    token: { value: 'test-token' },
    user: { value: { id: 'u1', username: 'testuser' } },
  }),
}))

vi.mock('../../src/api/practice', () => ({
  getSession: vi.fn().mockResolvedValue({
    id: 's1',
    mode: 'PRACTICE',
    bank_id: 'b1',
    current_index: 0,
    answers: {},
  }),
  getSessionQuestions: vi.fn().mockResolvedValue([
    {
      id: 'q1',
      stem: 'What is EasyExam?',
      type: 'SINGLE',
      options: [
        { key: 'A', content: 'An exam app' },
        { key: 'B', content: 'Other' },
      ],
      answer: 'A',
      explanation: 'Explanation for Q1',
    },
  ]),
  submitAttempt: vi.fn(),
  completeSession: vi.fn(),
  syncDraft: vi.fn(),
}))

vi.mock('../../src/api/questions', () => ({
  getQuestion: vi.fn(),
  listQuestionVersions: vi.fn().mockResolvedValue([]),
  updateQuestion: vi.fn(),
  getQuestionConflict: vi.fn().mockResolvedValue({ has_conflict: false }),
  resolveQuestionConflict: vi.fn(),
  regradeQuestion: vi.fn(),
}))

vi.mock('../../src/api/ai', () => ({
  generateAnswer: vi.fn(),
  listAnswerVersions: vi.fn().mockResolvedValue([]),
  adoptAnswer: vi.fn(),
  saveCandidate: vi.fn(),
  verifyWeb: vi.fn(),
  listQuestionConversations: vi.fn().mockResolvedValue([]),
  listConversationMessages: vi.fn().mockResolvedValue([]),
  sendChatMessage: vi.fn(),
  generateVariant: vi.fn(),
}))

vi.mock('../../src/api/learning', () => ({
  markWeak: vi.fn(),
  unmarkWeak: vi.fn(),
}))

vi.mock('../../src/api/kills', () => ({
  killQuestion: vi.fn(),
}))

vi.mock('../../src/api/sync', () => ({
  triggerSyncEvent: vi.fn(),
}))

describe('PracticeViewV1 component integration', () => {
  it('toggles more menu on "⋯" click and renders key action items', async () => {
    const wrapper = mount(PracticeViewV1, {
      props: {
        token: 'test-token',
        sessionId: 's1',
      },
    })

    // Wait for onMounted session/questions to load
    await new Promise(r => setTimeout(r, 50))

    // 1. Initial state: dropdown menu is closed
    expect(wrapper.find('.mobile-dropdown-menu').exists()).toBe(false)

    // 2. Click "⋯" button
    const moreBtn = wrapper.find('.btn-more-menu')
    expect(moreBtn.exists()).toBe(true)
    await moreBtn.trigger('click')

    // 3. Dropdown menu appears
    const dropdown = wrapper.find('.mobile-dropdown-menu')
    expect(dropdown.exists()).toBe(true)

    // 4. Verify key action items exist
    const helpBtn = dropdown.find('.btn-help-guide')
    expect(helpBtn.exists()).toBe(true)

    const editBtn = dropdown.find('.btn-edit-question')
    expect(editBtn.exists()).toBe(true)

    const killBtn = dropdown.find('.btn-kill')
    expect(killBtn.exists()).toBe(true)

    // Header complete button is accessible
    const completeBtn = wrapper.find('.btn-header-complete')
    expect(completeBtn.exists()).toBe(true)
  })
})
