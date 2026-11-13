import { describe, it, expect, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import CommandPalette from '../../src/components/CommandPalette.vue'
import LoginView from '../../src/views/LoginView.vue'
import { t } from '../../src/composables/useLocale.js'

vi.mock('../../src/api/auth', () => ({
  register: vi.fn(),
  login: vi.fn(),
}))

const banks = [
  { id: 'bank-1', name: 'Bank One', category: 'Net', description: 'First', question_count: 4 },
  { id: 'bank-2', name: 'Bank Two', category: 'Db', description: 'Second', question_count: 2 },
]

const commands = [
  { id: 'today', title: 'Today', icon: 'home', action: () => {} },
]

let wrapper = null

function mountPalette() {
  wrapper = mount(CommandPalette, {
    attachTo: document.body,
    props: { banks, commands },
  })
  return wrapper
}

async function openPalette() {
  wrapper.vm.open()
  await nextTick()
  await nextTick()
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  document.body.style.overflow = ''
  document.body.style.paddingRight = ''
  vi.restoreAllMocks()
})

describe('CommandPalette combobox semantics', () => {
  it('exposes a combobox driving a listbox of options', async () => {
    mountPalette()
    await openPalette()

    const input = wrapper.find('.cmd-palette-input')
    expect(input.attributes('role')).toBe('combobox')
    expect(input.attributes('aria-expanded')).toBe('true')
    expect(input.attributes('aria-autocomplete')).toBe('list')
    expect(input.attributes('aria-label')).toBe(t('commands.search_placeholder'))

    const listboxId = input.attributes('aria-controls')
    expect(listboxId).toBe('cmd-palette-listbox')
    const listbox = wrapper.find(`#${listboxId}`)
    expect(listbox.exists()).toBe(true)
    expect(listbox.attributes('role')).toBe('listbox')

    const options = wrapper.findAll('[role="option"]')
    expect(options).toHaveLength(banks.length + commands.length)
    options.forEach(option => expect(option.attributes('id')).toBeTruthy())
    expect(new Set(options.map(option => option.attributes('id'))).size).toBe(options.length)
  })

  it('points aria-activedescendant at the active option and moves with the arrow keys', async () => {
    mountPalette()
    await openPalette()

    const input = wrapper.find('.cmd-palette-input')
    expect(input.attributes('aria-activedescendant')).toBe('cmd-palette-opt-bank-0')
    expect(wrapper.find('#cmd-palette-opt-bank-0').attributes('aria-selected')).toBe('true')

    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe('cmd-palette-opt-bank-1')
    expect(wrapper.find('#cmd-palette-opt-bank-0').attributes('aria-selected')).toBe('false')
    expect(wrapper.find('#cmd-palette-opt-bank-1').attributes('aria-selected')).toBe('true')

    // Arrow navigation crosses from the bank group into the action group.
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe('cmd-palette-opt-action-0')

    // Up moves back to the previous option.
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe('cmd-palette-opt-bank-1')
  })

  it('runs the active option on Enter and closes on Escape', async () => {
    mountPalette()
    await openPalette()

    await wrapper.find('.cmd-palette-input').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('select-bank')).toHaveLength(1)
    expect(wrapper.find('.cmd-palette-modal').exists()).toBe(false)

    await openPalette()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect(wrapper.find('.cmd-palette-modal').exists()).toBe(false)
  })

  it('locks background scrolling while open and restores it on close', async () => {
    mountPalette()
    document.body.style.overflow = 'auto'

    await openPalette()
    expect(document.body.style.overflow).toBe('hidden')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect(document.body.style.overflow).toBe('auto')
  })
})

describe('LoginView password visibility toggle', () => {
  it('is keyboard reachable and exposes an accessible name + aria-pressed', async () => {
    wrapper = mount(LoginView, { attachTo: document.body })
    const toggle = wrapper.find('.auth-eye')

    expect(toggle.element.tagName).toBe('BUTTON')
    // The old `tabindex="-1"` made the toggle unreachable by Tab; no override now.
    expect(toggle.attributes('tabindex')).toBeUndefined()
    expect(toggle.attributes('aria-pressed')).toBe('false')
    expect(toggle.attributes('aria-label')).toBe(t('ep.auth.show_password'))
    expect(toggle.text()).toBe(t('ep.auth.show_password'))

    toggle.element.focus()
    expect(document.activeElement).toBe(toggle.element)
  })

  it('toggles the password input type and its pressed state', async () => {
    wrapper = mount(LoginView)
    const toggle = wrapper.find('.auth-eye')
    const password = wrapper.find('#login-password')

    expect(password.attributes('type')).toBe('password')
    await toggle.trigger('click')
    expect(password.attributes('type')).toBe('text')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    expect(toggle.attributes('aria-label')).toBe(t('ep.auth.hide_password'))
    expect(toggle.attributes('aria-controls')).toBe('login-password')

    await toggle.trigger('click')
    expect(password.attributes('type')).toBe('password')
    expect(toggle.attributes('aria-pressed')).toBe('false')
  })

  it('declares password-manager autocomplete hints for sign-in and registration', async () => {
    wrapper = mount(LoginView)
    expect(wrapper.find('#login-username').attributes('autocomplete')).toBe('username')
    expect(wrapper.find('#login-password').attributes('autocomplete')).toBe('current-password')

    await wrapper.find('.auth-switch button').trigger('click')
    expect(wrapper.find('#login-password').attributes('autocomplete')).toBe('new-password')
    expect(wrapper.find('#login-confirm').attributes('autocomplete')).toBe('new-password')
  })
})
