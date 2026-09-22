<template>
  <div v-if="visible" class="tutor-overlay" @click.self="$emit('close')">
    <div class="tutor-drawer animate-slide-up">
      <!-- Drawer Header -->
      <div class="tutor-header">
        <div class="tutor-title-group">
          <span class="tutor-icon">🤖</span>
          <div>
            <h3 class="tutor-title">AI 助教深度点拨</h3>
            <p class="tutor-subtitle">已自动打包当前题目与错选上下文</p>
          </div>
        </div>
        <button class="tutor-close-btn" @click="$emit('close')" aria-label="关闭AI助教">✕</button>
      </div>

      <!-- Quick Context Summary Bar -->
      <div class="tutor-context-summary">
        <div class="summary-tag">
          <span class="tag-label">你的选择:</span>
          <span class="tag-val" :class="context.user_answer === context.correct_answer ? 'text-success' : 'text-danger'">
            {{ formatAnswer(context.user_answer) || '未作答' }}
          </span>
        </div>
        <div class="summary-tag">
          <span class="tag-label">正确答案:</span>
          <span class="tag-val text-success">{{ formatAnswer(context.correct_answer) }}</span>
        </div>
        <div v-if="context.mistake_cause" class="summary-tag">
          <span class="tag-label">归因:</span>
          <span class="tag-val text-warning">{{ formatCause(context.mistake_cause) }}</span>
        </div>
      </div>

      <!-- Messages Thread -->
      <div ref="messagesContainer" class="tutor-messages">
        <!-- Welcome / Auto prompt on first open -->
        <div v-if="messages.length === 0 && !isStreaming" class="welcome-box">
          <p class="welcome-tip">👋 我是你的专属刷题 AI 助教！点击下方快捷提问，我将一针见血为你剖析考点：</p>
        </div>

        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="message-row"
          :class="msg.role === 'user' ? 'row-user' : 'row-assistant'"
        >
          <div class="message-bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'">
            <div v-if="msg.role === 'assistant'" class="bubble-header">
              <span class="bubble-role">AI 助教</span>
            </div>
            <div class="bubble-content" style="white-space: pre-wrap;">{{ msg.content }}</div>
          </div>
        </div>

        <!-- Streaming cursor indicator -->
        <div v-if="isStreaming" class="streaming-indicator">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="streaming-text">AI 正在组织思路...</span>
        </div>
      </div>

      <!-- Quick Preset Prompts -->
      <div class="quick-prompts-bar">
        <button
          v-for="(prompt, idx) in quickPrompts"
          :key="idx"
          class="btn-quick-prompt"
          :disabled="isStreaming"
          @click="sendQuery(prompt)"
        >
          {{ prompt }}
        </button>
      </div>

      <!-- Input Bar -->
      <div class="tutor-input-bar">
        <input
          v-model="inputQuery"
          type="text"
          placeholder="追问考点、解题技巧或记忆口诀..."
          class="tutor-input"
          :disabled="isStreaming"
          @keydown.enter="sendQuery(inputQuery)"
        />
        <button
          class="btn-send"
          :disabled="isStreaming || !inputQuery.trim()"
          @click="sendQuery(inputQuery)"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  context: {
    type: Object,
    default: () => ({
      stem: '',
      options: [],
      user_answer: '',
      correct_answer: '',
      official_explanation: '',
      mistake_cause: ''
    })
  }
})

const emit = defineEmits(['close'])

const messages = ref([])
const inputQuery = ref('')
const isStreaming = ref(false)
const messagesContainer = ref(null)

const quickPrompts = [
  '🎯 为什么选错？请一针见血点拨',
  '💡 通俗解释考点与陷阱',
  '🔄 生成一道同类变式题',
  '🧠 总结考点记忆口诀'
]

function formatAnswer(ans) {
  if (Array.isArray(ans)) return ans.join(', ')
  if (typeof ans === 'boolean') return ans ? '正确' : '错误'
  return String(ans || '')
}

function formatCause(cause) {
  const map = {
    READING_MISS: '审题粗心',
    CONCEPT_GAP: '概念盲区',
    METHOD_GAP: '思路不熟',
    OPTION_TRAP: '陷阱诱导',
    CALCULATION_ERROR: '计算失误',
    CARELESSNESS: '其他手滑'
  }
  return map[cause] || cause
}

