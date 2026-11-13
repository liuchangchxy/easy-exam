import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import ChangePasswordModal from '../../src/components/ChangePasswordModal.vue'
import { t } from '../../src/composables/useLocale.js'

vi.mock('../../src/api/auth', () => ({
  changePassword: vi.fn(),
}))

import { changePassword } from '../../src/api/auth'

// AppDialog teleports to <body>; stubbing Teleport keeps the markup inside
// the attached wrapper so focus assertions stay deterministic.
const mountOptions = { global: { stubs: { teleport: true } } }

enableAutoUnmount(afterEach)

function pressKey(target, key, options = {}) {
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...options })
  )
}

describe('ChangePasswordModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    document.body.style.overflow = ''
  })

  it('moves focus to the current-password field, locks scroll and restores focus on close', async () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()

    const wrapper = mount(ChangePasswordModal, {
      props: { token: 't1' },
      attachTo: document.body,
      ...mountOptions,
    })
    await flushPromises()

    const panel = wrapper.find('.app-dialog-panel')
    expect(panel.exists()).toBe(true)
    expect(document.activeElement).toBe(wrapper.find('#change-pwd-old').element)
    expect(panel.element.contains(document.activeElement)).toBe(true)
    expect(document.body.style.overflow).toBe('hidden')

    wrapper.unmount()
    await flushPromises()

    expect(document.activeElement).toBe(trigger)
    expect(document.body.style.overflow).toBe('')
    trigger.remove()
  })

  it('wraps Tab and Shift+Tab inside the dialog', async () => {
    const wrapper = mount(ChangePasswordModal, {
      props: { token: 't1' },
      attachTo: document.body,
      ...mountOptions,
    })
    await flushPromises()

    const closeButton = wrapper.find('.app-dialog-close').element
    const submit = wrapper.find('button[type="submit"]').element
    expect(document.activeElement).toBe(wrapper.find('#change-pwd-old').element)

    submit.focus()
    pressKey(submit, 'Tab')
    expect(document.activeElement).toBe(closeButton)

    pressKey(closeButton, 'Tab', { shiftKey: true })
    expect(document.activeElement).toBe(submit)
  })

  it('emits close on Escape even when focus sits outside the dialog', async () => {
    const wrapper = mount(ChangePasswordModal, { props: { token: 't1' }, ...mountOptions })
    await flushPromises()

    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    expect(document.activeElement).toBe(document.body)

    pressKey(document.body, 'Escape')
    await flushPromises()

    expect(wrapper.emitted('close')).toBeTruthy()
    expect(wrapper.emitted('close').at(-1)).toEqual([])
  })

  it('keeps the existing form validation and payload', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = mount(ChangePasswordModal, { props: { token: 't1' }, ...mountOptions })
      await vi.advanceTimersByTimeAsync(0)

      await wrapper.find('#change-pwd-old').setValue('old-secret')
      await wrapper.find('#change-pwd-new').setValue('new-secret')
      await wrapper.find('#change-pwd-confirm').setValue('different-secret')
      await wrapper.find('form').trigger('submit')
      await vi.advanceTimersByTimeAsync(0)

      expect(changePassword).not.toHaveBeenCalled()
      expect(wrapper.find('.notice.bad').text()).toBe(t('ui.k0032'))

      changePassword.mockResolvedValue({ status: 'ok' })
      await wrapper.find('#change-pwd-confirm').setValue('new-secret')
      await wrapper.find('form').trigger('submit')
      await vi.advanceTimersByTimeAsync(0)

      expect(changePassword).toHaveBeenCalledWith('t1', 'old-secret', 'new-secret')
      expect(wrapper.emitted('success')).toBeTruthy()

      await vi.advanceTimersByTimeAsync(1200)
      expect(wrapper.emitted('close')).toBeTruthy()
      wrapper.unmount()
    } finally {
      vi.useRealTimers()
    }
  })
})
