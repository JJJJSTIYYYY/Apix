import fs from 'fs/promises'

import path from 'path'
import yaml from 'js-yaml'
import crypto from 'crypto'
import diff from 'fast-diff'
import trash from 'trash'

import { parentPort } from 'worker_threads'

import chokidar from 'chokidar'

import fg from 'fast-glob'
import archiver from 'archiver'

class FsWatcherWorker {

  constructor() {
    // Watchers
    this.watchers = new Map()

    // Root workspace dir
    this.root_dir = null

    // Event queue
    this.eventQueue = []

    // Event ignore map {path: content_hash}
    this.changeIgnoreMap = {}

    // Batch timer
    this.batchTimer = null

    // Event flush interval (ms)
    this.EVENT_FLUSH_INTERVAL = 150

    // Event transition table
    this.EVENT_TRANSITIONS = {
      add: {
        add: 'add',
        change: 'add',
        unlink: null
      },

      change: {
        add: 'add',
        change: 'change',
        unlink: 'unlink'
      },

      unlink: {
        add: 'change',
        change: 'unlink',
        unlink: 'unlink'
      },

      addDir: {
        addDir: 'addDir',
        changeDir: 'addDir',
        unlinkDir: null
      },

      changeDir: {
        addDir: 'addDir',
        changeDir: 'changeDir',
        unlinkDir: 'unlinkDir'
      },

      unlinkDir: {
        addDir: 'changeDir',
        changeDir: 'unlinkDir',
        unlinkDir: 'unlinkDir'
      }
    }

    // Bind message handler
    parentPort.on(
      'message',
      this.handleMessage.bind(this)
    )
  }

  // Chokidar options
  WATCH_OPTIONS = {
    ignored: this.IGNORE_GLOBS,

    ignoreInitial: true,

    persistent: true,

    depth: 0,

    followSymlinks: false
  }

  // Ignored names
  IGNORE_NAMES = new Set([
    // VCS
    '.git',
    '.svn',
    '.hg',

    // Dependencies
    'node_modules',

    // Build outputs
    '.next',
    '.nuxt',
    'dist',
    'build',
    'out',

    // Cache
    '.cache',
    '.temp',
    '.tmp',

    // Python
    '.venv',
    'venv',

    // IDE
    '.idea',
    '.vscode',

    // System files
    '.DS_Store',
    'Thumbs.db'
  ])


  // Ignored glob patterns
  IGNORE_GLOBS = [
    ...[...this.IGNORE_NAMES]
      .filter(
        name =>
          !name.includes('.db')
          &&
          !name.includes('.DS_Store')
      )
      .map(
        name => `**/${name}/**`
      ),

    '**/.DS_Store',
    '**/Thumbs.db'
  ]

  // Supported extensions
  SUPPORTED_EXTENSIONS = new Set([
    '.md',
    '.js',
    '.py',
    '.txt',
    '.aflow',
    '.agraph'
  ])

  // Check supported file
  isSupportedFile(filePath) {
    return this.SUPPORTED_EXTENSIONS.has(
      path.extname(filePath)
    )
  }

  guessFileMime(filePath) {
    if (filePath.endsWith(".md")) return 'md'
    else if (filePath.endsWith(".js")) return 'js'
    else if (filePath.endsWith(".py")) return 'py'
    else if (filePath.endsWith(".txt")) return 'txt'
    else if (filePath.endsWith(".aflow")) return 'aflow'
    else if (filePath.endsWith(".agraph")) return 'agraph'
    else return 'unsupport'
  }

  parseFileContent(raw_content, mime) {
    if (mime === 'md' || mime === 'js' || mime === 'py' || mime === 'txt') return raw_content || ''
    else if (mime === 'aflow') {
      try {
        return yaml.load(raw_content) || []
      } catch (error) {
        console.error('YAML load error:', error)
        return []
      }
    }
  }

  // Ignore name
  shouldIgnoreName(name) {
    return this.IGNORE_NAMES.has(name)
  }

  // Normalize path
  normalizePath(targetPath) {
    return path.resolve(targetPath)
  }

