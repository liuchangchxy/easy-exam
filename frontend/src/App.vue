<template>
  <LoginView v-if="!auth.isAuthenticated.value" @authenticated="handleAuthenticated" />
  <div v-else-if="auth.user.value?.must_change_password" class="force-pwd-wrapper">
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
  <LearningView v-else-if="page === 'learning'" :token="auth.token.value" @back="page = 'home'" @start-session="handleStartFromLearning" />
  <MistakesView v-else-if="page === 'mistakes'" :token="auth.token.value" @back="page = 'home'" @start-session="handleStartFromMistakes" />
  <ImportView v-else-if="page === 'import'" :token="auth.token.value" @back="page = 'home'" />
  <HomeView v-else :token="auth.token.value" :user="auth.user.value" @start="start" @mock-exam="startExam" @resume-session="handleResumeSession" @learning="page = 'learning'" @mistakes="page = 'mistakes'" @import="page = 'import'" @logout="auth.logout" />
</template>

<script setup>
import { onMounted, ref } from 'vue'
import LoginView from './views/LoginView.vue'
import HomeView from './views/HomeView.vue'
import PracticeViewV1 from './views/PracticeViewV1.vue'
import LearningView from './views/LearningView.vue'
import MistakesView from './views/MistakesView.vue'
import ImportView from './views/ImportView.vue'
import ExamView from './features/exam/ExamView.vue'
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

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changePwdError = ref('')
const changePwdSuccess = ref('')
const submittingPwd = ref(false)

onMounted(() => auth.loadCurrentUser())

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
  background: #f8fafc;
  padding: 1rem;
}
.force-pwd-card {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  padding: 2.5rem;
  max-width: 440px;
  width: 100%;
}
.force-pwd-badge {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  background: #fef2f2;
  color: #dc2626;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 9999px;
  margin-bottom: 0.75rem;
}
.force-pwd-desc {
  color: #475569;
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
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}
.force-pwd-alert.success {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}
.force-pwd-field {
  margin-bottom: 1rem;
}
.force-pwd-field label {
  display: block;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #334155;
  margin-bottom: 0.35rem;
}
.force-pwd-field input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.65rem 0.85rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.875rem;
  outline: none;
  transition: border-color 0.2s;
}
.force-pwd-field input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
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
  background: #2563eb;
  color: #ffffff;
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
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
}
.secondary-btn:hover {
  background: #f1f5f9;
}
</style>
