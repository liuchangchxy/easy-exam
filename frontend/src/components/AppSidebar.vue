<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- Brand Top -->
    <div class="sidebar-header">
      <div class="sidebar-brand" @click="$emit('navigate', 'home')">
        <div class="brand-logo-gem">
          <LinearIcon name="zap" size="14" />
        </div>
        <div v-if="!isCollapsed" class="brand-text-group">
          <span class="brand-name">EasyExam</span>
          <span class="brand-version">v1.0.7</span>
        </div>
      </div>
      <button
        type="button"
        class="sidebar-toggle-btn"
        :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
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
    </nav>

    <!-- Utility / Workspace Section -->
    <div class="sidebar-nav-section secondary">
      <div v-if="!isCollapsed" class="nav-section-title">配置与工具</div>
      <button type="button" class="sidebar-nav-item sub" @click="$emit('action', 'blueprint')" :title="isCollapsed ? '蓝图配置' : ''">
        <LinearIcon name="blueprint" size="15" />
        <span v-if="!isCollapsed" class="nav-item-label">考试蓝图</span>
      </button>
      <button type="button" class="sidebar-nav-item sub" @click="$emit('action', 'drafts')" :title="isCollapsed ? '草稿箱' : ''">
        <LinearIcon name="draft" size="15" />
        <span v-if="!isCollapsed" class="nav-item-label">变式草稿箱</span>
      </button>
      <button type="button" class="sidebar-nav-item sub" @click="$emit('action', 'ai')" :title="isCollapsed ? 'AI配置' : ''">
        <LinearIcon name="cpu" size="15" />
        <span v-if="!isCollapsed" class="nav-item-label">AI与检索</span>
      </button>
    </div>

    <!-- User & Footer -->
    <div class="sidebar-footer">
      <div class="sidebar-user-card" @click="$emit('action', 'profile')" :title="isCollapsed ? user?.username : ''">
        <div class="user-avatar-dot" :class="user?.is_admin ? 'admin' : 'normal'"></div>
        <div v-if="!isCollapsed" class="user-info">
          <span class="user-name">{{ user?.username || '未登录' }}</span>
          <span class="user-role">{{ user?.is_admin ? '管理员' : '普通学员' }}</span>
        </div>
      </div>
      <ThemeToggle compact />
      <LocaleToggle compact />
      <button
        type="button"
        class="sidebar-logout-btn"
        :title="t('nav.logout')"
        @click="$emit('logout')"
      >
        <LinearIcon name="logout" size="15" />
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import LinearIcon from './LinearIcon.vue'
import ThemeToggle from './ThemeToggle.vue'
import LocaleToggle from './LocaleToggle.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

defineProps({
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

defineEmits(['navigate', 'action', 'logout', 'open-palette'])

const isCollapsed = ref(false)
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
  align-items: center;
  justify-content: space-between;
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
}

.sidebar-user-card:hover {
  background: var(--bg-subtle);
}

.user-avatar-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.user-avatar-dot.admin {
  background: var(--primary);
}

.user-avatar-dot.normal {
  background: var(--success);
}

.user-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  padding: 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-logout-btn:hover {
  background: var(--danger-light);
  color: var(--danger);
}

.collapsed .sidebar-footer {
  flex-direction: column;
  justify-content: center;
}

.collapsed .sidebar-footer :deep(.theme-toggle) {
  width: 32px;
  min-width: 32px;
  height: 32px;
}

@media (max-width: 768px) {
  .app-sidebar {
    display: none;
  }
}
</style>