  // RPC response
  response(
    requestId,
    result = null,
    error = null
  ) {
    parentPort.postMessage({
      type: 'response',
      requestId,
      result,
      error
    })
  }

  // Merge event into map
  addEvent(eventMap, event) {
    const path =
      event.path

    const nextType =
      event.type

    const prevEvent =
      eventMap.get(path)

    // First event
    if (!prevEvent) {
      eventMap.set(path, event)
      return
    }

    const prevType =
      prevEvent.type

    const mergedType =
      this.EVENT_TRANSITIONS[
        prevType
      ]?.[
        nextType
      ]

    // Events cancelled
    if (!mergedType) {
      eventMap.delete(path)
      return
    }

    // Update merged event
    prevEvent.type =
      mergedType

    eventMap.set(
      path,
      prevEvent
    )
  }

  // Flush queued events
  flushEvents() {
    const merged =
      new Map()

    for (const event of this.eventQueue) {
      this.addEvent(
        merged,
        event
      )
    }

    const events =
      [...merged.values()]

    if (events.length > 0) {
      parentPort.postMessage({
        type: 'events',
        events
      })
    }

    // Clear queue
    this.eventQueue = []

    this.batchTimer = null
  }

  // Push watcher event
  pushEvent(event) {
    // Ignore unsupported files
    if (
      event.path
      &&
      !event.type.includes('Dir')
      &&
      !this.isSupportedFile(
        event.path
      )
    ) {
      return
    }

    // Stop watching removed directory
    if (event.type === 'unlinkDir') {
      this.unwatchDirectoryNode(
        event.path
      ).catch(() => {})
    }

    // Push event into queue
    this.eventQueue.push(event)

    // Debounce flush
    clearTimeout(
      this.batchTimer
    )

    this.batchTimer =
      setTimeout(() => {
        this.flushEvents()
      }, this.EVENT_FLUSH_INTERVAL)
  }

  // Create tree node
  createNode(
    name,
    fullPath,
    type
  ) {
    return {
      name,

      path:
        this.normalizePath(
          fullPath
        ),

      type
    }
  }

  // Sort directory children
  sortChildren(children) {
    if (!children) {
      return
    }

    children.sort(
      (a, b) => {
        // Directory first
        if (
          a.type !== b.type
        ) {
          return a.type === 'directory'
            ? -1
            : 1
        }

        return a.name.localeCompare(
          b.name
        )
      }
    )
  }

  // Scan single directory
  async scanDir(dirPath) {
    const normalizedPath =
      this.normalizePath(
        dirPath
      )

    const stat =
      await fs.stat(
        normalizedPath
      )

    const node =
      this.createNode(
        path.basename(
          normalizedPath
        ),
        normalizedPath,
        stat.isDirectory()
          ? 'directory'
          : 'file'
      )

    if (!stat.isDirectory()) {
      return node
    }

    const children = []

    const entries =
      await fs.readdir(
        normalizedPath,
        {
          withFileTypes: true
        }
      )

    for (const entry of entries) {
      if (
        this.shouldIgnoreName(
          entry.name
        )
      ) {
        continue
      }

      const fullPath =
        path.join(
          normalizedPath,
          entry.name
        )

      if (
        entry.isFile()
        &&
        !this.isSupportedFile(
          fullPath
        )
      ) {
        continue
      }

      children.push(
        this.createNode(
          entry.name,
          fullPath,
          entry.isDirectory()
            ? 'directory'
            : 'file'
        )
      )
    }

    this.sortChildren(
      children
    )

    return {
      ...node,
      children
    }
  }

  // Get directory tree
  async getDirectoryTree(
    targetPath = null
  ) {
    if (!this.root_dir) {
      return null
    }

    const normalizedPath =
      this.normalizePath(
        targetPath
        || this.root_dir
      )

    // Watch expanded node
    await this.watchDirectoryNode(
      normalizedPath
    )

    return await this.scanDir(
      normalizedPath
    )
  }

