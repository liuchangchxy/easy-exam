<template>
  <div class="shell">
    <AppSidebar
      :current-page="currentPage"
      :user="auth.user.value"
      :bank-count="banks.length"
      :review-count="reviewCount"
      :learning-trends="learningTrends"
      :theme="theme"
      @navigate="handleNavigate"
      @action="handleSidebarAction"
      @change-password="showChangePasswordModal = true"
      @logout="auth.logout"
      @toggle-theme="toggleTheme"
      @toggle-locale="toggleLocale"
    />
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <div class="crumb">
            <span class="here">{{ sectionLabel }}</span>
          </div>
        </div>
        <div class="topbar-right">
          <button type="button" class="icon-btn" :title="t('ep.action.search')" :aria-label="t('ep.action.search')" @click="openCommandPalette">
            <LinearIcon name="search" :size="16" />
          </button>
          <button type="button" class="icon-btn" :title="t('ep.action.theme')" :aria-label="t('ep.action.theme')" @click="toggleTheme">
            <LinearIcon :name="theme === 'dark' ? 'sun' : 'moon'" :size="16" />
          </button>
          <button type="button" class="icon-btn" :title="t('ep.action.language')" :aria-label="t('ep.action.language')" @click="toggleLocale">
            <LinearIcon name="globe" :size="16" />
          </button>
          <button type="button" class="user-mini" style="width: 34px; padding: 2px" :aria-label="t('ep.account.menu')" @click="router.push('/settings')">
            <span class="avatar">{{ userInitial }}</span>
          </button>
        </div>
      </header>

      <header class="mobile-top">
        <span class="brand-mark" aria-hidden="true">易</span>
        <span class="mt-title">{{ sectionLabel }}</span>
        <span class="mt-actions">
          <button type="button" class="icon-btn" :aria-label="t('ep.action.search')" @click="openCommandPalette">
            <LinearIcon name="search" :size="17" />
          </button>
          <button type="button" class="icon-btn" :aria-label="t('ep.account.menu')" @click="router.push('/settings')">
            <span class="avatar" style="width: 26px; height: 26px; font-size: 12px">{{ userInitial }}</span>
          </button>
        </span>
      </header>

      <main id="main-content" class="content">
        <router-view
          :token="auth.token.value"
          :user="auth.user.value"
          @start="handleStart"
          @mock-exam="handleMockExam"
          @resume-session="handleResumeSession"
          @start-session="handleStartSession"
          @learning="router.push('/review')"
          @mistakes="router.push('/review?tab=mistakes')"
          @import="router.push('/import')"
          @logout="auth.logout"
          @back="handleBack"
        />
      </main>
    </div>

    <MobileNav :current-page="currentPage" @navigate="handleNavigate" />
    <CommandPalette
      ref="commandPaletteRef"
      :commands="commands"
      :banks="banks"
      @execute="handleCommandExecute"
      @select-bank="handleSelectBank"
    />

    <BlueprintModal v-if="activeDialog === 'blueprint'" :token="auth.token.value" @close="activeDialog = null" />
    <AiDraftsModal v-if="activeDialog === 'drafts'" :token="auth.token.value" @close="activeDialog = null" />
    <AiConfigModal v-if="activeDialog === 'ai'" :token="auth.token.value" @close="activeDialog = null" />
    <ChangePasswordModal v-if="showChangePasswordModal" :token="auth.token.value" @close="showChangePasswordModal = false" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'
import MobileNav from '../components/MobileNav.vue'
import CommandPalette from '../components/CommandPalette.vue'
import BlueprintModal from '../components/BlueprintModal.vue'
import AiDraftsModal from '../components/AiDraftsModal.vue'
import AiConfigModal from '../components/AiConfigModal.vue'
import ChangePasswordModal from '../components/ChangePasswordModal.vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useAuthStore } from '../stores/authStore'
import { listBanks } from '../api/banks'
import { listDueMistakes } from '../api/mistakes'
import { startSession } from '../api/practice'
import { getLearningTrends } from '../api/learning'
import { useLocale } from '../composables/useLocale.js'
import { useTheme } from '../composables/useTheme.js'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t, toggleLocale } = useLocale()
const { theme, toggleTheme } = useTheme()

const commandPaletteRef = ref(null)
const banks = ref([])
const reviewCount = ref(0)
const learningTrends = ref(null)
const activeDialog = ref(null)
const showChangePasswordModal = ref(false)

const userInitial = computed(() => {
  const name = auth.user.value?.username
  return name ? name.charAt(0).toUpperCase() : '?'
})

const currentPage = computed(() => {
  const n = route.name
  if (n === 'home') return 'today'
  if (n === 'banks' || n === 'bank-manage' || n === 'bank-detail' || n === 'import') return 'banks'
  if (n === 'review' || n === 'mistakes' || n === 'learning') return 'review'
  if (n === 'exams') return 'exam'
  if (n === 'notes') return 'notes'
  if (n === 'settings') return 'settings'
  return 'today'
})

