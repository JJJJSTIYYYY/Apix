import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { pageRegistry } from './pageRegistry'

// Static routes that always exist
const staticRoutes = [
  {
    path: '/',
    redirect: '/loginPage'
  },
  {
    path: '/loginPage',
    name: 'login-page',
    component: () => import('@renderer/LoginPage.vue')
  },
  {
    path: '/home',
    name: 'home-page',
    redirect: '/sessionPage',
    component: () => import('@renderer/views/homePage.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: staticRoutes
})

// Dynamically register pages from registry
export function registerDynamicRoutes() {
  pageRegistry.forEach(page => {
    if (!router.hasRoute(page.name)) {
      router.addRoute({
        path: page.path,
        name: page.name,
        component: page.component
      })
    }
  })
}

// Auth guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // Not logged in → force to login
  if (!authStore.user && to.path !== '/loginPage') {
    next('/loginPage')
    return
  }

  // Logged in → block login page
  if (authStore.user && to.path === '/loginPage') {
    next('/home')
    return
  }

  next()
})

export default router




// 运行时动态扩展示例
// import { pageRegistry } from '@/router/pageRegistry'
// import { registerDynamicRoutes } from '@/router'

// // Inject at runtime (plugin / backend / electron main)
// pageRegistry.push({
//   path: '/pluginExample',
//   name: 'plugin-example',
//   title: '插件示例',
//   icon: 'House',
//   component: () => import('@/plugins/example/Page.vue')
// })

// registerDynamicRoutes()
