import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MobileNav from '../../src/components/MobileNav.vue'

describe('MobileNav component integration', () => {
  it('renders the five destinations plus the 更多 chrome menu', async () => {
    const wrapper = mount(MobileNav, {
      props: {
        currentPage: 'review',
      },
    })

    const buttons = wrapper.findAll('button.bn-item')
    expect(buttons.length).toBe(6)
    expect(wrapper.findAll('.bn-item.is-active').length).toBe(1)
    expect(wrapper.findAll('.bn-item.is-active')[0].attributes('class')).toContain('is-active')

    await buttons[2].trigger('click')
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')[0]).toEqual(['review'])

    await buttons[4].trigger('click')
    expect(wrapper.emitted('navigate')[1]).toEqual(['notes'])
  })

  it('the 更多 item opens the chrome menu instead of navigating', async () => {
    const wrapper = mount(MobileNav, { props: { currentPage: 'notes' } })
    const more = wrapper.findAll('button.bn-item')[5]
    expect(more.attributes('data-more-trigger')).toBeDefined()
    expect(more.attributes('aria-haspopup')).toBe('menu')
    expect(more.attributes('aria-expanded')).toBe('false')

    await more.trigger('click')
    expect(wrapper.emitted('more')).toHaveLength(1)
    expect(wrapper.emitted('navigate')).toBeUndefined()

    await wrapper.setProps({ moreOpen: true, currentPage: 'notes' })
    expect(wrapper.findAll('button.bn-item')[5].attributes('aria-expanded')).toBe('true')
    expect(wrapper.findAll('.bn-item.is-active').length).toBe(2)
  })
})
