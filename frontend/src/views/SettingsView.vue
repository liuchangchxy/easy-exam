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
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          class="settings-nav-item"
          :class="{ 'is-active': activeSection === item.key }"
          @click="selectSection(item.key)"
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

          <div class="setting-row setting-row-top">
            <div class="setting-label">
              <div class="setting-name">{{ t('ep.settings.accent') }}</div>
              <div class="setting-desc">{{ t('ep.settings.accent_note') }}</div>
            </div>
            <div class="accent-grid">
              <button
                v-for="preset in accentPresets"
                :key="preset.key"
                type="button"
                class="accent-option"
                :class="{ 'is-active': preset.active }"
                @click="setCustomAccent(preset.hex)"
              >
                <span class="accent-swatch" :style="{ background: preset.hex }"></span>
                <span class="accent-name">{{ t(preset.label) }}</span>
                <LinearIcon v-if="preset.active" name="check" :size="13" />
              </button>
              <label class="accent-option accent-custom">
                <span class="accent-swatch" :style="{ background: activeAccent }"></span>
                <span class="accent-name">{{ t('ep.settings.accent_custom') }}</span>
                <input type="color" class="accent-input" :value="activeAccent" :aria-label="t('ep.settings.accent_custom')" @input="onAccentInput" />
              </label>
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
              <select v-model="config.ai_provider" class="select" @change="saveAi">
                <option value="openai">{{ t('ep.settings.ai_provider_openai') }}</option>
                <option value="ollama">{{ t('ep.settings.ai_provider_ollama') }}</option>
              </select>
            </label>
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_base_url') }}</span>
              <input v-model.trim="config.ai_api_base" class="input" type="text" placeholder="https://api.openai.com/v1" @change="saveAi" />
            </label>
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_model') }}</span>
              <input v-model.trim="config.ai_model" class="input" type="text" placeholder="gpt-4o-mini" @change="saveAi" />
            </label>
            <label class="field">
              <span class="label">{{ t('ep.settings.ai_key') }}</span>
              <input v-model="config.ai_api_key" class="input" type="password" :placeholder="t('ep.settings.ai_key_placeholder')" @change="saveAi" />
              <span v-if="config.ai_api_key" class="hint">{{ t('ep.settings.ai_key_set') }}</span>
            </label>
          </div>

          <div class="notice info settings-note">
            <LinearIcon name="shield" :size="15" />
            <span>{{ t('ep.settings.ai_boundary') }}</span>
          </div>

          <div class="settings-actions">
            <span class="settings-hint">{{ t('ep.settings.auto_save_hint') }}</span>
            <span v-if="savingAi" class="settings-saved">{{ t('ep.settings.saving') }}</span>
            <span v-else-if="aiNotice" class="settings-saved" :class="{ 'is-error': aiError }">{{ aiNotice }}</span>
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
              <select v-model="config.search_provider" class="select" @change="saveWeb">
                <option value="open-webSearch">{{ t('ep.settings.web_on') }}</option>
                <option value="offline">{{ t('ep.settings.web_off') }}</option>
              </select>
            </label>
            <label v-if="config.search_provider !== 'offline'" class="field">
              <span class="label">{{ t('ep.settings.web_base_url') }}</span>
              <input v-model.trim="config.search_api_base" class="input" type="text" placeholder="http://localhost:8000/v1/search" @change="saveWeb" />
            </label>
            <label v-if="config.search_provider !== 'offline'" class="field">
              <span class="label">{{ t('ep.settings.web_key') }}</span>
              <input v-model="config.search_api_key" class="input" type="password" :placeholder="t('ep.settings.ai_key_placeholder')" @change="saveWeb" />
            </label>
          </div>

          <div class="settings-actions">
            <span class="settings-hint">{{ t('ep.settings.auto_save_hint') }}</span>
            <span v-if="savingWeb" class="settings-saved">{{ t('ep.settings.saving') }}</span>
            <span v-else-if="webNotice" class="settings-saved" :class="{ 'is-error': webError }">{{ webNotice }}</span>
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
import { useTheme } from '../composables/useTheme.js'
import { DENSITY_STORAGE_KEY, normalizeDensityPreference, restoreDensityPreference } from '../composables/density.js'
import { getAiConfig, updateAiConfig } from '../api/ai'
import pkg from '../../package.json'

const props = defineProps({
  token: { type: String, default: '' },
  user: { type: Object, default: null },
})

const emit = defineEmits(['logout'])
const route = useRoute()
const router = useRouter()

const { t, locale: currentLocale, setLocale } = useLocale()
const { mode, setMode, palette, palettes, setPalette, customAccent, setCustomAccent } = useTheme()

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

watch(
  () => route?.query?.section,
  value => {
    activeSection.value = normalizeSection(value)
  }
)

function requestLogout() {
  if (!window.confirm(t('ep.settings.logout_confirm'))) return
  emit('logout')
}
const showPasswordModal = ref(false)
const appVersion = pkg.version
const density = ref('balanced')

const navItems = [
  { key: 'appearance', label: 'ep.settings.nav_appearance', icon: 'sun' },
  { key: 'language', label: 'ep.settings.nav_language', icon: 'globe' },
  { key: 'ai', label: 'ep.settings.nav_ai', icon: 'cpu' },
  { key: 'web', label: 'ep.settings.nav_web', icon: 'link' },
  { key: 'account', label: 'ep.settings.nav_account', icon: 'user' },
  { key: 'about', label: 'ep.settings.nav_about', icon: 'info' },
]

