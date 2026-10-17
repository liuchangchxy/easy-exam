<template>
  <main class="settings-page">
    <header class="page-header settings-header">
      <div class="settings-title-group">
        <div class="settings-header-icon">
          <LinearIcon name="settings" size="20" />
        </div>
        <div>
          <h1>{{ t('settings.title') }}</h1>
          <p class="settings-subtitle">{{ t('settings.subtitle') }}</p>
        </div>
      </div>
    </header>

    <div class="settings-content-grid">
      <!-- 1. 外观与主题 (Appearance & Themes) -->
      <section class="settings-card appearance-card">
        <div class="card-section-header">
          <div class="section-title-wrap">
            <LinearIcon name="zap" size="18" />
            <h2>{{ t('settings.tab_appearance') }}</h2>
          </div>
          <p class="section-desc">{{ t('settings.palette_desc') }}</p>
        </div>

        <!-- 明暗模式切换 (Light / Dark / Follow System) -->
        <div class="settings-subgroup">
          <label class="group-label">{{ t('settings.theme_mode_title') }}</label>
          <div class="mode-toggle-segmented" role="radiogroup" :aria-label="t('settings.theme_mode_title')">
            <button
              type="button"
              class="segment-btn"
              :class="{ active: mode === 'light' }"
              role="radio"
              :aria-checked="mode === 'light'"
              @click="setMode('light')"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5" />
                <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
              <span>{{ t('settings.theme_mode_light') }}</span>
            </button>
            <button
              type="button"
              class="segment-btn"
              :class="{ active: mode === 'dark' }"
              role="radio"
              :aria-checked="mode === 'dark'"
              @click="setMode('dark')"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
              <span>{{ t('settings.theme_mode_dark') }}</span>
            </button>
            <button
              type="button"
              class="segment-btn"
              :class="{ active: mode === 'system' }"
              role="radio"
              :aria-checked="mode === 'system'"
              @click="setMode('system')"
            >
              <LinearIcon name="terminal" size="15" />
              <span>{{ t('settings.theme_mode_system') }}</span>
            </button>
          </div>
        </div>

        <!-- 8 个主题系列预览卡片 -->
        <div class="settings-subgroup">
          <label class="group-label">{{ t('settings.palette_title') }}</label>
          <div class="palettes-grid">
            <button
              v-for="p in paletteList"
              :key="p.id"
              type="button"
              class="palette-preview-card"
              :class="{ active: palette === p.id }"
              :data-preview-palette="p.id"
              @click="setPalette(p.id)"
            >
              <div class="palette-swatch-box" :style="{ background: p.bgPage, borderColor: p.border }">
                <div class="mini-card-surface" :style="{ background: p.bgCard, borderColor: p.border }">
                  <div class="mini-accent-badge" :style="{ background: p.primary, color: p.onPrimary }">
                    <LinearIcon v-if="palette === p.id" name="check" size="10" />
                  </div>
                  <div class="mini-lines">
                    <span class="mini-line title-line" :style="{ background: p.textMain }"></span>
                    <span class="mini-line sub-line" :style="{ background: p.textMuted }"></span>
                  </div>
                </div>
              </div>
              <div class="palette-card-meta">
                <span class="palette-name">{{ p.name }}</span>
                <span class="palette-desc">{{ p.desc }}</span>
              </div>
            </button>
          </div>
        </div>

        <!-- 自定义强调色 (Custom Accent Color) -->
        <div class="settings-subgroup custom-accent-section">
          <div class="accent-title-row">
            <div>
              <label class="group-label">{{ t('settings.custom_accent_title') }}</label>
              <p class="sub-hint">{{ t('settings.custom_accent_desc') }}</p>
            </div>
            <span v-if="customAccent" class="contrast-badge">
              <LinearIcon name="check" size="12" /> {{ t('settings.contrast_ok') }}
            </span>
          </div>

          <div class="custom-accent-controls">
            <div class="picker-input-group">
              <input
                type="color"
                class="accent-color-picker"
                :value="activePrimaryColor"
                :aria-label="t('settings.custom_accent_title')"
                @input="handleColorPickerInput"
              />
              <input
                type="text"
                class="accent-hex-input"
                :value="customAccent || activePrimaryColor"
                :placeholder="t('settings.accent_hex_placeholder')"
                maxlength="7"
                :aria-label="t('settings.custom_accent_title')"
                @change="handleHexInputChange"
              />
            </div>

            <!-- 常用推荐预设 -->
            <div class="preset-chips">
              <span class="preset-label">{{ t('settings.preset_colors') }}</span>
              <button
                v-for="c in presetColors"
                :key="c"
                type="button"
                class="preset-chip"
                :style="{ background: c }"
                :aria-label="c"
                @click="setCustomAccent(c)"
              ></button>
              <button
                v-if="customAccent"
                type="button"
                class="btn-reset-accent"
                @click="resetCustomAccent"
              >
                {{ t('settings.reset_accent') }}
              </button>
            </div>
          </div>

          <!-- 实时控件预览组件展示 -->
          <div class="live-preview-box">
            <span class="preview-label">{{ t('settings.preview_heading') }}</span>
            <div class="preview-elements-row">
              <button type="button" class="primary btn-compact">
                {{ t('settings.preview_btn_primary') }}
              </button>
              <button type="button" class="secondary-btn btn-compact">
                {{ t('settings.preview_btn_secondary') }}
              </button>
              <span class="sample-badge">
                <LinearIcon name="check" size="12" /> {{ t('settings.preview_badge') }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. 账户与安全 (Account & Security) -->
      <section class="settings-card">
        <div class="card-section-header">
          <div class="section-title-wrap">
            <LinearIcon name="user" size="18" />
            <h2>{{ t('settings.tab_account') }}</h2>
          </div>
          <p class="section-desc">{{ t('ui.k0027') }}</p>
        </div>

        <div class="account-card-body">
          <div class="account-profile-row">
            <div class="account-avatar" :class="user?.is_admin ? 'role-admin' : 'role-user'">
              {{ userInitial }}
            </div>
            <div class="account-details">
              <strong class="account-username">{{ user?.username || t('sidebar.not_logged_in') }}</strong>
              <span class="account-role-tag">{{ user?.is_admin ? t('sidebar.role_admin') : t('sidebar.role_user') }}</span>
            </div>
          </div>

          <div class="account-actions-row">
            <button type="button" class="secondary-btn" @click="openPasswordModal">
              <LinearIcon name="key" size="14" /> {{ t('settings.account_change_pwd') }}
            </button>
            <button type="button" class="btn-ghost-danger" @click="$emit('logout')">
              <LinearIcon name="logout" size="14" /> {{ t('settings.account_logout') }}
            </button>
          </div>
        </div>
      </section>

      <!-- 3. 语言偏好 (Language) -->
      <section class="settings-card">
        <div class="card-section-header">
          <div class="section-title-wrap">
            <LinearIcon name="globe" size="18" />
            <h2>{{ t('settings.tab_language') }}</h2>
          </div>
          <p class="section-desc">{{ t('settings.lang_desc') }}</p>
        </div>

        <div class="settings-subgroup">
          <div class="mode-toggle-segmented">
            <button
              type="button"
              class="segment-btn"
              data-locale="zh-CN"
              :class="{ active: currentLocale === 'zh-CN' }"
              @click="setLocale('zh-CN')"
            >
              {{ t('settings.lang_zh') }}
            </button>
            <button
              type="button"
              class="segment-btn"
              data-locale="en-US"
              :class="{ active: currentLocale === 'en-US' }"
              @click="setLocale('en-US')"
            >
              {{ t('settings.lang_en') }}
            </button>
          </div>
        </div>
      </section>

      <!-- 4. 关于系统 (About) -->
      <section class="settings-card about-card">
        <div class="card-section-header">
          <div class="section-title-wrap">
            <LinearIcon name="exam" size="18" />
            <h2>{{ t('settings.tab_about') }}</h2>
          </div>
          <p class="section-desc">{{ t('settings.about_desc') }}</p>
        </div>

        <div class="about-info-grid">
          <div class="about-item">
            <span class="about-item-label">{{ t('settings.about_version') }}</span>
            <strong class="about-item-val font-mono">v1.0.17</strong>
          </div>
          <div class="about-item">
            <span class="about-item-label">{{ t('settings.about_design_system_label') }}</span>
            <strong class="about-item-val">{{ t('settings.about_design_system_val') }}</strong>
          </div>
          <div class="about-item">
            <span class="about-item-label">{{ t('settings.about_fsrs_label') }}</span>
            <strong class="about-item-val">{{ t('settings.about_fsrs_val') }}</strong>
          </div>
          <div class="about-item">
            <span class="about-item-label">{{ t('settings.about_storage_label') }}</span>
            <strong class="about-item-val">{{ t('settings.about_storage_val') }}</strong>
          </div>
        </div>
      </section>
    </div>

    <!-- 修改密码弹窗 -->
    <ChangePasswordModal
      v-if="showPasswordModal"
      :token="token"
      @close="showPasswordModal = false"
    />
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import ChangePasswordModal from '../components/ChangePasswordModal.vue'
import { useLocale } from '../composables/useLocale.js'
import { useTheme } from '../composables/useTheme.js'
import { getContrastTextColor } from '../design/themePreference.js'

const props = defineProps({
  token: { type: String, default: '' },
  user: { type: Object, default: null },
})

defineEmits(['logout'])

const { t, locale: currentLocale, setLocale } = useLocale()
const { theme, mode, palette, customAccent, setMode, setPalette, setCustomAccent, resetCustomAccent } = useTheme()

const showPasswordModal = ref(false)

const userInitial = computed(() => {
  const name = props.user?.username
  return name ? name.charAt(0).toUpperCase() : 'U'
})

function openPasswordModal() {
  showPasswordModal.value = true
}

const presetColors = Object.freeze([
  '#2563eb', // Blue-Grey
  '#3b6978', // Mist Blue
  '#0891b2', // Ocean Cyan
  '#7c3aed', // Amethyst Violet
  '#e11d48', // Rose Crimson
  '#d97706', // Amber Sand
  '#286b53', // Forest Pine
  '#845339', // Mocha Espresso
])

const paletteList = computed(() => [
  {
    id: 'blue-grey',
    name: t('theme.blue_grey'),
    desc: t('theme.blue_grey_desc'),
    bgPage: '#f8fafc',
    bgCard: '#ffffff',
    primary: '#2563eb',
    onPrimary: '#ffffff',
    textMain: '#0f172a',
    textMuted: '#475569',
    border: '#cbd5e1',
  },
  {
    id: 'mist',
    name: t('theme.mist'),
    desc: t('theme.mist_desc'),
    bgPage: '#f4f6f8',
    bgCard: '#ffffff',
    primary: '#3b6978',
    onPrimary: '#ffffff',
    textMain: '#192533',
    textMuted: '#526375',
    border: '#d2dce6',
  },
  {
    id: 'ocean',
    name: t('theme.ocean'),
    desc: t('theme.ocean_desc'),
    bgPage: '#f0f9fa',
    bgCard: '#ffffff',
    primary: '#0891b2',
    onPrimary: getContrastTextColor('#0891b2'),
    textMain: '#0c2830',
    textMuted: '#3d6673',
    border: '#c4e3e8',
  },
  {
    id: 'amethyst',
    name: t('theme.amethyst'),
    desc: t('theme.amethyst_desc'),
    bgPage: '#faf5ff',
    bgCard: '#ffffff',
    primary: '#7c3aed',
    onPrimary: '#ffffff',
    textMain: '#24143d',
    textMuted: '#5e4a78',
    border: '#dac2f7',
  },
  {
    id: 'rose',
    name: t('theme.rose'),
    desc: t('theme.rose_desc'),
    bgPage: '#fff1f2',
    bgCard: '#ffffff',
    primary: '#e11d48',
    onPrimary: '#ffffff',
    textMain: '#3b111a',
    textMuted: '#783d49',
    border: '#f8b4c0',
  },
  {
    id: 'amber',
    name: t('theme.amber'),
    desc: t('theme.amber_desc'),
    bgPage: '#fffbeb',
    bgCard: '#ffffff',
    primary: '#d97706',
    onPrimary: getContrastTextColor('#d97706'),
    textMain: '#382305',
    textMuted: '#78531a',
    border: '#fcd34d',
  },
  {
    id: 'forest',
    name: t('theme.forest'),
    desc: t('theme.forest_desc'),
    bgPage: '#f5f3eb',
    bgCard: '#fffefa',
    primary: '#286b53',
    onPrimary: '#ffffff',
    textMain: '#20332b',
    textMuted: '#5c6b63',
    border: '#d9e1d9',
  },
  {
    id: 'mocha',
    name: t('theme.mocha'),
    desc: t('theme.mocha_desc'),
    bgPage: '#f5f0eb',
    bgCard: '#ffffff',
    primary: '#845339',
    onPrimary: '#ffffff',
    textMain: '#2b1f1a',
    textMuted: '#68554d',
    border: '#d8c8ba',
  },
])

const activePrimaryColor = computed(() => {
  if (customAccent.value) return customAccent.value
  const found = paletteList.value.find(p => p.id === palette.value)
  return found?.primary || '#2563eb'
})

function handleColorPickerInput(e) {
  const val = e.target.value
  if (val) setCustomAccent(val)
}

function handleHexInputChange(e) {
  const val = e.target.value.trim()
  if (!val) {
    resetCustomAccent()
    return
  }
  setCustomAccent(val)
}
</script>

<style scoped>
.settings-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.settings-header {
  margin-bottom: 0.5rem;
}

.settings-title-group {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.settings-header-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: var(--primary-light);
  color: var(--primary-fg, var(--primary));
  border: 1px solid var(--primary-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.settings-header h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.02em;
  margin: 0;
}

.settings-subtitle {
  font-size: 0.88rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.settings-content-grid {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.settings-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 1.5rem;
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.card-section-header {
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 0.85rem;
}

.section-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  color: var(--primary-fg, var(--primary));
}

.section-title-wrap h2 {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-main);
  margin: 0;
}

.section-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.35rem;
  line-height: 1.45;
}

.settings-subgroup {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.group-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-main);
}

