import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { nextTick } from 'vue'
import AppLayout from '../../src/layouts/AppLayout.vue'
import { useAuthStore } from '../../src/stores/authStore'
import { t } from '../../src/composables/useLocale.js'
import { BANK_LIST_QUERY_KEY } from '../../src/utils/bankListQuery.js'
import { recordNavigation, resetNavigationStack, canGoBack } from '../../src/router/backNavigation.js'
import { listBanks } from '../../src/api/banks'

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

async function mountLayout(path = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty, meta: { title: '今天' } },
      { path: '/banks', name: 'banks', component: Empty, meta: { title: '题库' } },
      { path: '/banks/:bankId', name: 'bank-detail', component: Empty, meta: { title: '题库', fallback: { name: 'banks' } } },
      { path: '/settings', name: 'settings', component: Empty, meta: { title: '设置' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  // Mirror the app router: the layout decides history-first back navigation
  // from this stack, so the test router has to feed it the same way.
  router.afterEach((to, from) => recordNavigation(to, from))
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
  resetNavigationStack('')
  const auth = useAuthStore()
  auth.token.value = ''
  auth.user.value = null
  sessionStorage.removeItem(BANK_LIST_QUERY_KEY)
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

describe('AppLayout second-level back control', () => {
  it('renders a back control on bank-detail and navigates to banks', async () => {
    await mountLayout('/banks/b1')

    const back = wrapper.find('[data-testid="page-back"]')
    expect(back.exists()).toBe(true)
    expect(back.attributes('aria-label')).toBe(t('ep.common.back_to_banks'))
    // The mobile header swaps the brand mark for the icon-only control.
    expect(wrapper.find('[data-testid="page-back-mobile"]').exists()).toBe(true)
    expect(wrapper.find('.mobile-top .brand-mark').exists()).toBe(false)

    await back.trigger('click')
    await flushPromises()
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/banks')
  })

  it('renders no back control on first-level pages', async () => {
    await mountLayout('/')
    expect(wrapper.find('[data-testid="page-back"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="page-back-mobile"]').exists()).toBe(false)
  })

  it('restores the stored bank-list query when returning to banks', async () => {
    const stored = { q: 'algebra', category: 'math', sort: 'recent', view: 'recycle' }
    sessionStorage.setItem(BANK_LIST_QUERY_KEY, JSON.stringify(stored))
    await mountLayout('/banks/b1')

    const pushSpy = vi.spyOn(wrapper.vm.$router, 'push')
    await wrapper.find('[data-testid="page-back"]').trigger('click')

    expect(pushSpy).toHaveBeenCalledTimes(1)
    expect(pushSpy).toHaveBeenCalledWith({ name: 'banks', query: stored })
    // The label stays the shared "back to banks" copy; the stored state does
    // not leak into target resolution.
    expect(wrapper.find('[data-testid="page-back"]').attributes('aria-label')).toBe(t('ep.common.back_to_banks'))
  })

  it('pushes an empty query when the bank list has no stored state', async () => {
    sessionStorage.removeItem(BANK_LIST_QUERY_KEY)
    await mountLayout('/banks/b1')

    const pushSpy = vi.spyOn(wrapper.vm.$router, 'push')
    await wrapper.find('[data-testid="page-back"]').trigger('click')

    expect(pushSpy).toHaveBeenCalledTimes(1)
    expect(pushSpy).toHaveBeenCalledWith({ name: 'banks', query: {} })
  })

  it('uses in-app history when the page was reached from another app page', async () => {
    await mountLayout('/banks')
    const router = wrapper.vm.$router
    await router.push('/banks/b1')
    await flushPromises()
    expect(canGoBack.value).toBe(true)

    const backSpy = vi.spyOn(router, 'back').mockImplementation(() => {})
    const pushSpy = vi.spyOn(router, 'push')
    await wrapper.find('[data-testid="page-back"]').trigger('click')

    expect(backSpy).toHaveBeenCalledTimes(1)
    expect(pushSpy).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="page-back"]').attributes('aria-label')).toBe(t('ep.common.back'))
  })

  it('names the bank in the crumb instead of repeating the area label', async () => {
    listBanks.mockResolvedValueOnce({ banks: [{ id: 'b1', name: '软考真题' }] })
    await mountLayout('/banks/b1')
    await flushPromises()

    const crumb = wrapper.find('.crumb')
    expect(crumb.text()).toContain('软考真题')
    expect(wrapper.find('.mobile-top .mt-title').text()).toBe('软考真题')
    expect(document.title).toContain('软考真题')
  })
})
