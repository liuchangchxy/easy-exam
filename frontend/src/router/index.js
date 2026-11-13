import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { recordNavigation } from './backNavigation'
import { adminGuard } from './guards'
import AppLayout from '../layouts/AppLayout.vue'
import HomeView from '../views/HomeView.vue'
import BanksView from '../views/BanksView.vue'
import ReviewView from '../views/ReviewView.vue'
import ExamCenterView from '../views/ExamCenterView.vue'
import ImportView from '../views/ImportView.vue'
import NotesView from '../views/NotesView.vue'
import SettingsView from '../views/SettingsView.vue'
import InstanceAdminView from '../views/InstanceAdminView.vue'
import ForbiddenView from '../views/ForbiddenView.vue'
import PracticeViewV1 from '../views/PracticeViewV1.vue'
import ExamView from '../features/exam/ExamView.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'home', component: HomeView, meta: { title: '今天' } },
      { path: 'banks', name: 'banks', component: BanksView, meta: { title: '题库' } },
      { path: 'banks/:bankId', name: 'bank-detail', component: () => import('../views/BankManageView.vue'), meta: { title: '题库', fallback: { name: 'banks' } } },
      // One workspace per bank. The old management URL is kept as a redirect so
      // bookmarks, deep links and older clients land on the same tabs.
      { path: 'banks/:bankId/manage', redirect: to => ({ name: 'bank-detail', params: to.params, query: to.query }) },
      { path: 'banks/:bankId/q/:questionId', name: 'question', component: () => import('../views/QuestionPageView.vue'), meta: { title: '题目', fallback: 'bank-detail' } },
      { path: 'review', name: 'review', component: ReviewView, meta: { title: '复习' } },
      { path: 'learning', redirect: { name: 'review' } },
      { path: 'mistakes', redirect: { name: 'review', query: { tab: 'mistakes' } } },
      { path: 'exams', name: 'exams', component: ExamCenterView, meta: { title: '模考' } },
      { path: 'import', name: 'import', component: ImportView, meta: { title: '导入' } },
      { path: 'notes', name: 'notes', component: NotesView, meta: { title: '资料' } },
      { path: 'settings', name: 'settings', component: SettingsView, meta: { title: '设置' } },
      { path: 'instance', name: 'instance-admin', component: InstanceAdminView, meta: { title: '实例管理', requiresAdmin: true } },
      { path: 'forbidden', name: 'forbidden', component: ForbiddenView, meta: { title: '无法访问' } },
    ],
  },
  {
    path: '/practice/:sessionId',
    name: 'practice',
    component: PracticeViewV1,
    props: route => ({ token: useAuthStore().token.value, sessionId: route.params.sessionId }),
  },
  {
    path: '/exam/:sessionId',
    name: 'exam',
    component: ExamView,
    props: route => ({ token: useAuthStore().token.value, sessionId: route.params.sessionId }),
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// Back navigation is history-first (see AppLayout.goBack). The stack below only
// decides whether an in-app history exists; it never chooses a parent page.
router.afterEach((to, from) => {
  recordNavigation(to, from)
})

// Page-level permissions. Never data permissions: those belong to the API and
// to each page's own access state.
router.beforeEach(to => adminGuard(to, useAuthStore()))

export default router
