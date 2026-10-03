<template>
  <div class="app-layout">
    <AppSidebar
      :current-page="currentRouteName"
      :user="auth.user.value"
      @navigate="handleNavigate"
      @action="handleSidebarAction"
      @change-password="showChangePasswordModal = true"
      @logout="auth.logout"
      @open-palette="openCommandPalette"
    />
    <main class="app-content-viewport">
      <router-view
        :token="auth.token.value"
        :user="auth.user.value"
        @start="handleStart"
        @mock-exam="handleMockExam"
        @resume-session="handleResumeSession"
        @start-session="handleStartSession"
        @learning="router.push('/learning')"
        @mistakes="router.push('/mistakes')"
        @import="router.push('/import')"
        @logout="auth.logout"
        @back="handleBack"
      />
    </main>
    <MobileNav v-if="isMobile" :current-page="currentRouteName" @navigate="handleNavigate" @open-palette="openCommandPalette" />
    <CommandPalette
      ref="commandPaletteRef"
      :commands="commands"
      :banks="banks"
      @execute="handleCommandExecute"
      @select-bank="handleSelectBank"
    />

    <!-- Global App Shell Modals: Open in-place across all pages without changing background -->
    <BlueprintModal
      v-if="activeDialog === 'blueprint'"
      :token="auth.token.value"
      @close="activeDialog = null"
    />
    <AiDraftsModal
      v-if="activeDialog === 'drafts'"
      :token="auth.token.value"
      @close="activeDialog = null"
    />
    <AiConfigModal
      v-if="activeDialog === 'ai'"
      :token="auth.token.value"
      @close="activeDialog = null"
    />
    <ChangePasswordModal
      v-if="showChangePasswordModal"
      :token="auth.token.value"
      @close="showChangePasswordModal = false"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'
import MobileNav from '../components/MobileNav.vue'
import CommandPalette from '../components/CommandPalette.vue'
import BlueprintModal from '../components/BlueprintModal.vue'
import AiDraftsModal from '../components/AiDraftsModal.vue'
import AiConfigModal from '../components/AiConfigModal.vue'
import ChangePasswordModal from '../components/ChangePasswordModal.vue'
import { useAuthStore } from '../stores/authStore'
import { listBanks } from '../api/banks'
import { startSession } from '../api/practice'
import { useLocale } from '../composables/useLocale.js'
import { useTheme } from '../composables/useTheme.js'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t, toggleLocale } = useLocale()
const { toggleTheme } = useTheme()

const commandPaletteRef = ref(null)
const banks = ref([])
const isMobile = ref(false)
const activeDialog = ref(null)
const showChangePasswordModal = ref(false)

const currentRouteName = computed(() => {
  return route.name || 'home'
})

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

function handleOpenDialogEvent(e) {
  const dlg = e.detail
  if (dlg) activeDialog.value = dlg
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  window.addEventListener('easyexam:open-dialog', handleOpenDialogEvent)
  if (auth.token.value) loadBanks()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('easyexam:open-dialog', handleOpenDialogEvent)
})

async function loadBanks() {
  if (!auth.token.value) return
  try {
    const res = await listBanks(auth.token.value)
    banks.value = res?.banks || (Array.isArray(res) ? res : [])
  } catch (err) {
    console.error('Failed to load banks for command palette', err)
  }
}

function handleNavigate(targetPage) {
  if (targetPage === 'home') router.push('/')
  else if (targetPage === 'learning') router.push('/learning')
  else if (targetPage === 'mistakes') router.push('/mistakes')
  else if (targetPage === 'import') router.push('/import')
  else if (targetPage === 'notes') router.push('/notes')
  else router.push('/')
}

function handleSidebarAction(action) {
  if (action === 'blueprint' || action === 'drafts' || action === 'ai') {
    // Open in-place over whatever current route the user is on! Zero background change!
    activeDialog.value = action
  } else if (action === 'change-password') {
    showChangePasswordModal.value = true
  } else if (action === 'profile' || action === 'notes') {
    router.push('/notes')
  }
}

function openCommandPalette() {
  if (auth.token.value) loadBanks()
  commandPaletteRef.value?.open()
}

const commands = computed(() => [
  { id: 'home', title: t('nav.home'), icon: 'layers', action: () => router.push('/') },
  { id: 'mistakes', title: t('nav.mistakes'), icon: 'target', action: () => router.push('/mistakes') },
  { id: 'learning', title: t('nav.learning'), icon: 'chart', action: () => router.push('/learning') },
  { id: 'notes', title: t('nav.notes'), icon: 'edit', action: () => router.push('/notes') },
  { id: 'import', title: t('nav.imports'), icon: 'inbox', action: () => router.push('/import') },
  { id: 'blueprint', title: t('sidebar.blueprint'), icon: 'blueprint', action: () => handleSidebarAction('blueprint') },
  { id: 'drafts', title: t('sidebar.drafts'), icon: 'draft', action: () => handleSidebarAction('drafts') },
  { id: 'ai', title: t('sidebar.ai_search'), icon: 'cpu', action: () => handleSidebarAction('ai') },
  { id: 'theme', title: t('ui.k0048'), icon: 'zap', action: () => toggleTheme() },
  { id: 'locale', title: t('locale.switch_language'), icon: 'globe', action: () => toggleLocale() },
  { id: 'logout', title: t('nav.logout'), icon: 'logout', action: () => auth.logout() },
])

function handleCommandExecute(cmd) {
  if (typeof cmd.action === 'function') {
    cmd.action()
  }
}

async function handleStart(bank) {
  try {
    const session = await startSession(auth.token.value, { bank_id: bank.id, mode: 'PRACTICE' })
    router.push(`/practice/${session.id}`)
  } catch (err) {
    console.error('Failed to start practice session', err)
  }
}

function handleMockExam(session) {
  router.push(`/exam/${session.id}`)
}

function handleResumeSession(session) {
  if (session.mode === 'EXAM') {
    router.push(`/exam/${session.id}`)
  } else {
    router.push(`/practice/${session.id}`)
  }
}

function handleStartSession(session) {
  router.push(`/practice/${session.id}`)
}

function handleBack() {
  router.push('/')
}

function handleSelectBank(bank) {
  handleStart(bank)
}
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100vw;
  min-height: 100vh;
  background: var(--bg-page);
  color: var(--text-main);
  overflow-x: hidden;
}

.app-content-viewport {
  flex: 1;
  min-width: 0;
  min-height: 100vh;
  overflow-y: auto;
  position: relative;
  scrollbar-gutter: stable;
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
    padding-bottom: 0;
  }
  .app-content-viewport {
    padding-bottom: calc(64px + env(safe-area-inset-bottom, 16px));
  }
}
</style>
