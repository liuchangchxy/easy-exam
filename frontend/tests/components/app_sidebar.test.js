import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppSidebar from '../../src/components/AppSidebar.vue'

function mountSidebar(overrides = {}) {
  return mount(AppSidebar, {
    props: {
      currentPage: 'today',
      user: { username: 'alice', is_admin: false },
      bankCount: 0,
      reviewCount: 0,
      learningTrends: null,
      ...overrides,
    },
  })
}

describe('AppSidebar account entry', () => {
  it('keeps exactly one Settings path and no duplicated account header', () => {
    const wrapper = mountSidebar()
    const settingsButtons = wrapper.findAll('.side-foot > button.nav-item')
    expect(settingsButtons).toHaveLength(1)
    expect(settingsButtons[0].find('.label').text()).not.toBe('')
    expect(wrapper.find('.user-popover').exists()).toBe(false)
    expect(wrapper.findAll('.popover-action')).toHaveLength(0)
  })

  it('the sidebar avatar asks the shell to open the shared account menu', async () => {
    const wrapper = mountSidebar()
    const trigger = wrapper.find('.user-mini')
    expect(trigger.attributes('data-account-trigger')).toBeDefined()
    expect(trigger.attributes('aria-haspopup')).toBe('menu')
    expect(trigger.attributes('aria-expanded')).toBe('false')

    await trigger.trigger('click')
    const emitted = wrapper.emitted('account-menu')
    expect(emitted).toHaveLength(1)
    expect(emitted[0][0]).toBe(trigger.element)
  })

  it('reflects the shared menu state on the trigger', () => {
    const wrapper = mountSidebar({ accountMenuOpen: true })
    expect(wrapper.find('.user-mini').attributes('aria-expanded')).toBe('true')
  })
})
