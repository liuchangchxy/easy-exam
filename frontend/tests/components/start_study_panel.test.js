import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import StartStudyPanel from '../../src/components/StartStudyPanel.vue'
import { setLocale } from '../../src/composables/useLocale.js'

const sessions = [
  {
    id: 's1',
    bank_name: 'Bank One',
    mode: 'PRACTICE',
    answered_count: 3,
    total_questions: 10,
  },
]

function mountPanel(props = {}) {
  return mount(StartStudyPanel, {
    props: { show: true, sessions, busy: false, ...props },
    global: { stubs: { teleport: true } },
  })
}

describe('StartStudyPanel', () => {
  beforeEach(() => {
    setLocale('zh-CN')
    document.body.innerHTML = ''
  })

  it('explains the in-progress session and lists it', () => {
    const wrapper = mountPanel()

    const panel = wrapper.find('[data-testid="start-study-panel"]')
    expect(panel.exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="start-study-session"]')).toHaveLength(1)
    expect(panel.text()).toContain('Bank One')

    wrapper.unmount()
  })

  it('emits continue, end-and-start and cancel from their own controls', async () => {
    const wrapper = mountPanel()

    await wrapper.find('[data-testid="start-study-continue"]').trigger('click')
    expect(wrapper.emitted('continue')).toHaveLength(1)

    await wrapper.find('[data-testid="start-study-end-and-start"]').trigger('click')
    expect(wrapper.emitted('end-and-start')).toHaveLength(1)

    await wrapper.find('[data-testid="start-study-cancel"]').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)

    wrapper.unmount()
  })

  it('does not render while closed and disables actions while busy', () => {
    const closed = mountPanel({ show: false })
    expect(closed.find('[data-testid="start-study-panel"]').exists()).toBe(false)
    closed.unmount()

    const busy = mountPanel({ busy: true })
    expect(busy.find('[data-testid="start-study-continue"]').attributes('disabled')).toBeDefined()
    expect(busy.find('[data-testid="start-study-end-and-start"]').attributes('disabled')).toBeDefined()
    expect(busy.find('[data-testid="start-study-cancel"]').attributes('disabled')).toBeDefined()
    busy.unmount()
  })
})
