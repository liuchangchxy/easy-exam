<template>
  <AccessDeniedState :kind="kind" :back-label="t('ep.common.back_home')" @back="goHome" />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AccessDeniedState from '../components/AccessDeniedState.vue'
import { useLocale } from '../composables/useLocale.js'

// Destination of a route the guard refused. The page is a normal child of the
// app shell, so the navigation stays available instead of trapping the user.
const route = useRoute()
const router = useRouter()
const { t } = useLocale()

const kind = computed(() => (route.query?.kind === 'missing' ? 'missing' : 'forbidden'))

function goHome() {
  router.push({ name: 'home' })
}
</script>
