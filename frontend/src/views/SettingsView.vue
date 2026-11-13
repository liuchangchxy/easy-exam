<template>
  <div class="settings-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.nav.settings') }}</div>
        <h1 class="page-title">{{ t('ep.settings.title') }}</h1>
        <p class="page-sub">{{ t('ep.settings.sub') }}</p>
      </div>
    </div>

    <div class="settings-layout">
      <nav class="settings-nav" :aria-label="t('ep.settings.title')">
        <!-- Group headings are ordered visually by CSS `order`, so the six
             nav items keep their historic DOM order (index-based tests and
             keyboard order stay stable). -->
        <div
          v-for="group in navGroups"
          :key="group.key"
          class="settings-nav-group"
          :data-group="group.key"
          :style="{ order: group.order }"
          aria-hidden="true"
        >{{ t(group.label) }}</div>
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          class="settings-nav-item"
          :class="{ 'is-active': activeSection === item.key }"
          :style="{ order: item.order }"
          @click="onNavClick(item)"
        >
          <LinearIcon :name="item.icon" :size="14" />
          <span>{{ t(item.label) }}</span>
        </button>
      </nav>

      <div class="settings-body">
        <!-- Appearance -->
        <section v-if="activeSection === 'appearance'" class="settings-section">
          <div class="settings-section-head">
            <h2>{{ t('ep.settings.nav_appearance') }}</h2>
            <p>{{ t('ep.settings.theme_note') }}</p>
          </div>

          <div class="setting-row">
            <div class="setting-label">
              <div class="setting-name">{{ t('ep.settings.theme') }}</div>
              <div class="setting-desc">{{ t('ep.settings.theme_light_desc') }}</div>
            </div>
            <div class="segmented" role="radiogroup" :aria-label="t('ep.settings.theme')">
              <button type="button" class="segment" :class="{ 'is-active': mode === 'light' }" role="radio" :aria-checked="mode === 'light'" @click="setMode('light')">
                <LinearIcon name="sun" :size="14" />{{ t('ep.settings.theme_light') }}
              </button>
              <button type="button" class="segment" :class="{ 'is-active': mode === 'dark' }" role="radio" :aria-checked="mode === 'dark'" @click="setMode('dark')">
                <LinearIcon name="moon" :size="14" />{{ t('ep.settings.theme_dark') }}
              </button>
            </div>
          </div>

          <div class="setting-row setting-row-top settings-stack-row settings-palette-row">
            <div class="setting-label">
              <div class="setting-name">{{ t('ep.settings.palette') }}</div>
              <div class="setting-desc">{{ t('ep.settings.palette_note') }}</div>
            </div>
            <div class="palette-grid settings-palette-grid" role="radiogroup" :aria-label="t('ep.settings.palette')">
              <button
                v-for="id in palettes"
                :key="id"
                type="button"
                class="palette-option settings-palette-card"
                :class="{ 'is-active': palette === id }"
                role="radio"
                :aria-checked="palette === id"
                :aria-label="t(`ep.settings.palette_${id}`)"
                :data-palette="id"
                @click="setPalette(id)"
              >
                <span class="palette-swatch" :style="{ background: paletteSwatch(id).paper }">
                  <i
                    v-for="(color, stopIndex) in paletteSwatch(id).stops"
                    :key="stopIndex"
                    :style="{ background: color }"
                  ></i>
                </span>
                <span class="palette-name">
                  <span>{{ t(`ep.settings.palette_${id}`) }}</span>
                  <LinearIcon v-if="palette === id" name="check" :size="13" />
                </span>
              </button>
            </div>
          </div>

          <div class="setting-row setting-row-top settings-stack-row">
            <div class="setting-label">
              <div class="setting-name">{{ densityLabel }}</div>
              <div class="setting-desc">{{ densityNote }}</div>
            </div>
            <div class="settings-density-options" role="radiogroup" :aria-label="densityLabel">
              <button
                v-for="option in densityOptions"
                :key="option.key"
                type="button"
                class="settings-density-option"
                :class="{ 'is-active': density === option.key }"
                role="radio"
                :aria-checked="density === option.key"
                :data-density-option="option.key"
                @click="setDensity(option.key)"
              >
                <LinearIcon :name="option.icon" :size="14" />
                <span>{{ option.label }}</span>
              </button>
            </div>
          </div>

        </section>

        <!-- Language -->
        <section v-else-if="activeSection === 'language'" class="settings-section">
          <div class="settings-section-head">
            <h2>{{ t('ep.settings.nav_language') }}</h2>
            <p>{{ t('ep.settings.language') }}</p>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <div class="setting-name">{{ t('ep.settings.language') }}</div>
              <div class="setting-desc">{{ t('ep.settings.about_languages_value') }}</div>
            </div>
            <div class="segmented" role="radiogroup" :aria-label="t('ep.settings.language')">
              <button type="button" class="segment" :class="{ 'is-active': currentLocale === 'zh-CN' }" role="radio" :aria-checked="currentLocale === 'zh-CN'" @click="setLocale('zh-CN')">
                {{ t('ep.settings.lang_zh') }}
              </button>
              <button type="button" class="segment" :class="{ 'is-active': currentLocale === 'en-US' }" role="radio" :aria-checked="currentLocale === 'en-US'" @click="setLocale('en-US')">
                {{ t('ep.settings.lang_en') }}
              </button>
            </div>
          </div>
        </section>

        <!-- AI -->
        <section v-else-if="activeSection === 'ai'" class="settings-section">
          <div class="settings-section-head">
            <h2>{{ t('ep.settings.nav_ai') }}</h2>
            <p>{{ t('ep.settings.ai_note') }}</p>
          </div>

          <div class="notice" :class="aiConfigured ? 'ok' : 'info'" style="margin-bottom: 16px">
            <LinearIcon :name="aiConfigured ? 'check' : 'info'" :size="15" />
            <span>{{ aiConfigured ? t('ep.settings.ai_configured') : t('ep.settings.ai_unconfigured') }}</span>
          </div>

          <div class="settings-fields">
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_provider') }}</span>
              <select v-model="config.ai_provider" class="select" @change="saveField('ai_provider')">
                <option value="openai">{{ t('ep.settings.ai_provider_openai') }}</option>
                <option value="ollama">{{ t('ep.settings.ai_provider_ollama') }}</option>
              </select>
            </label>
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_base_url') }}</span>
              <input v-model.trim="config.ai_api_base" class="input" type="text" placeholder="https://api.openai.com/v1" @change="saveField('ai_api_base')" />
              <span class="hint">{{ t('ep.settings.default_hint') }}</span>
            </label>
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_model') }}</span>
              <input v-model.trim="config.ai_model" class="input" type="text" placeholder="gpt-4o-mini" @change="saveField('ai_model')" />
              <span class="hint">{{ t('ep.settings.default_hint') }}</span>
            </label>
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_key') }}</span>
              <input v-model="config.ai_api_key" class="input" type="password" :placeholder="t('ep.settings.ai_key_placeholder')" @change="saveField('ai_api_key')" />
              <span v-if="config.ai_api_key" class="hint">{{ t('ep.settings.ai_key_set') }}</span>
            </label>
          </div>

          <div class="notice info settings-note">
            <LinearIcon name="shield" :size="15" />
            <span>{{ t('ep.settings.ai_boundary') }}</span>
          </div>

          <div class="settings-actions">
            <span class="settings-hint">{{ t('ep.settings.auto_save_hint') }}</span>
            <button
              type="button"
              class="btn btn-sm"
              data-testid="ai-test"
              :disabled="aiTesting || savingAi"
              @click="testConnection('ai')"
            >
              <LinearIcon name="zap" :size="14" />{{ t('ep.settings.ai_test') }}
            </button>
            <span v-if="savingAi" class="settings-saved">{{ t('ep.settings.saving') }}</span>
            <span v-else-if="aiNotice" class="settings-saved" :class="{ 'is-error': aiError }">{{ aiNotice }}</span>
            <span v-if="aiTesting" class="settings-saved" role="status">{{ t('ep.settings.test_testing') }}</span>
            <span
              v-else-if="aiTestMessage"
              class="settings-saved"
              :class="{ 'is-error': aiTestFailed }"
              :role="aiTestFailed ? 'alert' : 'status'"
            >{{ aiTestMessage }}</span>
          </div>
        </section>

        <!-- Web check -->
        <section v-else-if="activeSection === 'web'" class="settings-section">
          <div class="settings-section-head">
            <h2>{{ t('ep.settings.nav_web') }}</h2>
            <p>{{ t('ep.settings.web_note') }}</p>
          </div>

          <div class="settings-fields">
            <label class="field">
              <span class="label">{{ t('ep.settings.web_provider') }}</span>
              <select v-model="config.search_provider" class="select" @change="saveField('search_provider')">
                <option value="open-webSearch">{{ t('ep.settings.web_on') }}</option>
                <option value="offline">{{ t('ep.settings.web_off') }}</option>
              </select>
            </label>
            <label v-if="config.search_provider !== 'offline'" class="field">
              <span class="label">{{ t('ep.settings.web_base_url') }}</span>
              <input v-model.trim="config.search_api_base" class="input" type="text" placeholder="http://localhost:8000/v1/search" @change="saveField('search_api_base')" />
              <span class="hint">{{ t('ep.settings.default_hint') }}</span>
            </label>
            <label v-if="config.search_provider !== 'offline'" class="field">
              <span class="label">{{ t('ep.settings.web_key') }}</span>
              <input v-model="config.search_api_key" class="input" type="password" :placeholder="t('ep.settings.ai_key_placeholder')" @change="saveField('search_api_key')" />
            </label>
          </div>

          <div class="settings-actions">
            <span class="settings-hint">{{ t('ep.settings.auto_save_hint') }}</span>
            <button
              type="button"
              class="btn btn-sm"
              data-testid="web-test"
              :disabled="webTesting || savingWeb"
              @click="testConnection('web')"
            >
              <LinearIcon name="zap" :size="14" />{{ t('ep.settings.ai_test') }}
            </button>
            <span v-if="savingWeb" class="settings-saved">{{ t('ep.settings.saving') }}</span>
            <span v-else-if="webNotice" class="settings-saved" :class="{ 'is-error': webError }">{{ webNotice }}</span>
            <span v-if="webTesting" class="settings-saved" role="status">{{ t('ep.settings.test_testing') }}</span>
            <span
              v-else-if="webTestMessage"
              class="settings-saved"
              :class="{ 'is-error': webTestFailed }"
              :role="webTestFailed ? 'alert' : 'status'"
            >{{ webTestMessage }}</span>
          </div>
        </section>

        <!-- Account -->
        <section v-else-if="activeSection === 'account'" class="settings-section">
          <div class="settings-section-head">
            <h2>{{ t('ep.settings.nav_account') }}</h2>
            <p>{{ t('ep.settings.account_note') }}</p>
          </div>

          <div class="account-block">
            <span class="avatar lg">{{ userInitial }}</span>
            <div class="account-main">
              <div class="account-name">{{ user?.username || t('ep.account.guest') }}</div>
              <div class="account-role">{{ user?.is_admin ? t('ep.role.admin') : t('ep.role.user') }}</div>
            </div>
          </div>

          <div class="sessions-block">
            <div class="sessions-head">
              <div>
                <h3 class="sessions-title">{{ t('ep.account.sessions_title') }}</h3>
                <p class="sessions-note">{{ t('ep.account.sessions_note') }}</p>
              </div>
              <button
                type="button"
                class="btn btn-sm"
                data-testid="logout-other-sessions"
                :disabled="sessionsLoading || sessionsBusy || !otherSessionCount"
                @click="requestLogoutOtherSessions"
              >
                <LinearIcon name="logout" :size="14" />
                {{ t('ep.account.sessions_logout_others') }}
              </button>
            </div>

            <div v-if="sessionsLoading" class="sessions-state" role="status">
              <span class="spinner" aria-hidden="true"></span>
              <span>{{ t('ep.account.sessions_loading') }}</span>
            </div>

            <div v-else-if="sessionsError" class="notice bad sessions-notice" role="alert">
              <LinearIcon name="alert" :size="15" />
              <span>{{ t('ep.account.sessions_load_failed') }}</span>
              <button type="button" class="btn btn-sm" @click="loadSessions">{{ t('ep.common.retry') }}</button>
            </div>

            <div v-else-if="!sessions.length" class="empty sessions-empty">
              <div class="empty-mark"><LinearIcon name="shield" :size="24" /></div>
              <div class="empty-title">{{ t('ep.account.sessions_empty') }}</div>
            </div>

            <div v-else class="mtable-wrap">
              <table class="mtable sessions-table">
                <thead>
                  <tr>
                    <th class="sessions-col-device">{{ t('ep.account.sessions_col_device') }}</th>
                    <th class="sessions-col-date">{{ t('ep.account.sessions_col_created') }}</th>
                    <th class="sessions-col-date">{{ t('ep.account.sessions_col_last_seen') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="session in sessions" :key="session.id" class="mtable-row">
                    <td class="sessions-col-device">
                      <span class="session-agent">{{ sessionLabel(session) }}</span>
                      <span v-if="session.current" class="tag brand sessions-current">{{ t('ep.account.sessions_current') }}</span>
                    </td>
                    <td class="sessions-col-date mono">{{ formatSessionDate(session.created_at) }}</td>
                    <td class="sessions-col-date mono">{{ formatSessionDate(session.last_seen_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="sessionsNotice" class="notice ok sessions-notice" role="status">
              <LinearIcon name="check" :size="15" />
              <span>{{ sessionsNotice }}</span>
            </div>
            <div v-if="sessionsActionError" class="notice bad sessions-notice" role="alert">
              <LinearIcon name="alert" :size="15" />
              <span>{{ sessionsActionError }}</span>
            </div>
          </div>

          <div class="settings-actions">
            <button type="button" class="btn" @click="showPasswordModal = true">
              <LinearIcon name="key" :size="14" />{{ t('ep.settings.change_password') }}
            </button>
            <button type="button" class="btn btn-danger" @click="requestLogout">
              <LinearIcon name="logout" :size="14" />{{ t('ep.settings.logout') }}
            </button>
          </div>

          <div class="notice info settings-note">
            <LinearIcon name="lock" :size="15" />
            <span>{{ t('ep.settings.privacy') }}</span>
          </div>
        </section>

        <!-- About -->
        <section v-else class="settings-section">
          <div class="settings-section-head">
            <h2>{{ t('ep.settings.nav_about') }}</h2>
            <p>{{ t('ep.settings.about_deployment_value') }}</p>
          </div>

          <div class="kv about-kv">
            <div class="kv-row"><span class="kv-key">{{ t('ep.settings.about_deployment') }}</span><span class="kv-val">{{ t('ep.settings.about_deployment_value') }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.settings.about_storage') }}</span><span class="kv-val">{{ t('ep.settings.about_storage_value') }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.settings.about_languages') }}</span><span class="kv-val">{{ t('ep.settings.about_languages_value') }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.settings.about_sync') }}</span><span class="kv-val">{{ t('ep.settings.about_sync_value') }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.settings.version_label') }}</span><span class="kv-val mono">v{{ appVersion }}</span></div>
          </div>
        </section>
      </div>
    </div>

    <ChangePasswordModal v-if="showPasswordModal" :token="token" @close="showPasswordModal = false" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import ChangePasswordModal from '../components/ChangePasswordModal.vue'
import { useLocale } from '../composables/useLocale.js'
import { useConfirm } from '../composables/useConfirm.js'
import { useToast } from '../composables/useToast.js'
import { useTheme } from '../composables/useTheme.js'
import { DENSITY_STORAGE_KEY, normalizeDensityPreference, restoreDensityPreference } from '../composables/density.js'
import { getAiConfig, updateAiConfig, testAiConfig } from '../api/ai'
import { listSessions, revokeOtherSessions } from '../api/admin'
import pkg from '../../package.json'

const props = defineProps({
  token: { type: String, default: '' },
  user: { type: Object, default: null },
})

const emit = defineEmits(['logout'])
const route = useRoute()
const router = useRouter()

const { t, locale: currentLocale, setLocale } = useLocale()
const { mode, setMode, palette, palettes, setPalette } = useTheme()
const { confirm: confirmAction } = useConfirm()
const toast = useToast()

const DEFAULT_SECTION = 'appearance'
const SECTION_QUERY = {
  appearance: 'appearance',
  language: 'language',
  ai: 'ai',
  web: 'network',
  account: 'account',
  about: 'about',
}
const QUERY_SECTION = Object.fromEntries(
  Object.entries(SECTION_QUERY).map(([key, query]) => [query, key])
)

function normalizeSection(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' && QUERY_SECTION[raw] ? QUERY_SECTION[raw] : DEFAULT_SECTION
}

const activeSection = ref(normalizeSection(route?.query?.section))

function selectSection(key) {
  const sectionKey = SECTION_QUERY[key] ? key : DEFAULT_SECTION
  const query = SECTION_QUERY[sectionKey]
  activeSection.value = sectionKey
  if (!router || !route) return
  if (route.query?.section === query) return
  router.push({ path: route.path, query: { ...(route.query || {}), section: query } })
}

// Instance administration is a route of its own, not a settings section, so it
// never enters SECTION_QUERY and never rewrites `?section=`.
function onNavClick(item) {
  if (item.route) {
    router.push({ name: item.route })
    return
  }
  selectSection(item.key)
}

watch(
  () => route?.query?.section,
  value => {
    activeSection.value = normalizeSection(value)
  }
)

function requestLogout() {
  return confirmAction({
    title: t('ep.settings.logout_confirm'),
    body: t('ep.settings.logout_body'),
    danger: true,
  }, () => emit('logout'))
}
const showPasswordModal = ref(false)
const appVersion = pkg.version
const density = ref('balanced')

// CSS `order` values keep the historic item DOM order while showing four
// groups: personal, collaboration/instance, operations, about.
const NAV_ITEM_ORDER = {
  appearance: 2,
  language: 3,
  account: 4,
  instance: 6,
  ai: 8,
  web: 9,
  about: 11,
}

const navItems = computed(() => {
  const items = [
    { key: 'appearance', label: 'ep.settings.nav_appearance', icon: 'sun' },
    { key: 'language', label: 'ep.settings.nav_language', icon: 'globe' },
    { key: 'ai', label: 'ep.settings.nav_ai', icon: 'cpu' },
    { key: 'web', label: 'ep.settings.nav_web', icon: 'link' },
    { key: 'account', label: 'ep.settings.nav_account', icon: 'user' },
    { key: 'about', label: 'ep.settings.nav_about', icon: 'info' },
  ]
  // Only instance admins ever see the admin console entry.
  if (props.user?.is_admin) {
    items.push({ key: 'instance', label: 'ep.settings.nav_instance', icon: 'users', route: 'instance-admin' })
  }
  return items.map(item => ({ ...item, order: NAV_ITEM_ORDER[item.key] }))
})

const navGroups = computed(() => [
  { key: 'personal', label: 'ep.settings.group_personal', order: 1 },
  { key: 'collab', label: 'ep.settings.group_collab', order: 5, adminOnly: true },
  { key: 'ops', label: 'ep.settings.group_ops', order: 7 },
  { key: 'about', label: 'ep.settings.group_about', order: 10 },
].filter(group => !group.adminOnly || props.user?.is_admin))

const PALETTE_SWATCHES = {
  editorial: { paper: '#f5f2ea', stops: ['#f5f2ea', '#fbf9f4', '#191b18', '#23554b'] },
  gruvbox: { paper: '#fbf1c7', stops: ['#fbf1c7', '#fff9e4', '#3c3836', '#af3a03'] },
  everforest: { paper: '#fdf6e3', stops: ['#fdf6e3', '#fffcf0', '#3d484d', '#4e6b3f'] },
  catppuccin: { paper: '#eff1f5', stops: ['#eff1f5', '#f7f8fb', '#4c4f69', '#8432e8'] },
}

function paletteSwatch(id) {
  return PALETTE_SWATCHES[id] || PALETTE_SWATCHES.editorial
}

const densityLabel = computed(() => currentLocale.value === 'en-US' ? 'Density' : '信息密度')
const densityNote = computed(() => currentLocale.value === 'en-US'
  ? 'Balanced for reading; dense for management and bulk review. Practice always uses the focused layout.'
  : '宽松适合阅读，紧凑适合管理与批量校对。练习页始终使用专注布局。')
const densityOptions = computed(() => currentLocale.value === 'en-US'
  ? [
      { key: 'balanced', label: 'Balanced', icon: 'list' },
      { key: 'dense', label: 'Dense', icon: 'grid' },
    ]
  : [
      { key: 'balanced', label: '宽松', icon: 'list' },
      { key: 'dense', label: '紧凑', icon: 'grid' },
    ])

function applyDensity(value, persist = true) {
  const next = normalizeDensityPreference(value)
  density.value = next
  if (typeof document !== 'undefined') document.documentElement.setAttribute('data-density', next)
  if (!persist) return
  try {
    globalThis.localStorage?.setItem(DENSITY_STORAGE_KEY, next)
  } catch {
    // Keep the in-page preference when storage is unavailable.
  }
}

function setDensity(value) {
  applyDensity(value)
}

function restoreDensity() {
  density.value = restoreDensityPreference()
}

const userInitial = computed(() => {
  const name = props.user?.username
  return name ? name.charAt(0).toUpperCase() : '?'
})

// Devices & sessions. Only the account section fetches them, and only when it
// is the visible section, so other settings stay a single AI-config call.
const sessions = ref([])
const sessionsLoading = ref(false)
const sessionsError = ref(false)
const sessionsBusy = ref(false)
const sessionsNotice = ref('')
const sessionsActionError = ref('')

const otherSessionCount = computed(() => sessions.value.filter(session => !session.current).length)

function formatSessionDate(value) {
  if (!value) return '—'
  const text = String(value)
  const parsed = new Date(text)
  if (Number.isNaN(parsed.getTime())) return text
  return parsed.toISOString().replace('T', ' ').slice(0, 16)
}

// A user agent is machine data, not prose: pick the readable product names and
// leave the raw string as the fallback.
function sessionLabel(session) {
  const ua = String(session?.user_agent || '').trim()
  if (!ua) return t('ep.account.sessions_unknown_device')
  const browser = ua.includes('Edg/') ? 'Edge'
    : ua.includes('OPR/') ? 'Opera'
      : ua.includes('Firefox/') ? 'Firefox'
        : ua.includes('Chrome/') ? 'Chrome'
          : ua.includes('Safari/') ? 'Safari'
            : ''
  const system = ua.includes('Windows') ? 'Windows'
    : ua.includes('Android') ? 'Android'
      : ua.includes('iPhone') || ua.includes('iPad') ? 'iOS'
        : ua.includes('Mac OS X') ? 'macOS'
          : ua.includes('Linux') ? 'Linux'
            : ''
  if (browser && system) return `${browser} · ${system}`
  if (browser) return browser
  if (system) return system
  return ua.length > 42 ? `${ua.slice(0, 42)}…` : ua
}

async function loadSessions() {
  if (!props.token) return
  sessionsLoading.value = true
  sessionsError.value = false
  sessionsActionError.value = ''
  try {
    const rows = await listSessions(props.token)
    sessions.value = Array.isArray(rows) ? rows : []
  } catch (_) {
    sessionsError.value = true
  } finally {
    sessionsLoading.value = false
  }
}

function requestLogoutOtherSessions() {
  if (!otherSessionCount.value) return
  return confirmAction({
    title: t('ep.account.sessions_logout_confirm'),
    body: t('ep.account.sessions_logout_body'),
    danger: true,
  }, logoutOtherSessions)
}

async function logoutOtherSessions() {
  sessionsBusy.value = true
  sessionsNotice.value = ''
  sessionsActionError.value = ''
  try {
    const result = await revokeOtherSessions(props.token)
    const count = Number(result?.revoked ?? 0)
    sessionsNotice.value = t('ep.account.sessions_revoked', { count })
    await loadSessions()
  } catch (err) {
    sessionsActionError.value = `${t('ep.account.sessions_logout_failed')}${err?.detail || err?.message || ''}`
  } finally {
    sessionsBusy.value = false
  }
}

watch(
  activeSection,
  value => {
    if (value === 'account') loadSessions()
  },
  { immediate: true }
)

const AI_FIELDS = ['ai_provider', 'ai_api_base', 'ai_model', 'ai_api_key']
const WEB_FIELDS = ['search_provider', 'search_api_base', 'search_api_key']

const config = ref({
  ai_provider: 'openai',
  ai_api_base: '',
  ai_model: '',
  ai_api_key: '',
  search_provider: 'open-webSearch',
  search_api_key: '',
  search_api_base: '',
})
// Last known server state, used to flush only genuinely pending field edits
// before a connection test.
const savedConfig = ref({ ...config.value })

const savingAi = ref(false)
const savingWeb = ref(false)
const aiNotice = ref('')
const webNotice = ref('')
const aiError = ref(false)
const webError = ref(false)
const aiConfigured = ref(false)
const aiTesting = ref(false)
const webTesting = ref(false)
const aiTestMessage = ref('')
const webTestMessage = ref('')
const aiTestFailed = ref(false)
const webTestFailed = ref(false)

async function loadConfig() {
  if (!props.token) return
  try {
    const res = await getAiConfig(props.token)
    aiConfigured.value = Boolean(res.is_configured)
    config.value = {
      ai_provider: res.ai_provider || 'openai',
      ai_api_base: res.ai_api_base ?? '',
      ai_model: res.ai_model ?? '',
      ai_api_key: res.ai_api_key || '',
      search_provider: res.search_provider || 'open-webSearch',
      search_api_key: res.search_api_key || '',
      search_api_base: res.search_api_base ?? '',
    }
    savedConfig.value = { ...config.value }
  } catch (err) {
    aiError.value = true
    aiNotice.value = `${t('ep.settings.ai_load_failed')}${err.detail || err.message || ''}`
  }
}

// A PATCH response may echo the whole row. Only the masked secret fields and
// the configured flag are trusted; echoing the other fields would clobber an
// edit the user is still typing.
function applyServerConfig(updated, savedKeys = []) {
  if (!updated || typeof updated !== 'object') return
  if (updated.is_configured !== undefined) aiConfigured.value = Boolean(updated.is_configured)
  for (const key of ['ai_api_key', 'search_api_key']) {
    if (!savedKeys.includes(key) || updated[key] === undefined) continue
    config.value[key] = updated[key] ?? ''
    savedConfig.value[key] = config.value[key]
  }
}

async function saveField(key) {
  if (!props.token) return
  const isWeb = WEB_FIELDS.includes(key)
  const saving = isWeb ? savingWeb : savingAi
  const notice = isWeb ? webNotice : aiNotice
  const error = isWeb ? webError : aiError
  saving.value = true
  notice.value = ''
  error.value = false
  if (isWeb) {
    webTestMessage.value = ''
    webTestFailed.value = false
  } else {
    aiTestMessage.value = ''
    aiTestFailed.value = false
  }
  try {
    const updated = await updateAiConfig(props.token, { [key]: config.value[key] })
    savedConfig.value[key] = config.value[key]
    applyServerConfig(updated, [key])
    // A field that saved itself is a transient confirmation, not page state.
    toast.success(t(isWeb ? 'ep.settings.web_saved' : 'ep.settings.ai_saved'))
  } catch (err) {
    error.value = true
    notice.value = err.detail || err.message
  } finally {
    saving.value = false
  }
}

async function flushPendingFields(kind) {
  const keys = (kind === 'web' ? WEB_FIELDS : AI_FIELDS)
    .filter(key => config.value[key] !== savedConfig.value[key])
  if (!keys.length) return false
  const payload = Object.fromEntries(keys.map(key => [key, config.value[key]]))
  const updated = await updateAiConfig(props.token, payload)
  for (const key of keys) savedConfig.value[key] = config.value[key]
  applyServerConfig(updated, keys)
  return true
}

async function testConnection(kind) {
  if (!props.token) return
  const isWeb = kind === 'web'
  const testing = isWeb ? webTesting : aiTesting
  if (testing.value) return
  const message = isWeb ? webTestMessage : aiTestMessage
  const failed = isWeb ? webTestFailed : aiTestFailed
  const notice = isWeb ? webNotice : aiNotice
  const error = isWeb ? webError : aiError
  testing.value = true
  message.value = ''
  failed.value = false
  try {
    // The endpoint must test what the user sees, so pending auto-saves run
    // first. If that write fails, do not claim a test result.
    if (await flushPendingFields(kind)) {
      error.value = false
      toast.success(t(isWeb ? 'ep.settings.web_saved' : 'ep.settings.ai_saved'))
    }
    const result = await testAiConfig(props.token, isWeb ? 'search' : 'ai')
    if (result?.ok) {
      message.value = t('ep.settings.test_success')
    } else {
      failed.value = true
      message.value = result?.message || t('ep.settings.test_failed')
    }
  } catch (err) {
    failed.value = true
    message.value = err?.detail || err?.message || t('ep.settings.test_failed')
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  restoreDensity()
  loadConfig()
})
</script>

<style scoped>
.settings-page { padding-top: 26px; }
.settings-layout { display: grid; grid-template-columns: 184px minmax(0, 1fr); gap: 48px; margin-top: 26px; align-items: start; }
.settings-nav { display: flex; flex-direction: column; border-top: 1px solid var(--line); padding-top: 8px; position: sticky; top: 66px; }
.settings-nav-group {
  margin: 12px 8px 2px; padding: 0;
  font-size: 10.5px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ink-4);
}
.settings-nav-group:first-of-type { margin-top: 0; }
.settings-nav-item {
  display: flex; align-items: center; gap: 9px; width: 100%; min-height: 36px;
  padding: 0 8px; border: 0; background: none; color: var(--ink-2);
  font-size: 12.5px; text-align: left; cursor: pointer;
}
.settings-nav-item:hover { background: var(--surface-2); color: var(--ink); }
.settings-nav-item.is-active { color: var(--brand); font-weight: 600; }
.settings-nav-item svg { color: var(--ink-4); }
.settings-nav-item.is-active svg { color: var(--brand); }

