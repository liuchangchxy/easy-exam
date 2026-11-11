import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { nextTick } from 'vue'
import AppLayout from '../../src/layouts/AppLayout.vue'
import { useAuthStore } from '../../src/stores/authStore'
import { t } from '../../src/composables/useLocale.js'

vi.mock('../../src/api/auth', () => ({
  login: vi.fn(),
  currentUser: vi.fn(),
  logout: vi.fn().mockResolvedValue({}),
}))
vi.mock('../../src/api/banks', () => ({ listBanks: vi.fn().mockResolvedValue({ banks: [] }) }))
vi.mock('../../src/api/mistakes', () => ({ listDueMistakes: vi.fn().mockResolvedValue([]) }))
vi.mock('../../src/api/practice', () => ({ startSession: vi.fn() }))
vi.mock('../../src/api/learning', () => ({ getLearningTrends: vi.fn().mockResolvedValue(null) }))

const Empty = { template: '<div />' }

let wrapper = null

async function mountLayout() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty },
      { path: '/banks/:bankId', name: 'bank-detail', component: Empty },
      { path: '/settings', name: 'settings', component: Empty },
    ],
  })
  await router.push('/')
  await router.isReady()
  const auth = useAuthStore()
  auth.token.value = 'test-token'
  auth.user.value = { username: 'alice', is_admin: false }
  wrapper = mount(AppLayout, { global: { plugins: [router] } })
  await nextTick()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  const auth = useAuthStore()
  auth.token.value = ''
  auth.user.value = null
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('AppLayout shared account menu', () => {
  it('opens one menu with an identity header and no Settings row; the sidebar owns no trigger', async () => {
    await mountLayout()
    expect(wrapper.find('.sidebar [data-account-trigger]').exists()).toBe(false)
    expect(wrapper.find('.sidebar .avatar').exists()).toBe(false)

    await wrapper.find('.topbar [data-account-trigger]').trigger('click')
    expect(wrapper.findAll('.account-menu')).toHaveLength(1)

    const menu = wrapper.find('.account-menu')
    expect(menu.find('.account-menu-name').text()).toBe('alice')
    expect(menu.find('.account-menu-role').text()).toBe(t('ep.role.user'))
    const menuText = menu.text()
    expect(menuText).not.toContain('设置')
    expect(menuText).not.toContain('Settings')

    // The mobile-top avatar opens the very same menu instance.
    await wrapper.find('.mobile-top [data-account-trigger]').trigger('click')
    expect(wrapper.findAll('.account-menu')).toHaveLength(1)
    expect(wrapper.find('.mobile-top [data-account-trigger]').attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('.topbar [data-account-trigger]').attributes('aria-expanded')).toBe('false')
  })

  it('shows the admin role label in the menu header for admins', async () => {
    await mountLayout()
    const auth = useAuthStore()
    auth.user.value = { username: 'alice', is_admin: true }
    await nextTick()
    await wrapper.find('.topbar [data-account-trigger]').trigger('click')
    expect(wrapper.find('.account-menu-name').text()).toBe('alice')
    expect(wrapper.find('.account-menu-role').text()).toBe(t('ep.role.admin'))
  })

  it('asks for confirmation before signing out from the account menu', async () => {
    await mountLayout()
    const confirmSpy = vi.fn().mockReturnValue(false)
    vi.stubGlobal('confirm', confirmSpy)
    const auth = useAuthStore()

    await wrapper.find('.topbar [data-account-trigger]').trigger('click')
    await wrapper.find('.account-menu .popover-action.is-danger').trigger('click')
    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(confirmSpy.mock.calls[0][0]).toBeTruthy()
    expect(auth.token.value).toBe('test-token')

    confirmSpy.mockReturnValue(true)
    await wrapper.find('.account-menu .popover-action.is-danger').trigger('click')
    await nextTick()
    expect(confirmSpy).toHaveBeenCalledTimes(2)
    expect(auth.token.value).toBe('')
  })
})