  // Watch workspace root
  async watchWorkspace(
    dirPath
  ) {
    // await this.unwatchWorkspace()

    this.root_dir =
      this.normalizePath(
        dirPath
      )

    // Watch root only
    await this.watchDirectoryNode(
      this.root_dir
    )

    return await this.scanDir(
      this.root_dir
    )
  }

  // Unwatch workspace
  async unwatchWorkspace() {
    for (const watchedPath of [
      ...this.watchers.keys()
    ]) {
      await this.unwatchDirectoryNode(
        watchedPath
      )
    }

    this.watchers.clear()

    this.root_dir = null
  }

  // Watch expanded directory node
  async watchDirectoryNode(
    dirPath
  ) {
    const normalizedPath =
      this.normalizePath(
        dirPath
      )

    if (
      this.watchers.has(
        normalizedPath
      )
    ) {
      return
    }

    console.log(
      '[watchDirectoryNode] Path:',
      normalizedPath
    )

    const watcher =
      chokidar.watch(
        normalizedPath,
        this.WATCH_OPTIONS
      )

    const events = [
      'add',
      'change',
      'unlink',
      'addDir',
      'unlinkDir'
    ]

    for (const eventName of events) {
      watcher.on(
        eventName,
        targetPath => {
          this.pushEvent({
            type: eventName,
            path: targetPath,
            parent: normalizedPath,
            time: Date.now()
          })
        }
      )
    }

    watcher.on(
      'error',
      err => {
        console.error(
          '[Watcher Error]',
          normalizedPath,
          err
        )
      }
    )

    this.watchers.set(
      normalizedPath,
      watcher
    )
  }

  // Unwatch collapsed directory node
  async unwatchDirectoryNode(
    dirPath
  ) {
    const normalizedPath =
      this.normalizePath(
        dirPath
      )

    console.log(
      '[unwatchDirectoryNode] Path:',
      normalizedPath
    )

    // Find current watcher subtree
    const watcherPaths =
      [...this.watchers.keys()]
        .filter(
          watcherPath =>
            watcherPath === normalizedPath
            ||
            watcherPath.startsWith(
              normalizedPath
              + path.sep
            )
        )
        // Child first
        .sort(
          (a, b) =>
            b.length - a.length
        )

    for (const watcherPath of watcherPaths) {
      const watcher =
        this.watchers.get(
          watcherPath
        )

      if (!watcher) {
        continue
      }

      try {
        await watcher.close()
      }
      catch {
        // Ignore close error
      }

      this.watchers.delete(
        watcherPath
      )
    }
  }

  // Create file
  async createFile(
    filePath,
    encoding = 'utf-8'
  ) {
    const normalizedPath =
      this.normalizePath(
        filePath
      )

    await fs.mkdir(
      path.dirname(
        normalizedPath
      ),
      {
        recursive: true
      }
    )

    await fs.writeFile(
      normalizedPath,
      '',
      encoding
    )

    return normalizedPath
  }

  // Create directory
  async createDirectory(
    dirPath
  ) {
    const normalizedPath =
      this.normalizePath(
        dirPath
      )

    await fs.mkdir(
      normalizedPath,
      {
        recursive: true
      }
    )

    return normalizedPath
  }

  // Delete file
  async deleteFile(filePath) {
    const normalizedPath =
      this.normalizePath(filePath)

    await trash([
      normalizedPath
    ])
  }

  // Delete directory
  async deleteDirectory(dirPath) {
    const normalizedPath =
      this.normalizePath(dirPath)

    await trash([
      normalizedPath
    ])

    await this.unwatchDirectoryNode(
      normalizedPath
    )
  }

  // Rename file or directory
  async rename(
    oldPath,
    newPath
  ) {
    const normalizedOldPath =
      this.normalizePath(
        oldPath
      )

    const normalizedNewPath =
      this.normalizePath(
        newPath
      )

    await fs.mkdir(
      path.dirname(
        normalizedNewPath
      ),
      {
        recursive: true
      }
    )

    // Save watcher subtree
    const watcherPaths =
      [...this.watchers.keys()]
        .filter(
          watchedPath =>
            watchedPath
            === normalizedOldPath
            ||
            watchedPath.startsWith(
              normalizedOldPath
              + path.sep
            )
        )
        .sort(
          (a, b) =>
            a.length - b.length
        )

    await fs.rename(
      normalizedOldPath,
      normalizedNewPath
    )

    // Rebuild watcher subtree
    for (const watchedPath of watcherPaths) {
      const relativePath =
        path.relative(
          normalizedOldPath,
          watchedPath
        )

      const newWatchedPath =
        path.join(
          normalizedNewPath,
          relativePath
        )

      await this.unwatchDirectoryNode(
        watchedPath
      )

      await this.watchDirectoryNode(
        newWatchedPath
      )
    }
  }

