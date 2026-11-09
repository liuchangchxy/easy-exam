import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MobileNav from '../../src/components/MobileNav.vue'

describe('MobileNav component integration', () => {
  it('opens more menu on click and emits navigate event when clicking item', async () => {
    const wrapper = mount(MobileNav, {
      props: {
        currentPage: 'home',
      },
    })

    // 1. Initial state: “更多” popup is closed
    expect(wrapper.find('.mobile-nav-more-popup').exists()).toBe(false)

    // 2. User clicks “更多” button
    const moreBtn = wrapper.find('.mobile-nav-item-more')
    expect(moreBtn.exists()).toBe(true)
    await moreBtn.trigger('click')

    // 3. Popup appears, import and settings items exist
    const popup = wrapper.find('.mobile-nav-more-popup')
    expect(popup.exists()).toBe(true)

    const buttons = popup.findAll('button.more-popup-item')
    expect(buttons.length).toBe(2)

    // 4. Click import button and verify navigate event
    const importBtn = buttons[0]
    await importBtn.trigger('click')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')[0]).toEqual(['import'])

    // Popup is closed after selection
    expect(wrapper.find('.mobile-nav-more-popup').exists()).toBe(false)

    // 5. Open again and click settings button
    await moreBtn.trigger('click')
    expect(wrapper.find('.mobile-nav-more-popup').exists()).toBe(true)

    const settingsBtn = wrapper.find('.mobile-nav-more-popup').findAll('button.more-popup-item')[1]
    await settingsBtn.trigger('click')

    expect(wrapper.emitted('navigate')[1]).toEqual(['settings'])
  })
})
