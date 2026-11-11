import { describe, it, expect, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import CommandPalette from '../../src/components/CommandPalette.vue'

const banks = [
  { id: 'bank-1', name: 'Bank One', category: 'Net', description: 'First', question_count: 4 },
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
  vi.restoreAllMocks()
})

describe('CommandPalette focus management', () => {
  it('traps Tab inside the modal and restores focus to the trigger on Escape', async () => {
    mountPalette()
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()

    await openPalette()
    expect(document.activeElement).toBe(wrapper.find('.cmd-palette-input').element)

    // Focusing something behind the modal and pressing Tab must pull focus back in.
    trigger.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    expect(document.activeElement).toBe(wrapper.find('.cmd-palette-input').element)

    // Escape is handled at document level, not only inside the backdrop.
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    await nextTick()
    expect(wrapper.find('.cmd-palette-modal').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger)
  })

  it('wraps Shift+Tab from the first focusable element to the last', async () => {
    mountPalette()
    await openPalette()
    const input = wrapper.find('.cmd-palette-input').element
    input.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }))
    const buttons = wrapper.find('.cmd-palette-modal').element.querySelectorAll('button')
    expect(document.activeElement).toBe(buttons[buttons.length - 1])
  })
})

describe('CommandPalette bank rows', () => {
  it('a row opens the bank while Start Practice stays an explicit secondary action', async () => {
    mountPalette()
    await openPalette()

    await wrapper.find('.cmd-bank-practice').trigger('click')
    expect(wrapper.emitted('practice-bank')).toHaveLength(1)
    expect(wrapper.emitted('select-bank')).toBeUndefined()
    await nextTick()
    expect(wrapper.find('.cmd-palette-modal').exists()).toBe(false)

    await openPalette()
    await wrapper.find('.bank-item').trigger('click')
    expect(wrapper.emitted('select-bank')).toHaveLength(1)
    expect(wrapper.emitted('practice-bank')).toHaveLength(1)
  })
})
