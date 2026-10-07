import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: () => (localStorage.getItem('token') ? '/home' : '/login') },
  { path: '/login', component: () => import('./views/Login.vue') },
  {
    path: '/home',
    component: () => import('./views/Home.vue'),
    children: [
      { path: '', redirect: 'employee' },
      { path: 'employee', component: () => import('./views/Employee.vue') },
      { path: 'reviewer', component: () => import('./views/Reviewer.vue') },
      { path: 'config', component: () => import('./views/ConfigPage.vue') },
      { path: 'monitor', component: () => import('./views/MonitorPage.vue') },
      { path: 'dashboard', component: () => import('./views/Dashboard.vue') },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) return '/login'
  if (to.path === '/login' && token) return '/home'
  return true
})

export default router
