import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MobileNav from '../../src/components/MobileNav.vue'

describe('MobileNav component integration', () => {
  it('renders the five primary destinations and emits navigate on click', async () => {
    const wrapper = mount(MobileNav, {
      props: {
        currentPage: 'review',
      },
    })

    const buttons = wrapper.findAll('button.bn-item')
    expect(buttons.length).toBe(5)
    expect(wrapper.findAll('.bn-item.is-active').length).toBe(1)
    expect(wrapper.findAll('.bn-item.is-active')[0].attributes('class')).toContain('is-active')

    await buttons[2].trigger('click')
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')[0]).toEqual(['review'])

    await buttons[4].trigger('click')
    expect(wrapper.emitted('navigate')[1]).toEqual(['notes'])
  })
})
