import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppSidebar from '../../src/components/AppSidebar.vue'

function mountSidebar(overrides = {}) {
  return mount(AppSidebar, {
    props: {
      currentPage: 'today',
      bankCount: 0,
      reviewCount: 0,
      learningTrends: null,
      ...overrides,
    },
  })
}

describe('AppSidebar footer', () => {
  it('keeps exactly one Settings path and no duplicated account header', () => {
    const wrapper = mountSidebar()
    const settingsButtons = wrapper.findAll('.side-foot > button.nav-item')
    expect(settingsButtons).toHaveLength(1)
    expect(settingsButtons[0].find('.label').text()).not.toBe('')
    expect(wrapper.find('.user-popover').exists()).toBe(false)
    expect(wrapper.findAll('.popover-action')).toHaveLength(0)
  })

  it('owns no identity: no avatar, name, role or account trigger in the sidebar', () => {
    const wrapper = mountSidebar({ currentPage: 'settings' })
    expect(wrapper.find('.avatar').exists()).toBe(false)
    expect(wrapper.find('.user-mini').exists()).toBe(false)
    expect(wrapper.find('.user-name').exists()).toBe(false)
    expect(wrapper.find('.user-sub').exists()).toBe(false)
    expect(wrapper.find('[data-account-trigger]').exists()).toBe(false)
    expect(wrapper.emitted('account-menu')).toBeUndefined()
  })
})
