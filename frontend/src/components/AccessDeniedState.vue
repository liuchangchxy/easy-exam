<template>
  <div class="access-denied" data-testid="access-denied" :data-kind="kind">
    <div class="ad-mark" aria-hidden="true">
      <LinearIcon :name="kind === 'missing' ? 'search' : 'shield'" :size="24" />
    </div>
    <p class="page-eyebrow">{{ t('ep.brand.name') }}</p>
    <h1 class="page-title">{{ title }}</h1>
    <p class="ad-desc">{{ description }}</p>
    <div class="ad-actions">
      <button type="button" class="btn btn-primary" data-testid="access-denied-back" @click="emit('back')">
        {{ backLabel || t('ep.common.back_to_banks') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'

// A page the user cannot see is still a page: it says what happened and offers
// the one way out. Used when the backend answers 403 (not a member) or 404
// (bank gone) for a resource the URL promised.
const props = defineProps({
  kind: { type: String, default: 'forbidden' },
  // The exit differs by page: a bank denial returns to the bank list, an
  // instance-admin denial returns home.
  backLabel: { type: String, default: '' },
})
const emit = defineEmits(['back'])
const { t } = useLocale()

const title = computed(() => t(props.kind === 'missing' ? 'ep.access.missing_title' : 'ep.access.forbidden_title'))
const description = computed(() => t(props.kind === 'missing' ? 'ep.access.missing_desc' : 'ep.access.forbidden_desc'))
</script>

<style scoped>
.access-denied {
  max-width: 520px;
  margin: 12vh auto 0;
  padding: 0 24px;
  text-align: left;
}

.ad-mark {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  color: var(--ink-3);
  margin-bottom: 18px;
}

.ad-desc {
  color: var(--ink-3);
  font-size: 14px;
  line-height: 1.7;
  margin: 10px 0 0;
}

.ad-actions {
  margin-top: 24px;
}
</style>
