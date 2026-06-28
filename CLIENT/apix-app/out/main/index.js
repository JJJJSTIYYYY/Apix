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
const fsWatcherWorker = "import fs from 'fs/promises'\r\n\r\nimport path from 'path'\r\nimport yaml from 'js-yaml'\r\nimport crypto from 'crypto'\r\nimport diff from 'fast-diff'\r\nimport trash from 'trash'\r\n\r\nimport { parentPort } from 'worker_threads'\r\n\r\nimport chokidar from 'chokidar'\r\n\r\nimport fg from 'fast-glob'\r\nimport archiver from 'archiver'\r\n\r\nclass FsWatcherWorker {\r\n\r\n  constructor() {\r\n    // Watchers\r\n    this.watchers = new Map()\r\n\r\n    // Root workspace dir\r\n    this.root_dir = null\r\n\r\n    // Event queue\r\n    this.eventQueue = []\r\n\r\n    // Event ignore map {path: content_hash}\r\n    this.changeIgnoreMap = {}\r\n\r\n    // Batch timer\r\n    this.batchTimer = null\r\n\r\n    // Event flush interval (ms)\r\n    this.EVENT_FLUSH_INTERVAL = 150\r\n\r\n    // Event transition table\r\n    this.EVENT_TRANSITIONS = {\r\n      add: {\r\n        add: 'add',\r\n        change: 'add',\r\n        unlink: null\r\n      },\r\n\r\n      change: {\r\n        add: 'add',\r\n        change: 'change',\r\n        unlink: 'unlink'\r\n      },\r\n\r\n      unlink: {\r\n        add: 'change',\r\n        change: 'unlink',\r\n        unlink: 'unlink'\r\n      },\r\n\r\n      addDir: {\r\n        addDir: 'addDir',\r\n        changeDir: 'addDir',\r\n        unlinkDir: null\r\n      },\r\n\r\n      changeDir: {\r\n        addDir: 'addDir',\r\n        changeDir: 'changeDir',\r\n        unlinkDir: 'unlinkDir'\r\n      },\r\n\r\n      unlinkDir: {\r\n        addDir: 'changeDir',\r\n        changeDir: 'unlinkDir',\r\n        unlinkDir: 'unlinkDir'\r\n      }\r\n    }\r\n\r\n    // Bind message handler\r\n    parentPort.on(\r\n      'message',\r\n      this.handleMessage.bind(this)\r\n    )\r\n  }\r\n\r\n  // Chokidar options\r\n  WATCH_OPTIONS = {\r\n    ignored: this.IGNORE_GLOBS,\r\n\r\n    ignoreInitial: true,\r\n\r\n    persistent: true,\r\n\r\n    depth: 0,\r\n\r\n    followSymlinks: false\r\n  }\r\n\r\n  // Ignored names\r\n  IGNORE_NAMES = new Set([\r\n    // VCS\r\n    '.git',\r\n    '.svn',\r\n    '.hg',\r\n\r\n    // Dependencies\r\n    'node_modules',\r\n\r\n    // Build outputs\r\n    '.next',\r\n    '.nuxt',\r\n    'dist',\r\n    'build',\r\n    'out',\r\n\r\n    // Cache\r\n    '.cache',\r\n    '.temp',\r\n    '.tmp',\r\n\r\n    // Python\r\n    '.venv',\r\n    'venv',\r\n\r\n    // IDE\r\n    '.idea',\r\n    '.vscode',\r\n\r\n    // System files\r\n    '.DS_Store',\r\n    'Thumbs.db'\r\n  ])\r\n\r\n\r\n  // Ignored glob patterns\r\n  IGNORE_GLOBS = [\r\n    ...[...this.IGNORE_NAMES]\r\n      .filter(\r\n        name =>\r\n          !name.includes('.db')\r\n          &&\r\n          !name.includes('.DS_Store')\r\n      )\r\n      .map(\r\n        name => `**/${name}/**`\r\n      ),\r\n\r\n    '**/.DS_Store',\r\n    '**/Thumbs.db'\r\n  ]\r\n\r\n  // Supported extensions\r\n  SUPPORTED_EXTENSIONS = new Set([\r\n    '.md',\r\n    '.js',\r\n    '.py',\r\n    '.txt',\r\n    '.aflow',\r\n    '.agraph'\r\n  ])\r\n\r\n  // Check supported file\r\n  isSupportedFile(filePath) {\r\n    return this.SUPPORTED_EXTENSIONS.has(\r\n      path.extname(filePath)\r\n    )\r\n  }\r\n\r\n  guessFileMime(filePath) {\r\n    if (filePath.endsWith(\".md\")) return 'md'\r\n    else if (filePath.endsWith(\".js\")) return 'js'\r\n    else if (filePath.endsWith(\".py\")) return 'py'\r\n    else if (filePath.endsWith(\".txt\")) return 'txt'\r\n    else if (filePath.endsWith(\".aflow\")) return 'aflow'\r\n    else if (filePath.endsWith(\".agraph\")) return 'agraph'\r\n    else return 'unsupport'\r\n  }\r\n\r\n  parseFileContent(raw_content, mime) {\r\n    if (mime === 'md' || mime === 'js' || mime === 'py' || mime === 'txt') return raw_content || ''\r\n    else if (mime === 'aflow') {\r\n      try {\r\n        return yaml.load(raw_content) || []\r\n      } catch (error) {\r\n        console.error('YAML load error:', error)\r\n        return []\r\n      }\r\n    }\r\n  }\r\n\r\n  // Ignore name\r\n  shouldIgnoreName(name) {\r\n    return this.IGNORE_NAMES.has(name)\r\n  }\r\n\r\n  // Normalize path\r\n  normalizePath(targetPath) {\r\n    return path.resolve(targetPath)\r\n  }\r\n\r\n  // RPC response\r\n  response(\r\n    requestId,\r\n    result = null,\r\n    error = null\r\n  ) {\r\n    parentPort.postMessage({\r\n      type: 'response',\r\n      requestId,\r\n      result,\r\n      error\r\n    })\r\n  }\r\n\r\n  // Merge event into map\r\n  addEvent(eventMap, event) {\r\n    const path =\r\n      event.path\r\n\r\n    const nextType =\r\n      event.type\r\n\r\n    const prevEvent =\r\n      eventMap.get(path)\r\n\r\n    // First event\r\n    if (!prevEvent) {\r\n      eventMap.set(path, event)\r\n      return\r\n    }\r\n\r\n    const prevType =\r\n      prevEvent.type\r\n\r\n    const mergedType =\r\n      this.EVENT_TRANSITIONS[\r\n        prevType\r\n      ]?.[\r\n        nextType\r\n      ]\r\n\r\n    // Events cancelled\r\n    if (!mergedType) {\r\n      eventMap.delete(path)\r\n      return\r\n    }\r\n\r\n    // Update merged event\r\n    prevEvent.type =\r\n      mergedType\r\n\r\n    eventMap.set(\r\n      path,\r\n      prevEvent\r\n    )\r\n  }\r\n\r\n  // Flush queued events\r\n  flushEvents() {\r\n    const merged =\r\n      new Map()\r\n\r\n    for (const event of this.eventQueue) {\r\n      this.addEvent(\r\n        merged,\r\n        event\r\n      )\r\n    }\r\n\r\n    const events =\r\n      [...merged.values()]\r\n\r\n    if (events.length > 0) {\r\n      parentPort.postMessage({\r\n        type: 'events',\r\n        events\r\n      })\r\n    }\r\n\r\n    // Clear queue\r\n    this.eventQueue = []\r\n\r\n    this.batchTimer = null\r\n  }\r\n\r\n  // Push watcher event\r\n  pushEvent(event) {\r\n    // Ignore unsupported files\r\n    if (\r\n      event.path\r\n      &&\r\n      !event.type.includes('Dir')\r\n      &&\r\n      !this.isSupportedFile(\r\n        event.path\r\n      )\r\n    ) {\r\n      return\r\n    }\r\n\r\n    // Stop watching removed directory\r\n    if (event.type === 'unlinkDir') {\r\n      this.unwatchDirectoryNode(\r\n        event.path\r\n      ).catch(() => {})\r\n    }\r\n\r\n    // Push event into queue\r\n    this.eventQueue.push(event)\r\n\r\n    // Debounce flush\r\n    clearTimeout(\r\n      this.batchTimer\r\n    )\r\n\r\n    this.batchTimer =\r\n      setTimeout(() => {\r\n        this.flushEvents()\r\n      }, this.EVENT_FLUSH_INTERVAL)\r\n  }\r\n\r\n  // Create tree node\r\n  createNode(\r\n    name,\r\n    fullPath,\r\n    type\r\n  ) {\r\n    return {\r\n      name,\r\n\r\n      path:\r\n        this.normalizePath(\r\n          fullPath\r\n        ),\r\n\r\n      type\r\n    }\r\n  }\r\n\r\n  // Sort directory children\r\n  sortChildren(children) {\r\n    if (!children) {\r\n      return\r\n    }\r\n\r\n    children.sort(\r\n      (a, b) => {\r\n        // Directory first\r\n        if (\r\n          a.type !== b.type\r\n        ) {\r\n          return a.type === 'directory'\r\n            ? -1\r\n            : 1\r\n        }\r\n\r\n        return a.name.localeCompare(\r\n          b.name\r\n        )\r\n      }\r\n    )\r\n  }\r\n\r\n  // Scan single directory\r\n  async scanDir(dirPath) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        dirPath\r\n      )\r\n\r\n    const stat =\r\n      await fs.stat(\r\n        normalizedPath\r\n      )\r\n\r\n    const node =\r\n      this.createNode(\r\n        path.basename(\r\n          normalizedPath\r\n        ),\r\n        normalizedPath,\r\n        stat.isDirectory()\r\n          ? 'directory'\r\n          : 'file'\r\n      )\r\n\r\n    if (!stat.isDirectory()) {\r\n      return node\r\n    }\r\n\r\n    const children = []\r\n\r\n    const entries =\r\n      await fs.readdir(\r\n        normalizedPath,\r\n        {\r\n          withFileTypes: true\r\n        }\r\n      )\r\n\r\n    for (const entry of entries) {\r\n      if (\r\n        this.shouldIgnoreName(\r\n          entry.name\r\n        )\r\n      ) {\r\n        continue\r\n      }\r\n\r\n      const fullPath =\r\n        path.join(\r\n          normalizedPath,\r\n          entry.name\r\n        )\r\n\r\n      if (\r\n        entry.isFile()\r\n        &&\r\n        !this.isSupportedFile(\r\n          fullPath\r\n        )\r\n      ) {\r\n        continue\r\n      }\r\n\r\n      children.push(\r\n        this.createNode(\r\n          entry.name,\r\n          fullPath,\r\n          entry.isDirectory()\r\n            ? 'directory'\r\n            : 'file'\r\n        )\r\n      )\r\n    }\r\n\r\n    this.sortChildren(\r\n      children\r\n    )\r\n\r\n    return {\r\n      ...node,\r\n      children\r\n    }\r\n  }\r\n\r\n  // Get directory tree\r\n  async getDirectoryTree(\r\n    targetPath = null\r\n  ) {\r\n    if (!this.root_dir) {\r\n      return null\r\n    }\r\n\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        targetPath\r\n        || this.root_dir\r\n      )\r\n\r\n    // Watch expanded node\r\n    await this.watchDirectoryNode(\r\n      normalizedPath\r\n    )\r\n\r\n    return await this.scanDir(\r\n      normalizedPath\r\n    )\r\n  }\r\n\r\n  // Watch workspace root\r\n  async watchWorkspace(\r\n    dirPath\r\n  ) {\r\n    // await this.unwatchWorkspace()\r\n\r\n    this.root_dir =\r\n      this.normalizePath(\r\n        dirPath\r\n      )\r\n\r\n    // Watch root only\r\n    await this.watchDirectoryNode(\r\n      this.root_dir\r\n    )\r\n\r\n    return await this.scanDir(\r\n      this.root_dir\r\n    )\r\n  }\r\n\r\n  // Unwatch workspace\r\n  async unwatchWorkspace() {\r\n    for (const watchedPath of [\r\n      ...this.watchers.keys()\r\n    ]) {\r\n      await this.unwatchDirectoryNode(\r\n        watchedPath\r\n      )\r\n    }\r\n\r\n    this.watchers.clear()\r\n\r\n    this.root_dir = null\r\n  }\r\n\r\n  // Watch expanded directory node\r\n  async watchDirectoryNode(\r\n    dirPath\r\n  ) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        dirPath\r\n      )\r\n\r\n    if (\r\n      this.watchers.has(\r\n        normalizedPath\r\n      )\r\n    ) {\r\n      return\r\n    }\r\n\r\n    console.log(\r\n      '[watchDirectoryNode] Path:',\r\n      normalizedPath\r\n    )\r\n\r\n    const watcher =\r\n      chokidar.watch(\r\n        normalizedPath,\r\n        this.WATCH_OPTIONS\r\n      )\r\n\r\n    const events = [\r\n      'add',\r\n      'change',\r\n      'unlink',\r\n      'addDir',\r\n      'unlinkDir'\r\n    ]\r\n\r\n    for (const eventName of events) {\r\n      watcher.on(\r\n        eventName,\r\n        targetPath => {\r\n          this.pushEvent({\r\n            type: eventName,\r\n            path: targetPath,\r\n            parent: normalizedPath,\r\n            time: Date.now()\r\n          })\r\n        }\r\n      )\r\n    }\r\n\r\n    watcher.on(\r\n      'error',\r\n      err => {\r\n        console.error(\r\n          '[Watcher Error]',\r\n          normalizedPath,\r\n          err\r\n        )\r\n      }\r\n    )\r\n\r\n    this.watchers.set(\r\n      normalizedPath,\r\n      watcher\r\n    )\r\n  }\r\n\r\n  // Unwatch collapsed directory node\r\n  async unwatchDirectoryNode(\r\n    dirPath\r\n  ) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        dirPath\r\n      )\r\n\r\n    console.log(\r\n      '[unwatchDirectoryNode] Path:',\r\n      normalizedPath\r\n    )\r\n\r\n    // Find current watcher subtree\r\n    const watcherPaths =\r\n      [...this.watchers.keys()]\r\n        .filter(\r\n          watcherPath =>\r\n            watcherPath === normalizedPath\r\n            ||\r\n            watcherPath.startsWith(\r\n              normalizedPath\r\n              + path.sep\r\n            )\r\n        )\r\n        // Child first\r\n        .sort(\r\n          (a, b) =>\r\n            b.length - a.length\r\n        )\r\n\r\n    for (const watcherPath of watcherPaths) {\r\n      const watcher =\r\n        this.watchers.get(\r\n          watcherPath\r\n        )\r\n\r\n      if (!watcher) {\r\n        continue\r\n      }\r\n\r\n      try {\r\n        await watcher.close()\r\n      }\r\n      catch {\r\n        // Ignore close error\r\n      }\r\n\r\n      this.watchers.delete(\r\n        watcherPath\r\n      )\r\n    }\r\n  }\r\n\r\n  // Create file\r\n  async createFile(\r\n    filePath,\r\n    encoding = 'utf-8'\r\n  ) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        filePath\r\n      )\r\n\r\n    await fs.mkdir(\r\n      path.dirname(\r\n        normalizedPath\r\n      ),\r\n      {\r\n        recursive: true\r\n      }\r\n    )\r\n\r\n    await fs.writeFile(\r\n      normalizedPath,\r\n      '',\r\n      encoding\r\n    )\r\n\r\n    return normalizedPath\r\n  }\r\n\r\n  // Create directory\r\n  async createDirectory(\r\n    dirPath\r\n  ) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        dirPath\r\n      )\r\n\r\n    await fs.mkdir(\r\n      normalizedPath,\r\n      {\r\n        recursive: true\r\n      }\r\n    )\r\n\r\n    return normalizedPath\r\n  }\r\n\r\n  // Delete file\r\n  async deleteFile(filePath) {\r\n    const normalizedPath =\r\n      this.normalizePath(filePath)\r\n\r\n    await trash([\r\n      normalizedPath\r\n    ])\r\n  }\r\n\r\n  // Delete directory\r\n  async deleteDirectory(dirPath) {\r\n    const normalizedPath =\r\n      this.normalizePath(dirPath)\r\n\r\n    await trash([\r\n      normalizedPath\r\n    ])\r\n\r\n    await this.unwatchDirectoryNode(\r\n      normalizedPath\r\n    )\r\n  }\r\n\r\n  // Rename file or directory\r\n  async rename(\r\n    oldPath,\r\n    newPath\r\n  ) {\r\n    const normalizedOldPath =\r\n      this.normalizePath(\r\n        oldPath\r\n      )\r\n\r\n    const normalizedNewPath =\r\n      this.normalizePath(\r\n        newPath\r\n      )\r\n\r\n    await fs.mkdir(\r\n      path.dirname(\r\n        normalizedNewPath\r\n      ),\r\n      {\r\n        recursive: true\r\n      }\r\n    )\r\n\r\n    // Save watcher subtree\r\n    const watcherPaths =\r\n      [...this.watchers.keys()]\r\n        .filter(\r\n          watchedPath =>\r\n            watchedPath\r\n            === normalizedOldPath\r\n            ||\r\n            watchedPath.startsWith(\r\n              normalizedOldPath\r\n              + path.sep\r\n            )\r\n        )\r\n        .sort(\r\n          (a, b) =>\r\n            a.length - b.length\r\n        )\r\n\r\n    await fs.rename(\r\n      normalizedOldPath,\r\n      normalizedNewPath\r\n    )\r\n\r\n    // Rebuild watcher subtree\r\n    for (const watchedPath of watcherPaths) {\r\n      const relativePath =\r\n        path.relative(\r\n          normalizedOldPath,\r\n          watchedPath\r\n        )\r\n\r\n      const newWatchedPath =\r\n        path.join(\r\n          normalizedNewPath,\r\n          relativePath\r\n        )\r\n\r\n      await this.unwatchDirectoryNode(\r\n        watchedPath\r\n      )\r\n\r\n      await this.watchDirectoryNode(\r\n        newWatchedPath\r\n      )\r\n    }\r\n  }\r\n\r\n  // Read full file\r\n  async readFile(\r\n    filePath,\r\n    encoding = 'utf-8'\r\n  ) {\r\n    const mime = this.guessFileMime(filePath)\r\n    if (mime === 'unsupport') return {mime: mime, content: null}\r\n    const content_raw = await fs.readFile(\r\n      this.normalizePath(\r\n        filePath\r\n      ),\r\n      encoding\r\n    )\r\n    const content = this.parseFileContent(content_raw, mime)\r\n    return {\r\n      mime: mime,\r\n      content: content\r\n    }\r\n  }\r\n\r\n  // Read full file and return CodeMirror patch\r\n  async reReadFile(\r\n    filePath,\r\n    version,\r\n    baseContent = '',\r\n    encoding = 'utf-8',\r\n  ) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        filePath\r\n      )\r\n\r\n    const mime =\r\n      this.guessFileMime(\r\n        normalizedPath\r\n      )\r\n\r\n    if (mime === 'unsupport') {\r\n      return {\r\n        changed: false,\r\n        mime: mime,\r\n        version: version,\r\n        patch: null\r\n      }\r\n    }\r\n\r\n    const content_raw =\r\n      await fs.readFile(\r\n        normalizedPath,\r\n        encoding\r\n      )\r\n\r\n    // Calculate current disk hash\r\n    const currentHash =\r\n      crypto\r\n        .createHash('sha256')\r\n        .update(content_raw, encoding)\r\n        .digest('hex')\r\n\r\n    const ignoredHash =\r\n      this.changeIgnoreMap[\r\n        normalizedPath\r\n      ]\r\n\r\n    // Ignore self write\r\n    if (currentHash === ignoredHash) {\r\n      delete this.changeIgnoreMap[\r\n        normalizedPath\r\n      ]\r\n\r\n      return {\r\n        changed: false,\r\n        mime: mime,\r\n        version: version,\r\n        patch: null\r\n      }\r\n    }\r\n\r\n    // Generate diff patch\r\n    const diffs =\r\n      diff(\r\n        baseContent,\r\n        content_raw\r\n      )\r\n\r\n    const patch = []\r\n\r\n    let cursor = 0\r\n\r\n    for (const [\r\n      type,\r\n      text\r\n    ] of diffs) {\r\n\r\n      // Equal\r\n      if (type === 0) {\r\n        cursor += text.length\r\n        continue\r\n      }\r\n\r\n      // Insert\r\n      if (type === 1) {\r\n        patch.push({\r\n          from: cursor,\r\n          to: cursor,\r\n          insert: text\r\n        })\r\n\r\n        continue\r\n      }\r\n\r\n      // Delete\r\n      if (type === -1) {\r\n        patch.push({\r\n          from: cursor,\r\n          to: cursor + text.length,\r\n          insert: ''\r\n        })\r\n\r\n        cursor += text.length\r\n      }\r\n    }\r\n\r\n    return {\r\n      changed:\r\n        patch.length > 0,\r\n      mime: mime,\r\n      version: version,\r\n      patch: patch\r\n    }\r\n  }\r\n\r\n  // Write full file\r\n  async writeFile(\r\n    filePath,\r\n    content,\r\n    encoding = 'utf-8'\r\n  ) {\r\n    const normalizedPath =\r\n      this.normalizePath(\r\n        filePath\r\n      )\r\n\r\n    // Save content hash before writing\r\n    this.changeIgnoreMap[normalizedPath] =\r\n      crypto\r\n        .createHash('sha256')\r\n        .update(content, encoding)\r\n        .digest('hex')\r\n\r\n    await fs.mkdir(\r\n      path.dirname(\r\n        normalizedPath\r\n      ),\r\n      {\r\n        recursive: true\r\n      }\r\n    )\r\n\r\n    await fs.writeFile(\r\n      normalizedPath,\r\n      content,\r\n      encoding\r\n    )\r\n  }\r\n\r\n  // Search files\r\n  async searchFiles(cwd) {\r\n    return await fg(\r\n      [\r\n        '**/*.md',\r\n        '**/*.aflow',\r\n        '**/*.agraph'\r\n      ],\r\n      {\r\n        cwd,\r\n\r\n        absolute: true,\r\n\r\n        onlyFiles: true,\r\n\r\n        ignore: this.IGNORE_GLOBS\r\n      }\r\n    )\r\n  }\r\n\r\n  // Search text\r\n  async searchText(\r\n    keyword,\r\n    cwd\r\n  ) {\r\n    const files =\r\n      await this.searchFiles(\r\n        cwd\r\n      )\r\n\r\n    const results = []\r\n\r\n    for (const filePath of files) {\r\n      try {\r\n        const content =\r\n          await this.readFile(\r\n            filePath\r\n          )\r\n\r\n        if (\r\n          content.includes(\r\n            keyword\r\n          )\r\n        ) {\r\n          results.push(\r\n            filePath\r\n          )\r\n        }\r\n      }\r\n      catch {\r\n        // Ignore unreadable file\r\n      }\r\n    }\r\n\r\n    return results\r\n  }\r\n\r\n  // Create Anthropic skill folder\r\n  async createSkillFolder(atPath, skillName) {\r\n    try {\r\n      const basePath =\r\n        this.normalizePath(\r\n          atPath\r\n        )\r\n\r\n      const skillDirPath =\r\n        path.join(\r\n          basePath,\r\n          skillName\r\n        )\r\n\r\n      // Check directory exists\r\n      try {\r\n        await fs.access(skillDirPath)\r\n\r\n        return {\r\n          success: false,\r\n          message: '技能包目录已存在'\r\n        }\r\n      }\r\n      catch {\r\n        // Directory not exists, continue create\r\n      }\r\n\r\n      // Create skill directory\r\n      await fs.mkdir(\r\n        skillDirPath,\r\n        { recursive: true }\r\n      )\r\n\r\n      // Anthropic skill metadata\r\n      const skillMeta = {\r\n        name: skillName,\r\n        description: '',\r\n        version: '1.0.0'\r\n      }\r\n\r\n      const yamlContent =\r\n        yaml.dump(\r\n          skillMeta,\r\n          {\r\n            lineWidth: -1\r\n          }\r\n        )\r\n\r\n      const skillMdContent =\r\n`---\r\n${yamlContent}---\r\n\r\n# ${skillName}\r\n\r\n- Add skill detail here.\r\n`\r\n\r\n      // Create SKILL.md\r\n      await fs.writeFile(\r\n        path.join(\r\n          skillDirPath,\r\n          'SKILL.md'\r\n        ),\r\n        skillMdContent,\r\n        'utf-8'\r\n      )\r\n\r\n      return {\r\n        success: true,\r\n        message: skillDirPath\r\n      }\r\n    }\r\n    catch (e) {\r\n      console.error('createSkillFolder error:', e)\r\n\r\n      return {\r\n        success: false,\r\n        message: e?.message || '创建技能包失败'\r\n      }\r\n    }\r\n  }\r\n\r\n  async compressFolder(atPath) {\r\n    const stat = await fs.stat(atPath);\r\n    const dir = path.dirname(atPath);\r\n\r\n    // Folder => folderName.zip\r\n    // File => fileName(without ext).zip\r\n    const baseName = stat.isDirectory()\r\n      ? path.basename(atPath)\r\n      : path.parse(atPath).name;\r\n\r\n    let zipPath = path.join(dir, `${baseName}.zip`);\r\n    let index = 1;\r\n\r\n    while (true) {\r\n      try {\r\n        await fs.access(zipPath);\r\n        zipPath = path.join(dir, `${baseName}(${index}).zip`);\r\n        index++;\r\n      } catch {\r\n        break;\r\n      }\r\n    }\r\n\r\n    return new Promise((resolve, reject) => {\r\n      import('fs')\r\n        .then(({ default: fsNative }) => {\r\n          const output = fsNative.createWriteStream(zipPath);\r\n          const archive = archiver('zip', {\r\n            zlib: { level: 9 }\r\n          });\r\n\r\n          output.on('close', () => resolve(zipPath));\r\n          output.on('error', reject);\r\n          archive.on('error', reject);\r\n\r\n          archive.pipe(output);\r\n\r\n          if (stat.isDirectory()) {\r\n            archive.directory(atPath, false);\r\n          } else {\r\n            archive.file(atPath, {\r\n              name: path.basename(atPath)\r\n            });\r\n          }\r\n\r\n          archive.finalize();\r\n        })\r\n        .catch(reject);\r\n    });\r\n  }\r\n\r\n  // RPC handlers\r\n  handlers = {\r\n    scanDir:\r\n      this.scanDir.bind(this),\r\n\r\n    watchWorkspace:\r\n      this.watchWorkspace.bind(this),\r\n\r\n    unwatchWorkspace:\r\n      this.unwatchWorkspace.bind(this),\r\n\r\n    watchDirectoryNode:\r\n      this.watchDirectoryNode.bind(this),\r\n\r\n    unwatchDirectoryNode:\r\n      this.unwatchDirectoryNode.bind(this),\r\n\r\n    getDirectoryTree:\r\n      this.getDirectoryTree.bind(this),\r\n\r\n    createFile:\r\n      this.createFile.bind(this),\r\n\r\n    deleteFile:\r\n      this.deleteFile.bind(this),\r\n\r\n    readFile:\r\n      this.readFile.bind(this),\r\n\r\n    reReadFile:\r\n      this.reReadFile.bind(this),\r\n\r\n    writeFile:\r\n      this.writeFile.bind(this),\r\n\r\n    searchFiles:\r\n      this.searchFiles.bind(this),\r\n\r\n    createDirectory:\r\n      this.createDirectory.bind(this),\r\n\r\n    deleteDirectory:\r\n      this.deleteDirectory.bind(this),\r\n\r\n    rename:\r\n      this.rename.bind(this),\r\n\r\n    searchText:\r\n      this.searchText.bind(this),\r\n\r\n    createSkillFolder:\r\n      this.createSkillFolder.bind(this),\r\n\r\n    compressFolder:\r\n      this.compressFolder.bind(this),\r\n  }\r\n\r\n  // Handle RPC message\r\n  async handleMessage(\r\n    message\r\n  ) {\r\n    const {\r\n      method,\r\n      params,\r\n      requestId\r\n    } = message\r\n\r\n    const handler =\r\n      this.handlers[method]\r\n\r\n    if (!handler) {\r\n      this.response(\r\n        requestId,\r\n        null,\r\n        `Unknown method: ${method}`\r\n      )\r\n\r\n      return\r\n    }\r\n\r\n    try {\r\n      const result =\r\n        await handler(\r\n          ...Object.values(\r\n            params\r\n          )\r\n        )\r\n\r\n      this.response(\r\n        requestId,\r\n        result\r\n      )\r\n    }\r\n    catch (err) {\r\n      this.response(\r\n        requestId,\r\n        null,\r\n        err.stack\r\n      )\r\n    }\r\n  }\r\n}\r\n\r\n// Create worker instance\r\nnew FsWatcherWorker()";
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
  electron.ipcMain.handle("openFileDialog", async (event, type, extensions = []) => {
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
      title: "APIX",
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
  electron.ipcMain.handle("api:new_chat", async (event, cid, workspace = "") => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/memory/conversation/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: "",
          title: "新的聊天...",
          workspace
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Create conversation failed.");
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
      if (!res.ok) {
        throw new Error(data.detail || "Update conversation failed.");
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
      if (!res.ok) {
        throw new Error(data.detail || "Get conversation list failed.");
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
      if (!res.ok) {
        throw new Error(data.detail || "Fetch conversation msgs failed.");
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
      if (!res.ok) {
        throw new Error(data.detail || "Delete messages failed.");
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
