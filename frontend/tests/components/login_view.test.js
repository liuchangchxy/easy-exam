import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LoginView from '../../src/views/LoginView.vue'

vi.mock('../../src/api/auth', () => ({
  register: vi.fn(),
  login: vi.fn(),
}))

import { register, login } from '../../src/api/auth'

async function flush() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('LoginView registration validation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  async function mountRegistering() {
    const wrapper = mount(LoginView)
    await wrapper.find('.auth-switch button').trigger('click')
    await wrapper.find('#login-username').setValue('new_user')
    await wrapper.find('#login-password').setValue('password-123456')
    return wrapper
  }

  it('requires the confirmation password to be entered', async () => {
    const wrapper = await mountRegistering()
    await wrapper.find('form').trigger('submit')
    await flush()

    expect(register).not.toHaveBeenCalled()
    expect(wrapper.find('.notice.bad').exists()).toBe(true)
  })

  it('rejects a mismatched confirmation password', async () => {
    const wrapper = await mountRegistering()
    await wrapper.find('#login-confirm').setValue('password-654321')
    await wrapper.find('form').trigger('submit')
    await flush()

    expect(register).not.toHaveBeenCalled()
    expect(wrapper.find('.notice.bad').exists()).toBe(true)
  })

  it('registers and logs in when both passwords match', async () => {
    const wrapper = await mountRegistering()
    register.mockResolvedValue({ id: 'u1' })
    login.mockResolvedValue({ token: 'tk', user: { id: 'u1', username: 'new_user' } })
    await wrapper.find('#login-confirm').setValue('password-123456')
    await wrapper.find('form').trigger('submit')
    await flush()

    expect(register).toHaveBeenCalledWith('new_user', 'password-123456')
    expect(login).toHaveBeenCalledWith('new_user', 'password-123456')
    expect(wrapper.emitted('authenticated')).toBeTruthy()
  })

  it('rejects passwords shorter than eight characters before calling the API', async () => {
    const wrapper = mount(LoginView)
    await wrapper.find('#login-username').setValue('new_user')
    await wrapper.find('#login-password').setValue('short')
    await wrapper.find('form').trigger('submit')
    await flush()

    expect(login).not.toHaveBeenCalled()
    expect(wrapper.find('.notice.bad').exists()).toBe(true)
  })
})
