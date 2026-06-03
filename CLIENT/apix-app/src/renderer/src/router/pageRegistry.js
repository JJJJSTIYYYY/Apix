// Central registry for all extensible pages
// Add new pages here or push at runtime
export const pageRegistry = [
  {
    path: '/assistPage',
    name: 'assist-page',
    title: '智能体',
    icon: 'ChatDotSquare',
    component: () => import('@renderer/views/assistPage.vue')
  },
  {
    path: '/flowEditPage',
    name: 'flow-edit-page',
    title: '文件资源管理',
    icon: 'CollectionTag',
    component: () => import('@renderer/views/taskFlowPage.vue')
  },
  {
    path: '/dataPage',
    name: 'data-page',
    title: '数据中心',
    icon: 'Coin',
    component: () => import('@renderer/views/dataPage.vue')
  },
  {
    path: '/taskPage',
    name: 'task-page',
    title: '任务视图',
    icon: 'Memo',
    component: () => import('@renderer/views/taskPage.vue')
  },
  // {
  //   path: '/reportPage',
  //   name: 'report-page',
  //   title: '任务流报告',
  //   icon: 'DataAnalysis',
  //   component: () => import('@renderer/views/reportPage.vue')
  // },
  // {
  //   path: '/serverPage',
  //   name: 'server-page',
  //   title: '服务',
  //   icon: 'Setting',
  //   component: () => import('@renderer/views/serverPage.vue')
  // },
  {
    path: '/settingPage',
    name: 'setting-page',
    title: '设置',
    icon: 'Setting',
    component: () => import('@renderer/views/settingPage.vue')
  }
]
