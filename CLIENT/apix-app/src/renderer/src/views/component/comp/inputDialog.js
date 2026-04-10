// InputDialog.js
import { createVNode, render } from 'vue'
import InputDialogVue from './inputDialog.vue'

export const InputDialog = {
  open(message, title = '请输入', options = {}) {
    return new Promise((resolve, reject) => {
      const container = document.createElement('div')
      document.body.appendChild(container)

      const vnode = createVNode(InputDialogVue, {
        message,
        title,
        options,
        onConfirm(value) {
          cleanup()
          resolve(value)
        },
        onCancel() {
          cleanup()
          reject()
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