// Reset or trigger initial tutor greeting when opening drawer
watch(
  () => props.visible,
  (val) => {
    if (val && messages.value.length === 0) {
      // Auto-trigger first-turn explanation if user answered incorrectly
      if (props.context.user_answer && props.context.user_answer !== props.context.correct_answer) {
        sendQuery('🎯 为什么选错？请一针见血点拨')
      }
    }
  }
)

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function sendQuery(queryText) {
  const trimmed = (queryText || '').trim()
  if (!trimmed || isStreaming.value) return

  inputQuery.value = ''
  messages.value.push({ role: 'user', content: trimmed })
  scrollToBottom()

  isStreaming.value = true

  // Create empty assistant message slot
  const assistantMsgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })

  try {
    const history = messages.value.slice(0, assistantMsgIndex).map(m => ({
      role: m.role,
      content: m.content
    }))

    const payload = {
      question_context: props.context,
      user_query: trimmed,
      history: history
    }

    const response = await fetch('/api/ai/tutor/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // keep trailing incomplete line

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (!trimmedLine.startsWith('data:')) continue

        const dataContent = trimmedLine.replace(/^data:\s*/, '')
        if (dataContent === '[DONE]') {
          break
        }
        messages.value[assistantMsgIndex].content += dataContent
        scrollToBottom()
      }
    }

    if (buffer.trim().startsWith('data:')) {
      const dataContent = buffer.trim().replace(/^data:\s*/, '')
      if (dataContent !== '[DONE]') {
        messages.value[assistantMsgIndex].content += dataContent
      }
    }
  } catch (err) {
    console.warn('AI tutor stream failed:', err)
    if (!messages.value[assistantMsgIndex].content) {
      messages.value[assistantMsgIndex].content =
        '【离线提示】当前 AI 助教连接未就绪或 NAS 本地模型离线。本题官方解析：\n\n' +
        (props.context.official_explanation || '暂无官方解析')
    }
  } finally {
    isStreaming.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
.tutor-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  z-index: 110;
  display: flex;
  justify-content: flex-end;
}

.tutor-drawer {
  width: 100%;
  max-width: 520px;
  height: 100vh;
  background-color: #ffffff;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

@media (max-width: 640px) {
  .tutor-overlay {
    align-items: flex-end;
  }
  .tutor-drawer {
    height: 85vh;
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
  }
}

.tutor-header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
}

.tutor-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tutor-icon {
  font-size: 1.75rem;
}

.tutor-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-main);
}

.tutor-subtitle {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.tutor-close-btn {
  font-size: 1.25rem;
  color: var(--text-muted);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}
.tutor-close-btn:hover {
  background-color: #f1f5f9;
}

.tutor-context-summary {
  display: flex;
  gap: 12px;
  padding: 8px 20px;
  background-color: #f8fafc;
  border-bottom: 1px solid var(--border);
  font-size: 0.8125rem;
}

.summary-tag {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tag-label {
  color: var(--text-muted);
}
.tag-val {
  font-weight: 600;
}
.text-success { color: var(--success); }
.text-danger { color: var(--danger); }
.text-warning { color: var(--warning); }

.tutor-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.welcome-box {
  background-color: var(--primary-light);
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 0.875rem;
  color: var(--primary-hover);
}

.message-row {
  display: flex;
  width: 100%;
}

.row-user {
  justify-content: flex-end;
}
.row-assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 86%;
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 0.9375rem;
  line-height: 1.55;
  box-shadow: var(--shadow-sm);
}

.bubble-user {
  background-color: var(--primary);
  color: #ffffff;
  border-bottom-right-radius: 4px;
}

.bubble-assistant {
  background-color: #f1f5f9;
  color: var(--text-main);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--border);
}

.bubble-header {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 4px;
}

.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.typing-dot {
  width: 6px;
  height: 6px;
  background-color: var(--primary);
  border-radius: 50%;
  animation: pulse-ring 1s infinite;
}

.quick-prompts-bar {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  background-color: #f8fafc;
}

.btn-quick-prompt {
  white-space: nowrap;
  background-color: #ffffff;
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 6px 12px;
  font-size: 0.8125rem;
  color: var(--text-main);
  transition: all 0.15s ease;
}
.btn-quick-prompt:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
  background-color: var(--primary-light);
}
.btn-quick-prompt:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tutor-input-bar {
  padding: 12px 16px;
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--border);
  background-color: #ffffff;
}

.tutor-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  outline: none;
  font-size: 0.9375rem;
  transition: border-color 0.2s;
}
.tutor-input:focus {
  border-color: var(--primary);
}

.btn-send {
  padding: 0 18px;
  background-color: var(--primary);
  color: #ffffff;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9375rem;
  transition: background-color 0.2s;
}
.btn-send:hover:not(:disabled) {
  background-color: var(--primary-hover);
}
.btn-send:disabled {
  background-color: #cbd5e1;
  cursor: not-allowed;
}
</style>
