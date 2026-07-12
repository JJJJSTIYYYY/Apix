"use strict";
const electron = require("electron");
const utils = require("@electron-toolkit/utils");
const path = require("path");
const fs = require("fs");
const os = require("os");
const worker_threads = require("worker_threads");
const crypto = require("crypto");
const axios = require("axios");
const FormData = require("form-data");
const yaml = require("js-yaml");
const WS_AI_API_BASE = "ws://127.0.0.1:5091";
const AI_API_BASE = "http://127.0.0.1:5091";
const MEMORY_API_BASE = "http://127.0.0.1:5093";
const FILE_API_BASE = "http://127.0.0.1:5094";
const WebSocket$1 = require("ws");
let ws = null;
let reconnectTimer = null;
let reconnectDelay = 1e3;
const MAX_RECONNECT_DELAY = 5e3;
let manuallyClosed = false;
const wsSubscribers = /* @__PURE__ */ new Map();
electron.ipcMain.on("ws:subscribe", (event) => {
  const wc = event.sender;
  wsSubscribers.set(wc.id, wc);
});
electron.ipcMain.on("ws:unsubscribe", (event) => {
  wsSubscribers.delete(event.sender.id);
});
function initWS(clientId) {
  if (ws) return ws;
  manuallyClosed = false;
  console.log("[WS] trying to connect...");
  ws = new WebSocket$1(`${WS_AI_API_BASE}/ws/default/${clientId}`);
  ws.on("open", () => {
    console.log("[WS] connected");
    reconnectDelay = 2e3;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  });
  ws.on("message", (data) => {
    let payload;
    try {
      payload = JSON.parse(data.toString());
    } catch (err) {
      console.error("[WS] invalid json:", err);
      return;
    }
    for (const wc of wsSubscribers.values()) {
      if (!wc.isDestroyed()) {
        wc.send("ws:message", payload);
      }
    }
  });
  ws.on("close", () => {
    console.warn("[WS] closed");
    ws = null;
    if (manuallyClosed) return;
    scheduleReconnect(clientId);
  });
  ws.on("error", (err) => {
    console.error("[WS] error:", err);
    try {
      ws.close();
    } catch (_) {
    }
  });
  return ws;
}
function scheduleReconnect(clientId) {
  if (reconnectTimer) return;
  console.warn(`[WS] reconnecting in ${reconnectDelay}ms...`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    initWS(clientId);
    reconnectDelay = Math.min(
      reconnectDelay * 1.5,
      MAX_RECONNECT_DELAY
    );
  }, reconnectDelay);
}
function closeWS() {
  manuallyClosed = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  wsSubscribers.clear();
}
function waitForOpen(ws2, timeout = 5e3) {
  return new Promise((resolve, reject) => {
    if (ws2.readyState === WebSocket$1.OPEN) return resolve();
    const timer = setTimeout(() => reject(new Error("WebSocket open timeout")), timeout);
    ws2.once("open", () => {
      clearTimeout(timer);
      resolve();
    });
    ws2.once("close", () => {
      clearTimeout(timer);
      reject(new Error("WebSocket closed before open"));
    });
    ws2.once("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}
function registerWebsocketIpc() {
  console.log("registerWebsocketIpc...");
  electron.ipcMain.handle("api:closeWebsocket", (event) => {
    try {
      closeWS();
      return true;
    } catch (err) {
      console.error("closeWebsocket error:", err);
      return false;
    }
  });
  electron.ipcMain.handle("api:initWebsocket", (event, clientId) => {
    try {
      closeWS();
      initWS(clientId);
      return true;
    } catch (err) {
      console.error("initWebsocket error:", err);
      return false;
    }
  });
}
const isMac = process.platform === "darwin";
const isWin = process.platform === "win32";
function registerWindowIpc(win) {
  console.log("registerWindowIpc...");
  electron.ipcMain.on("window-minimize", () => win.minimize());
  electron.ipcMain.on("window-maximize", () => {
    win.isMaximized() ? win.unmaximize() : win.maximize();
  });
  electron.ipcMain.on("window-close", () => {
    isWin ? win.close() : electron.app.quit();
  });
}
const fsWatcherWorker = "import fs from 'fs/promises'\n\nimport path from 'path'\nimport yaml from 'js-yaml'\nimport crypto from 'crypto'\nimport diff from 'fast-diff'\nimport trash from 'trash'\n\nimport { parentPort } from 'worker_threads'\n\nimport chokidar from 'chokidar'\n\nimport fg from 'fast-glob'\nimport archiver from 'archiver'\n\nclass FsWatcherWorker {\n\n  constructor() {\n    // Watchers\n    this.watchers = new Map()\n\n    // Root workspace dir\n    this.root_dir = null\n\n    // Event queue\n    this.eventQueue = []\n\n    // Event ignore map {path: content_hash}\n    this.changeIgnoreMap = {}\n\n    // Batch timer\n    this.batchTimer = null\n\n    // Event flush interval (ms)\n    this.EVENT_FLUSH_INTERVAL = 150\n\n    // Event transition table\n    this.EVENT_TRANSITIONS = {\n      add: {\n        add: 'add',\n        change: 'add',\n        unlink: null\n      },\n\n      change: {\n        add: 'add',\n        change: 'change',\n        unlink: 'unlink'\n      },\n\n      unlink: {\n        add: 'change',\n        change: 'unlink',\n        unlink: 'unlink'\n      },\n\n      addDir: {\n        addDir: 'addDir',\n        changeDir: 'addDir',\n        unlinkDir: null\n      },\n\n      changeDir: {\n        addDir: 'addDir',\n        changeDir: 'changeDir',\n        unlinkDir: 'unlinkDir'\n      },\n\n      unlinkDir: {\n        addDir: 'changeDir',\n        changeDir: 'unlinkDir',\n        unlinkDir: 'unlinkDir'\n      }\n    }\n\n    // Bind message handler\n    parentPort.on(\n      'message',\n      this.handleMessage.bind(this)\n    )\n  }\n\n  // Chokidar options\n  WATCH_OPTIONS = {\n    ignored: this.IGNORE_GLOBS,\n\n    ignoreInitial: true,\n\n    persistent: true,\n\n    depth: 0,\n\n    followSymlinks: false\n  }\n\n  // Ignored names\n  IGNORE_NAMES = new Set([\n    // VCS\n    '.git',\n    '.svn',\n    '.hg',\n\n    // Dependencies\n    'node_modules',\n\n    // Build outputs\n    '.next',\n    '.nuxt',\n    'dist',\n    'build',\n    'out',\n\n    // Cache\n    '.cache',\n    '.temp',\n    '.tmp',\n\n    // Python\n    '.venv',\n    'venv',\n\n    // IDE\n    '.idea',\n    '.vscode',\n\n    // System files\n    '.DS_Store',\n    'Thumbs.db'\n  ])\n\n\n  // Ignored glob patterns\n  IGNORE_GLOBS = [\n    ...[...this.IGNORE_NAMES]\n      .filter(\n        name =>\n          !name.includes('.db')\n          &&\n          !name.includes('.DS_Store')\n      )\n      .map(\n        name => `**/${name}/**`\n      ),\n\n    '**/.DS_Store',\n    '**/Thumbs.db'\n  ]\n\n  // Supported extensions\n  SUPPORTED_EXTENSIONS = new Set([\n    '.md',\n    '.js',\n    '.py',\n    '.txt',\n    '.aflow',\n    '.agraph'\n  ])\n\n  // Check supported file\n  isSupportedFile(filePath) {\n    return this.SUPPORTED_EXTENSIONS.has(\n      path.extname(filePath)\n    )\n  }\n\n  guessFileMime(filePath) {\n    if (filePath.endsWith(\".md\")) return 'md'\n    else if (filePath.endsWith(\".js\")) return 'js'\n    else if (filePath.endsWith(\".py\")) return 'py'\n    else if (filePath.endsWith(\".txt\")) return 'txt'\n    else if (filePath.endsWith(\".aflow\")) return 'aflow'\n    else if (filePath.endsWith(\".agraph\")) return 'agraph'\n    else return 'unsupport'\n  }\n\n  parseFileContent(raw_content, mime) {\n    if (mime === 'md' || mime === 'js' || mime === 'py' || mime === 'txt') return raw_content || ''\n    else if (mime === 'aflow') {\n      try {\n        return yaml.load(raw_content) || []\n      } catch (error) {\n        console.error('YAML load error:', error)\n        return []\n      }\n    }\n  }\n\n  // Ignore name\n  shouldIgnoreName(name) {\n    return this.IGNORE_NAMES.has(name)\n  }\n\n  // Normalize path\n  normalizePath(targetPath) {\n    return path.resolve(targetPath)\n  }\n\n  // RPC response\n  response(\n    requestId,\n    result = null,\n    error = null\n  ) {\n    parentPort.postMessage({\n      type: 'response',\n      requestId,\n      result,\n      error\n    })\n  }\n\n  // Merge event into map\n  addEvent(eventMap, event) {\n    const path =\n      event.path\n\n    const nextType =\n      event.type\n\n    const prevEvent =\n      eventMap.get(path)\n\n    // First event\n    if (!prevEvent) {\n      eventMap.set(path, event)\n      return\n    }\n\n    const prevType =\n      prevEvent.type\n\n    const mergedType =\n      this.EVENT_TRANSITIONS[\n        prevType\n      ]?.[\n        nextType\n      ]\n\n    // Events cancelled\n    if (!mergedType) {\n      eventMap.delete(path)\n      return\n    }\n\n    // Update merged event\n    prevEvent.type =\n      mergedType\n\n    eventMap.set(\n      path,\n      prevEvent\n    )\n  }\n\n  // Flush queued events\n  flushEvents() {\n    const merged =\n      new Map()\n\n    for (const event of this.eventQueue) {\n      this.addEvent(\n        merged,\n        event\n      )\n    }\n\n    const events =\n      [...merged.values()]\n\n    if (events.length > 0) {\n      parentPort.postMessage({\n        type: 'events',\n        events\n      })\n    }\n\n    // Clear queue\n    this.eventQueue = []\n\n    this.batchTimer = null\n  }\n\n  // Push watcher event\n  pushEvent(event) {\n    // Ignore unsupported files\n    if (\n      event.path\n      &&\n      !event.type.includes('Dir')\n      &&\n      !this.isSupportedFile(\n        event.path\n      )\n    ) {\n      return\n    }\n\n    // Stop watching removed directory\n    if (event.type === 'unlinkDir') {\n      this.unwatchDirectoryNode(\n        event.path\n      ).catch(() => {})\n    }\n\n    // Push event into queue\n    this.eventQueue.push(event)\n\n    // Debounce flush\n    clearTimeout(\n      this.batchTimer\n    )\n\n    this.batchTimer =\n      setTimeout(() => {\n        this.flushEvents()\n      }, this.EVENT_FLUSH_INTERVAL)\n  }\n\n  // Create tree node\n  createNode(\n    name,\n    fullPath,\n    type\n  ) {\n    return {\n      name,\n\n      path:\n        this.normalizePath(\n          fullPath\n        ),\n\n      type\n    }\n  }\n\n  // Sort directory children\n  sortChildren(children) {\n    if (!children) {\n      return\n    }\n\n    children.sort(\n      (a, b) => {\n        // Directory first\n        if (\n          a.type !== b.type\n        ) {\n          return a.type === 'directory'\n            ? -1\n            : 1\n        }\n\n        return a.name.localeCompare(\n          b.name\n        )\n      }\n    )\n  }\n\n  // Scan single directory\n  async scanDir(dirPath) {\n    const normalizedPath =\n      this.normalizePath(\n        dirPath\n      )\n\n    const stat =\n      await fs.stat(\n        normalizedPath\n      )\n\n    const node =\n      this.createNode(\n        path.basename(\n          normalizedPath\n        ),\n        normalizedPath,\n        stat.isDirectory()\n          ? 'directory'\n          : 'file'\n      )\n\n    if (!stat.isDirectory()) {\n      return node\n    }\n\n    const children = []\n\n    const entries =\n      await fs.readdir(\n        normalizedPath,\n        {\n          withFileTypes: true\n        }\n      )\n\n    for (const entry of entries) {\n      if (\n        this.shouldIgnoreName(\n          entry.name\n        )\n      ) {\n        continue\n      }\n\n      const fullPath =\n        path.join(\n          normalizedPath,\n          entry.name\n        )\n\n      if (\n        entry.isFile()\n        &&\n        !this.isSupportedFile(\n          fullPath\n        )\n      ) {\n        continue\n      }\n\n      children.push(\n        this.createNode(\n          entry.name,\n          fullPath,\n          entry.isDirectory()\n            ? 'directory'\n            : 'file'\n        )\n      )\n    }\n\n    this.sortChildren(\n      children\n    )\n\n    return {\n      ...node,\n      children\n    }\n  }\n\n  // Get directory tree\n  async getDirectoryTree(\n    targetPath = null\n  ) {\n    if (!this.root_dir) {\n      return null\n    }\n\n    const normalizedPath =\n      this.normalizePath(\n        targetPath\n        || this.root_dir\n      )\n\n    // Watch expanded node\n    await this.watchDirectoryNode(\n      normalizedPath\n    )\n\n    return await this.scanDir(\n      normalizedPath\n    )\n  }\n\n  // Watch workspace root\n  async watchWorkspace(\n    dirPath\n  ) {\n    // await this.unwatchWorkspace()\n\n    this.root_dir =\n      this.normalizePath(\n        dirPath\n      )\n\n    // Watch root only\n    await this.watchDirectoryNode(\n      this.root_dir\n    )\n\n    return await this.scanDir(\n      this.root_dir\n    )\n  }\n\n  // Unwatch workspace\n  async unwatchWorkspace() {\n    for (const watchedPath of [\n      ...this.watchers.keys()\n    ]) {\n      await this.unwatchDirectoryNode(\n        watchedPath\n      )\n    }\n\n    this.watchers.clear()\n\n    this.root_dir = null\n  }\n\n  // Watch expanded directory node\n  async watchDirectoryNode(\n    dirPath\n  ) {\n    const normalizedPath =\n      this.normalizePath(\n        dirPath\n      )\n\n    if (\n      this.watchers.has(\n        normalizedPath\n      )\n    ) {\n      return\n    }\n\n    console.log(\n      '[watchDirectoryNode] Path:',\n      normalizedPath\n    )\n\n    const watcher =\n      chokidar.watch(\n        normalizedPath,\n        this.WATCH_OPTIONS\n      )\n\n    const events = [\n      'add',\n      'change',\n      'unlink',\n      'addDir',\n      'unlinkDir'\n    ]\n\n    for (const eventName of events) {\n      watcher.on(\n        eventName,\n        targetPath => {\n          this.pushEvent({\n            type: eventName,\n            path: targetPath,\n            parent: normalizedPath,\n            time: Date.now()\n          })\n        }\n      )\n    }\n\n    watcher.on(\n      'error',\n      err => {\n        console.error(\n          '[Watcher Error]',\n          normalizedPath,\n          err\n        )\n      }\n    )\n\n    this.watchers.set(\n      normalizedPath,\n      watcher\n    )\n  }\n\n  // Unwatch collapsed directory node\n  async unwatchDirectoryNode(\n    dirPath\n  ) {\n    const normalizedPath =\n      this.normalizePath(\n        dirPath\n      )\n\n    console.log(\n      '[unwatchDirectoryNode] Path:',\n      normalizedPath\n    )\n\n    // Find current watcher subtree\n    const watcherPaths =\n      [...this.watchers.keys()]\n        .filter(\n          watcherPath =>\n            watcherPath === normalizedPath\n            ||\n            watcherPath.startsWith(\n              normalizedPath\n              + path.sep\n            )\n        )\n        // Child first\n        .sort(\n          (a, b) =>\n            b.length - a.length\n        )\n\n    for (const watcherPath of watcherPaths) {\n      const watcher =\n        this.watchers.get(\n          watcherPath\n        )\n\n      if (!watcher) {\n        continue\n      }\n\n      try {\n        await watcher.close()\n      }\n      catch {\n        // Ignore close error\n      }\n\n      this.watchers.delete(\n        watcherPath\n      )\n    }\n  }\n\n  // Create file\n  async createFile(\n    filePath,\n    encoding = 'utf-8'\n  ) {\n    const normalizedPath =\n      this.normalizePath(\n        filePath\n      )\n\n    await fs.mkdir(\n      path.dirname(\n        normalizedPath\n      ),\n      {\n        recursive: true\n      }\n    )\n\n    await fs.writeFile(\n      normalizedPath,\n      '',\n      encoding\n    )\n\n    return normalizedPath\n  }\n\n  // Create directory\n  async createDirectory(\n    dirPath\n  ) {\n    const normalizedPath =\n      this.normalizePath(\n        dirPath\n      )\n\n    await fs.mkdir(\n      normalizedPath,\n      {\n        recursive: true\n      }\n    )\n\n    return normalizedPath\n  }\n\n  // Delete file\n  async deleteFile(filePath) {\n    const normalizedPath =\n      this.normalizePath(filePath)\n\n    await trash([\n      normalizedPath\n    ])\n  }\n\n  // Delete directory\n  async deleteDirectory(dirPath) {\n    const normalizedPath =\n      this.normalizePath(dirPath)\n\n    await trash([\n      normalizedPath\n    ])\n\n    await this.unwatchDirectoryNode(\n      normalizedPath\n    )\n  }\n\n  // Rename file or directory\n  async rename(\n    oldPath,\n    newPath\n  ) {\n    const normalizedOldPath =\n      this.normalizePath(\n        oldPath\n      )\n\n    const normalizedNewPath =\n      this.normalizePath(\n        newPath\n      )\n\n    await fs.mkdir(\n      path.dirname(\n        normalizedNewPath\n      ),\n      {\n        recursive: true\n      }\n    )\n\n    // Save watcher subtree\n    const watcherPaths =\n      [...this.watchers.keys()]\n        .filter(\n          watchedPath =>\n            watchedPath\n            === normalizedOldPath\n            ||\n            watchedPath.startsWith(\n              normalizedOldPath\n              + path.sep\n            )\n        )\n        .sort(\n          (a, b) =>\n            a.length - b.length\n        )\n\n    await fs.rename(\n      normalizedOldPath,\n      normalizedNewPath\n    )\n\n    // Rebuild watcher subtree\n    for (const watchedPath of watcherPaths) {\n      const relativePath =\n        path.relative(\n          normalizedOldPath,\n          watchedPath\n        )\n\n      const newWatchedPath =\n        path.join(\n          normalizedNewPath,\n          relativePath\n        )\n\n      await this.unwatchDirectoryNode(\n        watchedPath\n      )\n\n      await this.watchDirectoryNode(\n        newWatchedPath\n      )\n    }\n  }\n\n  // Read full file\n  async readFile(\n    filePath,\n    encoding = 'utf-8'\n  ) {\n    const mime = this.guessFileMime(filePath)\n    if (mime === 'unsupport') return {mime: mime, content: null}\n    const content_raw = await fs.readFile(\n      this.normalizePath(\n        filePath\n      ),\n      encoding\n    )\n    const content = this.parseFileContent(content_raw, mime)\n    return {\n      mime: mime,\n      content: content\n    }\n  }\n\n  // Read full file and return CodeMirror patch\n  async reReadFile(\n    filePath,\n    version,\n    baseContent = '',\n    encoding = 'utf-8',\n  ) {\n    const normalizedPath =\n      this.normalizePath(\n        filePath\n      )\n\n    const mime =\n      this.guessFileMime(\n        normalizedPath\n      )\n\n    if (mime === 'unsupport') {\n      return {\n        changed: false,\n        mime: mime,\n        version: version,\n        patch: null\n      }\n    }\n\n    const content_raw =\n      await fs.readFile(\n        normalizedPath,\n        encoding\n      )\n\n    // Calculate current disk hash\n    const currentHash =\n      crypto\n        .createHash('sha256')\n        .update(content_raw, encoding)\n        .digest('hex')\n\n    const ignoredHash =\n      this.changeIgnoreMap[\n        normalizedPath\n      ]\n\n    // Ignore self write\n    if (currentHash === ignoredHash) {\n      delete this.changeIgnoreMap[\n        normalizedPath\n      ]\n\n      return {\n        changed: false,\n        mime: mime,\n        version: version,\n        patch: null\n      }\n    }\n\n    // Generate diff patch\n    const diffs =\n      diff(\n        baseContent,\n        content_raw\n      )\n\n    const patch = []\n\n    let cursor = 0\n\n    for (const [\n      type,\n      text\n    ] of diffs) {\n\n      // Equal\n      if (type === 0) {\n        cursor += text.length\n        continue\n      }\n\n      // Insert\n      if (type === 1) {\n        patch.push({\n          from: cursor,\n          to: cursor,\n          insert: text\n        })\n\n        continue\n      }\n\n      // Delete\n      if (type === -1) {\n        patch.push({\n          from: cursor,\n          to: cursor + text.length,\n          insert: ''\n        })\n\n        cursor += text.length\n      }\n    }\n\n    return {\n      changed:\n        patch.length > 0,\n      mime: mime,\n      version: version,\n      patch: patch\n    }\n  }\n\n  // Write full file\n  async writeFile(\n    filePath,\n    content,\n    encoding = 'utf-8'\n  ) {\n    const normalizedPath =\n      this.normalizePath(\n        filePath\n      )\n\n    // Save content hash before writing\n    this.changeIgnoreMap[normalizedPath] =\n      crypto\n        .createHash('sha256')\n        .update(content, encoding)\n        .digest('hex')\n\n    await fs.mkdir(\n      path.dirname(\n        normalizedPath\n      ),\n      {\n        recursive: true\n      }\n    )\n\n    await fs.writeFile(\n      normalizedPath,\n      content,\n      encoding\n    )\n  }\n\n  // Search files\n  async searchFiles(cwd) {\n    return await fg(\n      [\n        '**/*.md',\n        '**/*.aflow',\n        '**/*.agraph'\n      ],\n      {\n        cwd,\n\n        absolute: true,\n\n        onlyFiles: true,\n\n        ignore: this.IGNORE_GLOBS\n      }\n    )\n  }\n\n  // Search text\n  async searchText(\n    keyword,\n    cwd\n  ) {\n    const files =\n      await this.searchFiles(\n        cwd\n      )\n\n    const results = []\n\n    for (const filePath of files) {\n      try {\n        const content =\n          await this.readFile(\n            filePath\n          )\n\n        if (\n          content.includes(\n            keyword\n          )\n        ) {\n          results.push(\n            filePath\n          )\n        }\n      }\n      catch {\n        // Ignore unreadable file\n      }\n    }\n\n    return results\n  }\n\n  // Create Anthropic skill folder\n  async createSkillFolder(atPath, skillName) {\n    try {\n      const basePath =\n        this.normalizePath(\n          atPath\n        )\n\n      const skillDirPath =\n        path.join(\n          basePath,\n          skillName\n        )\n\n      // Check directory exists\n      try {\n        await fs.access(skillDirPath)\n\n        return {\n          success: false,\n          message: '技能包目录已存在'\n        }\n      }\n      catch {\n        // Directory not exists, continue create\n      }\n\n      // Create skill directory\n      await fs.mkdir(\n        skillDirPath,\n        { recursive: true }\n      )\n\n      // Anthropic skill metadata\n      const skillMeta = {\n        name: skillName,\n        description: '',\n        version: '1.0.0'\n      }\n\n      const yamlContent =\n        yaml.dump(\n          skillMeta,\n          {\n            lineWidth: -1\n          }\n        )\n\n      const skillMdContent =\n`---\n${yamlContent}---\n\n# ${skillName}\n\n- Add skill detail here.\n`\n\n      // Create SKILL.md\n      await fs.writeFile(\n        path.join(\n          skillDirPath,\n          'SKILL.md'\n        ),\n        skillMdContent,\n        'utf-8'\n      )\n\n      return {\n        success: true,\n        message: skillDirPath\n      }\n    }\n    catch (e) {\n      console.error('createSkillFolder error:', e)\n\n      return {\n        success: false,\n        message: e?.message || '创建技能包失败'\n      }\n    }\n  }\n\n  async compressFolder(atPath) {\n    const stat = await fs.stat(atPath);\n    const dir = path.dirname(atPath);\n\n    // Folder => folderName.zip\n    // File => fileName(without ext).zip\n    const baseName = stat.isDirectory()\n      ? path.basename(atPath)\n      : path.parse(atPath).name;\n\n    let zipPath = path.join(dir, `${baseName}.zip`);\n    let index = 1;\n\n    while (true) {\n      try {\n        await fs.access(zipPath);\n        zipPath = path.join(dir, `${baseName}(${index}).zip`);\n        index++;\n      } catch {\n        break;\n      }\n    }\n\n    return new Promise((resolve, reject) => {\n      import('fs')\n        .then(({ default: fsNative }) => {\n          const output = fsNative.createWriteStream(zipPath);\n          const archive = archiver('zip', {\n            zlib: { level: 9 }\n          });\n\n          output.on('close', () => resolve(zipPath));\n          output.on('error', reject);\n          archive.on('error', reject);\n\n          archive.pipe(output);\n\n          if (stat.isDirectory()) {\n            archive.directory(atPath, false);\n          } else {\n            archive.file(atPath, {\n              name: path.basename(atPath)\n            });\n          }\n\n          archive.finalize();\n        })\n        .catch(reject);\n    });\n  }\n\n  // RPC handlers\n  handlers = {\n    scanDir:\n      this.scanDir.bind(this),\n\n    watchWorkspace:\n      this.watchWorkspace.bind(this),\n\n    unwatchWorkspace:\n      this.unwatchWorkspace.bind(this),\n\n    watchDirectoryNode:\n      this.watchDirectoryNode.bind(this),\n\n    unwatchDirectoryNode:\n      this.unwatchDirectoryNode.bind(this),\n\n    getDirectoryTree:\n      this.getDirectoryTree.bind(this),\n\n    createFile:\n      this.createFile.bind(this),\n\n    deleteFile:\n      this.deleteFile.bind(this),\n\n    readFile:\n      this.readFile.bind(this),\n\n    reReadFile:\n      this.reReadFile.bind(this),\n\n    writeFile:\n      this.writeFile.bind(this),\n\n    searchFiles:\n      this.searchFiles.bind(this),\n\n    createDirectory:\n      this.createDirectory.bind(this),\n\n    deleteDirectory:\n      this.deleteDirectory.bind(this),\n\n    rename:\n      this.rename.bind(this),\n\n    searchText:\n      this.searchText.bind(this),\n\n    createSkillFolder:\n      this.createSkillFolder.bind(this),\n\n    compressFolder:\n      this.compressFolder.bind(this),\n  }\n\n  // Handle RPC message\n  async handleMessage(\n    message\n  ) {\n    const {\n      method,\n      params,\n      requestId\n    } = message\n\n    const handler =\n      this.handlers[method]\n\n    if (!handler) {\n      this.response(\n        requestId,\n        null,\n        `Unknown method: ${method}`\n      )\n\n      return\n    }\n\n    try {\n      const result =\n        await handler(\n          ...Object.values(\n            params\n          )\n        )\n\n      this.response(\n        requestId,\n        result\n      )\n    }\n    catch (err) {\n      this.response(\n        requestId,\n        null,\n        err.stack\n      )\n    }\n  }\n}\n\n// Create worker instance\nnew FsWatcherWorker()";
class FileSystemManager {
  constructor(options = {}) {
    this.onEvents = options.onEvents || (() => {
    });
    this.requestId = 0;
    this.pendingRequests = /* @__PURE__ */ new Map();
    this.worker = new worker_threads.Worker(
      fsWatcherWorker,
      {
        eval: true
      }
    );
    this.worker.on(
      "message",
      (message) => {
        this._handleMessage(
          message
        );
      }
    );
    this.worker.on(
      "error",
      (err) => {
        console.error(
          "[FS Worker Crash]",
          err
        );
      }
    );
  }
  // Handle worker message
  _handleMessage(message) {
    const {
      type,
      requestId
    } = message;
    if (type === "events") {
      this.onEvents(
        message.events
      );
      return;
    }
    if (type === "response") {
      const pending = this.pendingRequests.get(
        requestId
      );
      if (!pending) {
        return;
      }
      this.pendingRequests.delete(
        requestId
      );
      if (message.error) {
        pending.reject(
          message.error
        );
      } else {
        pending.resolve(
          message.result
        );
      }
    }
  }
  // RPC call
  _call(method, params = {}) {
    return new Promise(
      (resolve, reject) => {
        const requestId = ++this.requestId;
        this.pendingRequests.set(
          requestId,
          {
            resolve,
            reject
          }
        );
        this.worker.postMessage({
          type: "call",
          method,
          params,
          requestId
        });
      }
    );
  }
  // Watch workspace
  watchWorkspace(dirPath) {
    if (dirPath && dirPath !== "") {
      return this._call(
        "watchWorkspace",
        { dirPath }
      );
    }
  }
  // Unwatch workspace
  unwatchWorkspace() {
    return this._call(
      "unwatchWorkspace"
    );
  }
  // Get directory tree inside workspace
  getDirectoryTree(targetPath) {
    return this._call(
      "getDirectoryTree",
      { targetPath }
    );
  }
  // Watch a node
  watchDirectoryNode(targetPath) {
    return this._call(
      "watchDirectoryNode",
      { targetPath }
    );
  }
  // Collapse directory tree inside workspace
  collapseDirectoryTree(targetPath) {
    return this._call(
      "unwatchDirectoryNode",
      { targetPath }
    );
  }
  // Create file
  createFile(filePath, encoding = "utf-8") {
    return this._call(
      "createFile",
      { filePath, encoding }
    );
  }
  // Delete file
  deleteFile(filePath) {
    return this._call(
      "deleteFile",
      { filePath }
    );
  }
  // Read file
  readFile(filePath, encoding = "utf-8") {
    return this._call(
      "readFile",
      { filePath, encoding }
    );
  }
  // reRead file
  reReadFile(filePath, version, baseContent = "", encoding = "utf-8") {
    return this._call(
      "reReadFile",
      { filePath, version, baseContent, encoding }
    );
  }
  // Write file
  writeFile(filePath, content, encoding = "utf-8") {
    return this._call(
      "writeFile",
      { filePath, content, encoding }
    );
  }
  // Search files
  searchFiles(cwd) {
    return this._call(
      "searchFiles",
      { cwd }
    );
  }
  // Create directory
  createDirectory(dirPath) {
    return this._call(
      "createDirectory",
      { dirPath }
    );
  }
  // Delete directory
  deleteDirectory(dirPath) {
    return this._call(
      "deleteDirectory",
      { dirPath }
    );
  }
  // Rename
  rename(oldPath, newPath) {
    return this._call(
      "rename",
      { oldPath, newPath }
    );
  }
  // Search text
  searchText(keyword, cwd) {
    return this._call(
      "searchText",
      { keyword, cwd }
    );
  }
  // Search text
  createSkillFolder(atPath, skillName) {
    return this._call(
      "createSkillFolder",
      { atPath, skillName }
    );
  }
  // Search text
  compressFolder(atPath) {
    return this._call(
      "compressFolder",
      { atPath }
    );
  }
  // Dispose
  async dispose() {
    await this.worker.terminate();
  }
}
function registerFileIpc(mainWindow) {
  console.log("registerFileIpc...");
  const dataDir = path.join(electron.app.getPath("userData"), "ApiX");
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  console.log("Apix data dir:", dataDir);
  const fsManager = new FileSystemManager({
    onEvents(events) {
      mainWindow.webContents.send(
        "fs:events",
        events
      );
    }
  });
  electron.ipcMain.handle("openFileDialog", async (event, type, extensions = [], title = "APIX") => {
    let properties = [];
    if (type === "file") {
      properties = ["openFile"];
    } else if (type === "folder") {
      properties = ["openDirectory"];
    } else {
      throw new Error(`Unknown dialog type: ${type}`);
    }
    const normalizedExtensions = Array.isArray(extensions) ? extensions.filter((ext) => typeof ext === "string" && ext.trim() !== "").map((ext) => ext.replace(/^\./, "").toLowerCase()) : [];
    const result = await electron.dialog.showOpenDialog({
      title,
      properties,
      filters: type === "file" && normalizedExtensions.length > 0 ? [
        {
          name: "Allowed Files",
          extensions: normalizedExtensions
        }
      ] : []
    });
    if (result.canceled || result.filePaths.length === 0) {
      return result;
    }
    const selectedPath = result.filePaths[0];
    const stat = fs.statSync(selectedPath);
    if (type === "file") {
      if (!stat.isFile()) {
        throw new Error("Please select a file.");
      }
      const ext = path.extname(selectedPath).slice(1).toLowerCase();
      if (normalizedExtensions.length > 0 && !normalizedExtensions.includes(ext)) {
        throw new Error(`Unsupported file type: .${ext}`);
      }
    } else if (!stat.isDirectory()) {
      throw new Error("Please select a folder.");
    }
    return result;
  });
  electron.ipcMain.handle("openDir", async (event, dirPath, fileName = "") => {
    try {
      if (fileName) {
        const fullPath = path.join(dirPath, fileName);
        electron.shell.showItemInFolder(fullPath);
        return { success: true };
      }
      const err = await electron.shell.openPath(dirPath);
      if (err) {
        console.error("Failed to open directory:", err);
        return { success: false, error: err };
      }
      return { success: true };
    } catch (e) {
      console.error("openCacheDir error:", e);
      return { success: false, error: String(e) };
    }
  });
  electron.ipcMain.handle("openCacheDir", async () => {
    try {
      const dataDir2 = path.join(electron.app.getPath("userData"), "ApiX");
      if (!fs.existsSync(dataDir2)) {
        fs.mkdirSync(dataDir2, { recursive: true });
      }
      console.log("Apix data dir:", dataDir2);
      const err = await electron.shell.openPath(dataDir2);
      if (err) {
        console.error("Failed to open directory:", err);
        return { success: false, error: err };
      }
      return { success: true, path: dataDir2 };
    } catch (e) {
      console.error("openCacheDir error:", e);
      return { success: false, error: String(e) };
    }
  });
  electron.ipcMain.handle("openImageTemp", async (_, base64, fileName) => {
    try {
      const tempDir = path.join(os.tmpdir(), "apix-temp");
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
      }
      const filePath = path.join(tempDir, fileName);
      fs.writeFileSync(filePath, Buffer.from(base64, "base64"));
      await electron.shell.openPath(filePath);
      return { success: true, path: filePath };
    } catch (err) {
      console.error("openImageTemp error:", err);
      return { success: false, error: String(err) };
    }
  });
  electron.ipcMain.handle("createTempFileFromBase64", async (_, base64, fileName) => {
    try {
      const tempDir = path.join(os.tmpdir(), "apix-temp");
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
      }
      const filePath = path.join(tempDir, fileName);
      fs.writeFileSync(filePath, Buffer.from(base64, "base64"));
      return filePath;
    } catch (err) {
      console.error("createTempFileFromBase64 error:", err);
      return null;
    }
  });
  electron.ipcMain.handle("cleanTempDir", async (_, maxAgeMs = 24 * 60 * 60 * 1e3) => {
    try {
      const tempDir = path.join(os.tmpdir(), "apix-temp");
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
        return { success: true, removed: 0 };
      }
      const files = fs.readdirSync(tempDir);
      let removedCount = 0;
      for (const file of files) {
        const filePath = path.join(tempDir, file);
        try {
          const stat = fs.statSync(filePath);
          if (!stat.isFile()) continue;
          const age = Date.now() - stat.mtimeMs;
          if (age > maxAgeMs) {
            fs.unlinkSync(filePath);
            removedCount++;
          }
        } catch (err) {
          console.warn("[cleanTempDir] skip:", filePath, err);
        }
      }
      return {
        success: true,
        removed: removedCount
      };
    } catch (err) {
      console.error("[cleanTempDir] error:", err);
      return {
        success: false,
        error: String(err)
      };
    }
  });
  electron.ipcMain.handle(
    "fs:watch",
    async (_, dirPath) => {
      await fsManager.watchWorkspace(dirPath);
    }
  );
  electron.ipcMain.handle(
    "fs:unwatch",
    async (_) => {
      await fsManager.unwatchWorkspace();
    }
  );
  electron.ipcMain.handle(
    "fs:getDirectoryTree",
    async (_, targetPath) => {
      return await fsManager.getDirectoryTree(targetPath);
    }
  );
  electron.ipcMain.handle(
    "fs:watchDirectoryNode",
    async (_, targetPath) => {
      return await fsManager.watchDirectoryNode(targetPath);
    }
  );
  electron.ipcMain.handle(
    "fs:collapseDirectoryTree",
    async (_, targetPath) => {
      return await fsManager.collapseDirectoryTree(targetPath);
    }
  );
  electron.ipcMain.handle(
    "fs:createFile",
    async (_, filePath, encoding = "utf-8") => {
      return await fsManager.createFile(filePath, encoding);
    }
  );
  electron.ipcMain.handle(
    "fs:deleteFile",
    async (_, filePath) => {
      await fsManager.deleteFile(filePath);
    }
  );
  electron.ipcMain.handle(
    "fs:readFile",
    async (_, filePath, encoding = "utf-8") => {
      return await fsManager.readFile(filePath, encoding);
    }
  );
  electron.ipcMain.handle(
    "fs:reReadFile",
    async (_, filePath, version, baseContent = "", encoding = "utf-8") => {
      return await fsManager.reReadFile(filePath, version, baseContent, encoding);
    }
  );
  electron.ipcMain.handle(
    "fs:writeFile",
    async (_, filePath, content, encoding = "utf-8") => {
      await fsManager.writeFile(filePath, content, encoding);
    }
  );
  electron.ipcMain.handle(
    "fs:searchFiles",
    async (_, cwd) => {
      return await fsManager.searchFiles(cwd);
    }
  );
  electron.ipcMain.handle(
    "fs:createDirectory",
    async (_, dirPath) => {
      return await fsManager.createDirectory(dirPath);
    }
  );
  electron.ipcMain.handle(
    "fs:deleteDirectory",
    async (_, dirPath) => {
      return await fsManager.deleteDirectory(dirPath);
    }
  );
  electron.ipcMain.handle(
    "fs:rename",
    async (_, oldPath, newPath) => {
      await fsManager.rename(oldPath, newPath);
    }
  );
  electron.ipcMain.handle(
    "fs:searchText",
    async (_, keyword, cwd) => {
      return await fsManager.searchText(keyword, cwd);
    }
  );
  electron.ipcMain.handle(
    "fs:createSkillFolder",
    async (_, atPath, skillName) => {
      return await fsManager.createSkillFolder(atPath, skillName);
    }
  );
  electron.ipcMain.handle(
    "fs:compressSkillFloder",
    async (_, atPath) => {
      const skillMdPath = path.join(atPath, "SKILL.md");
      await fs.promises.access(skillMdPath);
      return fsManager.compressFolder(atPath);
    }
  );
}
const WebSocket = require("ws");
function registerAiIpc() {
  console.log("registerAiIpc...");
  electron.ipcMain.handle("api:chat", async (event, cid, sid, hid, content, re_generate, chat_config) => {
    let ws2 = initWS(cid);
    try {
      await waitForOpen(ws2);
    } catch (err) {
      throw new Error("WebSocket not connected, please try again!");
    }
    if (!ws2 || ws2.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected, please try again!");
    }
    ws2.send(
      JSON.stringify({
        action: "chat_with_llm",
        data: {
          client_id: cid,
          session_id: sid,
          history_id: hid,
          platform: "default",
          messages: content,
          re_generate,
          config: chat_config
        }
      })
    );
    return true;
  });
  electron.ipcMain.handle("api:send_event", async (event, cid, action, ws_event) => {
    let ws2 = initWS(cid);
    try {
      await waitForOpen(ws2);
    } catch (err) {
      throw new Error("WebSocket not connected, please try again!");
    }
    if (!ws2 || ws2.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected, please try again!");
    }
    ws2.send(
      JSON.stringify({
        action,
        data: ws_event
      })
    );
    return true;
  });
  electron.ipcMain.handle("api:stop", async (event, cid, sid, hid) => {
    let ws2 = initWS(cid);
    try {
      await waitForOpen(ws2);
    } catch (err) {
      throw new Error("WebSocket not connected, please try again!");
    }
    if (!ws2 || ws2.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected, please try again!");
    }
    ws2.send(
      JSON.stringify({
        action: "abort_generation",
        data: {
          client_id: cid,
          session_id: sid,
          history_id: hid,
          platform: "default"
        }
      })
    );
    return true;
  });
  electron.ipcMain.handle("api:new_chat", async (event, cid, workspace = "", title = "新的聊天...") => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/memory/conversation/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: "",
          title,
          workspace
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.messages || "Create conversation failed.");
      }
      return data;
    } catch (err) {
      console.error("Create conversation error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_conversation", async (event, cid, sid, hid, new_info) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: sid,
          history_id: hid,
          title: new_info.title ?? null,
          workspace: new_info.workspace ?? null,
          is_pinned: new_info.star ?? null,
          is_deleted: new_info.deleted ?? null,
          has_new_message: new_info.has_new_message ?? null
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.messages || "Update conversation failed.");
      }
      return data;
    } catch (err) {
      console.error("Update conversation error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:fetch_chat_list", async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: ""
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.messages || "Get conversation list failed.");
      }
      return data;
    } catch (err) {
      console.error("Get conversation list error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_chat_meta", async (event, hid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/meta`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          history_id: hid
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.messages || "Get conversation list failed.");
      }
      return data;
    } catch (err) {
      console.error("Get conversation list error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:fetch_chat_messages", async (event, cid, sid, hid, branch_id) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          history_id: hid,
          current_node_id: branch_id
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.messages || "Fetch conversation msgs failed.");
      }
      let messages = data.messages;
      const branches = data.branches;
      messages = attachSiblingLinks(messages, branches);
      data.messages = messages;
      return data;
    } catch (err) {
      console.error("Fetch conversation msgs error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:delete_messages", async (event, cid, hid, node_ids) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/memory/delete_messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          history_id: hid,
          messages: node_ids ?? []
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.messages || "Delete messages failed.");
      }
      return data;
    } catch (err) {
      console.error("Delete messages error:", err);
      throw err;
    }
  });
}
function attachSiblingLinks(messages, branches) {
  if (!messages || !messages.length) return messages;
  const activeNodeSet = new Set(messages.map((m) => m.node_id));
  const nodeSiblingLinkMap = /* @__PURE__ */ new Map();
  for (const parentId in branches) {
    const siblings = branches[parentId];
    if (!siblings || siblings.length <= 1) continue;
    const activeNode = siblings.find((s) => activeNodeSet.has(s.node_id));
    if (!activeNode) continue;
    const idx = siblings.findIndex((s) => s.node_id === activeNode.node_id);
    const pre = siblings.slice(0, idx).map((s) => s.node_id);
    const next = siblings.slice(idx + 1).map((s) => s.node_id);
    nodeSiblingLinkMap.set(activeNode.node_id, {
      pre_node: pre,
      next_node: next
    });
  }
  for (const msg of messages) {
    const link = nodeSiblingLinkMap.get(msg.node_id);
    if (link) {
      msg.pre_node = link.pre_node;
      msg.next_node = link.next_node;
    }
  }
  return messages;
}
function registerClipboardIpc() {
  console.log("registerClipboardIpc...");
  electron.ipcMain.handle("api:copyToClipboard", (event, payload) => {
    try {
      if (payload.type === "text") {
        electron.clipboard.writeText(payload.data);
      } else if (payload.type === "image") {
        const img = electron.nativeImage.createFromDataURL(payload.data);
        electron.clipboard.writeImage(img);
      }
      return true;
    } catch (err) {
      console.error("copyToClipboard error:", err);
      return false;
    }
  });
}
const AES_KEY = Buffer.from("0123456789abcdef");
const AES_IV = Buffer.from("abcdef9876543210");
function encryptPassword(password) {
  const cipher = crypto.createCipheriv("aes-128-cbc", AES_KEY, AES_IV);
  let encrypted = cipher.update(password, "utf8", "base64");
  encrypted += cipher.final("base64");
  return encrypted;
}
function registerLogreIpc() {
  console.log("registerLogreIpc...");
  electron.ipcMain.handle("auth:login", async (_, payload) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: payload.username,
          password: encryptPassword(payload.password)
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.messages?.msg || "Login failed");
      }
      return data;
    } catch (err) {
      console.error("Login error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("auth:register", async (_, payload) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: payload.username,
          password: encryptPassword(payload.password)
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Register failed");
      }
      return data;
    } catch (err) {
      console.error("Register error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("auth:ensure_user", async (_, client_id) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/auth/ensure_user`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Ensure failed");
      }
      return data;
    } catch (err) {
      console.error("Ensure error:", err);
      throw err;
    }
  });
}
function registerAiConfigIpc() {
  console.log("registerAiConfigIpc...");
  electron.ipcMain.handle("api:get_models_list", async (event, model_provider, api_key, config) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/get_models_list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model_provider,
          api_key,
          config
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Get models list failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:get_models_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:set_proxy", async (event, http_proxy, https_proxy, no_proxy) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/set_proxy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          http_proxy,
          https_proxy,
          no_proxy
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Set proxy failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:set_proxy] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:clear_vision_cache", async (event) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/clear_vision_cache`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Clear cache failed.");
      }
      if (!data.success) {
        throw new Error(data.messages || "Clear cache failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:clear_vision_cache] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:create_llm_provider", async (event, cid, provider_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/provider/create_llm_provider`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          ...provider_meta
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.messages || "Create providers failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:create_llm_provider] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_llm_providers", async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/provider/get_llm_providers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.messages || "Get providers failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:get_llm_providers] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_llm_provider", async (event, provider_id, cid, new_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/provider/update_llm_provider`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          provider_id,
          client_id: cid,
          ...new_meta
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.messages || "Update providers failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:update_llm_provider] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:auto_fetch_model_list", async (event, endpoint, api_key) => {
    try {
      const base = endpoint.replace(/\/+$/, "");
      const url = `${base}/models`;
      const res = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          ...api_key ? { Authorization: `Bearer ${api_key}` } : {}
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          data?.error?.message || data?.detail || "Fetch models failed."
        );
      }
      let models = [];
      if (Array.isArray(data)) {
        models = data;
      } else if (Array.isArray(data.data)) {
        models = data.data;
      } else if (Array.isArray(data.models)) {
        models = data.models;
      } else {
        throw new Error("Unexpected response format.");
      }
      const ids = models.map((m) => m?.id || m?.name).filter((id) => typeof id === "string" && id.length > 0);
      return ids;
    } catch (err) {
      console.error("[ipc:auto_fetch_model_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:create_mcp_server", async (event, cid, mcp_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/mcp/create_mcp_server`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          ...mcp_meta
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(
          data.detail || data.messages || "Create mcp server failed."
        );
      }
      return data.messages;
    } catch (err) {
      console.error(
        "[ipc:create_mcp_server] error:",
        err
      );
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_mcp_servers", async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/mcp/get_mcp_servers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(
          data.detail || data.messages || "Get mcp servers failed."
        );
      }
      return data.messages;
    } catch (err) {
      console.error(
        "[ipc:get_mcp_servers] error:",
        err
      );
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_mcp_server", async (event, mcp_id, cid, new_meta) => {
    try {
      const res = await fetch(
        `${MEMORY_API_BASE}/mcp/update_mcp_server`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            mcp_id,
            client_id: cid,
            ...new_meta
          })
        }
      );
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(
          data.detail || data.messages || "Update mcp server failed."
        );
      }
      return data.messages;
    } catch (err) {
      console.error(
        "[ipc:update_mcp_server] error:",
        err
      );
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_mcp_tools", async (event, mcp_id, cid, mcp_meta) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/get_mcp_tools`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          mcp_id,
          client_id: cid,
          mcp_meta
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(
          data.detail || data.messages || "Get mcp tools failed."
        );
      }
      return data.messages;
    } catch (err) {
      console.error(
        "[ipc:get_mcp_tools] error:",
        err
      );
      throw err;
    }
  });
}
function registerAiFilesIpc() {
  console.log("registerAiFiles...");
  electron.ipcMain.handle("api:get_embed_list", async (event, model_provider, api_key) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/info/get_models_list`,
        {
          model_provider,
          api_key
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:get_models_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:upload_files", async (event, cid, files) => {
    try {
      const form = new FormData();
      form.append("client_id", cid);
      for (const file of files) {
        const stat = fs.statSync(file.path);
        if (!stat.isFile()) {
          console.warn("[upload_files] skip non-file:", file.path);
          continue;
        }
        form.append(
          "files",
          fs.createReadStream(file.path),
          file.name
        );
      }
      const resp = await axios.post(
        `${FILE_API_BASE}/file/file/insert_file`,
        form,
        {
          headers: {
            ...form.getHeaders()
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data;
    } catch (err) {
      console.error("[ipc:upload_files] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:upload_skills", async (event, cid, files) => {
    try {
      const form = new FormData();
      form.append("client_id", cid);
      for (const file of files) {
        form.append(
          "files",
          fs.createReadStream(file.path),
          file.name
        );
      }
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/insert_skills`,
        form,
        {
          headers: {
            ...form.getHeaders()
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data;
    } catch (err) {
      console.error("[ipc:upload_skills] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_available_skills", async (event, cid, limit) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/get_available_skills`,
        {
          client_id: cid,
          limit
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:get_available_skills] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_skill_status", async (event, cid, skill_id, active) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/update_skill`,
        {
          client_id: cid,
          skill_id,
          is_active: active
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:update_skill_status] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:delete_skill", async (event, cid, skill_id) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/update_skill`,
        {
          client_id: cid,
          skill_id,
          deleted: true
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:delete_skill] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:upload_documents", async (event, cid, files) => {
    try {
      const form = new FormData();
      form.append("client_id", cid);
      for (const file of files) {
        form.append(
          "files",
          fs.createReadStream(file.path),
          file.name
        );
      }
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/insert_document`,
        form,
        {
          headers: {
            ...form.getHeaders()
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data;
    } catch (err) {
      console.error("[ipc:upload_documents] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_document_status", async (event, cid, document_id, active) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          is_active: active
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:update_document_status] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_document_description", async (event, cid, document_id, description) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          description
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:update_document_description] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:delete_document", async (event, cid, document_id) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          deleted: true
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:delete_document] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_available_documents", async (event, cid, limit) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/get_available_documents`,
        {
          client_id: cid,
          limit
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:get_available_documents] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:embed_document", async (event, cid, document_id, model) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/embed_document`,
        {
          client_id: cid,
          document_id,
          selected_embed_model: model
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:embed_document] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:load_resource", async (event, cid, fileId) => {
    try {
      const resp = await axios.get(
        `${FILE_API_BASE}/file/file/load_resource`,
        {
          params: {
            file_id: fileId,
            client_id: cid
          },
          responseType: "arraybuffer"
        }
      );
      return {
        ok: true,
        fileId,
        clientId: cid,
        contentType: resp.headers["content-type"] || "application/octet-stream",
        contentDisposition: resp.headers["content-disposition"] || "",
        etag: resp.headers["etag"] || "",
        sha256: resp.headers["x-file-sha256"] || "",
        buffer: Buffer.from(resp.data).toString("base64")
      };
    } catch (err) {
      console.error("[ipc:load_resource] error:", err?.message || err);
      const status = err?.response?.status || 500;
      const detail = err?.response?.data || err?.message || "load resource failed";
      return {
        ok: false,
        status,
        detail
      };
    }
  });
}
function registerAiTaskIpc() {
  console.log("registerAiTaskIpc...");
  electron.ipcMain.handle("api:get_ai_task_list", async (event, clear) => {
    try {
      let api_port = "";
      if (clear) {
        api_port = "clear_finished_tasks";
      } else {
        api_port = "get_sub_agent_task_list";
      }
      const res = await fetch(`${AI_API_BASE}/api/v1/${api_port}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Get task list failed.");
      }
      if (!data.success) {
        throw new Error(data.messages || "Get task list failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:get_ai_task_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:stop_task", async (event, history_id, task_id) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/stop_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          history_id,
          task_id
        })
      });
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.messages || "Stop task failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:stop_task] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:create_cron_task", async (event, cid, cron_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/cron/create_cron_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          ...cron_meta
        })
      });
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.messages || "Create cron task failed.");
      }
      const tid = data.messages.task_id;
      const repeat = cron_meta.repeat;
      const exec_time = cron_meta.exec_time;
      const res_2 = await fetch(`${AI_API_BASE}/api/v1/sync_cron/${tid}/${repeat}/${exec_time.replace(" ", "T")}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        }
      });
      const data_2 = await res_2.json();
      if (!data_2.success) {
        throw new Error(data_2.messages || "Failed to sync cron tasks.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:create_cron_task] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_cron_task_list", async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/cron/get_cron_tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid
        })
      });
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.messages || "Get cron tasks failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:get_cron_tasks] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_cron_task", async (event, tid, repeat, exec_time, new_info) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/cron/update_cron_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          task_id: tid,
          ...new_info
        })
      });
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.messages || "Update cron task failed.");
      }
      if (exec_time !== "") {
        const res_2 = await fetch(`${AI_API_BASE}/api/v1/sync_cron/${tid}/${repeat}/${exec_time.replace(" ", "T")}`, {
          method: "GET",
          headers: {
            "Content-Type": "application/json"
          }
        });
        const data_2 = await res_2.json();
        if (!data_2.success) {
          throw new Error(data_2.messages || "Failed to sync cron tasks.");
        }
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:update_cron_task] error:", err);
      throw err;
    }
  });
}
const TEST_API_BASE = "http://127.0.0.1:5090";
function registerLocalTaskIpc() {
  console.log("registerLocalTaskIpc...");
  const dataDir = path.join(electron.app.getPath("userData"), "ApiX");
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  console.log("Apix data dir:", dataDir);
  electron.ipcMain.handle("readData", (event, key) => {
    const filePath = path.join(dataDir, `${key}.yaml`);
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, "utf-8").trim();
    return content ? yaml.load(content) : null;
  });
  electron.ipcMain.handle("writeData", (event, key, value) => {
    const filePath = path.join(dataDir, `${key}.yaml`);
    fs.writeFileSync(filePath, yaml.dump(value), "utf-8");
    return true;
  });
  electron.ipcMain.handle("api:submit_case", async (event, cid, content) => {
    try {
      const res = await fetch(`${TEST_API_BASE}/plugin/submit_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          content
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Submit case list failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:submit_case] error:", err);
      throw err;
    }
  });
}
const iconPath = electron.app.isPackaged ? path.join(process.resourcesPath, "app.asar", "resources", "APIX.png") : path.join(process.cwd(), "resources", "APIX.png");
let MicaBrowserWindow = null;
if (isWin) {
  try {
    ;
    ({ MicaBrowserWindow } = require("mica-electron"));
  } catch (e) {
    console.log("Failed to load mica-electron:", e);
  }
}
const baseWindowOptions = {
  width: 1570,
  height: 970,
  minWidth: 1570,
  minHeight: 970,
  show: false,
  autoHideMenuBar: true,
  icon: iconPath,
  webPreferences: {
    preload: path.join(__dirname, "../preload/index.js"),
    // nodeIntegration: true,
    // contextIsolation: false,
    sandbox: false,
    contextIsolation: true,
    nodeIntegration: false,
    webSecurity: true
  }
};
const macWindowOptions = {
  ...baseWindowOptions,
  frame: false,
  transparent: true,
  vibrancy: "popover",
  visualEffectState: "active"
};
const winMicaOptions = {
  ...baseWindowOptions,
  frame: false,
  resizable: true,
  transparent: false
};
const linuxWindowOptions = {
  ...baseWindowOptions
};
function createAppWindow() {
  let mainWindow;
  if (isMac) {
    mainWindow = new electron.BrowserWindow(macWindowOptions);
  } else if (isWin && MicaBrowserWindow) {
    mainWindow = new MicaBrowserWindow(winMicaOptions);
  } else {
    mainWindow = new electron.BrowserWindow(linuxWindowOptions);
  }
  return mainWindow;
}
function createMainWindow() {
  let mainWindow = createAppWindow();
  registerWindowIpc(mainWindow);
  registerFileIpc(mainWindow);
  registerLocalTaskIpc();
  registerAiIpc();
  registerAiConfigIpc();
  registerAiFilesIpc();
  registerAiTaskIpc();
  registerClipboardIpc();
  registerLogreIpc();
  registerWebsocketIpc();
  mainWindow.on("ready-to-show", () => {
    if (isWin && typeof mainWindow.setMicaEffect === "function") {
      mainWindow.setMicaEffect();
      mainWindow.setRoundedCorner?.();
      mainWindow.setMicaTabbedEffect?.();
      mainWindow.setMicaAcrylicEffect?.();
    }
    mainWindow.show();
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    electron.shell.openExternal(url);
    return { action: "deny" };
  });
  if (utils.is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
  return mainWindow;
}
electron.app.whenReady().then(() => {
  const root = process.cwd();
  console.warn("root is ", root);
  utils.electronApp.setAppUserModelId("com.electron");
  electron.app.on("browser-window-created", (_, window) => {
    utils.optimizer.watchWindowShortcuts(window);
  });
  createMainWindow();
  electron.app.on("activate", () => {
    if (electron.BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});
electron.app.on("window-all-closed", () => {
  if (!isMac) {
    closeWS();
    electron.app.quit();
  }
});