const PALETTE_SWATCHES = {
  editorial: { paper: '#f5f2ea', accent: '#23554b', stops: ['#f5f2ea', '#fbf9f4', '#191b18', '#23554b'] },
  gruvbox: { paper: '#fbf1c7', accent: '#af3a03', stops: ['#fbf1c7', '#fff9e4', '#3c3836', '#af3a03'] },
  everforest: { paper: '#fdf6e3', accent: '#4e6b3f', stops: ['#fdf6e3', '#fffcf0', '#3d484d', '#4e6b3f'] },
  catppuccin: { paper: '#eff1f5', accent: '#8839ef', stops: ['#eff1f5', '#f7f8fb', '#4c4f69', '#8839ef'] },
}

function paletteSwatch(id) {
  return PALETTE_SWATCHES[id] || PALETTE_SWATCHES.editorial
}

const accentPresets = computed(() => {
  const pine = '#23554b'
  const active = customAccent.value || pine
  return [
    { key: 'pine', label: 'ep.settings.accent_pine', hex: pine, active: active.toLowerCase() === pine },
    { key: 'indigo', label: 'ep.settings.accent_indigo', hex: '#33456b', active: active.toLowerCase() === '#33456b' },
    { key: 'ochre', label: 'ep.settings.accent_ochre', hex: '#8a5c24', active: active.toLowerCase() === '#8a5c24' },
    { key: 'ink', label: 'ep.settings.accent_ink', hex: '#191b18', active: active.toLowerCase() === '#191b18' },
  ]
})

const activeAccent = computed(() => customAccent.value || '#23554b')

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

const config = ref({
  ai_provider: 'openai',
  ai_api_base: 'https://api.openai.com/v1',
  ai_model: 'gpt-4o-mini',
  ai_api_key: '',
  search_provider: 'open-webSearch',
  search_api_key: '',
  search_api_base: 'http://localhost:8000/v1/search',
})

const savingAi = ref(false)
const savingWeb = ref(false)
const aiNotice = ref('')
const webNotice = ref('')
const aiError = ref(false)
const webError = ref(false)
const aiConfigured = ref(false)

function onAccentInput(event) {
  setCustomAccent(event.target.value)
}

async function loadConfig() {
  if (!props.token) return
  try {
    const res = await getAiConfig(props.token)
    aiConfigured.value = Boolean(res.is_configured)
    config.value = {
      ai_provider: res.ai_provider || 'openai',
      ai_api_base: res.ai_api_base || 'https://api.openai.com/v1',
      ai_model: res.ai_model || 'gpt-4o-mini',
      ai_api_key: res.ai_api_key || '',
      search_provider: res.search_provider || 'open-webSearch',
      search_api_key: res.search_api_key || '',
      search_api_base: res.search_api_base || 'http://localhost:8000/v1/search',
    }
  } catch (err) {
    aiError.value = true
    aiNotice.value = `${t('ep.settings.ai_load_failed')}${err.detail || err.message || ''}`
  }
}

async function saveAi() {
  savingAi.value = true
  aiNotice.value = ''
  aiError.value = false
  try {
    const updated = await updateAiConfig(props.token, config.value)
    config.value.ai_api_key = updated.ai_api_key ?? ''
    aiConfigured.value = Boolean(updated.is_configured)
    aiNotice.value = t('ep.settings.ai_saved')
  } catch (err) {
    aiError.value = true
    aiNotice.value = err.detail || err.message
  } finally {
    savingAi.value = false
  }
}

async function saveWeb() {
  savingWeb.value = true
  webNotice.value = ''
  webError.value = false
  try {
    const updated = await updateAiConfig(props.token, config.value)
    config.value.search_api_key = updated.search_api_key ?? ''
    aiConfigured.value = Boolean(updated.is_configured)
    webNotice.value = t('ep.settings.web_saved')
  } catch (err) {
    webError.value = true
    webNotice.value = err.detail || err.message
  } finally {
    savingWeb.value = false
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
.settings-nav { border-top: 1px solid var(--line); padding-top: 8px; position: sticky; top: 66px; }
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

.accent-grid { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
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
.accent-option {
  display: flex; align-items: center; gap: 7px; height: 34px; padding: 0 10px;
  border: 1px solid var(--line); background: none; color: var(--ink-2);
  font-size: 12px; cursor: pointer; position: relative;
}
.accent-option:hover { border-color: var(--ink-4); }
.accent-option.is-active { border-color: var(--brand-line); color: var(--brand); }
.accent-swatch { width: 14px; height: 14px; flex: none; border: 1px solid rgba(0, 0, 0, .12); }
.accent-custom { overflow: hidden; }
.accent-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }

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

@media (max-width: 880px) {
  .settings-layout { grid-template-columns: minmax(0, 1fr); gap: 14px; }
  .settings-nav { display: flex; gap: 2px; overflow-x: auto; position: static; border-top: 0; border-bottom: 1px solid var(--line); padding: 0 0 8px; }
  .settings-nav-item { width: auto; white-space: nowrap; }
  .settings-body { max-width: 100%; }
}
@media (max-width: 640px) {
  .setting-row { flex-direction: column; align-items: flex-start; gap: 12px; }
  .accent-grid { justify-content: flex-start; }
  .settings-fields { grid-template-columns: minmax(0, 1fr); }
  .segmented { width: 100%; }
  .segment { flex: 1; justify-content: center; }
  .settings-palette-row .settings-palette-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .settings-palette-card .palette-swatch { height: 38px; }
  .settings-density-options { width: 100%; }
  .settings-density-option { flex: 1; justify-content: center; }
}
</style>
