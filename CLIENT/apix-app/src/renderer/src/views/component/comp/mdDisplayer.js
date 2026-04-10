// mdDisplayer.js
import { createVNode, render } from 'vue'
import MdDisplayerVue from './mdDisplayer.vue'

export const mdDisplayer = {
  show(content, title = '内容查看', options = {}) {
    return new Promise((resolve) => {
      const container = document.createElement('div')
      document.body.appendChild(container)

      const vnode = createVNode(MdDisplayerVue, {
        content,
        title,
        options,
        onClose() {
          cleanup()
          resolve()
        },
      })

      function cleanup() {
        render(null, container)
        document.body.removeChild(container)
      }

      render(vnode, container)
    })
  },
}
