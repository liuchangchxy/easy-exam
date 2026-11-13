import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SettingsView from '../../src/views/SettingsView.vue'
import { setLocale } from '../../src/composables/useLocale.js'

vi.mock('../../src/api/ai', () => ({
  getAiConfig: vi.fn(),
  updateAiConfig: vi.fn(),
}))

vi.mock('../../src/api/admin', () => ({
  listSessions: vi.fn(),
  revokeOtherSessions: vi.fn(),
}))

import { getAiConfig } from '../../src/api/ai'
import { listSessions, revokeOtherSessions } from '../../src/api/admin'

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const ADMIN = { id: 1, username: 'admin', is_admin: true }
const MEMBER = { id: 2, username: 'bob', is_admin: false }

const SESSIONS = [
  {
    id: 11,
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    created_at: '2026-11-01T08:00:00Z',
    last_seen_at: '2026-11-13T09:30:00Z',
    current: true,
  },
  {
    id: 12,
    user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    created_at: '2026-11-02T10:00:00Z',
    last_seen_at: '2026-11-12T11:00:00Z',
    current: false,
  },
]

async function mountSettings(path = '/settings?section=account', user = ADMIN) {
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
    attachTo: document.body,
  })
  await flush()
  return { wrapper, router }
}

let confirmMock
let wrapper

describe('SettingsView devices and sessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setLocale('zh-CN')
    document.body.innerHTML = ''
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
    listSessions.mockResolvedValue(SESSIONS)
    revokeOtherSessions.mockResolvedValue({ revoked: 1 })
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    wrapper = null
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('lists the caller sessions and marks only the current device', async () => {
    const mounted = await mountSettings()
    wrapper = mounted.wrapper

    expect(listSessions).toHaveBeenCalledWith('t1')
    expect(wrapper.text()).toContain('Chrome · Windows')
    expect(wrapper.text()).toContain('Safari · macOS')
    expect(wrapper.text()).toContain('2026-11-01 08:00')
    expect(wrapper.text()).toContain('2026-11-12 11:00')

    const badges = wrapper.findAll('.sessions-current')
    expect(badges).toHaveLength(1)
    expect(badges[0].text()).toBe('本机')
  })

  it('still shows the instance role line in the account section', async () => {
    const mounted = await mountSettings('/settings?section=account', ADMIN)
    wrapper = mounted.wrapper

    expect(wrapper.find('.account-role').text()).toBe('管理员')
  })

  it('asks for confirmation and reports how many sessions were revoked', async () => {
    revokeOtherSessions.mockResolvedValue({ revoked: 1 })
    const mounted = await mountSettings()
    wrapper = mounted.wrapper

    await wrapper.find('[data-testid="logout-other-sessions"]').trigger('click')
    await flush()

    expect(confirmMock).toHaveBeenCalledWith('退出其他设备？其他设备上的登录会立即失效。')
    expect(revokeOtherSessions).toHaveBeenCalledWith('t1')
    expect(wrapper.text()).toContain('已退出 1 个其他设备')
    expect(listSessions).toHaveBeenCalledTimes(2)
  })

  it('does not revoke sessions when the confirmation is declined', async () => {
    confirmMock.mockReturnValue(false)
    const mounted = await mountSettings()
    wrapper = mounted.wrapper

    await wrapper.find('[data-testid="logout-other-sessions"]').trigger('click')
    await flush()

    expect(confirmMock).toHaveBeenCalled()
    expect(revokeOtherSessions).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('已退出')
  })

  it('hides the instance-admin nav item from non-admins', async () => {
    const mounted = await mountSettings('/settings', MEMBER)
    wrapper = mounted.wrapper

    expect(wrapper.findAll('.settings-nav-item')).toHaveLength(6)
    expect(wrapper.find('.settings-nav').text()).not.toContain('实例管理')
  })

  it('shows the instance-admin nav item to admins and routes to it', async () => {
    const mounted = await mountSettings('/settings', ADMIN)
    wrapper = mounted.wrapper

    const items = wrapper.findAll('.settings-nav-item')
    expect(items).toHaveLength(7)
    const instanceItem = items.find(item => item.text().includes('实例管理'))
    expect(instanceItem).toBeTruthy()

    await instanceItem.trigger('click')
    await flush()

    expect(mounted.router.currentRoute.value.name).toBe('instance-admin')
  })

  it('offers a retry when sessions fail to load', async () => {
    listSessions.mockRejectedValueOnce({ status: 500 })
    const mounted = await mountSettings()
    wrapper = mounted.wrapper

    expect(wrapper.text()).toContain('会话读取失败')
    const retry = wrapper.findAll('button').find(button => button.text().includes('重试'))
    await retry.trigger('click')
    await flush()

    expect(listSessions).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Chrome · Windows')
  })
})