.settings-body { min-width: 0; max-width: 720px; }
.settings-section { border-top: 1px solid var(--line); padding-top: 18px; }
.settings-section-head { margin-bottom: 22px; }
.settings-section-head h2 { margin: 0; font-family: var(--font-serif); font-size: 22px; font-weight: 600; line-height: 1.3; }
.settings-section-head p { margin: 6px 0 0; font-size: 12px; line-height: 1.7; color: var(--ink-3); max-width: 58ch; }

.setting-row { display: flex; align-items: center; justify-content: space-between; gap: 28px; padding: 16px 0; border-top: 1px solid var(--line); }
.setting-row-top { align-items: flex-start; }
.setting-label { min-width: 0; }
.setting-name { font-size: 13px; font-weight: 500; color: var(--ink); }
.setting-desc { margin-top: 3px; font-size: 12px; line-height: 1.65; color: var(--ink-3); max-width: 44ch; }

.segmented { display: inline-flex; border: 1px solid var(--line-strong); flex: none; }
.segment {
  display: flex; align-items: center; gap: 6px; height: 32px; padding: 0 14px;
  border: 0; border-left: 1px solid var(--line); background: none;
  color: var(--ink-2); font-size: 12px; cursor: pointer;
}
.segment:first-child { border-left: 0; }
.segment:hover { background: var(--surface-2); color: var(--ink); }
.segment.is-active { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

.palette-grid { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
.palette-option {
  display: flex; align-items: center; gap: 7px; height: 34px; padding: 0 10px;
  border: 1px solid var(--line); background: none; color: var(--ink-2);
  font-size: 12px; cursor: pointer;
}
.palette-option:hover { border-color: var(--ink-4); }
.palette-option.is-active { border-color: var(--brand-line); color: var(--brand); }
.palette-swatch {
  width: 16px; height: 16px; flex: none; border: 1px solid var(--line-strong);
  display: inline-flex; align-items: center; justify-content: center;
}
.palette-swatch-dot { width: 7px; height: 7px; border-radius: 50%; }

.settings-stack-row { flex-direction: column; align-items: stretch; gap: 12px; }
.settings-palette-row .settings-palette-grid {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px; justify-content: stretch; width: 100%;
}
.settings-palette-card {
  display: flex; flex-direction: column; align-items: stretch; gap: 7px;
  height: auto; padding: 8px; text-align: left;
  border: 1px solid var(--line); border-radius: 4px; background: var(--surface);
}
.settings-palette-card:hover { border-color: var(--ink-4); }
.settings-palette-card.is-active { border-color: var(--ink); color: var(--ink); }
.settings-palette-card .palette-swatch {
  width: 100%; height: 46px; border: 1px solid var(--line); border-radius: 2px;
  overflow: hidden; display: flex; align-items: stretch; justify-content: stretch;
}
.settings-palette-card .palette-swatch i { flex: 1; display: block; }
.settings-palette-card .palette-name {
  display: flex; align-items: center; justify-content: space-between; gap: 6px;
  font-size: 12.5px; font-weight: 600;
}
.settings-density-options { display: flex; gap: 8px; flex-wrap: wrap; }
.settings-density-option {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 14px;
  border: 1px solid var(--line-strong); border-radius: 2px;
  background: none; color: var(--ink-2); font-size: 12px; cursor: pointer;
}
.settings-density-option:hover { background: var(--surface-2); color: var(--ink); }
.settings-density-option.is-active { background: var(--brand-soft); border-color: var(--brand-line); color: var(--brand); font-weight: 600; }

.settings-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 20px; }
.settings-note { margin-top: 20px; }
.settings-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--line); }
.settings-saved { font-size: 12px; color: var(--ok); }
.settings-saved.is-error { color: var(--bad); }
.settings-hint { margin-right: auto; font-size: 12px; color: var(--ink-3); }

