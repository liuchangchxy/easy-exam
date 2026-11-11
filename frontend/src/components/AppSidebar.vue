<template>
  <aside class="sidebar" :aria-label="t('ep.nav.primary')">
    <button type="button" class="brand" @click="$emit('navigate', 'today')">
      <span class="brand-mark" aria-hidden="true">易</span>
      <span class="brand-text">
        <span class="brand-name">{{ t('ep.brand.name') }}</span>
        <span class="brand-sub">{{ t('ep.brand.sub') }}</span>
      </span>
    </button>

    <nav class="side-nav" :aria-label="t('ep.nav.areas')">
      <span class="nav-label">{{ t('ep.nav.study') }}</span>
      <button
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="nav-item"
        :class="{ 'is-active': currentPage === item.key }"
        :aria-current="currentPage === item.key ? 'page' : undefined"
        @click="$emit('navigate', item.key)"
      >
        <span class="nav-ico"><LinearIcon :name="item.icon" :size="17" /></span>
        <span class="label">{{ t(item.label) }}</span>
        <span v-if="item.key === 'review' && reviewCount > 0" class="nav-count">{{ reviewCount }}</span>
        <span v-else-if="item.key === 'banks' && bankCount > 0" class="nav-count">{{ bankCount }}</span>
      </button>
    </nav>

    <div v-if="learningTrends" class="side-study-state">
      <div class="ss-label">{{ t('ep.today.figure_due') }}</div>
      <div class="ss-value">{{ reviewCount }} <small>{{ t('ui.k0101') }}</small></div>
      <div class="ss-bar" role="progressbar" :aria-valuenow="coveragePercent" aria-valuemin="0" aria-valuemax="100">
        <div class="ss-bar-fill" :style="{ width: coveragePercent + '%' }"></div>
      </div>
      <div class="ss-row">
        <span>{{ t('ui.k0386') }}</span>
        <strong>{{ coveragePercent }}%</strong>
      </div>
      <div class="ss-row">
        <span>{{ t('ui.k0391') }}</span>
        <strong>{{ accuracyText }}</strong>
      </div>
    </div>

    <div class="side-foot">
      <button
        type="button"
        class="nav-item"
        :class="{ 'is-active': currentPage === 'settings' }"
        @click="$emit('navigate', 'settings')"
      >
        <span class="nav-ico"><LinearIcon name="settings" :size="17" /></span>
        <span class="label">{{ t('ep.nav.settings') }}</span>
      </button>

      <button
        type="button"
        class="user-mini"
        data-account-trigger
        aria-haspopup="menu"
        :aria-expanded="accountMenuOpen ? 'true' : 'false'"
        :aria-label="t('ep.account.menu')"
        @click="$emit('account-menu', $event.currentTarget)"
      >
        <span class="avatar">{{ userInitial }}</span>
        <span class="user-meta">
          <span class="user-name">{{ user?.username || t('ep.account.guest') }}</span>
          <span class="user-sub">{{ user?.is_admin ? t('ep.role.admin') : t('ep.role.user') }}</span>
        </span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  currentPage: { type: String, default: 'today' },
  user: { type: Object, default: null },
  bankCount: { type: Number, default: 0 },
  reviewCount: { type: Number, default: 0 },
  learningTrends: { type: Object, default: null },
  accountMenuOpen: { type: Boolean, default: false },
})

defineEmits(['navigate', 'account-menu'])

const navItems = [
  { key: 'today', label: 'ep.nav.today', icon: 'home' },
  { key: 'banks', label: 'ep.nav.banks', icon: 'library' },
  { key: 'review', label: 'ep.nav.review', icon: 'review' },
  { key: 'exam', label: 'ep.nav.exams', icon: 'exam' },
  { key: 'notes', label: 'ep.nav.library', icon: 'note' },
]

const userInitial = computed(() => {
  const name = props.user?.username
  return name ? name.charAt(0).toUpperCase() : '?'
})

const coveragePercent = computed(() => {
  const value = Number(props.learningTrends?.coverage_percent)
  return Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 0
})
const accuracyText = computed(() => {
  const value = Number(props.learningTrends?.recent?.correct_rate)
  return Number.isFinite(value) ? `${Math.round(value)}%` : '—'
})
</script>

<style scoped>
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 0 2px;
  background: none;
  border: 0;
  text-align: left;
  cursor: pointer;
  color: inherit;
}

.side-foot { position: relative; }
</style>
