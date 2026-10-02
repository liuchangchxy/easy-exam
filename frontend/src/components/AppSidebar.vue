<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- Brand Top -->
    <div class="sidebar-header">
      <div class="sidebar-brand" @click="$emit('navigate', 'home')">
        <div class="brand-logo-gem">
          <LinearIcon name="exam" size="16" />
        </div>
        <div v-if="!isCollapsed" class="brand-text-group">
          <span class="brand-name">EasyExam</span>
          <span class="brand-version">v1.0.16</span>
        </div>
      </div>
      <button
        type="button"
        class="sidebar-toggle-btn"
        :title="isCollapsed ? t('ui.k0035') : t('ui.k0036')"
        @click="isCollapsed = !isCollapsed"
      >
        <LinearIcon name="chevron-right" size="14" :style="{ transform: isCollapsed ? 'none' : 'rotate(180deg)', transition: 'transform 150ms ease' }" />
      </button>
    </div>

    <!-- Quick Command Trigger -->
    <div class="sidebar-cmd-wrapper">
      <button type="button" class="sidebar-cmd-btn" @click="$emit('open-palette')" :title="isCollapsed ? t('nav.search') : ''">
        <LinearIcon name="command" size="14" />
        <span v-if="!isCollapsed" class="cmd-btn-text">{{ t('nav.search') }}</span>
        <span v-if="!isCollapsed" class="cmd-btn-key">⌘K</span>
      </button>
    </div>

    <!-- Main Navigation -->
    <nav class="sidebar-nav-section">
      <div v-if="!isCollapsed" class="nav-section-title">EasyExam</div>
      <button
        type="button"
        class="sidebar-nav-item"
        :class="{ active: currentPage === 'home' }"
        @click="$emit('navigate', 'home')"
        :title="isCollapsed ? t('nav.home') : ''"
      >
        <LinearIcon name="layers" size="16" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('nav.home') }}</span>
        <span v-if="!isCollapsed && bankCount > 0" class="nav-item-badge">{{ bankCount }}</span>
      </button>

      <button
        type="button"
        class="sidebar-nav-item"
        :class="{ active: currentPage === 'mistakes' }"
        @click="$emit('navigate', 'mistakes')"
        :title="isCollapsed ? t('nav.mistakes') : ''"
      >
        <LinearIcon name="target" size="16" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('nav.mistakes') }}</span>
        <span v-if="!isCollapsed" class="nav-item-sub">FSRS</span>
      </button>

      <button
        type="button"
        class="sidebar-nav-item"
        :class="{ active: currentPage === 'learning' }"
        @click="$emit('navigate', 'learning')"
        :title="isCollapsed ? t('nav.learning') : ''"
      >
        <LinearIcon name="chart" size="16" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('nav.learning') }}</span>
      </button>

      <button
        type="button"
        class="sidebar-nav-item"
        :class="{ active: currentPage === 'import' }"
        @click="$emit('navigate', 'import')"
        :title="isCollapsed ? t('nav.imports') : ''"
      >
        <LinearIcon name="inbox" size="16" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('nav.imports') }}</span>
      </button>

      <button
        type="button"
        class="sidebar-nav-item"
        :class="{ active: currentPage === 'notes' }"
        @click="$emit('navigate', 'notes')"
        :title="isCollapsed ? t('nav.notes') : ''"
      >
        <LinearIcon name="edit" size="16" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('nav.notes') }}</span>
      </button>
    </nav>

    <!-- Utility / Workspace Section -->
    <div class="sidebar-nav-section secondary">
      <div v-if="!isCollapsed" class="nav-section-title">{{ t('sidebar.config_tools') }}</div>
      <button type="button" class="sidebar-nav-item sub" @click="$emit('action', 'blueprint')" :title="isCollapsed ? t('sidebar.blueprint') : ''">
        <LinearIcon name="blueprint" size="15" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('sidebar.blueprint') }}</span>
      </button>
      <button type="button" class="sidebar-nav-item sub" @click="$emit('action', 'drafts')" :title="isCollapsed ? t('sidebar.drafts') : ''">
        <LinearIcon name="draft" size="15" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('sidebar.drafts') }}</span>
      </button>
      <button type="button" class="sidebar-nav-item sub" @click="$emit('action', 'ai')" :title="isCollapsed ? t('sidebar.ai_search') : ''">
        <LinearIcon name="cpu" size="15" />
        <span v-if="!isCollapsed" class="nav-item-label">{{ t('sidebar.ai_search') }}</span>
      </button>
    </div>

    <!-- User & Footer -->
    <div class="sidebar-footer">
      <div class="sidebar-footer-row user-row">
        <div
          class="sidebar-user-card"
          :class="{ active: showUserMenu }"
          @click="toggleUserMenu"
          :title="isCollapsed ? (user?.username || t('sidebar.not_logged_in')) : ''"
        >
          <div class="user-avatar-badge" :class="user?.is_admin ? 'role-admin' : 'role-user'">
            {{ userInitial }}
          </div>
          <div v-if="!isCollapsed" class="user-info">
            <span class="user-name">{{ user?.username || t('sidebar.not_logged_in') }}</span>
            <span class="user-role">{{ user?.is_admin ? t('sidebar.role_admin') : t('sidebar.role_user') }}</span>
          </div>
        </div>
        <button
          type="button"
          class="sidebar-logout-btn"
          :title="t('nav.logout')"
          @click="$emit('logout')"
        >
          <LinearIcon name="logout" size="14" />
          <span v-if="!isCollapsed" class="logout-label">{{ t('nav.logout') }}</span>
        </button>
      </div>
      <div class="sidebar-footer-row tools-row">
        <ThemeToggle compact />
        <LocaleToggle compact />
      </div>

      <!-- 个人信息与快捷控制弹出气泡 (解决点左下角无反应) -->
      <div v-if="showUserMenu" class="user-popover-menu" @click.stop>
        <div class="popover-user-header">
          <div class="popover-avatar" :class="user?.is_admin ? 'role-admin' : 'role-user'">
            {{ userInitial }}
          </div>
          <div class="popover-info">
            <span class="popover-name">{{ user?.username || t('sidebar.not_logged_in') }}</span>
            <span class="popover-badge" :class="user?.is_admin ? 'admin' : 'user'">
              {{ user?.is_admin ? t('sidebar.role_admin') : t('sidebar.role_user') }}
            </span>
          </div>
        </div>
        <div class="popover-actions">
          <button type="button" class="popover-action-item" @click="handleChangePassword">
            <LinearIcon name="key" size="14" />
            <span>{{ t('ui.k0002') }}</span>
          </button>
          <button type="button" class="popover-action-item logout" @click="handleLogout">
            <LinearIcon name="logout" size="14" />
            <span>{{ t('nav.logout') }}</span>
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import LinearIcon from './LinearIcon.vue'
import ThemeToggle from './ThemeToggle.vue'
import LocaleToggle from './LocaleToggle.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  currentPage: {
    type: String,
    default: 'home'
  },
  user: {
    type: Object,
    default: null
  },
  bankCount: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['navigate', 'action', 'logout', 'open-palette', 'change-password'])

