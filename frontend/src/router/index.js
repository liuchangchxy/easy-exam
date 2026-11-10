import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import AppLayout from '../layouts/AppLayout.vue'
import HomeView from '../views/HomeView.vue'
import BanksView from '../views/BanksView.vue'
import BankDetailView from '../views/BankDetailView.vue'
import ReviewView from '../views/ReviewView.vue'
import ExamCenterView from '../views/ExamCenterView.vue'
import ImportView from '../views/ImportView.vue'
import NotesView from '../views/NotesView.vue'
import SettingsView from '../views/SettingsView.vue'
import PracticeViewV1 from '../views/PracticeViewV1.vue'
import ExamView from '../features/exam/ExamView.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'home', component: HomeView, meta: { title: '今天' } },
      { path: 'banks', name: 'banks', component: BanksView, meta: { title: '题库' } },
      { path: 'banks/:bankId', name: 'bank-detail', component: BankDetailView, meta: { title: '题库' } },
      { path: 'banks/:bankId/manage', name: 'bank-manage', component: () => import('../views/BankManageView.vue'), meta: { title: '管理' } },
      { path: 'review', name: 'review', component: ReviewView, meta: { title: '复习' } },
      { path: 'learning', redirect: { name: 'review' } },
      { path: 'mistakes', redirect: { name: 'review', query: { tab: 'mistakes' } } },
      { path: 'exams', name: 'exams', component: ExamCenterView, meta: { title: '模考' } },
      { path: 'import', name: 'import', component: ImportView, meta: { title: '导入' } },
      { path: 'notes', name: 'notes', component: NotesView, meta: { title: '资料' } },
      { path: 'settings', name: 'settings', component: SettingsView, meta: { title: '设置' } },
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

export default router
