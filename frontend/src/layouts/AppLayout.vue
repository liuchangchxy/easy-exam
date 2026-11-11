<template>
  <div class="shell">
    <AppSidebar
      :current-page="currentPage"
      :user="auth.user.value"
      :bank-count="banks.length"
      :review-count="reviewCount"
      :learning-trends="learningTrends"
      :account-menu-open="accountMenuOpen && accountMenuAnchor === 'sidebar'"
      @navigate="handleNavigate"
      @account-menu="toggleAccountMenu"
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
          <button
            type="button"
            class="user-mini"
            style="width: 34px; padding: 2px"
            data-account-trigger
            aria-haspopup="menu"
            :aria-expanded="accountMenuOpen && accountMenuAnchor === 'topbar' ? 'true' : 'false'"
            :aria-label="t('ep.account.menu')"
            @click="toggleAccountMenu($event.currentTarget)"
          >
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
          <button
            type="button"
            class="icon-btn"
            data-account-trigger
            aria-haspopup="menu"
            :aria-expanded="accountMenuOpen && accountMenuAnchor === 'mobile' ? 'true' : 'false'"
            :aria-label="t('ep.account.menu')"
            @click="toggleAccountMenu($event.currentTarget)"
          >
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

    <MobileNav
      :current-page="currentPage"
      :more-open="moreMenuOpen"
      @navigate="handleNavigate"
      @more="toggleMoreMenu"
    />

    <!-- One account menu for every avatar; it is anchored to whichever trigger opened it. -->
    <div
      v-if="accountMenuOpen"
      ref="accountMenuRef"
      class="account-menu"
      role="menu"
      :aria-label="t('ep.account.menu')"
      :style="accountMenuStyle"
      @focusout="handleAccountMenuFocusOut"
    >
      <button type="button" role="menuitem" class="popover-action" @click="openChangePassword">
        <LinearIcon name="key" :size="15" />
        <span>{{ t('ep.account.change_password') }}</span>
      </button>
      <button type="button" role="menuitem" class="popover-action is-danger" @click="requestLogout">
        <LinearIcon name="logout" :size="15" />
        <span>{{ t('ep.account.logout') }}</span>
      </button>
    </div>

    <!-- Mobile chrome overflow: the single mobile owner of Settings, theme and language. -->
    <div
      v-if="moreMenuOpen"
      ref="moreMenuRef"
      class="chrome-more-menu"
      role="menu"
      :aria-label="t('ep.nav.more')"
      @focusout="handleMoreMenuFocusOut"
    >
      <button type="button" role="menuitem" class="popover-action" @click="handleMoreNavigate('settings')">
        <LinearIcon name="settings" :size="15" />
        <span>{{ t('ep.nav.settings') }}</span>
      </button>
      <button type="button" role="menuitem" class="popover-action" @click="handleMoreTheme">
        <LinearIcon :name="theme === 'dark' ? 'sun' : 'moon'" :size="15" />
        <span>{{ t('ep.action.theme') }}</span>
      </button>
      <button type="button" role="menuitem" class="popover-action" @click="handleMoreLocale">
        <LinearIcon name="globe" :size="15" />
        <span>{{ t('ep.action.language') }}</span>
      </button>
    </div>

    <CommandPalette
      ref="commandPaletteRef"
      :commands="commands"
      :banks="banks"
      @execute="handleCommandExecute"
      @select-bank="handleSelectBank"
      @practice-bank="handlePracticeBank"
    />

    <AiDraftsModal v-if="activeDialog === 'drafts'" :token="auth.token.value" @close="activeDialog = null" />
    <ChangePasswordModal v-if="showChangePasswordModal" :token="auth.token.value" @close="showChangePasswordModal = false" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'
import MobileNav from '../components/MobileNav.vue'
import CommandPalette from '../components/CommandPalette.vue'
import AiDraftsModal from '../components/AiDraftsModal.vue'
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

// Shell menus: one account menu shared by every avatar, plus the mobile
// chrome menu that owns Settings / theme / language.
const accountMenuOpen = ref(false)
const accountMenuAnchor = ref('')
const accountMenuStyle = ref({})
const accountMenuRef = ref(null)
const accountMenuTrigger = ref(null)
const moreMenuOpen = ref(false)
const moreMenuRef = ref(null)
const moreMenuTrigger = ref(null)

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
  document.addEventListener('click', handleDocumentClick)
  document.addEventListener('keydown', handleDocumentKeydown)
  if (auth.token.value) loadShellData()
})

onUnmounted(() => {
  window.removeEventListener('easyexam:open-dialog', handleOpenDialogEvent)
  document.removeEventListener('click', handleDocumentClick)
  document.removeEventListener('keydown', handleDocumentKeydown)
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
    closeAccountMenu(false)
    closeMoreMenu(false)
    // Returning from practice/exam after a session ends must refresh the shell
    // counts (due review, banks, trends). Skip practice/exam routes themselves
    // to avoid fetching on every question transition.
    if (previous !== undefined && (name === 'home' || name === 'review' || name === 'banks')) {
      loadShellData()
    }
  },
  { immediate: true }
)

/* ---------- Account menu (one implementation, three anchors) ---------- */

function toggleAccountMenu(trigger) {
  if (accountMenuOpen.value && accountMenuTrigger.value === trigger) {
    closeAccountMenu(true)
    return
  }
  closeMoreMenu(false)
  accountMenuTrigger.value = trigger || null
  if (trigger?.closest?.('.sidebar')) accountMenuAnchor.value = 'sidebar'
  else if (trigger?.closest?.('.mobile-top')) accountMenuAnchor.value = 'mobile'
  else accountMenuAnchor.value = 'topbar'
  accountMenuOpen.value = true
  nextTick(() => {
    positionAccountMenu()
    accountMenuRef.value?.querySelector('button')?.focus()
  })
}

