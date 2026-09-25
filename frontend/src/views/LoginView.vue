<template>
  <main class="auth-page">
    <section class="auth-card">
      <h1>易考宝</h1>
      <p>私有云刷题与错题消灭系统</p>
      <form @submit.prevent="submit">
        <input v-model="username" autocomplete="username" placeholder="用户名" required />
        <input v-model="password" autocomplete="current-password" placeholder="密码（至少 8 位）" type="password" required minlength="8" />
        <button type="submit" :disabled="busy">{{ busy ? '处理中…' : (registering ? '注册并登录' : '登录') }}</button>
      </form>
      <button class="link-button" type="button" @click="registering = !registering">{{ registering ? '已有账号？登录' : '首次使用？创建账号' }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import * as authApi from '../api/auth'

const emit = defineEmits(['authenticated'])
const username = ref('')
const password = ref('')
const registering = ref(false)
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (registering.value) await authApi.register(username.value, password.value)
    const result = await authApi.login(username.value, password.value)
    localStorage.setItem('easyexam_token', result.token)
    emit('authenticated', result)
  } catch (err) {
    error.value = err.detail || err.message || '操作失败'
  } finally { busy.value = false }
}
</script>
