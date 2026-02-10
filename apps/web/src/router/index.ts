import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: 'dashboard.title' },
  },
  {
    path: '/baselines',
    name: 'Baselines',
    component: () => import('@/views/BaselineListView.vue'),
    meta: { title: 'baseline.title' },
  },
  {
    path: '/baselines/:id',
    name: 'BaselineDetail',
    component: () => import('@/views/BaselineDetailView.vue'),
    meta: { title: 'baseline.detail.title' },
  },
  {
    path: '/heats',
    name: 'Heats',
    component: () => import('@/views/HeatListView.vue'),
    meta: { title: 'heat.title' },
  },
  {
    path: '/heats/:id',
    name: 'HeatDetail',
    component: () => import('@/views/HeatDetailView.vue'),
    meta: { title: 'heat.detailTitle' },
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/TaskListView.vue'),
    meta: { title: 'task.title' },
  },
  {
    path: '/tasks/:id',
    name: 'TaskDetail',
    component: () => import('@/views/TaskDetailView.vue'),
    meta: { title: 'task.title' },
  },
  {
    path: '/inbox',
    name: 'Inbox',
    component: () => import('@/views/InboxView.vue'),
    meta: { title: 'inbox.title' },
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/views/ReportListView.vue'),
    meta: { title: 'report.title' },
  },
  {
    path: '/reports/:date',
    name: 'ReportDetail',
    component: () => import('@/views/ReportDetailView.vue'),
    meta: { title: 'report.dailyReport' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: 'settings.title' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