const isCollapsed = ref(false)
const showUserMenu = ref(false)
let mediaQuery = null

const userInitial = computed(() => {
  const name = props.user?.username
  return name ? name.charAt(0).toUpperCase() : 'U'
})

function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

function handleChangePassword() {
  showUserMenu.value = false
  emit('change-password')
}

function handleLogout() {
  showUserMenu.value = false
  emit('logout')
}

function handleGlobalClick(e) {
  if (showUserMenu.value && !e.target.closest('.sidebar-user-card') && !e.target.closest('.user-popover-menu')) {
    showUserMenu.value = false
  }
}

function checkAutoCollapse(e) {
  if (e.matches) {
    isCollapsed.value = true
  } else if (typeof window !== 'undefined' && window.innerWidth >= 1100) {
    isCollapsed.value = false
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('click', handleGlobalClick)
    if (window.innerWidth < 1100 && window.innerWidth > 768) {
      isCollapsed.value = true
    }
    mediaQuery = window.matchMedia('(max-width: 1100px)')
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', checkAutoCollapse)
    } else if (mediaQuery.addListener) {
      mediaQuery.addListener(checkAutoCollapse)
    }
  }
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('click', handleGlobalClick)
  }
  if (mediaQuery) {
    if (mediaQuery.removeEventListener) {
      mediaQuery.removeEventListener('change', checkAutoCollapse)
    } else if (mediaQuery.removeListener) {
      mediaQuery.removeListener(checkAutoCollapse)
    }
  }
})
</script>

