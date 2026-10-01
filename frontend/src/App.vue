<template>
  <LoginView v-if="!auth.isAuthenticated.value" @authenticated="handleAuthenticated" />
  <div v-else-if="auth.user.value?.must_change_password" class="force-pwd-wrapper">
    <div class="force-pwd-theme"><ThemeToggle compact /></div>
    <div class="force-pwd-card">
      <div class="force-pwd-badge">安全提醒</div>
      <h2>请修改初始密码</h2>
      <p class="force-pwd-desc">您的账户当前使用系统分配的临时密码，为了账户安全，必须修改密码后方可继续使用（新密码至少 8 位）。</p>

      <div v-if="changePwdError" class="force-pwd-alert error">{{ changePwdError }}</div>
      <div v-if="changePwdSuccess" class="force-pwd-alert success">{{ changePwdSuccess }}</div>

      <div class="force-pwd-field">
        <label>当前临时密码</label>
        <input v-model="oldPassword" type="password" placeholder="请输入当前密码" />
      </div>
      <div class="force-pwd-field">
        <label>新密码（至少 8 位）</label>
        <input v-model="newPassword" type="password" placeholder="请输入新密码" />
      </div>
      <div class="force-pwd-field">
        <label>确认新密码</label>
        <input v-model="confirmPassword" type="password" placeholder="请再次输入新密码" />
      </div>

      <div class="force-pwd-actions">
        <button class="primary-btn" :disabled="submittingPwd" @click="handleForceChangePassword">
          {{ submittingPwd ? '提交中...' : '确认修改并进入系统' }}
        </button>
        <button class="secondary-btn" @click="auth.logout">退出登录</button>
      </div>
    </div>
  </div>
  <ExamView v-else-if="activeExam" :token="auth.token.value" :session-id="activeExam.id" @back="activeExam = null" />
  <PracticeViewV1 v-else-if="activeSession" :token="auth.token.value" :session-id="activeSession.id" @back="handleBackFromPractice" />
  <div v-else class="app-layout">
    <AppSidebar
      :current-page="page"
      :user="auth.user.value"
      @navigate="handleNavigate"
      @action="handleSidebarAction"
      @logout="auth.logout"
      @open-palette="openCommandPalette"
    />
    <main class="app-content-viewport">
      <LearningView v-if="page === 'learning'" :token="auth.token.value" @back="page = 'home'" @start-session="handleStartFromLearning" />
      <MistakesView v-else-if="page === 'mistakes'" :token="auth.token.value" @back="page = 'home'" @start-session="handleStartFromMistakes" />
      <ImportView v-else-if="page === 'import'" :token="auth.token.value" @back="page = 'home'" />
      <HomeView
        v-else
        ref="homeViewRef"
        :token="auth.token.value"
        :user="auth.user.value"
        @start="start"
        @mock-exam="startExam"
        @resume-session="handleResumeSession"
        @learning="page = 'learning'"
        @mistakes="page = 'mistakes'"
        @import="page = 'import'"
        @logout="auth.logout"
      />
    </main>
    <MobileNav v-if="isMobile" :current-page="page" @navigate="handleNavigate" @open-palette="openCommandPalette" />
    <CommandPalette ref="commandPaletteRef" :commands="commands" @execute="handleCommandExecute" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import LoginView from './views/LoginView.vue'
import HomeView from './views/HomeView.vue'
import PracticeViewV1 from './views/PracticeViewV1.vue'
import LearningView from './views/LearningView.vue'
import MistakesView from './views/MistakesView.vue'
import ImportView from './views/ImportView.vue'
import ExamView from './features/exam/ExamView.vue'
import AppSidebar from './components/AppSidebar.vue'
import MobileNav from './components/MobileNav.vue'
import CommandPalette from './components/CommandPalette.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import { useAuthStore } from './stores/authStore'
import { useSyncLoop } from './composables/useSyncLoop'
import { startSession } from './api/practice'
import { changePassword } from './api/auth'

const auth = useAuthStore()
useSyncLoop(auth.token, auth.user)
const activeSession = ref(null)
const activeExam = ref(null)
const page = ref('home')
const previousPage = ref('home')
const homeViewRef = ref(null)
const commandPaletteRef = ref(null)

function handleNavigate(targetPage) {
  page.value = targetPage
}

function openCommandPalette() {
  commandPaletteRef.value?.open()
}

function handleSidebarAction(action) {
  if (page.value !== 'home') {
    page.value = 'home'
    nextTick(() => {
      triggerHomeAction(action)
    })
  } else {
    triggerHomeAction(action)
  }
}

function triggerHomeAction(action) {
  if (!homeViewRef.value) return
  if (action === 'blueprint') homeViewRef.value.openBlueprintDialog?.()
  else if (action === 'drafts') homeViewRef.value.openDraftsDialog?.()
  else if (action === 'ai') homeViewRef.value.openAiConfigDialog?.()
  else if (action === 'profile') homeViewRef.value.openAssetsDialog?.()
  else if (action === 'create_bank') {
    homeViewRef.value.showCreateDialog = true
  }
}

