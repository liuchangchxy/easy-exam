<template>
  <div class="manage-page instance-admin-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.admin.eyebrow') }}</div>
        <h1 class="page-title">{{ t('ep.admin.title') }}</h1>
        <p class="page-sub">{{ t('ep.admin.sub') }}</p>
      </div>
    </div>

    <div class="tabs instance-admin-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab"
        :class="{ 'is-active': activeTab === tab.key }"
        :data-testid="'instance-tab-' + tab.key"
        @click="activeTab = tab.key"
      >
        {{ t(tab.label) }}
      </button>
    </div>

    <!-- Users -->
    <section v-if="activeTab === 'users'" class="instance-panel">
      <div class="settings-section-head instance-section-head">
        <h2>{{ t('ep.admin.tab_users') }}</h2>
        <p>{{ t('ep.admin.users_note') }}</p>
      </div>

      <div v-if="usersLoading" class="instance-loading" role="status">
        <span class="spinner" aria-hidden="true"></span>
        <span>{{ t('ep.admin.loading') }}</span>
      </div>

      <div v-else-if="usersError" class="notice bad instance-notice" role="alert">
        <LinearIcon name="alert" :size="15" />
        <span>{{ t('ep.admin.users_load_failed') }}</span>
        <button type="button" class="btn btn-sm" @click="loadUsers()">{{ t('ep.common.retry') }}</button>
      </div>

      <div v-else-if="!users.length" class="empty">
        <div class="empty-mark"><LinearIcon name="users" :size="26" /></div>
        <div class="empty-title">{{ t('ep.admin.users_empty') }}</div>
        <div class="empty-desc">{{ t('ep.admin.users_empty_hint') }}</div>
      </div>

      <div v-else class="mtable-wrap">
        <table class="mtable admin-users-table">
          <thead>
            <tr>
              <th class="admin-col-user">{{ t('ep.admin.col_username') }}</th>
              <th class="admin-col-role">{{ t('ep.admin.col_role') }}</th>
              <th class="admin-col-status">{{ t('ep.admin.col_status') }}</th>
              <th class="admin-col-created">{{ t('ep.admin.col_created') }}</th>
              <th class="admin-col-banks">{{ t('ep.admin.col_banks') }}</th>
              <th class="admin-col-actions">{{ t('ep.admin.col_actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in users" :key="row.id" class="mtable-row" :data-user-id="row.id">
              <td class="admin-col-user">
                <span class="admin-username">{{ row.username }}</span>
                <span v-if="isSelf(row)" class="tag brand admin-self-tag">{{ t('ep.admin.self_tag') }}</span>
              </td>
              <td class="admin-col-role">
                <span class="tag" :class="{ brand: row.is_admin }">{{ row.is_admin ? t('ep.admin.role_admin') : t('ep.admin.role_user') }}</span>
              </td>
              <td class="admin-col-status">
                <span class="tag" :class="row.is_active ? 'ok' : 'bad'">{{ row.is_active ? t('ep.admin.status_active') : t('ep.admin.status_disabled') }}</span>
                <span v-if="row.must_change_password" class="tag warn admin-must-change">{{ t('ep.admin.must_change') }}</span>
              </td>
              <td class="admin-col-created mono">{{ formatDate(row.created_at) }}</td>
              <td class="admin-col-banks mono">{{ row.bank_count ?? 0 }}</td>
              <td class="admin-col-actions">
                <div class="admin-row-actions">
                  <button
                    type="button"
                    class="btn btn-sm"
                    :disabled="isBusy(row) || roleLocked(row)"
                    :title="lockReason(row) || undefined"
                    @click="toggleAdmin(row)"
                  >
                    {{ row.is_admin ? t('ep.admin.action_remove_admin') : t('ep.admin.action_make_admin') }}
                  </button>
                  <button
                    type="button"
                    class="btn btn-sm"
                    :class="{ 'btn-danger': row.is_active }"
                    :disabled="isBusy(row) || statusLocked(row)"
                    :title="lockReason(row) || undefined"
                    @click="toggleActive(row)"
                  >
                    {{ row.is_active ? t('ep.admin.action_disable') : t('ep.admin.action_enable') }}
                  </button>
                  <button
                    type="button"
                    class="btn btn-sm"
                    :disabled="isBusy(row)"
                    @click="askResetPassword(row)"
                  >
                    {{ t('ep.admin.action_reset') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="actionNotice" class="notice ok instance-notice" role="status">
        <LinearIcon name="check" :size="15" />
        <span>{{ actionNotice }}</span>
      </div>
      <div v-if="actionError" class="notice bad instance-notice" role="alert">
        <LinearIcon name="alert" :size="15" />
        <span>{{ actionError }}</span>
      </div>
    </section>

    <!-- Instance settings -->
    <section v-else class="instance-panel">
      <div class="settings-section-head instance-section-head">
        <h2>{{ t('ep.admin.settings_title') }}</h2>
        <p>{{ t('ep.admin.settings_note') }}</p>
      </div>

      <div v-if="settingsLoading" class="instance-loading" role="status">
        <span class="spinner" aria-hidden="true"></span>
        <span>{{ t('ep.admin.loading') }}</span>
      </div>

      <div v-else-if="settingsLoadError" class="notice bad instance-notice" role="alert">
        <LinearIcon name="alert" :size="15" />
        <span>{{ t('ep.admin.settings_load_failed') }}</span>
        <button type="button" class="btn btn-sm" @click="loadSettings()">{{ t('ep.common.retry') }}</button>
      </div>

      <template v-else>
        <div class="setting-row instance-setting-row">
          <div class="setting-label">
            <div class="setting-name">{{ t('ep.admin.allow_registration') }}</div>
            <div class="setting-desc">{{ t('ep.admin.allow_registration_desc') }}</div>
          </div>
          <label class="admin-switch">
            <input
              v-model="allowRegistrationDraft"
              type="checkbox"
              data-testid="allow-registration-toggle"
              :disabled="settingsSaving"
            />
            <span>{{ allowRegistrationDraft ? t('ep.admin.registration_on') : t('ep.admin.registration_off') }}</span>
          </label>
        </div>

        <div class="notice info instance-notice">
          <LinearIcon name="info" :size="15" />
          <span>{{ t('ep.admin.registration_closed_note') }}</span>
        </div>

        <div class="settings-actions instance-settings-actions">
          <button
            type="button"
            class="btn btn-primary"
            data-testid="save-instance-settings"
            :disabled="settingsSaving || !settingsDirty"
            @click="saveSettings"
          >
            {{ settingsSaving ? t('ep.admin.saving') : t('ep.admin.save') }}
          </button>
          <span v-if="settingsSaved" class="settings-saved" role="status">{{ t('ep.admin.saved') }}</span>
          <span v-if="settingsSaveError" class="settings-saved is-error" role="alert">{{ settingsSaveError }}</span>
        </div>
      </template>
    </section>

    <!-- The temporary password lives only in this component's memory. -->
    <AppDialog
      :open="Boolean(temporaryPassword)"
      :title="t('ep.admin.reset_title')"
      panel-class="instance-reset-dialog"
      @close="closeResetDialog"
    >
      <p class="reset-for">{{ t('ep.admin.reset_for', { username: resetUsername }) }}</p>
      <div class="reset-password-row">
        <code class="reset-password">{{ temporaryPassword }}</code>
        <button type="button" class="btn btn-sm" data-testid="copy-temporary-password" @click="copyTemporaryPassword">
          <LinearIcon name="copy" :size="14" />
          {{ copied ? t('ep.admin.reset_copied') : t('ep.admin.reset_copy') }}
        </button>
      </div>
      <div class="notice warn reset-warning">
        <LinearIcon name="shield" :size="15" />
        <span>{{ t('ep.admin.reset_warning') }}</span>
      </div>
      <template #foot>
        <button type="button" class="btn btn-primary" @click="closeResetDialog">{{ t('ep.admin.reset_close') }}</button>
      </template>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppDialog from '../components/AppDialog.vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import {
  getAdminSettings,
  listAdminUsers,
  resetUserPassword,
  updateAdminSettings,
  updateAdminUser,
} from '../api/admin'

const props = defineProps({
  token: { type: String, default: '' },
  user: { type: Object, default: null },
})

const { t } = useLocale()

const tabs = [
  { key: 'users', label: 'ep.admin.tab_users' },
  { key: 'settings', label: 'ep.admin.tab_settings' },
]
const activeTab = ref('users')

// Users
const users = ref([])
const usersLoading = ref(true)
const usersError = ref(false)
const actionError = ref('')
const actionNotice = ref('')
const busyUserId = ref(null)

// Instance settings: the draft is separate from the saved value so a failed
// save can never leave the toggle claiming a state the server never accepted.
const settingsLoading = ref(true)
const settingsLoadError = ref(false)
const settingsSaving = ref(false)
const settingsSaved = ref(false)
const settingsSaveError = ref('')
const savedAllowRegistration = ref(false)
const allowRegistrationDraft = ref(false)

// Reset-password dialog
const temporaryPassword = ref('')
const resetUsername = ref('')
const copied = ref(false)

const currentUserId = computed(() => (props.user?.id == null ? '' : String(props.user.id)))
const adminCount = computed(() => users.value.filter(row => row.is_admin).length)
const settingsDirty = computed(() => allowRegistrationDraft.value !== savedAllowRegistration.value)

function isSelf(row) {
  return currentUserId.value !== '' && String(row.id) === currentUserId.value
}

// The backend refuses to demote or disable the last admin; mirror that rule so
// the button is never clickable into a guaranteed 400.
function isLastAdmin(row) {
  return Boolean(row.is_admin) && adminCount.value <= 1
}

function roleLocked(row) {
  return isSelf(row) || isLastAdmin(row)
}

function statusLocked(row) {
  return isSelf(row) || isLastAdmin(row)
}

function lockReason(row) {
  if (isSelf(row)) return t('ep.admin.hint_self')
  if (isLastAdmin(row)) return t('ep.admin.hint_last_admin')
  return ''
}

function isBusy(row) {
  return busyUserId.value === row.id
}

function formatDate(value) {
  if (!value) return '—'
  const text = String(value)
  const parsed = new Date(text)
  if (Number.isNaN(parsed.getTime())) return text
  return parsed.toISOString().replace('T', ' ').slice(0, 16)
}

async function loadUsers({ silent = false } = {}) {
  if (!silent) {
    usersLoading.value = true
    usersError.value = false
  }
  try {
    const rows = await listAdminUsers(props.token)
    users.value = Array.isArray(rows) ? rows : []
    usersError.value = false
  } catch (_) {
    if (silent) {
      actionError.value = t('ep.admin.users_load_failed')
    } else {
      usersError.value = true
    }
  } finally {
    if (!silent) usersLoading.value = false
  }
}

async function loadSettings() {
  settingsLoading.value = true
  settingsLoadError.value = false
  try {
    const settings = await getAdminSettings(props.token)
    savedAllowRegistration.value = Boolean(settings?.allow_registration)
    allowRegistrationDraft.value = savedAllowRegistration.value
  } catch (_) {
    settingsLoadError.value = true
  } finally {
    settingsLoading.value = false
  }
}

async function runUserAction(row, patch) {
  if (isBusy(row)) return
  busyUserId.value = row.id
  actionError.value = ''
  actionNotice.value = ''
  try {
    await updateAdminUser(props.token, row.id, patch)
    await loadUsers({ silent: true })
    actionNotice.value = t('ep.admin.updated')
  } catch (err) {
    actionError.value = `${t('ep.admin.update_failed')}${err?.detail || err?.message || ''}`
  } finally {
    busyUserId.value = null
  }
}

function toggleAdmin(row) {
  if (roleLocked(row)) return
  return runUserAction(row, { is_admin: !row.is_admin })
}

function toggleActive(row) {
  if (statusLocked(row)) return
  return runUserAction(row, { is_active: !row.is_active })
}

async function askResetPassword(row) {
  if (isBusy(row)) return
  busyUserId.value = row.id
  actionError.value = ''
  actionNotice.value = ''
  try {
    const result = await resetUserPassword(props.token, row.id)
    temporaryPassword.value = result?.temporary_password || ''
    resetUsername.value = row.username
    copied.value = false
    if (!temporaryPassword.value) {
      actionError.value = t('ep.admin.reset_failed')
    }
  } catch (err) {
    actionError.value = `${t('ep.admin.reset_failed')}${err?.detail || err?.message || ''}`
  } finally {
    busyUserId.value = null
  }
}

function closeResetDialog() {
  temporaryPassword.value = ''
  resetUsername.value = ''
  copied.value = false
}

async function copyTemporaryPassword() {
  if (!temporaryPassword.value) return
  try {
    await navigator.clipboard.writeText(temporaryPassword.value)
    copied.value = true
  } catch (_) {
    copied.value = false
  }
}

async function saveSettings() {
  if (settingsSaving.value || !settingsDirty.value) return
  const previous = savedAllowRegistration.value
  const next = allowRegistrationDraft.value
  settingsSaving.value = true
  settingsSaved.value = false
  settingsSaveError.value = ''
  try {
    const updated = await updateAdminSettings(props.token, { allow_registration: next })
    const confirmed = typeof updated?.allow_registration === 'boolean' ? updated.allow_registration : next
    savedAllowRegistration.value = confirmed
    allowRegistrationDraft.value = confirmed
    settingsSaved.value = true
  } catch (err) {
    allowRegistrationDraft.value = previous
    settingsSaveError.value = `${t('ep.admin.save_failed')}${err?.detail || err?.message || ''}`
  } finally {
    settingsSaving.value = false
  }
}

onMounted(() => {
  loadUsers()
  loadSettings()
})
</script>

<style scoped>
.instance-admin-page { max-width: 1080px; }
.instance-admin-tabs { margin-top: 18px; }
.instance-section-head { margin-top: 22px; margin-bottom: 18px; }
.instance-section-head h2 {
  margin: 0; font-family: var(--font-serif); font-size: 22px; font-weight: 600; line-height: 1.3;
}
.instance-section-head p {
  margin: 6px 0 0; font-size: 12px; line-height: 1.7; color: var(--ink-3); max-width: 58ch;
}
.instance-panel { padding-top: 2px; }
.instance-notice { margin-top: 12px; }
.instance-loading {
  display: flex; align-items: center; gap: 8px;
  padding: 24px 0; font-size: 12.5px; color: var(--ink-3);
  border-top: 1px solid var(--line);
}

.mtable-wrap { overflow-x: auto; }
.mtable { width: 100%; border-collapse: collapse; table-layout: fixed; }
.mtable th {
  padding: 9px 10px; text-align: left;
  font-size: 12px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
  color: var(--ink-3); border-bottom: 1px solid var(--line); white-space: nowrap;
}
.mtable td {
  padding: 8px 10px; border-bottom: 1px solid var(--line);
  font-size: 12px; color: var(--ink-2); vertical-align: middle;
}
.mtable-row:hover { background: var(--surface-2); }
.admin-users-table .admin-col-user { width: 190px; }
.admin-users-table .admin-col-role { width: 120px; }
.admin-users-table .admin-col-status { width: 168px; }
.admin-users-table .admin-col-created { width: 140px; }
.admin-users-table .admin-col-banks { width: 76px; }
.admin-users-table .admin-col-actions { width: auto; }
.admin-users-table td.admin-col-created,
.admin-users-table td.admin-col-banks { white-space: nowrap; }
.admin-username { color: var(--ink); font-weight: 500; }
.admin-self-tag { margin-left: 6px; }
.admin-must-change { margin-left: 4px; }
.admin-row-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.admin-row-actions .btn { white-space: nowrap; }

.instance-setting-row {
  display: flex; align-items: center; justify-content: space-between; gap: 28px;
  padding: 16px 0; border-top: 1px solid var(--line);
}
.setting-label { min-width: 0; }
.setting-name { font-size: 13px; font-weight: 500; color: var(--ink); }
.setting-desc { margin-top: 3px; font-size: 12px; line-height: 1.65; color: var(--ink-3); max-width: 48ch; }
.admin-switch {
  display: inline-flex; align-items: center; gap: 8px; flex: none;
  font-size: 12px; color: var(--ink-2); cursor: pointer;
}
.admin-switch input { width: 15px; height: 15px; cursor: pointer; }
.instance-settings-actions {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--line);
}
.settings-saved { font-size: 12px; color: var(--ok); }
.settings-saved.is-error { color: var(--bad); }

.reset-for { margin: 0 0 12px; font-size: 12.5px; color: var(--ink-2); }
.reset-password-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.reset-password {
  flex: 1 1 220px; min-width: 0;
  padding: 10px 12px; border: 1px solid var(--line-strong); background: var(--surface-2);
  font-family: var(--font-mono); font-size: 14px; letter-spacing: .04em;
  overflow-wrap: anywhere;
}
.reset-warning { margin-top: 14px; }

@media (max-width: 760px) {
  .admin-users-table { min-width: 760px; }
  .instance-setting-row { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