<style scoped>
.app-sidebar {
  width: 220px;
  height: 100vh;
  position: sticky;
  top: 0;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 180ms cubic-bezier(0.2, 0, 0, 1);
  user-select: none;
  z-index: 100;
  flex-shrink: 0;
}

.app-sidebar.collapsed {
  width: 58px;
}

.sidebar-header {
  height: 52px;
  padding: 0 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-subtle);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  cursor: pointer;
  overflow: hidden;
}

.brand-logo-gem {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--primary-light);
  border: 1px solid var(--primary-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  flex-shrink: 0;
}

.brand-text-group {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  white-space: nowrap;
}

.brand-name {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-main);
  font-family: inherit;
}

.brand-version {
  font-size: 0.65rem;
  font-family: var(--linear-mono, monospace);
  color: var(--text-tertiary);
}

.sidebar-toggle-btn {
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-toggle-btn:hover {
  background: var(--bg-subtle);
  color: var(--text-main);
}

.sidebar-cmd-wrapper {
  padding: 0.75rem 0.65rem 0.4rem;
}

.sidebar-cmd-btn {
  width: 100%;
  height: 32px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.55rem;
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.78rem;
  transition: all 100ms ease;
  justify-content: flex-start;
}

.sidebar-cmd-btn:hover {
  background: var(--bg-subtle);
  border-color: var(--border-strong);
  color: var(--text-main);
}

.cmd-btn-text {
  flex: 1;
  text-align: left;
}

.cmd-btn-key {
  font-size: 0.65rem;
  font-family: var(--linear-mono, monospace);
  padding: 1px 4px;
  background: var(--bg-subtle);
  border-radius: 3px;
  color: var(--text-muted);
}

.sidebar-nav-section {
  padding: 0.5rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-nav-section.secondary {
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
}

.nav-section-title {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  padding: 0.35rem 0.5rem;
}

.sidebar-nav-item {
  width: 100%;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0 0.65rem;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.825rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 80ms ease;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-nav-item:hover {
  background: var(--bg-subtle);
  color: var(--text-main);
}

.sidebar-nav-item.active {
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
}

.sidebar-nav-item.sub {
  font-size: 0.785rem;
  color: var(--text-muted);
}

.sidebar-nav-item.sub:hover {
  color: var(--text-main);
}

.nav-item-label {
  flex: 1;
  text-align: left;
}

.nav-item-badge {
  font-size: 0.68rem;
  font-family: var(--linear-mono, monospace);
  padding: 1px 5px;
  background: var(--bg-subtle);
  border-radius: 10px;
  color: var(--text-tertiary);
}

.nav-item-sub {
  font-size: 0.65rem;
  font-family: var(--linear-mono, monospace);
  color: var(--primary);
  background: var(--primary-light);
  padding: 1px 4px;
  border-radius: 3px;
}

.sidebar-footer {
  margin-top: auto;
  padding: 0.65rem 0.5rem;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  position: relative;
}

.sidebar-footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  width: 100%;
}

.sidebar-footer-row.user-row {
  min-width: 0;
}

.sidebar-footer-row.tools-row {
  justify-content: flex-start;
  gap: 0.5rem;
}

.sidebar-user-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  overflow: hidden;
  padding: 4px;
  border-radius: 6px;
  flex: 1;
  min-width: 0;
  transition: all 120ms ease;
  user-select: none;
}

.sidebar-user-card:hover,
.sidebar-user-card.active {
  background: var(--bg-subtle);
}

.user-avatar-badge {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  font-weight: 700;
  font-size: 0.78rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  text-transform: uppercase;
  transition: all 120ms ease;
}

.user-avatar-badge.role-admin {
  background: rgba(37, 99, 235, 0.12);
  color: var(--primary);
  border: 1px solid rgba(37, 99, 235, 0.28);
}

.user-avatar-badge.role-user {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.28);
}

