import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { defineComponent, h, nextTick } from 'vue'
import {
  keyboardInsetFromViewport,
  useKeyboardInset,
  KEYBOARD_INSET_PROPERTY,
} from '../../src/composables/useKeyboardInset.js'
import AppLayout from '../../src/layouts/AppLayout.vue'
import { useAuthStore } from '../../src/stores/authStore'

vi.mock('../../src/api/auth', () => ({
  login: vi.fn(),
  currentUser: vi.fn(),
  logout: vi.fn().mockResolvedValue({}),
}))
vi.mock('../../src/api/banks', () => ({ listBanks: vi.fn().mockResolvedValue({ banks: [] }) }))
vi.mock('../../src/api/mistakes', () => ({ listDueMistakes: vi.fn().mockResolvedValue([]) }))
vi.mock('../../src/api/practice', () => ({
  startSession: vi.fn(),
  listActiveSessions: vi.fn().mockResolvedValue([]),
  abandonSession: vi.fn().mockResolvedValue({}),
  abandonAllSessions: vi.fn().mockResolvedValue({}),
}))
vi.mock('../../src/api/learning', () => ({ getLearningTrends: vi.fn().mockResolvedValue(null) }))

const Probe = defineComponent({
  setup() {
    useKeyboardInset()
    return () => h('div', { class: 'kb-probe' })
  },
})

function readInset() {
  return document.documentElement.style.getPropertyValue(KEYBOARD_INSET_PROPERTY)
}

function installViewport(height, layoutHeight = 800) {
  const viewport = new EventTarget()
  viewport.height = height
  viewport.offsetTop = 0
  const add = vi.spyOn(viewport, 'addEventListener')
  const remove = vi.spyOn(viewport, 'removeEventListener')
  Object.defineProperty(window, 'visualViewport', { configurable: true, value: viewport })
  Object.defineProperty(window, 'innerHeight', { configurable: true, writable: true, value: layoutHeight })
  return { viewport, add, remove }
}

afterEach(() => {
  delete window.visualViewport
  document.documentElement.style.removeProperty(KEYBOARD_INSET_PROPERTY)
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  const auth = useAuthStore()
  auth.token.value = ''
  auth.user.value = null
})

describe('responsive contract: keyboard inset', () => {
  it('computes the covered slice, clamped at zero, and degrades without visualViewport', () => {
    expect(keyboardInsetFromViewport(null, 800)).toBe(0)
    expect(keyboardInsetFromViewport({ height: 500, offsetTop: 0 }, 800)).toBe(300)
    expect(keyboardInsetFromViewport({ height: 500, offsetTop: 100 }, 800)).toBe(200)
    expect(keyboardInsetFromViewport({ height: 900, offsetTop: 0 }, 800)).toBe(0)
    expect(keyboardInsetFromViewport({ height: 0, offsetTop: 0 }, 0)).toBe(0)
  })

  it('publishes --kb-inset on resize and removes its listeners on unmount', async () => {
    const { viewport, add, remove } = installViewport(500)
    const wrapper = mount(Probe, { attachTo: document.body })
    await nextTick()

    expect(add).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(add).toHaveBeenCalledWith('scroll', expect.any(Function))
    expect(readInset()).toBe('300px')

    viewport.height = 200
    viewport.dispatchEvent(new Event('resize'))
    await nextTick()
    expect(readInset()).toBe('600px')

    wrapper.unmount()
    expect(remove).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(remove).toHaveBeenCalledWith('scroll', expect.any(Function))
    expect(readInset()).toBe('')
  })

  it('publishes 0 when the browser has no visualViewport', async () => {
    const wrapper = mount(Probe, { attachTo: document.body })
    await nextTick()
    expect(readInset()).toBe('0px')
    wrapper.unmount()
  })
})

describe('responsive contract: shell logout', () => {
  it('asks before calling auth logout and cancelling keeps the session', async () => {
    const Empty = { template: '<div />' }
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: Empty },
        { path: '/banks', name: 'banks', component: Empty },
        { path: '/settings', name: 'settings', component: Empty },
      ],
    })
    await router.push('/')
    await router.isReady()

    const confirmSpy = vi.fn().mockReturnValue(false)
    vi.stubGlobal('confirm', confirmSpy)

    const auth = useAuthStore()
    auth.token.value = 'test-token'
    auth.user.value = { username: 'alice', is_admin: false }

    const wrapper = mount(AppLayout, { global: { plugins: [router] }, attachTo: document.body })
    await nextTick()

    await wrapper.find('.topbar [data-account-trigger]').trigger('click')
    await wrapper.find('.account-menu .popover-action.is-danger').trigger('click')
    await flushPromises()

    // The shell still asks through the platform confirm; the shared dialog
    // seam (useConfirm) swaps the presenter without changing this contract.
    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(confirmSpy.mock.calls[0][0]).toBeTruthy()
    expect(auth.token.value).toBe('test-token')

    confirmSpy.mockReturnValue(true)
    // Cancelling leaves the account menu open, so the same item is right there.
    await wrapper.find('.account-menu .popover-action.is-danger').trigger('click')
    await flushPromises()
    expect(auth.token.value).toBe('')

    wrapper.unmount()
  })
})