.sub-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

/* Segmented Toggle Control */
.mode-toggle-segmented {
  display: inline-flex;
  background: var(--bg-subtle);
  padding: 4px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  gap: 4px;
  width: fit-content;
  max-width: 100%;
}

.segment-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1.15rem;
  font-size: 0.85rem;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 120ms ease;
  min-height: 38px;
  user-select: none;
}

.segment-btn:hover {
  color: var(--text-main);
}

.segment-btn.active {
  background: var(--bg-card);
  color: var(--primary-fg, var(--primary));
  border: 1px solid var(--primary-border, var(--border));
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

/* Palettes Grid */
.palettes-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.85rem;
}

.palette-preview-card {
  display: flex;
  flex-direction: column;
  padding: 0.65rem;
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--border);
  background: var(--bg-card);
  cursor: pointer;
  transition: all 150ms ease;
  text-align: left;
}

.palette-preview-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.palette-preview-card.active {
  border-color: var(--primary-fg, var(--primary));
  box-shadow: 0 0 0 2px var(--primary-border, var(--primary-light));
}

.palette-swatch-box {
  height: 64px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  margin-bottom: 0.6rem;
}

.mini-card-surface {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  padding: 6px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: var(--shadow-xs);
  box-sizing: border-box;
}

.mini-accent-badge {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.mini-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.mini-line {
  height: 4px;
  border-radius: 2px;
}

.mini-line.title-line {
  width: 70%;
}

.mini-line.sub-line {
  width: 45%;
  opacity: 0.6;
}

.palette-card-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.palette-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-main);
}