.sidebar-user-card:hover .user-avatar-badge,
.sidebar-user-card.active .user-avatar-badge {
  transform: scale(1.06);
  box-shadow: 0 0 0 2px var(--primary-light);
}

/* 个人中心弹出卡片 (Popover) */
.user-popover-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 8px;
  width: 13.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  padding: 0.85rem;
  z-index: 100;
  animation: popoverSlideUp 150ms ease;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

@keyframes popoverSlideUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.popover-user-header {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid var(--border-subtle);
}

.popover-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-weight: 700;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  text-transform: uppercase;
}

.popover-avatar.role-admin {
  background: rgba(37, 99, 235, 0.12);
  color: var(--primary);
  border: 1px solid rgba(37, 99, 235, 0.28);
}

.popover-avatar.role-user {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.28);
}

.popover-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.popover-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.popover-badge {
  font-size: 0.68rem;
  padding: 1px 6px;
  border-radius: 4px;
  width: fit-content;
  margin-top: 2px;
}

.popover-badge.admin {
  background: var(--primary-light);
  color: var(--primary);
}

.popover-badge.user {
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.popover-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.popover-action-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.45rem 0.65rem;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  font-size: 0.82rem;
  color: var(--text-main);
  cursor: pointer;
  transition: all 120ms ease;
  text-align: left;
}

.popover-action-item:hover {
  background: var(--bg-subtle);
}

.popover-action-item.logout {
  color: var(--danger);
}

.popover-action-item.logout:hover {
  background: var(--danger-light);
}

.user-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  flex: 1;
}

.user-name {
  font-size: 0.785rem;
  color: var(--text-main);
  font-weight: 500;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.user-role {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.sidebar-logout-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 0.75rem;
  white-space: nowrap;
}

.logout-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.sidebar-logout-btn:hover .logout-label {
  color: var(--danger);
}

.sidebar-logout-btn:hover {
  background: var(--danger-light);
  color: var(--danger);
}

.collapsed .sidebar-header {
  padding: 0 6px;
  justify-content: space-between;
}

.collapsed .sidebar-brand {
  overflow: visible;
  gap: 0;
}

.collapsed .brand-logo-gem {
  width: 24px;
  height: 24px;
  min-width: 24px;
  min-height: 24px;
  flex-shrink: 0;
}

.collapsed .sidebar-toggle-btn {
  padding: 2px;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.collapsed .sidebar-cmd-wrapper {
  padding: 0.5rem 0.35rem 0.25rem;
  display: flex;
  justify-content: center;
}

.collapsed .sidebar-cmd-btn {
  width: 36px;
  height: 32px;
  padding: 0;
  justify-content: center;
}

.collapsed .sidebar-nav-section {
  padding: 0.5rem 0.35rem;
  align-items: center;
}

.collapsed .sidebar-nav-item {
  width: 36px;
  height: 34px;
  padding: 0;
  justify-content: center;
  gap: 0;
  border-radius: 6px;
}

.collapsed .sidebar-footer {
  padding: 0.65rem 0.35rem;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.collapsed .sidebar-user-card {
  width: 32px;
  height: 32px;
  padding: 0;
  justify-content: center;
  align-items: center;
  flex: none;
}

.collapsed .sidebar-footer-row {
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.collapsed .sidebar-logout-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  justify-content: center;
}

.collapsed .sidebar-footer :deep(.theme-toggle) {
  width: 32px;
  min-width: 32px;
  height: 32px;
}

@media (max-width: 1100px) and (min-width: 769px) {
  .app-sidebar:not(.collapsed) {
    position: absolute;
    left: 0;
    top: 0;
    z-index: 200;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }
}

@media (max-width: 768px) {
  .app-sidebar {
    display: none;
  }
}
</style>