function positionAccountMenu() {
  if (!accountMenuTrigger.value || typeof window === 'undefined') return
  const rect = accountMenuTrigger.value.getBoundingClientRect()
  const width = 208
  if (accountMenuAnchor.value === 'sidebar') {
    accountMenuStyle.value = {
      left: `${Math.min(rect.right + 8, window.innerWidth - width - 8)}px`,
      bottom: `${Math.max(8, window.innerHeight - rect.bottom)}px`,
    }
  } else {
    const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8))
    accountMenuStyle.value = { left: `${left}px`, top: `${rect.bottom + 6}px` }
  }
}

function closeAccountMenu(restoreFocus) {
  if (!accountMenuOpen.value) return
  const trigger = accountMenuTrigger.value
  accountMenuOpen.value = false
  accountMenuAnchor.value = ''
  accountMenuTrigger.value = null
  if (restoreFocus && trigger) nextTick(() => trigger.focus?.())
}

function handleAccountMenuFocusOut(event) {
  const next = event.relatedTarget
  if (next?.closest?.('[data-account-trigger]')) return
  if (next && accountMenuRef.value?.contains(next)) return
  closeAccountMenu(false)
}

function openChangePassword() {
  closeAccountMenu(false)
  showChangePasswordModal.value = true
}

function requestLogout() {
  const message = t('ep.account.logout_confirm')
  if (typeof window !== 'undefined' && typeof window.confirm === 'function' && !window.confirm(message)) return
  closeAccountMenu(false)
  auth.logout()
}

/* ---------- Mobile chrome menu (Settings / theme / language) ---------- */

function toggleMoreMenu(trigger) {
  if (moreMenuOpen.value && moreMenuTrigger.value === trigger) {
    closeMoreMenu(true)
    return
  }
  closeAccountMenu(false)
  moreMenuTrigger.value = trigger || null
  moreMenuOpen.value = true
  nextTick(() => {
    moreMenuRef.value?.querySelector('button')?.focus()
  })
}

function closeMoreMenu(restoreFocus) {
  if (!moreMenuOpen.value) return
  const trigger = moreMenuTrigger.value
  moreMenuOpen.value = false
  moreMenuTrigger.value = null
  if (restoreFocus && trigger) nextTick(() => trigger.focus?.())
}

function handleMoreMenuFocusOut(event) {
  const next = event.relatedTarget
  if (next?.closest?.('[data-more-trigger]')) return
  if (next && moreMenuRef.value?.contains(next)) return
  closeMoreMenu(false)
}

function handleMoreNavigate(target) {
  closeMoreMenu(false)
  handleNavigate(target)
}

function handleMoreTheme() {
  toggleTheme()
  closeMoreMenu(true)
}

function handleMoreLocale() {
  toggleLocale()
  closeMoreMenu(true)
}

/* ---------- Dismissal shared by both shell menus ---------- */

function handleDocumentClick(event) {
  const target = event.target
  if (!(target instanceof Element)) return
  if (accountMenuOpen.value
      && !target.closest('.account-menu')
      && !target.closest('[data-account-trigger]')) {
    closeAccountMenu(false)
  }
  if (moreMenuOpen.value
      && !target.closest('.chrome-more-menu')
      && !target.closest('[data-more-trigger]')) {
    closeMoreMenu(false)
  }
}

function handleDocumentKeydown(event) {
  if (event.key !== 'Escape') return
  if (accountMenuOpen.value) {
    event.preventDefault()
    closeAccountMenu(true)
  }
  if (moreMenuOpen.value) {
    event.preventDefault()
    closeMoreMenu(true)
  }
}

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
  if (action === 'drafts') {
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
  { id: 'drafts', title: t('sidebar.drafts'), icon: 'draft', action: () => handleSidebarAction('drafts') },
  { id: 'ai', title: t('sidebar.ai_search'), icon: 'cpu', action: () => router.push({ path: '/settings', query: { section: 'ai' } }) },
  { id: 'theme', title: t('ep.action.theme'), icon: 'moon', action: () => toggleTheme() },
  { id: 'locale', title: t('ep.action.language'), icon: 'globe', action: () => toggleLocale() },
  { id: 'logout', title: t('ep.account.logout'), icon: 'logout', action: () => requestLogout() },
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
  // A palette row opens the bank, matching every other bank row in the app.
  router.push(`/banks/${bank.id}`)
}

function handlePracticeBank(bank) {
  // Starting practice stays an explicit secondary action inside the row.
  handleStart(bank)
}
</script>

<style scoped>
.account-menu,
.chrome-more-menu {
  position: fixed;
  width: 208px;
  padding: 6px;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-xs);
  box-shadow: var(--shadow-2);
  z-index: 130;
}

.chrome-more-menu {
  left: 12px;
  right: 12px;
  bottom: calc(64px + env(safe-area-inset-bottom) + 8px);
  width: auto;
  z-index: 110;
}

.popover-action {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  min-height: 36px;
  padding: 0 9px;
  border: 0;
  background: none;
  color: var(--ink-2);
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
}

.popover-action:hover { background: var(--surface-2); color: var(--ink); }
.popover-action.is-danger { color: var(--bad); }
.popover-action.is-danger:hover { background: var(--bad-soft); }

@media (min-width: 769px) {
  .chrome-more-menu { display: none; }
}
</style>
