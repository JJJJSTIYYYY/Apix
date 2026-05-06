import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './assets/global.css'
import './assets/tab_card_global.css'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from '@router/index'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { useAppCacheData  } from './store/app'
import {
  // create naive ui
  create,
  // component
  NButton
} from 'naive-ui'
const naive = create({
  components: [NButton]
})



async function bootstrap() {
  const app = createApp(App)

  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.use(router)
  app.use(ElementPlus)
  app.use(naive)

  const pinia = createPinia()
  app.use(pinia)

  const store = useAppCacheData()
  await store.init()

  app.mount('#app')
}

bootstrap()