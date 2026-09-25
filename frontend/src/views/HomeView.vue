<template>
  <main class="home-page">
    <header class="page-header"><div><h1>我的题库</h1><p>{{ user?.username }}</p></div><nav><button @click="showCreateDialog = true">创建题库</button><button @click="$emit('import')">导入题目</button><button @click="$emit('learning')">学习诊断</button><button @click="$emit('mistakes')">错题与斩杀</button><button @click="$emit('logout')">退出</button></nav></header>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">正在加载题库…</p>
    <section v-else class="bank-grid">
      <article v-for="bank in banks" :key="bank.id" class="bank-card">
        <h2>{{ bank.name }}</h2><p>{{ bank.description || '暂无描述' }}</p><small>{{ bank.question_count }} 题</small>
        <div class="bank-actions">
          <button :disabled="!bank.question_count" @click="$emit('start', bank)">开始刷题</button>
          <button :disabled="!bank.question_count" @click="openExamSetup(bank)">开始模考</button>
        </div>
      </article>
      <p v-if="!banks.length">还没有题库，请点击上方“创建题库”或通过“导入题目”添加。</p>
    </section>
    <div v-if="showCreateDialog" class="exam-setup-backdrop" @click.self="showCreateDialog = false">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="create-bank-title" @submit.prevent="handleCreateBank">
        <h2 id="create-bank-title">创建新题库</h2>
        <label>题库名称
          <input v-model.trim="newBank.name" type="text" placeholder="例如：软考高项历年真题" required />
        </label>
        <label>分类
          <input v-model.trim="newBank.category" type="text" placeholder="默认分类" />
        </label>
        <label>描述说明
          <textarea v-model.trim="newBank.description" placeholder="关于该题库的简要说明" rows="3"></textarea>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showCreateDialog = false">取消</button>
          <button type="submit" :disabled="creatingBank">{{ creatingBank ? '正在创建…' : '确认创建' }}</button>
        </div>
      </form>
    </div>
    <div v-if="examBank" class="exam-setup-backdrop" @click.self="examBank = null">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="exam-setup-title" @submit.prevent="beginExam">
        <h2 id="exam-setup-title">模考设置</h2>
        <p>{{ examBank.name }} · 共 {{ examBank.question_count }} 题</p>
        <label>本次题量
          <input v-model.number="totalQuestions" type="number" min="1" :max="examBank.question_count" required />
        </label>
        <label>时长（分钟，0 表示不限时）
          <input v-model.number="timeLimitMinutes" type="number" min="0" max="600" required />
        </label>
        <p v-if="examError" class="error">{{ examError }}</p>
        <div class="bank-actions">
          <button type="button" @click="examBank = null">取消</button>
          <button type="submit" :disabled="startingExam">{{ startingExam ? '正在创建…' : '开始考试' }}</button>
        </div>
      </form>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { listBanks, createBank } from '../api/banks'
import { startExam } from '../api/exams'

const props = defineProps({ token: { type: String, required: true }, user: { type: Object, default: null } })
const emit = defineEmits(['start', 'mock-exam', 'learning', 'mistakes', 'import', 'logout'])
const banks = ref([])
const loading = ref(true)
const error = ref('')
const examBank = ref(null)
const totalQuestions = ref(0)
const timeLimitMinutes = ref(120)
const startingExam = ref(false)
const examError = ref('')
const showCreateDialog = ref(false)
const creatingBank = ref(false)
const createError = ref('')
const newBank = ref({ name: '', description: '', category: '默认分类' })

async function handleCreateBank() {
  if (!newBank.value.name) return
  creatingBank.value = true
  createError.value = ''
  try {
    await createBank(props.token, {
      name: newBank.value.name,
      description: newBank.value.description,
      category: newBank.value.category || '默认分类',
    })
    showCreateDialog.value = false
    newBank.value = { name: '', description: '', category: '默认分类' }
    banks.value = await listBanks(props.token)
  } catch (err) {
    createError.value = err.detail || err.message
  } finally {
    creatingBank.value = false
  }
}

function openExamSetup(bank) {
  examBank.value = bank
  totalQuestions.value = bank.question_count
  timeLimitMinutes.value = 120
  examError.value = ''
}

async function beginExam() {
  if (!examBank.value || totalQuestions.value < 1 || totalQuestions.value > examBank.value.question_count) return
  startingExam.value = true
  examError.value = ''
  try {
    const session = await startExam(props.token, {
      bank_id: examBank.value.id,
      total_questions: totalQuestions.value,
      time_limit: timeLimitMinutes.value,
    })
    emit('mock-exam', session)
    examBank.value = null
  } catch (err) {
    examError.value = err.detail || err.message
  } finally {
    startingExam.value = false
  }
}

onMounted(async () => {
  try { banks.value = await listBanks(props.token) } catch (err) { error.value = err.detail || err.message } finally { loading.value = false }
})
</script>

<style scoped>
.bank-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.exam-setup-backdrop { position: fixed; inset: 0; z-index: 20; display: grid; place-items: center; padding: 1rem; background: rgb(15 23 42 / 0.48); }
.exam-setup-dialog { width: min(100%, 28rem); display: grid; gap: 1rem; padding: 1.5rem; border-radius: 1rem; background: var(--bg-card); box-shadow: var(--shadow-lg); }
.exam-setup-dialog label { display: grid; gap: 0.35rem; }
.exam-setup-dialog input { width: 100%; padding: 0.65rem; border: 1px solid var(--border); border-radius: 0.5rem; }
</style>