.account-block { display: flex; align-items: center; gap: 14px; padding: 16px 0; border-top: 1px solid var(--line); }
.account-main { min-width: 0; }
.account-name { font-size: 15px; font-weight: 500; }
.account-role { margin-top: 2px; font-size: 12px; color: var(--ink-3); letter-spacing: .03em; }
.about-kv { border-top: 1px solid var(--line); }

.sessions-block { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--line); }
.sessions-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 14px; flex-wrap: wrap; margin-bottom: 8px;
}
.sessions-title { margin: 0; font-size: 13px; font-weight: 600; color: var(--ink); }
.sessions-note { margin: 4px 0 0; font-size: 12px; line-height: 1.65; color: var(--ink-3); max-width: 46ch; }
.sessions-state {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 0; font-size: 12px; color: var(--ink-3);
}
.sessions-notice { margin-top: 10px; }
.sessions-empty { padding: 24px 0; border-top: 0; }
.sessions-empty .empty-title { font-size: 13px; }

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
.sessions-table .sessions-col-device { width: auto; }
.sessions-table .sessions-col-date { width: 140px; }
.sessions-table td.sessions-col-date { white-space: nowrap; }
.session-agent { color: var(--ink); }
.sessions-current { margin-left: 6px; }

@media (max-width: 880px) {
  .settings-layout { grid-template-columns: minmax(0, 1fr); gap: 14px; }
  .settings-nav { display: flex; flex-direction: row; gap: 2px; overflow-x: auto; position: static; border-top: 0; border-bottom: 1px solid var(--line); padding: 0 0 8px; }
  .settings-nav-group { margin: 0 4px 0 8px; align-self: center; white-space: nowrap; }
  .settings-nav-group:first-of-type { margin-left: 0; }
  .settings-nav-item { width: auto; white-space: nowrap; }
  .settings-body { max-width: 100%; }
}
@media (max-width: 640px) {
  .setting-row { flex-direction: column; align-items: flex-start; gap: 12px; }
  .settings-fields { grid-template-columns: minmax(0, 1fr); }
  .segmented { width: 100%; }
  .segment { flex: 1; justify-content: center; }
  .settings-palette-row .settings-palette-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .settings-palette-card .palette-swatch { height: 38px; }
  .settings-density-options { width: 100%; }
  .settings-density-option { flex: 1; justify-content: center; }
}
</style>
