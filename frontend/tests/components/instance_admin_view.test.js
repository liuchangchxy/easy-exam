import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import InstanceAdminView from '../../src/views/InstanceAdminView.vue'
import { setLocale } from '../../src/composables/useLocale.js'

vi.mock('../../src/api/admin', () => ({
  listAdminUsers: vi.fn(),
  updateAdminUser: vi.fn(),
  resetUserPassword: vi.fn(),
  getAdminSettings: vi.fn(),
  updateAdminSettings: vi.fn(),
  listSessions: vi.fn(),
  revokeOtherSessions: vi.fn(),
}))

import {
  listAdminUsers,
  updateAdminUser,
  resetUserPassword,
  getAdminSettings,
  updateAdminSettings,
} from '../../src/api/admin'

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

const ADMIN = {
  id: 1,
  username: 'admin',
  is_admin: true,
  is_active: true,
  must_change_password: false,
  created_at: '2026-11-01T08:30:00Z',
  bank_count: 3,
}
const BOB = {
  id: 2,
  username: 'bob',
  is_admin: false,
  is_active: true,
  must_change_password: false,
  created_at: '2026-11-02T09:00:00Z',
  bank_count: 7,
}
const CAROL = {
  id: 3,
  username: 'carol',
  is_admin: false,
  is_active: false,
  must_change_password: true,
  created_at: '2026-11-03T10:15:00Z',
  bank_count: 0,
}

function mountView(user = ADMIN) {
  return mount(InstanceAdminView, {
    props: { token: 't1', user },
    attachTo: document.body,
  })
}

function rowButton(wrapper, userId, label) {
  const row = wrapper.find(`[data-user-id="${userId}"]`)
  const button = row.findAll('button').find(item => item.text().includes(label))
  if (!button) throw new Error(`button "${label}" not found for user ${userId}`)
  return button
}

