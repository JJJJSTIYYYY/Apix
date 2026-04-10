// ConfirmDialog.js. 1
import { createVNode, render } from 'vue'
import ConfirmDialogVue from './confirmDialog.vue'

export const ConfirmDialog = {
  confirm(message, title = '确认', options = {}) {
    return new Promise((resolve, reject) => {
      const container = document.createElement('div')
      document.body.appendChild(container)

      const vnode = createVNode(ConfirmDialogVue, {
        message,
        title,
        options,
        onConfirm() {
          cleanup()
          resolve()
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
