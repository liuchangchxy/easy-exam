import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

import AppLayout from '../layouts/AppLayout.vue'
import HomeView from '../views/HomeView.vue'
import LearningView from '../views/LearningView.vue'
import MistakesView from '../views/MistakesView.vue'
import ImportView from '../views/ImportView.vue'
import NotesView from '../views/NotesView.vue'
import PracticeViewV1 from '../views/PracticeViewV1.vue'
import ExamView from '../features/exam/ExamView.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'home',
        component: HomeView,
        meta: { title: '题库大厅' }
      },
      {
        path: 'learning',
        name: 'learning',
        component: LearningView,
        meta: { title: '复习中心' }
      },
      {
        path: 'mistakes',
        name: 'mistakes',
        component: MistakesView,
        meta: { title: '错题攻克' }
      },
      {
        path: 'import',
        name: 'import',
        component: ImportView,
        meta: { title: '导入题库' }
      },
      {
        path: 'notes',
        name: 'notes',
        component: NotesView,
        meta: { title: '知识笔记' }
      }
    ]
  },
  {
    path: '/practice/:sessionId',
    name: 'practice',
    component: PracticeViewV1,
    props: route => ({ token: useAuthStore().token.value, sessionId: route.params.sessionId })
  },
  {
    path: '/exam/:sessionId',
    name: 'exam',
    component: ExamView,
    props: route => ({ token: useAuthStore().token.value, sessionId: route.params.sessionId })
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
