import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SettingsView from '../../src/views/SettingsView.vue'

vi.mock('../../src/api/ai', () => ({
  getAiConfig: vi.fn(),
  updateAiConfig: vi.fn(),
  testAiConfig: vi.fn(),
}))

vi.mock('../../src/api/admin', () => ({
  listSessions: vi.fn(),
  revokeOtherSessions: vi.fn(),
}))

import { getAiConfig, updateAiConfig, testAiConfig } from '../../src/api/ai'
import { setLocale } from '../../src/composables/useLocale.js'

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const ADMIN = { id: 1, username: 'admin', is_admin: true }
const MEMBER = { id: 2, username: 'bob', is_admin: false }

const SERVER_CONFIG = {
  ai_provider: 'openai',
  ai_api_base: 'https://api.openai.com/v1',
  ai_model: 'gpt-4o-mini',
  ai_api_key: '',
  search_provider: 'open-webSearch',
  search_api_key: '',
  search_api_base: 'http://localhost:8000/v1/search',
  is_configured: false,
}

async function mountSettings(path = '/settings', user = MEMBER) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings', name: 'settings', component: SettingsView },
      { path: '/instance', name: 'instance-admin', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(SettingsView, {
    props: { token: 't1', user },
    global: { plugins: [router] },
  })
  await flush()
  return { wrapper, router }
}

let wrapper

