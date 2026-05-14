// Mock workspace tree data
export const mockWorkspace = {
  name: 'APIX',
  path: '/Users/admin/APIX',
  type: 'directory',

  children: [
    {
      name: 'src',
      path: '/Users/admin/APIX/src',
      type: 'directory',

      children: [
        {
          name: 'components',
          path: '/Users/admin/APIX/src/components',
          type: 'directory',

          children: [
            {
              name: 'chat_panel.vue',
              path: '/Users/admin/APIX/src/components/chat_panel.vue',
              type: 'file',
            },

            {
              name: 'file_explorer.vue',
              path: '/Users/admin/APIX/src/components/file_explorer.vue',
              type: 'file',
            },

            {
              name: 'message_item.vue',
              path: '/Users/admin/APIX/src/components/message_item.vue',
              type: 'file',
            },
          ],
        },

        {
          name: 'views',
          path: '/Users/admin/APIX/src/views',
          type: 'directory',

          children: [
            {
              name: 'home.vue',
              path: '/Users/admin/APIX/src/views/home.vue',
              type: 'file',
            },

            {
              name: 'settings.vue',
              path: '/Users/admin/APIX/src/views/settings.vue',
              type: 'file',
            },
          ],
        },

        {
          name: 'assets',
          path: '/Users/admin/APIX/src/assets',
          type: 'directory',

          children: [
            {
              name: 'logo.png',
              path: '/Users/admin/APIX/src/assets/logo.png',
              type: 'file',
            },

            {
              name: 'background.jpg',
              path: '/Users/admin/APIX/src/assets/background.jpg',
              type: 'file',
            },
          ],
        },

        {
          name: 'main.js',
          path: '/Users/admin/APIX/src/main.js',
          type: 'file',
        },

        {
          name: 'App.vue',
          path: '/Users/admin/APIX/src/App.vue',
          type: 'file',
        },
      ],
    },

    {
      name: 'electron',
      path: '/Users/admin/APIX/electron',
      type: 'directory',

      children: [
        {
          name: 'main.js',
          path: '/Users/admin/APIX/electron/main.js',
          type: 'file',
        },

        {
          name: 'preload.js',
          path: '/Users/admin/APIX/electron/preload.js',
          type: 'file',
        },

        {
          name: 'ipc',
          path: '/Users/admin/APIX/electron/ipc',
          type: 'directory',

          children: [
            {
              name: 'fs.js',
              path: '/Users/admin/APIX/electron/ipc/fs.js',
              type: 'file',
            },

            {
              name: 'window.js',
              path: '/Users/admin/APIX/electron/ipc/window.js',
              type: 'file',
            },
          ],
        },
      ],
    },

    {
      name: 'node_modules',
      path: '/Users/admin/APIX/node_modules',
      type: 'directory',

      children: [
        {
          name: '.bin',
          path: '/Users/admin/APIX/node_modules/.bin',
          type: 'directory',

          children: [],
        },

        {
          name: 'vue',
          path: '/Users/admin/APIX/node_modules/vue',
          type: 'directory',

          children: [],
        },

        {
          name: 'electron',
          path: '/Users/admin/APIX/node_modules/electron',
          type: 'directory',

          children: [],
        },
      ],
    },

    {
      name: 'package.json',
      path: '/Users/admin/APIX/package.json',
      type: 'file',
    },

    {
      name: 'vite.config.js',
      path: '/Users/admin/APIX/vite.config.js',
      type: 'file',
    },

    {
      name: '.gitignore',
      path: '/Users/admin/APIX/.gitignore',
      type: 'file',
    },

    {
      name: 'README.md',
      path: '/Users/admin/APIX/README.md',
      type: 'file',
    },
  ],
}