.palette-desc {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.25;
}

/* Custom Accent */
.accent-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.contrast-badge {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--success-fg, var(--success));
  background: var(--success-light);
  border: 1px solid var(--success-border);
  padding: 0.25rem 0.6rem;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
}

.custom-accent-controls {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  flex-wrap: wrap;
}

.picker-input-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 4px 8px;
}

.accent-color-picker {
  -webkit-appearance: none;
  appearance: none;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  background: transparent;
  padding: 0;
}

.accent-color-picker::-webkit-color-swatch-wrapper {
  padding: 0;
}

.accent-color-picker::-webkit-color-swatch {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.accent-hex-input {
  border: none;
  background: transparent;
  font-family: var(--linear-mono);
  font-size: 0.85rem;
  color: var(--text-main);
  width: 75px;
  padding: 0;
}

.accent-hex-input:focus {
  outline: none;
}

.preset-chips {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.preset-label {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.preset-chip {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--bg-card);
  box-shadow: 0 0 0 1px var(--border);
  cursor: pointer;
  transition: transform 120ms ease;
  padding: 0;
}

.preset-chip:hover {
  transform: scale(1.18);
}

.btn-reset-accent {
  font-size: 0.78rem;
  color: var(--text-muted);
  background: transparent;
  border: none;
  text-decoration: underline;
  cursor: pointer;
  margin-left: 0.4rem;
}

.btn-reset-accent:hover {
  color: var(--text-main);
}

.live-preview-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.preview-label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-muted);
}