describe('InstanceAdminView', () => {
  let wrapper

  beforeEach(() => {
    vi.clearAllMocks()
    setLocale('zh-CN')
    document.body.innerHTML = ''
    listAdminUsers.mockResolvedValue([ADMIN, BOB, CAROL])
    getAdminSettings.mockResolvedValue({ allow_registration: true })
    updateAdminUser.mockResolvedValue({})
    updateAdminSettings.mockResolvedValue({ allow_registration: false })
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('lists users with their instance role, status, join date and bank count', async () => {
    wrapper = mountView()
    await flush()

    expect(listAdminUsers).toHaveBeenCalledWith('t1')
    const bob = wrapper.find('[data-user-id="2"]')
    expect(bob.text()).toContain('bob')
    expect(bob.text()).toContain('2026-11-02')
    expect(bob.text()).toContain('7')

    const carol = wrapper.find('[data-user-id="3"]')
    expect(carol.text()).toContain('已禁用')
    expect(carol.text()).toContain('待改密')

    const adminRow = wrapper.find('[data-user-id="1"]')
    expect(adminRow.text()).toContain('管理员')
    expect(adminRow.find('.admin-self-tag').text()).toBe('我')
  })

  it('promotes a member through the role endpoint and reloads the list', async () => {
    wrapper = mountView()
    await flush()

    await rowButton(wrapper, 2, '设为管理员').trigger('click')
    await flush()

    expect(updateAdminUser).toHaveBeenCalledWith('t1', 2, { is_admin: true })
    expect(listAdminUsers).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('用户已更新')
  })

  it('disables and enables users through the status endpoint', async () => {
    wrapper = mountView()
    await flush()

    await rowButton(wrapper, 2, '禁用').trigger('click')
    await flush()
    expect(updateAdminUser).toHaveBeenLastCalledWith('t1', 2, { is_active: false })

    await rowButton(wrapper, 3, '启用').trigger('click')
    await flush()
    expect(updateAdminUser).toHaveBeenLastCalledWith('t1', 3, { is_active: true })
  })

  it('locks the self row and explains why', async () => {
    wrapper = mountView()
    await flush()

    const roleButton = rowButton(wrapper, 1, '取消管理员')
    const statusButton = rowButton(wrapper, 1, '禁用')

    expect(roleButton.element.disabled).toBe(true)
    expect(statusButton.element.disabled).toBe(true)
    expect(roleButton.attributes('title')).toBe('不能在这里修改自己的角色或状态。')
    expect(rowButton(wrapper, 1, '重置密码').element.disabled).toBe(false)
  })

  it('locks the last admin when the caller is not that account', async () => {
    listAdminUsers.mockResolvedValue([ADMIN])
    wrapper = mountView({ id: 99, username: 'observer', is_admin: true })
    await flush()

    const roleButton = rowButton(wrapper, 1, '取消管理员')
    const statusButton = rowButton(wrapper, 1, '禁用')
    expect(roleButton.element.disabled).toBe(true)
    expect(statusButton.element.disabled).toBe(true)
    expect(roleButton.attributes('title')).toBe('这是最后一位管理员，取消后会没有管理员。')
  })

  it('shows a reset temporary password once, in a dialog, and forgets it on close', async () => {
    resetUserPassword.mockResolvedValue({ temporary_password: 'Temp-9x!', user: BOB })
    wrapper = mountView()
    await flush()

    await rowButton(wrapper, 2, '重置密码').trigger('click')
    await flush()

    expect(resetUserPassword).toHaveBeenCalledWith('t1', 2)
    const panel = document.querySelector('.app-dialog-panel')
    expect(panel).not.toBeNull()
    expect(panel.textContent).toContain('Temp-9x!')
    expect(panel.textContent).toContain('只显示一次')
    expect(panel.querySelector('[data-testid="copy-temporary-password"]')).not.toBeNull()

    panel.querySelector('.app-dialog-foot .btn-primary').click()
    await flush()

    expect(document.querySelector('.app-dialog-panel')).toBeNull()
    expect(document.body.textContent).not.toContain('Temp-9x!')
  })

  it('saves the registration toggle explicitly and confirms it', async () => {
    wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="instance-tab-settings"]').trigger('click')
    const toggle = wrapper.find('[data-testid="allow-registration-toggle"]')
    expect(toggle.element.checked).toBe(true)

    await toggle.setValue(false)
    expect(updateAdminSettings).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="save-instance-settings"]').trigger('click')
    await flush()

    expect(updateAdminSettings).toHaveBeenCalledWith('t1', { allow_registration: false })
    expect(toggle.element.checked).toBe(false)
    expect(wrapper.text()).toContain('设置已保存')
  })

  it('keeps the previous registration value when saving fails', async () => {
    updateAdminSettings.mockRejectedValue({ status: 500, detail: 'boom' })
    wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="instance-tab-settings"]').trigger('click')
    const toggle = wrapper.find('[data-testid="allow-registration-toggle"]')
    await toggle.setValue(false)
    await wrapper.find('[data-testid="save-instance-settings"]').trigger('click')
    await flush()

    expect(toggle.element.checked).toBe(true)
    expect(wrapper.text()).toContain('保存失败')
    expect(wrapper.text()).not.toContain('设置已保存')
  })

  it('offers a retry when the user list fails to load', async () => {
    listAdminUsers.mockRejectedValueOnce({ status: 500 })
    wrapper = mountView()
    await flush()

    expect(wrapper.text()).toContain('用户列表读取失败')
    const retry = wrapper.findAll('button').find(button => button.text().includes('重试'))
    expect(retry).toBeTruthy()

    await retry.trigger('click')
    await flush()

    expect(listAdminUsers).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('bob')
  })

  it('offers a retry when instance settings fail to load', async () => {
    getAdminSettings.mockRejectedValueOnce({ status: 500 })
    wrapper = mountView()
    await flush()

    await wrapper.find('[data-testid="instance-tab-settings"]').trigger('click')
    expect(wrapper.text()).toContain('实例设置读取失败')

    getAdminSettings.mockResolvedValue({ allow_registration: false })
    const retry = wrapper.findAll('button').find(button => button.text().includes('重试'))
    await retry.trigger('click')
    await flush()

    expect(wrapper.find('[data-testid="allow-registration-toggle"]').element.checked).toBe(false)
  })
})