  // Read full file
  async readFile(
    filePath,
    encoding = 'utf-8'
  ) {
    const mime = this.guessFileMime(filePath)
    if (mime === 'unsupport') return {mime: mime, content: null}
    const content_raw = await fs.readFile(
      this.normalizePath(
        filePath
      ),
      encoding
    )
    const content = this.parseFileContent(content_raw, mime)
    return {
      mime: mime,
      content: content
    }
  }

  // Read full file and return CodeMirror patch
  async reReadFile(
    filePath,
    version,
    baseContent = '',
    encoding = 'utf-8',
  ) {
    const normalizedPath =
      this.normalizePath(
        filePath
      )

    const mime =
      this.guessFileMime(
        normalizedPath
      )

    if (mime === 'unsupport') {
      return {
        changed: false,
        mime: mime,
        version: version,
        patch: null
      }
    }

    const content_raw =
      await fs.readFile(
        normalizedPath,
        encoding
      )

    // Calculate current disk hash
    const currentHash =
      crypto
        .createHash('sha256')
        .update(content_raw, encoding)
        .digest('hex')

    const ignoredHash =
      this.changeIgnoreMap[
        normalizedPath
      ]

    // Ignore self write
    if (currentHash === ignoredHash) {
      delete this.changeIgnoreMap[
        normalizedPath
      ]

      return {
        changed: false,
        mime: mime,
        version: version,
        patch: null
      }
    }

    // Generate diff patch
    const diffs =
      diff(
        baseContent,
        content_raw
      )

    const patch = []

    let cursor = 0

    for (const [
      type,
      text
    ] of diffs) {

      // Equal
      if (type === 0) {
        cursor += text.length
        continue
      }

      // Insert
      if (type === 1) {
        patch.push({
          from: cursor,
          to: cursor,
          insert: text
        })

        continue
      }

      // Delete
      if (type === -1) {
        patch.push({
          from: cursor,
          to: cursor + text.length,
          insert: ''
        })

        cursor += text.length
      }
    }

    return {
      changed:
        patch.length > 0,
      mime: mime,
      version: version,
      patch: patch
    }
  }

  // Write full file
  async writeFile(
    filePath,
    content,
    encoding = 'utf-8'
  ) {
    const normalizedPath =
      this.normalizePath(
        filePath
      )

    // Save content hash before writing
    this.changeIgnoreMap[normalizedPath] =
      crypto
        .createHash('sha256')
        .update(content, encoding)
        .digest('hex')

    await fs.mkdir(
      path.dirname(
        normalizedPath
      ),
      {
        recursive: true
      }
    )

    await fs.writeFile(
      normalizedPath,
      content,
      encoding
    )
  }

  // Search files
  async searchFiles(cwd) {
    return await fg(
      [
        '**/*.md',
        '**/*.aflow',
        '**/*.agraph'
      ],
      {
        cwd,

        absolute: true,

        onlyFiles: true,

        ignore: this.IGNORE_GLOBS
      }
    )
  }

  // Search text
  async searchText(
    keyword,
    cwd
  ) {
    const files =
      await this.searchFiles(
        cwd
      )

    const results = []

    for (const filePath of files) {
      try {
        const content =
          await this.readFile(
            filePath
          )

        if (
          content.includes(
            keyword
          )
        ) {
          results.push(
            filePath
          )
        }
      }
      catch {
        // Ignore unreadable file
      }
    }

    return results
  }