const commands = computed(() => [
  { id: 'nav-home', title: '题库大厅', description: '浏览全部题库与统计', icon: 'layers', shortcut: 'G H', action: () => handleNavigate('home') },
  { id: 'nav-mistakes', title: '错题与斩杀', description: '错题归因与 FSRS 复习', icon: 'target', shortcut: 'G M', action: () => handleNavigate('mistakes') },
  { id: 'nav-learning', title: '学习诊断', description: '掌握度雷达与记忆曲线', icon: 'chart', shortcut: 'G D', action: () => handleNavigate('learning') },
  { id: 'nav-import', title: '导入题库', description: '解析导入试题文档', icon: 'inbox', shortcut: 'G I', action: () => handleNavigate('import') },
  { id: 'act-create', title: '创建新题库', description: '新建一个空题库', icon: 'plus', shortcut: 'C B', action: () => handleSidebarAction('create_bank') },
  { id: 'act-blueprint', title: '考试蓝图配置', description: '管理多知识点与分值配比', icon: 'blueprint', action: () => handleSidebarAction('blueprint') },
  { id: 'act-drafts', title: '变式草稿箱', description: '查看生成的题目变式', icon: 'draft', action: () => handleSidebarAction('drafts') },
  { id: 'act-ai', title: 'AI 助教与搜索设置', description: '配置 API Key 与模型', icon: 'cpu', action: () => handleSidebarAction('ai') },
  { id: 'act-profile', title: '个人资料与安全', description: '查看用户信息与登录状态', icon: 'user', action: () => handleSidebarAction('profile') },
  { id: 'act-logout', title: '退出登录', description: '清理当前凭证退出', icon: 'logout', action: () => auth.logout() },
])

function handleCommandExecute(cmd) {
  cmd.action?.()
}

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changePwdError = ref('')
const changePwdSuccess = ref('')
const submittingPwd = ref(false)

const isMobile = ref(false)
let mobileMql = null

function updateMobile(e) {
  isMobile.value = e.matches
}

onMounted(() => {
  auth.loadCurrentUser()
  if (typeof window !== 'undefined' && window.matchMedia) {
    mobileMql = window.matchMedia('(max-width: 768px)')
    isMobile.value = mobileMql.matches
    if (mobileMql.addEventListener) {
      mobileMql.addEventListener('change', updateMobile)
    } else if (mobileMql.addListener) {
      mobileMql.addListener(updateMobile)
    }
  }
})

onUnmounted(() => {
  if (mobileMql) {
    if (mobileMql.removeEventListener) {
      mobileMql.removeEventListener('change', updateMobile)
    } else if (mobileMql.removeListener) {
      mobileMql.removeListener(updateMobile)
    }
  }
})

function handleAuthenticated(result) {
  if (result?.token) auth.token.value = result.token
  auth.user.value = result?.user || result
}

async function handleForceChangePassword() {
  changePwdError.value = ''
  changePwdSuccess.value = ''
  if (!oldPassword.value) {
    changePwdError.value = '请输入当前临时密码'
    return
  }
  if (!newPassword.value || newPassword.value.length < 8) {
    changePwdError.value = '新密码长度至少为 8 位'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    changePwdError.value = '两次输入的新密码不一致'
    return
  }

  submittingPwd.value = true
  try {
    await changePassword(auth.token.value, oldPassword.value, newPassword.value)
    changePwdSuccess.value = '密码修改成功，正在进入系统...'
    if (auth.user.value) {
      auth.user.value.must_change_password = false
    }
  } catch (err) {
    changePwdError.value = err.message || '密码修改失败，请检查旧密码是否正确'
  } finally {
    submittingPwd.value = false
  }
}

async function start(bank) {
  previousPage.value = 'home'
  activeSession.value = await startSession(auth.token.value, { bank_id: bank.id, mode: 'PRACTICE' })
}
function handleStartFromMistakes(session) {
  previousPage.value = 'mistakes'
  activeSession.value = session
}
function handleStartFromLearning(session) {
  previousPage.value = 'learning'
  activeSession.value = session
}
function handleResumeSession(session) {
  if (session.mode === 'EXAM') {
    activeExam.value = session
  } else {
    previousPage.value = 'home'
    activeSession.value = session
  }
}
function handleBackFromPractice() {
  activeSession.value = null
  page.value = previousPage.value || 'home'
  previousPage.value = 'home'
}
function startExam(session) { activeExam.value = session }
</script>

<style scoped>
.force-pwd-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  padding: 1rem;
}
.force-pwd-theme {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 2;
}
.force-pwd-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
  padding: 2.5rem;
  max-width: 440px;
  width: 100%;
}
.force-pwd-badge {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  background: var(--danger-light);
  color: var(--danger);
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 9999px;
  margin-bottom: 0.75rem;
}
.force-pwd-desc {
  color: var(--text-muted);
  font-size: 0.875rem;
  line-height: 1.5;
  margin-top: 0.5rem;
  margin-bottom: 1.5rem;
}
.force-pwd-alert {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}
.force-pwd-alert.error {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-border);
}
.force-pwd-alert.success {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid var(--success-border);
}
.force-pwd-field {
  margin-bottom: 1rem;
}
.force-pwd-field label {
  display: block;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-main);
  margin-bottom: 0.35rem;
}
.force-pwd-field input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--text-main);
  background: var(--bg-page);
  font-size: 0.875rem;
  outline: none;
  transition: border-color 0.2s;
}
.force-pwd-field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent);
}
.force-pwd-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.primary-btn {
  width: 100%;
  padding: 0.75rem;
  background: var(--primary);
  color: var(--on-primary);
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.secondary-btn {
  width: 100%;
  padding: 0.65rem;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
}
.secondary-btn:hover {
  background: var(--bg-subtle);
}
</style>