describe('SettingsView layering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setLocale('zh-CN')
    getAiConfig.mockResolvedValue({ ...SERVER_CONFIG })
    updateAiConfig.mockResolvedValue({ ...SERVER_CONFIG, is_configured: true })
    testAiConfig.mockResolvedValue({ ok: true, message: '' })
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    wrapper = null
    setLocale('zh-CN')
  })

  it('renders the six nav items in their historic order inside translated groups', async () => {
    const mounted = await mountSettings('/settings', MEMBER)
    wrapper = mounted.wrapper

    const items = wrapper.findAll('.settings-nav-item')
    expect(items.map(item => item.text())).toEqual([
      '外观',
      '语言',
      'AI 解释',
      '联网核查',
      '账号与安全',
      '关于与数据',
    ])

    const groups = wrapper.findAll('.settings-nav-group')
    expect(groups.map(group => group.text())).toEqual(['个人', '运维', '关于'])
  })

  it('adds the collaboration group heading only for instance admins and keeps instance last', async () => {
    const mounted = await mountSettings('/settings', ADMIN)
    wrapper = mounted.wrapper

    const items = wrapper.findAll('.settings-nav-item')
    expect(items).toHaveLength(7)
    expect(items[6].text()).toContain('实例管理')
    expect(wrapper.findAll('.settings-nav-group').map(group => group.text())).toEqual([
      '个人',
      '协作与实例',
      '运维',
      '关于',
    ])
  })

  it('translates the group headings', async () => {
    setLocale('en-US')
    const mounted = await mountSettings('/settings', MEMBER)
    wrapper = mounted.wrapper

    expect(wrapper.findAll('.settings-nav-group').map(group => group.text())).toEqual([
      'Personal',
      'Operations',
      'About',
    ])
    expect(wrapper.findAll('.settings-nav-item')[2].text()).toContain('AI explanations')
  })

  it('patches only the AI field that changed', async () => {
    const mounted = await mountSettings('/settings?section=ai')
    wrapper = mounted.wrapper

    const inputs = wrapper.findAll('.settings-fields input')
    expect(inputs[1].element.value).toBe('gpt-4o-mini')
    await inputs[1].setValue('gpt-4o')
    await flush()

    expect(updateAiConfig).toHaveBeenCalledTimes(1)
    expect(updateAiConfig).toHaveBeenCalledWith('t1', { ai_model: 'gpt-4o' })
  })

  it('patches only the web field that changed', async () => {
    const mounted = await mountSettings('/settings?section=network')
    wrapper = mounted.wrapper

    const inputs = wrapper.findAll('.settings-fields input')
    expect(inputs).toHaveLength(2)
    await inputs[0].setValue('http://search.example:8080/v1/search')
    await flush()

    expect(updateAiConfig).toHaveBeenCalledTimes(1)
    expect(updateAiConfig).toHaveBeenCalledWith('t1', {
      search_api_base: 'http://search.example:8080/v1/search',
    })
  })

  it('patches the web provider on its own', async () => {
    const mounted = await mountSettings('/settings?section=network')
    wrapper = mounted.wrapper

    await wrapper.find('.settings-fields select').setValue('offline')
    await flush()

    expect(updateAiConfig).toHaveBeenCalledWith('t1', { search_provider: 'offline' })
  })

  it('tests the AI connection with the right kind and renders success', async () => {
    const mounted = await mountSettings('/settings?section=ai')
    wrapper = mounted.wrapper

    await wrapper.find('[data-testid="ai-test"]').trigger('click')
    await flush()

    expect(testAiConfig).toHaveBeenCalledWith('t1', 'ai')
    expect(wrapper.text()).toContain('连接成功')
    expect(wrapper.find('.settings-section [role="status"]').text()).toContain('连接成功')
  })

  it('tests the web connection with the right kind', async () => {
    const mounted = await mountSettings('/settings?section=network')
    wrapper = mounted.wrapper

    await wrapper.find('[data-testid="web-test"]').trigger('click')
    await flush()

    expect(testAiConfig).toHaveBeenCalledWith('t1', 'search')
  })

  it('renders the returned failure message as an alert', async () => {
    testAiConfig.mockResolvedValue({ ok: false, message: '401 invalid API key' })
    const mounted = await mountSettings('/settings?section=ai')
    wrapper = mounted.wrapper

    await wrapper.find('[data-testid="ai-test"]').trigger('click')
    await flush()

    expect(wrapper.text()).toContain('401 invalid API key')
    expect(wrapper.find('.settings-section [role="alert"]').text()).toContain('401 invalid API key')
  })

  it('disables the test control and shows progress while the test runs', async () => {
    let resolveTest
    testAiConfig.mockImplementation(() => new Promise(resolve => { resolveTest = resolve }))
    const mounted = await mountSettings('/settings?section=ai')
    wrapper = mounted.wrapper

    const button = wrapper.find('[data-testid="ai-test"]')
    await button.trigger('click')
    await flush()

    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('连接中…')

    resolveTest({ ok: true, message: '' })
    await flush()
    await flush()

    expect(button.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('连接成功')
  })

  it('flushes a pending auto-save before testing the current values', async () => {
    const mounted = await mountSettings('/settings?section=ai')
    wrapper = mounted.wrapper

    const model = wrapper.findAll('.settings-fields input')[1]
    model.element.value = 'gpt-4o'
    await model.trigger('input')

    await wrapper.find('[data-testid="ai-test"]').trigger('click')
    await flush()

    expect(updateAiConfig).toHaveBeenCalledWith('t1', { ai_model: 'gpt-4o' })
    expect(updateAiConfig.mock.invocationCallOrder[0])
      .toBeLessThan(testAiConfig.mock.invocationCallOrder[0])
  })

  it('leaves saved configuration untouched when the connection test fails', async () => {
    testAiConfig.mockResolvedValue({ ok: false, message: 'unreachable' })
    const mounted = await mountSettings('/settings?section=ai')
    wrapper = mounted.wrapper

    await wrapper.find('[data-testid="ai-test"]').trigger('click')
    await flush()

    expect(updateAiConfig).not.toHaveBeenCalled()
    expect(wrapper.findAll('.settings-fields input')[1].element.value).toBe('gpt-4o-mini')
    expect(wrapper.text()).toContain('unreachable')
  })

  it('sends a partial PATCH and a typed test POST at the API layer', async () => {
    const actual = await vi.importActual('../../src/api/ai')
    const calls = []
    const previousFetch = globalThis.fetch
    globalThis.fetch = async (url, options) => {
      calls.push({ url, options })
      return { ok: true, status: 200, json: async () => ({}) }
    }
    try {
      await actual.updateAiConfig('t1', { ai_model: 'gpt-4o' })
      await actual.testAiConfig('t1', 'search')
    } finally {
      globalThis.fetch = previousFetch
    }

    expect(calls[0].url).toBe('/api/v1/ai/config')
    expect(calls[0].options.method).toBe('PATCH')
    expect(JSON.parse(calls[0].options.body)).toEqual({ ai_model: 'gpt-4o' })
    expect(calls[1].url).toBe('/api/v1/ai/config/test')
    expect(calls[1].options.method).toBe('POST')
    expect(JSON.parse(calls[1].options.body)).toEqual({ kind: 'search' })
  })
})
