<template>
  <nav class="bottomnav" :aria-label="t('ep.nav.bottom')">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="bn-item"
      :class="{ 'is-active': item.key === 'more' ? moreOpen : currentPage === item.key }"
      :aria-current="item.key !== 'more' && currentPage === item.key ? 'page' : undefined"
      :aria-haspopup="item.key === 'more' ? 'menu' : undefined"
      :aria-expanded="item.key === 'more' ? (moreOpen ? 'true' : 'false') : undefined"
      :data-more-trigger="item.key === 'more' ? '' : undefined"
      @click="item.key === 'more' ? $emit('more', $event.currentTarget) : $emit('navigate', item.key)"
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
  moreOpen: { type: Boolean, default: false },
})

defineEmits(['navigate', 'more'])

const items = [
  { key: 'today', label: 'ep.nav.today', icon: 'home' },
  { key: 'banks', label: 'ep.nav.banks', icon: 'library' },
  { key: 'review', label: 'ep.nav.review', icon: 'review' },
  { key: 'exam', label: 'ep.nav.exams', icon: 'exam' },
  { key: 'notes', label: 'ep.nav.library', icon: 'note' },
  { key: 'more', label: 'ep.nav.more', icon: 'more' },
]
</script>
