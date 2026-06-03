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



export const mockMcpList = [
  {
    mcp_id: 'mcp_001',
    name: 'Filesystem',
    description: 'Provides local filesystem access including file reading, writing, directory listing and file management operations.',
    transport: 'stdio',
    endpoint: 'npx @modelcontextprotocol/server-filesystem',
    tool_count: 12,
    enabled: true,
    updated_at: '2026-06-01 10:30:00',
  },

  {
    mcp_id: 'mcp_002',
    name: 'GitHub',
    description: 'Interact with GitHub repositories, issues, pull requests and workflows through MCP tools.',
    transport: 'http',
    endpoint: 'https://mcp.github.company.com/mcp',
    tool_count: 28,
    enabled: true,
    updated_at: '2026-05-31 18:20:00',
  },

  {
    mcp_id: 'mcp_003',
    name: 'PostgreSQL',
    description: 'Execute SQL queries and inspect database schema with controlled permissions.',
    transport: 'http',
    endpoint: 'https://db-mcp.internal.company.com/mcp',
    tool_count: 8,
    enabled: false,
    updated_at: '2026-05-30 09:15:00',
  },

  {
    mcp_id: 'mcp_004',
    name: 'Playwright Browser',
    description: 'Browser automation service supporting navigation, screenshots and web interaction.',
    transport: 'stdio',
    endpoint: 'npx @playwright/mcp',
    tool_count: 16,
    enabled: true,
    updated_at: '2026-05-29 16:40:00',
  },

  {
    mcp_id: 'mcp_005',
    name: 'Slack',
    description: 'Send messages, read channels and interact with Slack workspaces.',
    transport: 'http',
    endpoint: 'https://slack-mcp.company.com/mcp',
    tool_count: 22,
    enabled: false,
    updated_at: '2026-05-28 13:50:00',
  },

  {
    mcp_id: 'mcp_006',
    name: 'Knowledge Base',
    description: 'Enterprise document retrieval and semantic search service for internal knowledge.',
    transport: 'http',
    endpoint: 'https://kb.company.com/mcp',
    tool_count: 6,
    enabled: true,
    updated_at: '2026-05-27 11:00:00',
  },

  {
    mcp_id: 'mcp_007',
    name: 'Docker',
    description: 'Manage containers, inspect images and execute containerized workloads.',
    transport: 'stdio',
    endpoint: 'docker run company/mcp-docker-server',
    tool_count: 19,
    enabled: false,
    updated_at: '2026-05-25 20:18:00',
  },

  {
    mcp_id: 'mcp_008',
    name: 'Redis',
    description: 'Inspect keys, run commands and monitor cache usage through MCP.',
    transport: 'http',
    endpoint: 'https://redis-mcp.company.com/mcp',
    tool_count: 10,
    enabled: true,
    updated_at: '2026-05-24 08:45:00',
  },
]