.preview-elements-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.sample-badge {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--primary-fg, var(--primary));
  background: var(--primary-light);
  border: 1px solid var(--primary-border);
  padding: 0.35rem 0.65rem;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

/* Account Profile */
.account-profile-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.account-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  font-size: 1.25rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-avatar.role-admin {
  background: var(--primary-light);
  color: var(--primary-fg, var(--primary));
  border: 1.5px solid var(--primary-border);
}

.account-avatar.role-user {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
  border: 1.5px solid rgba(16, 185, 129, 0.3);
}

.account-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.account-username {
  font-size: 1.05rem;
  color: var(--text-main);
}

.account-role-tag {
  font-size: 0.75rem;
  color: var(--text-muted);
  width: fit-content;
  background: var(--bg-subtle);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}

.account-actions-row {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-top: 0.5rem;
}

/* About Grid */
.about-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
}

.about-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 0.75rem;
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
}

.about-item-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.about-item-val {
  font-size: 0.85rem;
  color: var(--text-main);
  font-weight: 500;
}

.font-mono {
  font-family: var(--linear-mono);
}

@media (max-width: 900px) {
  .palettes-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .settings-page {
    padding: 1rem 0.85rem 5rem;
  }
  .about-info-grid {
    grid-template-columns: 1fr;
  }
  .mode-toggle-segmented {
    width: 100%;
  }
  .segment-btn {
    flex: 1;
    justify-content: center;
    padding: 0.45rem 0.5rem;
    font-size: 0.8rem;
  }
  .custom-accent-controls {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
