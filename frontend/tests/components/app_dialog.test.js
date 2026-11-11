import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AppDialog from '../../src/components/AppDialog.vue'
import { useDirtyGuard } from '../../src/composables/useDirtyGuard'
import { ref } from 'vue'

function mountDialog(props = {}, slots = {}) {
  return mount(AppDialog, {
    props: {
      open: true,
      title: 'Dialog title',
      ...props,
    },
    slots,
    attachTo: document.body,
  })
}

function pressKey(target, key, options = {}) {
  target.dispatchEvent(
    new KeyboardEvent('keydown', {
      key,
      bubbles: true,
      cancelable: true,
      ...options,
    })
  )
}

describe('AppDialog', () => {
  let wrapper

  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    wrapper = null
    vi.restoreAllMocks()
    document.body.innerHTML = ''
    document.body.style.overflow = ''
  })

  it('exposes the dialog contract and focuses the initialFocus selector', async () => {
    wrapper = mountDialog(
      { initialFocus: '.focus-target' },
      { default: '<button class="focus-target">First action</button><button class="other">Other</button>' }
    )
    await flushPromises()

    const panel = document.querySelector('.app-dialog-panel')
    expect(panel).not.toBeNull()
    expect(panel.getAttribute('role')).toBe('dialog')
    expect(panel.getAttribute('aria-modal')).toBe('true')
    expect(panel.getAttribute('aria-labelledby')).toBeTruthy()
    expect(document.getElementById(panel.getAttribute('aria-labelledby')).textContent).toBe('Dialog title')
    expect(document.activeElement).toBe(document.querySelector('.focus-target'))
  })

  it('emits close("escape") from a document-level listener even when focus is on body', async () => {
    wrapper = mountDialog({}, { default: '<button class="focus-target">First action</button>' })
    await flushPromises()

    document.body.setAttribute('tabindex', '-1')
    document.body.focus()
    expect(document.activeElement).toBe(document.body)

    pressKey(document.body, 'Escape')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('close')[0]).toEqual(['escape'])
  })

  it('does not emit escape when closeOnEscape is false', async () => {
    wrapper = mountDialog({ closeOnEscape: false })
    await flushPromises()

    pressKey(document.body, 'Escape')

    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('wraps Tab and Shift+Tab inside the dialog', async () => {
    wrapper = mountDialog(
      { initialFocus: '.first' },
      { default: '<button class="first">First</button><button class="last">Last</button>' }
    )
    await flushPromises()

    const closeButton = document.querySelector('.app-dialog-close')
    const first = document.querySelector('.first')
    const last = document.querySelector('.last')
    expect(document.activeElement).toBe(first)

    last.focus()
    pressKey(last, 'Tab')
    expect(document.activeElement).toBe(closeButton)

    pressKey(closeButton, 'Tab', { shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('emits close("button") from the header close control and close("backdrop") from the scrim', async () => {
    wrapper = mountDialog()
    await flushPromises()

    document.querySelector('.app-dialog-close').click()
    expect(wrapper.emitted('close').at(-1)).toEqual(['button'])

    document.querySelector('.app-dialog-scrim').click()
    expect(wrapper.emitted('close').at(-1)).toEqual(['backdrop'])
  })

  it('ignores scrim clicks when closeOnBackdrop is false', async () => {
    wrapper = mountDialog({ closeOnBackdrop: false })
    await flushPromises()

    document.querySelector('.app-dialog-scrim').click()

    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('restores focus to the previously focused trigger when closed', async () => {
    const trigger = document.createElement('button')
    trigger.className = 'dialog-trigger'
    trigger.textContent = 'Open'
    document.body.appendChild(trigger)
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    wrapper = mountDialog({}, { default: '<button class="inside">Inside</button>' })
    await flushPromises()
    expect(document.activeElement).not.toBe(trigger)
    expect(document.querySelector('.app-dialog-panel').contains(document.activeElement)).toBe(true)

    await wrapper.setProps({ open: false })
    await flushPromises()

    expect(document.activeElement).toBe(trigger)
  })

  it('locks body scroll while open and restores it on close', async () => {
    wrapper = mountDialog()
    await flushPromises()
    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.setProps({ open: false })
    await flushPromises()
    expect(document.body.style.overflow).toBe('')
  })
})

describe('useDirtyGuard', () => {
  it('closes immediately when the draft is clean', () => {
    const requestClose = vi.fn()
    const isDirty = ref(false)
    const guard = useDirtyGuard(() => isDirty.value, requestClose)

    const blocked = guard.confirmDiscard('cancel')

    expect(blocked).toBe(false)
    expect(guard.discardPromptOpen.value).toBe(false)
    expect(requestClose).toHaveBeenCalledTimes(1)
    expect(requestClose).toHaveBeenCalledWith('cancel')
  })

  it('blocks the close when the draft is dirty and only closes after acceptance', () => {
    const requestClose = vi.fn()
    const isDirty = ref(true)
    const guard = useDirtyGuard(isDirty, requestClose)

    const blocked = guard.confirmDiscard('backdrop')

    expect(blocked).toBe(true)
    expect(guard.discardPromptOpen.value).toBe(true)
    expect(requestClose).not.toHaveBeenCalled()

    guard.confirmDiscardAccept()

    expect(guard.discardPromptOpen.value).toBe(false)
    expect(requestClose).toHaveBeenCalledTimes(1)
    expect(requestClose).toHaveBeenCalledWith('backdrop')
  })

  it('cancelling the prompt keeps the editor open and clears the pending close', () => {
    const requestClose = vi.fn()
    const isDirty = ref(true)
    const guard = useDirtyGuard(isDirty, requestClose)

    guard.confirmDiscard()
    guard.confirmDiscardCancel()

    expect(guard.discardPromptOpen.value).toBe(false)
    expect(requestClose).not.toHaveBeenCalled()

    // Accepting afterwards must not replay a cancelled close request.
    guard.confirmDiscardAccept()
    expect(requestClose).not.toHaveBeenCalled()
  })
})
