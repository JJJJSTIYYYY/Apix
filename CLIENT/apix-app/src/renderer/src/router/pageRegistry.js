// Central registry for all extensible pages
// Add new pages here or push at runtime
export const pageRegistry = [
  {
    path: '/sessionPage',
    name: 'session-page',
    title: 'Testing',
    icon: 'House',
    component: () => import('@renderer/views/casePage.vue')
  },
  {
    path: '/assistPage',
    name: 'assist-page',
    title: 'Assistant',
    icon: 'ChatDotSquare',
    component: () => import('@renderer/views/assistPage.vue')
  },
  {
    path: '/dataPage',
    name: 'data-page',
    title: 'KnowledgeBase',
    icon: 'Coin',
    component: () => import('@renderer/views/dataPage.vue')
  },
  {
    path: '/taskPage',
    name: 'task-page',
    title: 'Task',
    icon: 'Memo',
    component: () => import('@renderer/views/taskPage.vue')
  },
  {
    path: '/reportPage',
    name: 'report-page',
    title: 'Reports',
    icon: 'DataAnalysis',
    component: () => import('@renderer/views/reportPage.vue')
  },
  {
    path: '/settingPage',
    name: 'setting-page',
    title: 'Settings',
    icon: 'Setting',
    component: () => import('@renderer/views/settingPage.vue')
  }
]
