import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SettingsView from '../../src/views/SettingsView.vue'

vi.mock('../../src/api/ai', () => ({
  getAiConfig: vi.fn(),
  updateAiConfig: vi.fn(),
}))

import { getAiConfig, updateAiConfig } from '../../src/api/ai'
import { setLocale } from '../../src/composables/useLocale.js'

async function flush() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

function navButton(wrapper, index) {
  return wrapper.findAll('.settings-nav-item')[index]
}

async function mountWithRoute(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/settings', name: 'settings', component: SettingsView }],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(SettingsView, {
    props: { token: 't1' },
    global: { plugins: [router] },
  })
  await flush()
  return { wrapper, router }
}

let confirmMock

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setLocale('zh-CN')
    confirmMock = vi.fn(() => true)
    vi.stubGlobal('confirm', confirmMock)
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
    updateAiConfig.mockResolvedValue({
      ai_provider: 'openai',
      ai_api_base: 'https://api.openai.com/v1',
      ai_model: 'gpt-4o-mini',
      ai_api_key: '',
      search_provider: 'open-webSearch',
      search_api_key: '',
      search_api_base: 'http://localhost:8000/v1/search',
      is_configured: true,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('surfaces the unconfigured AI state in settings', async () => {
    const { wrapper } = await mountWithRoute('/settings')
    await navButton(wrapper, 2).trigger('click')
    await flush()

    expect(getAiConfig).toHaveBeenCalledWith('t1')
    expect(wrapper.text()).toContain('AI 尚未配置')
  })

  it('asks for confirmation before signing out', async () => {
    const { wrapper } = await mountWithRoute('/settings')
    await navButton(wrapper, 4).trigger('click')

    const signOutButtons = wrapper.findAll('button').filter(button => button.text().includes('退出登录'))
    expect(signOutButtons).toHaveLength(1)

    await signOutButtons[0].trigger('click')
    expect(confirmMock).toHaveBeenCalledWith('确定要退出登录吗？')
    expect(wrapper.emitted('logout')).toHaveLength(1)
  })

  it('does not sign out when the confirmation is declined', async () => {
    confirmMock.mockReturnValue(false)
    const { wrapper } = await mountWithRoute('/settings')
    await navButton(wrapper, 4).trigger('click')

    await wrapper.findAll('button').find(button => button.text().includes('退出登录')).trigger('click')

    expect(confirmMock).toHaveBeenCalled()
    expect(wrapper.emitted('logout')).toBeUndefined()
  })

  it('restores the active section from the ?section= query on load', async () => {
    const { wrapper } = await mountWithRoute('/settings?section=ai')

    expect(wrapper.find('.settings-nav-item.is-active').text()).toContain('AI 解释')
    expect(wrapper.text()).toContain('AI 尚未配置')
  })

  it('accepts network as the query value for the web-check section', async () => {
    const { wrapper } = await mountWithRoute('/settings?section=network')

    expect(wrapper.find('.settings-nav-item.is-active').text()).toContain('联网核查')
  })

  it('falls back to appearance for missing or unknown section values', async () => {
    const missing = await mountWithRoute('/settings')
    expect(missing.wrapper.find('.settings-nav-item.is-active').text()).toContain('外观')

    const unknown = await mountWithRoute('/settings?section=bogus')
    expect(unknown.wrapper.find('.settings-nav-item.is-active').text()).toContain('外观')
  })

  it('writes the section to the query so browser history stays on settings', async () => {
    const { wrapper, router } = await mountWithRoute('/settings')
    await flush()

    await wrapper.findAll('.settings-nav-item')[3].trigger('click')
    await flush()

    expect(router.currentRoute.value.path).toBe('/settings')
    expect(router.currentRoute.value.query.section).toBe('network')
    expect(wrapper.find('.settings-nav-item.is-active').text()).toContain('联网核查')

    await router.push('/settings?section=account')
    await flush()
    expect(wrapper.find('.settings-nav-item.is-active').text()).toContain('账号与安全')
  })

  it('applies AI configuration changes immediately without a save button', async () => {
    const { wrapper } = await mountWithRoute('/settings?section=ai')

    const modelInput = wrapper.findAll('.settings-fields input')[1]
    await modelInput.setValue('gpt-4o')
    await flush()

    expect(updateAiConfig).toHaveBeenCalledWith('t1', expect.objectContaining({ ai_model: 'gpt-4o' }))
    expect(wrapper.findAll('button').some(button => button.text().includes('保存配置'))).toBe(false)
    expect(wrapper.text()).toContain('更改后自动保存')
  })

  it('renders every palette family exposed by the theme system', async () => {
    const { wrapper } = await mountWithRoute('/settings')

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
    const { wrapper } = await mountWithRoute('/settings')

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
