import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ConfirmHost from '../../src/components/ConfirmHost.vue'
import ToastHost from '../../src/components/ToastHost.vue'
import {
  askConfirm,
  askNotice,
  resetConfirmPresenter,
  resetNoticePresenter,
  setConfirmPresenter,
  setNoticePresenter,
} from '../../src/composables/useConfirm.js'
import { clearToasts, useToast } from '../../src/composables/useToast.js'
import SettingsView from '../../src/views/SettingsView.vue'
import { setLocale } from '../../src/composables/useLocale.js'

enableAutoUnmount(afterEach)

vi.mock('../../src/api/ai', () => ({
  getAiConfig: vi.fn().mockResolvedValue({
    ai_provider: 'openai',
    ai_api_base: 'https://api.openai.com/v1',
    ai_model: 'gpt-4o-mini',
    ai_api_key: '',
    search_provider: 'open-webSearch',
    search_api_key: '',
    search_api_base: 'http://localhost:8000/v1/search',
    is_configured: false,
  }),
  updateAiConfig: vi.fn(),
  testAiConfig: vi.fn(),
}))

vi.mock('../../src/api/admin', () => ({
  listSessions: vi.fn().mockResolvedValue([]),
  revokeOtherSessions: vi.fn(),
}))

function pressEscape() {
  document.body.setAttribute('tabindex', '-1')
  document.body.focus()
  document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
}

describe('shared confirmation dialog', () => {
  let host

  beforeEach(() => {
    document.body.innerHTML = ''
    setLocale('zh-CN')
    resetConfirmPresenter()
    resetNoticePresenter()
    host = mount(ConfirmHost, { attachTo: document.body })
    setConfirmPresenter(options => host.vm.present(options))
  })

  afterEach(() => {
    resetConfirmPresenter()
    resetNoticePresenter()
    host = null
    document.body.innerHTML = ''
  })

  it('renders the editorial dialog and resolves true on the confirm button', async () => {
    const pending = askConfirm({ title: 'Delete this bank?', body: 'It moves to the recycle bin.', danger: true })
    await flushPromises()

    const panel = document.querySelector('[data-testid="confirm-dialog"]')
    expect(panel).not.toBeNull()
    expect(panel.textContent).toContain('Delete this bank?')
    expect(panel.textContent).toContain('It moves to the recycle bin.')
    expect(panel.querySelector('[data-testid="confirm-ok"]').classList.contains('btn-danger')).toBe(true)

    panel.querySelector('[data-testid="confirm-ok"]').click()
    await expect(pending).resolves.toBe(true)
    await flushPromises()
    expect(document.querySelector('[data-testid="confirm-dialog"]')).toBeNull()
  })

  it('resolves false when the quiet cancel button is used', async () => {
    const pending = askConfirm({ title: 'Delete this bank?' })
    await flushPromises()

    document.querySelector('[data-testid="confirm-cancel"]').click()
    await expect(pending).resolves.toBe(false)
  })

  it('resolves false on Escape and on a backdrop click', async () => {
    const escaped = askConfirm({ title: 'Archive this bank?' })
    await flushPromises()
    pressEscape()
    await expect(escaped).resolves.toBe(false)
    await flushPromises()

    const backdrop = askConfirm({ title: 'Archive this bank?' })
    await flushPromises()
    document.querySelector('.app-dialog-scrim').click()
    await expect(backdrop).resolves.toBe(false)
  })

  it('falls back to the native confirm with the title alone when no presenter is registered', async () => {
    resetConfirmPresenter()
    const nativeConfirm = vi.fn(() => true)
    vi.stubGlobal('confirm', nativeConfirm)
    try {
      await expect(askConfirm({ title: 'Leave bank?', body: 'ignored by the fallback' })).resolves.toBe(true)
      expect(nativeConfirm).toHaveBeenCalledWith('Leave bank?')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('routes askNotice through the presenter and falls back to alert(title)', async () => {
    const seen = []
    setNoticePresenter(options => seen.push(options.title))
    askNotice({ title: 'Could not copy', body: 'detail' })
    expect(seen).toEqual(['Could not copy'])

    resetNoticePresenter()
    const nativeAlert = vi.fn()
    vi.stubGlobal('alert', nativeAlert)
    try {
      askNotice({ title: 'Could not copy' })
      expect(nativeAlert).toHaveBeenCalledWith('Could not copy')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

describe('SettingsView uses the shared confirm before signing out', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    setLocale('zh-CN')
    resetConfirmPresenter()
  })

  afterEach(() => {
    resetConfirmPresenter()
    document.body.innerHTML = ''
  })

  it('asks before emitting logout and emits only after the dialog accepts', async () => {
    const host = mount(ConfirmHost, { attachTo: document.body })
    setConfirmPresenter(options => host.vm.present(options))

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/settings', name: 'settings', component: SettingsView }],
    })
    await router.push('/settings?section=account')
    await router.isReady()

    const wrapper = mount(SettingsView, {
      props: { token: 't1' },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    const signOut = wrapper.findAll('button').find(button => button.text().includes('退出登录'))
    await signOut.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('logout')).toBeUndefined()
    const panel = document.querySelector('[data-testid="confirm-dialog"]')
    expect(panel).not.toBeNull()
    expect(panel.textContent).toContain('确定要退出登录吗？')

    panel.querySelector('[data-testid="confirm-ok"]').click()
    await flushPromises()
    expect(wrapper.emitted('logout')).toHaveLength(1)
  })
})

describe('shared toast queue', () => {
  beforeEach(() => {
    clearToasts()
  })

  afterEach(() => {
    clearToasts()
    document.body.innerHTML = ''
  })

  it('shows one queued toast at a time and advances when it is dismissed', async () => {
    const wrapper = mount(ToastHost, { attachTo: document.body })
    const { success, error } = useToast()

    success('Saved')
    error('Failed to save')
    await flushPromises()

    const toasts = document.querySelectorAll('#toast-root .toast')
    expect(toasts).toHaveLength(1)
    expect(toasts[0].textContent).toContain('Saved')
    expect(toasts[0].getAttribute('role')).toBe('status')

    document.querySelector('#toast-root .toast-dismiss').click()
    await flushPromises()

    const next = document.querySelectorAll('#toast-root .toast')
    expect(next).toHaveLength(1)
    expect(next[0].textContent).toContain('Failed to save')
    expect(next[0].classList.contains('bad')).toBe(true)
    wrapper.unmount()
  })

  it('dismisses the visible toast on its own after the timeout', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = mount(ToastHost, { attachTo: document.body })
      useToast().success('Saved')
      await flushPromises()
      expect(document.querySelectorAll('#toast-root .toast')).toHaveLength(1)

      await vi.advanceTimersByTimeAsync(4100)
      await flushPromises()
      expect(document.querySelectorAll('#toast-root .toast')).toHaveLength(0)
      wrapper.unmount()
    } finally {
      vi.useRealTimers()
    }
  })
})