const sectionLabel = computed(() => {
  const map = {
    today: 'ep.nav.today',
    banks: 'ep.nav.banks',
    review: 'ep.nav.review',
    exam: 'ep.nav.exams',
    notes: 'ep.nav.library',
    settings: 'ep.nav.settings',
  }
  return t(map[currentPage.value] || 'ep.nav.today')
})

function handleOpenDialogEvent(e) {
  const dlg = e.detail
  if (dlg) activeDialog.value = dlg
}

onMounted(() => {
  window.addEventListener('easyexam:open-dialog', handleOpenDialogEvent)
  if (auth.token.value) loadShellData()
})

onUnmounted(() => {
  window.removeEventListener('easyexam:open-dialog', handleOpenDialogEvent)
  delete document.body.dataset.route
})

async function loadShellData() {
  if (!auth.token.value) return
  const [bankResult, dueResult, trendResult] = await Promise.allSettled([
    listBanks(auth.token.value),
    listDueMistakes(auth.token.value),
    getLearningTrends(auth.token.value, { window_days: 7 }),
  ])

  if (bankResult.status === 'fulfilled') {
    const res = bankResult.value
    banks.value = res?.banks || (Array.isArray(res) ? res : [])
  } else {
    console.error('Failed to load banks for command palette', bankResult.reason)
  }

  reviewCount.value = dueResult.status === 'fulfilled' && Array.isArray(dueResult.value)
    ? dueResult.value.length
    : 0
  learningTrends.value = trendResult.status === 'fulfilled' ? trendResult.value : null
}

watch(
  () => route.name,
  (name, previous) => {
    if (typeof document !== 'undefined') {
      document.body.dataset.route = typeof name === 'string' ? name : 'today'
    }
    // Returning from practice/exam after a session ends must refresh the shell
    // counts (due review, banks, trends). Skip practice/exam routes themselves
    // to avoid fetching on every question transition.
    if (previous !== undefined && (name === 'home' || name === 'review' || name === 'banks')) {
      loadShellData()
    }
  },
  { immediate: true }
)

function handleNavigate(targetPage) {
  if (targetPage === 'today') router.push('/')
  else if (targetPage === 'banks') router.push('/banks')
  else if (targetPage === 'review') router.push('/review')
  else if (targetPage === 'exam') router.push('/exams')
  else if (targetPage === 'notes') router.push('/notes')
  else if (targetPage === 'settings') router.push('/settings')
  else router.push('/')
}

function handleSidebarAction(action) {
  if (action === 'blueprint' || action === 'drafts' || action === 'ai') {
    activeDialog.value = action
  } else if (action === 'change-password') {
    showChangePasswordModal.value = true
  } else if (action === 'settings') {
    router.push('/settings')
  }
}

function openCommandPalette() {
  if (auth.token.value) loadShellData()
  commandPaletteRef.value?.open()
}

const commands = computed(() => [
  { id: 'today', title: t('ep.nav.today'), icon: 'home', action: () => router.push('/') },
  { id: 'banks', title: t('ep.nav.banks'), icon: 'library', action: () => router.push('/banks') },
  { id: 'review', title: t('ep.nav.review'), icon: 'review', action: () => router.push('/review') },
  { id: 'exam', title: t('ep.nav.exams'), icon: 'exam', action: () => router.push('/exams') },
  { id: 'notes', title: t('ep.nav.library'), icon: 'note', action: () => router.push('/notes') },
  { id: 'settings', title: t('ep.nav.settings'), icon: 'settings', action: () => router.push('/settings') },
  { id: 'blueprint', title: t('sidebar.blueprint'), icon: 'blueprint', action: () => handleSidebarAction('blueprint') },
  { id: 'drafts', title: t('sidebar.drafts'), icon: 'draft', action: () => handleSidebarAction('drafts') },
  { id: 'ai', title: t('sidebar.ai_search'), icon: 'cpu', action: () => handleSidebarAction('ai') },
  { id: 'theme', title: t('ep.action.theme'), icon: 'moon', action: () => toggleTheme() },
  { id: 'locale', title: t('ep.action.language'), icon: 'globe', action: () => toggleLocale() },
  { id: 'logout', title: t('ep.account.logout'), icon: 'logout', action: () => auth.logout() },
])

function handleCommandExecute(cmd) {
  if (typeof cmd.action === 'function') cmd.action()
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
  if (session.mode === 'EXAM') router.push(`/exam/${session.id}`)
  else router.push(`/practice/${session.id}`)
}

function handleStartSession(session) {
  if (session?.mode === 'EXAM') router.push(`/exam/${session.id}`)
  else router.push(`/practice/${session.id}`)
}

function handleBack() {
  router.push('/')
}

function handleSelectBank(bank) {
  handleStart(bank)
}
</script>
