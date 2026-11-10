import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SettingsView from '../../src/views/SettingsView.vue'

vi.mock('../../src/api/ai', () => ({
  getAiConfig: vi.fn(),
  updateAiConfig: vi.fn(),
}))

import { getAiConfig } from '../../src/api/ai'
import { setLocale } from '../../src/composables/useLocale.js'

async function flush() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

function navButton(wrapper, index) {
  return wrapper.findAll('.settings-nav-item')[index]
}

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setLocale('zh-CN')
    getAiConfig.mockResolvedValue({
      ai_provider: 'openai',
      ai_api_base: 'https://api.openai.com/v1',
      ai_model: 'gpt-4o-mini',
      ai_api_key: '',
      search_provider: 'open-webSearch',
      search_api_key: '',
      search_api_base: 'http://localhost:8000/v1/search',
      is_configured: false,
    })
  })

  it('surfaces the unconfigured AI state in settings', async () => {
    const wrapper = mount(SettingsView, { props: { token: 't1' } })
    await flush()
    await navButton(wrapper, 2).trigger('click')
    await flush()

    expect(getAiConfig).toHaveBeenCalledWith('t1')
    expect(wrapper.text()).toContain('AI 尚未配置')
  })

  it('exposes exactly one sign-out action in the account section', async () => {
    const wrapper = mount(SettingsView, { props: { token: 't1' } })
    await flush()
    await navButton(wrapper, 4).trigger('click')

    const signOutButtons = wrapper.findAll('button').filter(button => button.text().includes('退出登录'))
    expect(signOutButtons).toHaveLength(1)

    await signOutButtons[0].trigger('click')
    expect(wrapper.emitted('logout')).toHaveLength(1)
  })

  it('renders every palette family exposed by the theme system', async () => {
    const wrapper = mount(SettingsView, { props: { token: 't1' } })
    await flush()

    const options = wrapper.findAll('.palette-option')
    expect(options.map(option => option.attributes('data-palette'))).toEqual([
      'editorial',
      'gruvbox',
      'everforest',
      'catppuccin',
    ])
    expect(options.map(option => option.text())).toEqual([
      '编辑部',
      'Gruvbox',
      'Everforest',
      'Catppuccin',
    ])
    expect(wrapper.find('[data-palette="editorial"]').attributes('aria-checked')).toBe('true')
  })

  it('persists the selected palette without changing the light/dark mode', async () => {
    const wrapper = mount(SettingsView, { props: { token: 't1' } })
    await flush()

    await wrapper.find('[data-palette="gruvbox"]').trigger('click')
    expect(localStorage.getItem('easyexam-theme-palette')).toBe('gruvbox')
    expect(document.documentElement.getAttribute('data-theme-palette')).toBe('gruvbox')
    expect(wrapper.find('[data-palette="gruvbox"]').attributes('aria-checked')).toBe('true')

    const darkButton = wrapper.findAll('.segment').find(button => button.text().includes('深色'))
    await darkButton.trigger('click')

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem('easyexam-theme-mode')).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme-palette')).toBe('gruvbox')
    expect(localStorage.getItem('easyexam-theme-palette')).toBe('gruvbox')
    expect(wrapper.find('[data-palette="gruvbox"]').attributes('aria-checked')).toBe('true')
  })
})
