<template>
  <div v-if="visible" class="drawer-overlay" @click.self="$emit('close')">
    <div class="drawer-sheet animate-slide-up">
      <!-- Drag Handle -->
      <div class="drawer-handle-bar">
        <div class="drawer-handle"></div>
      </div>

      <!-- Header -->
      <div class="drawer-header">
        <div class="drawer-title-group">
          <h3 class="drawer-title">答题卡</h3>
          <span class="drawer-progress">已答 {{ answeredCount }} / {{ total }}</span>
        </div>
        <button class="drawer-close-btn" @click="$emit('close')" aria-label="关闭答题卡">✕</button>
      </div>

      <!-- Legend -->
      <div class="drawer-legend">
        <div v-if="mode === 'PRACTICE'" class="legend-item">
          <span class="legend-dot dot-correct"></span>
          <span>正确</span>
        </div>
        <div v-if="mode === 'PRACTICE'" class="legend-item">
          <span class="legend-dot dot-wrong"></span>
          <span>错误</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-answered"></span>
          <span>{{ mode === 'PRACTICE' ? '已作答' : '已填选' }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-flagged"></span>
          <span>存疑标记</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-unanswered"></span>
          <span>未答</span>
        </div>
      </div>

      <!-- Questions Grid -->
      <div class="drawer-grid-container">
        <div class="drawer-grid">
          <button
            v-for="(q, index) in questions"
            :key="q.id || index"
            class="grid-circle"
            :class="getCircleClass(q, index)"
            @click="handleSelect(index)"
          >
            <span>{{ index + 1 }}</span>
            <span v-if="isFlagged(q.id)" class="flag-indicator" title="存疑标记">★</span>
          </button>
        </div>
      </div>

      <!-- Footer Buttons -->
      <div class="drawer-footer">
        <button
          v-if="mode === 'EXAM'"
          class="btn-submit-exam"
          @click="$emit('submit')"
        >
          📝 交卷并查看诊断报告
        </button>
        <button
          v-else
          class="btn-finish-practice"
          @click="$emit('submit')"
        >
          🏁 结束本次刷题并结算
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  total: {
    type: Number,
    default: 0
  },
  currentIndex: {
    type: Number,
    default: 0
  },
  questions: {
    type: Array,
    default: () => []
  },
  answers: {
    type: Object,
    default: () => ({})
  },
  results: {
    type: Object,
    default: () => ({})
  },
  flags: {
    type: Array,
    default: () => []
  },
  mode: {
    type: String,
    default: 'PRACTICE'
  }
})

const emit = defineEmits(['close', 'select', 'submit'])

const answeredCount = computed(() => {
  return Object.keys(props.answers).filter(k => props.answers[k] !== undefined && props.answers[k] !== null && props.answers[k] !== '').length
})

function isFlagged(qId) {
  return props.flags.includes(qId)
}

function getCircleClass(q, index) {
  const classes = []
  const qId = q.id

  if (index === props.currentIndex) {
    classes.push('is-current')
  }

  const result = props.results[qId]
  if (result !== undefined && result !== null) {
    if (result.is_correct) {
      classes.push('status-correct')
    } else {
      classes.push('status-wrong')
    }
  } else if (props.answers[qId] !== undefined && props.answers[qId] !== null && props.answers[qId] !== '') {
    classes.push('status-answered')
  } else {
    classes.push('status-unanswered')
  }

  return classes.join(' ')
}

function handleSelect(index) {
  emit('select', index)
  emit('close')
}
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  z-index: 100;
  display: flex;
  justify-content: center;
  align-items: flex-end;
}

.drawer-sheet {
  width: 100%;
  max-width: 640px;
  max-height: 80vh;
  background-color: #ffffff;
  border-top-left-radius: 20px;
  border-top-right-radius: 20px;
  padding: 12px 20px 24px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

.drawer-handle-bar {
  display: flex;
  justify-content: center;
  padding-bottom: 8px;
}

.drawer-handle {
  width: 36px;
  height: 4px;
  background-color: #cbd5e1;
  border-radius: 2px;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.drawer-title-group {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.drawer-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-main);
}

.drawer-progress {
  font-size: 0.875rem;
  color: var(--text-muted);
}

.drawer-close-btn {
  font-size: 1.25rem;
  color: var(--text-muted);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}
.drawer-close-btn:hover {
  background-color: #f1f5f9;
}

.drawer-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 0;
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot-correct { background-color: var(--success); }
.dot-wrong { background-color: var(--danger); }
.dot-answered { background-color: var(--primary); }
.dot-flagged { background-color: var(--warning); }
.dot-unanswered { background-color: #e2e8f0; }

.drawer-grid-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
  margin-bottom: 12px;
}

.drawer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(44px, 1fr));
  gap: 12px;
}

.grid-circle {
  position: relative;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9375rem;
  font-weight: 600;
  transition: all 0.15s ease;
  user-select: none;
}

.grid-circle:active {
  transform: scale(0.92);
}

.is-current {
  outline: 3px solid var(--primary);
  outline-offset: 2px;
}

.status-unanswered {
  background-color: #f1f5f9;
  color: #475569;
  border: 1px solid #cbd5e1;
}

.status-answered {
  background-color: var(--primary-light);
  color: var(--primary);
  border: 1.5px solid var(--primary);
}

.status-correct {
  background-color: var(--success-light);
  color: var(--success);
  border: 1.5px solid var(--success);
}

.status-wrong {
  background-color: var(--danger-light);
  color: var(--danger);
  border: 1.5px solid var(--danger);
}

.flag-indicator {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 16px;
  height: 16px;
  background-color: var(--warning);
  color: #ffffff;
  border-radius: 50%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}

.drawer-footer {
  padding-top: 8px;
}

.btn-submit-exam, .btn-finish-practice {
  width: 100%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  text-align: center;
  transition: background-color 0.2s;
}

.btn-submit-exam {
  background-color: var(--primary);
  color: #ffffff;
}
.btn-submit-exam:hover {
  background-color: var(--primary-hover);
}

.btn-finish-practice {
  background-color: #f1f5f9;
  color: var(--text-main);
  border: 1px solid var(--border);
}
.btn-finish-practice:hover {
  background-color: #e2e8f0;
}
</style>