  // Create Anthropic skill folder
  async createSkillFolder(atPath, skillName) {
    try {
      const basePath =
        this.normalizePath(
          atPath
        )

      const skillDirPath =
        path.join(
          basePath,
          skillName
        )

      // Check directory exists
      try {
        await fs.access(skillDirPath)

        return {
          success: false,
          message: '技能包目录已存在'
        }
      }
      catch {
        // Directory not exists, continue create
      }

      // Create skill directory
      await fs.mkdir(
        skillDirPath,
        { recursive: true }
      )

      // Anthropic skill metadata
      const skillMeta = {
        name: skillName,
        description: '',
        version: '1.0.0'
      }

      const yamlContent =
        yaml.dump(
          skillMeta,
          {
            lineWidth: -1
          }
        )

      const skillMdContent =
`---
${yamlContent}---

# ${skillName}

- Add skill detail here.
`

      // Create SKILL.md
      await fs.writeFile(
        path.join(
          skillDirPath,
          'SKILL.md'
        ),
        skillMdContent,
        'utf-8'
      )

      return {
        success: true,
        message: skillDirPath
      }
    }
    catch (e) {
      console.error('createSkillFolder error:', e)

      return {
        success: false,
        message: e?.message || '创建技能包失败'
      }
    }
  }

  async compressFolder(atPath) {
    const stat = await fs.stat(atPath);
    const dir = path.dirname(atPath);

    // Folder => folderName.zip
    // File => fileName(without ext).zip
    const baseName = stat.isDirectory()
      ? path.basename(atPath)
      : path.parse(atPath).name;

    let zipPath = path.join(dir, `${baseName}.zip`);
    let index = 1;

    while (true) {
      try {
        await fs.access(zipPath);
        zipPath = path.join(dir, `${baseName}(${index}).zip`);
        index++;
      } catch {
        break;
      }
    }

    return new Promise((resolve, reject) => {
      import('fs')
        .then(({ default: fsNative }) => {
          const output = fsNative.createWriteStream(zipPath);
          const archive = archiver('zip', {
            zlib: { level: 9 }
          });

          output.on('close', () => resolve(zipPath));
          output.on('error', reject);
          archive.on('error', reject);

          archive.pipe(output);

          if (stat.isDirectory()) {
            archive.directory(atPath, false);
          } else {
            archive.file(atPath, {
              name: path.basename(atPath)
            });
          }

          archive.finalize();
        })
        .catch(reject);
    });
  }

  // RPC handlers
  handlers = {
    scanDir:
      this.scanDir.bind(this),

    watchWorkspace:
      this.watchWorkspace.bind(this),

    unwatchWorkspace:
      this.unwatchWorkspace.bind(this),

    watchDirectoryNode:
      this.watchDirectoryNode.bind(this),

    unwatchDirectoryNode:
      this.unwatchDirectoryNode.bind(this),

    getDirectoryTree:
      this.getDirectoryTree.bind(this),

    createFile:
      this.createFile.bind(this),

    deleteFile:
      this.deleteFile.bind(this),

    readFile:
      this.readFile.bind(this),

    reReadFile:
      this.reReadFile.bind(this),

    writeFile:
      this.writeFile.bind(this),

    searchFiles:
      this.searchFiles.bind(this),

    createDirectory:
      this.createDirectory.bind(this),

    deleteDirectory:
      this.deleteDirectory.bind(this),

    rename:
      this.rename.bind(this),

    searchText:
      this.searchText.bind(this),

    createSkillFolder:
      this.createSkillFolder.bind(this),

    compressFolder:
      this.compressFolder.bind(this),
  }

  // Handle RPC message
  async handleMessage(
    message
  ) {
    const {
      method,
      params,
      requestId
    } = message

    const handler =
      this.handlers[method]

    if (!handler) {
      this.response(
        requestId,
        null,
        `Unknown method: ${method}`
      )

      return
    }

    try {
      const result =
        await handler(
          ...Object.values(
            params
          )
        )

      this.response(
        requestId,
        result
      )
    }
    catch (err) {
      this.response(
        requestId,
        null,
        err.stack
      )
    }
  }
}

// Create worker instance
new FsWatcherWorker()