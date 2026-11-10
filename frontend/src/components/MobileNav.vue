<template>
  <nav class="bottomnav" :aria-label="t('ep.nav.bottom')">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="bn-item"
      :class="{ 'is-active': currentPage === item.key }"
      @click="$emit('navigate', item.key)"
    >
      <LinearIcon :name="item.icon" :size="21" />
      <span>{{ t(item.label) }}</span>
    </button>
  </nav>
</template>

<script setup>
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

defineProps({
  currentPage: { type: String, default: 'today' },
})

defineEmits(['navigate'])

const items = [
  { key: 'today', label: 'ep.nav.today', icon: 'home' },
  { key: 'banks', label: 'ep.nav.banks', icon: 'library' },
  { key: 'review', label: 'ep.nav.review', icon: 'review' },
  { key: 'exam', label: 'ep.nav.exams', icon: 'exam' },
  { key: 'notes', label: 'ep.nav.library', icon: 'note' },
]
</script>
