import { Worker } from 'worker_threads'

import fsWatcherWorker
from './workers/FsWatcherWorker.js?raw'

export class FileSystemManager {

    constructor(options = {}) {
        // Event callback
        this.onEvents =
            options.onEvents || (() => {})

        // RPC request id
        this.requestId = 0

        // Pending promises
        this.pendingRequests =
            new Map()

        // Create worker
        this.worker = new Worker(
            fsWatcherWorker,
            {
                eval: true
            }
        )

        // Worker messages
        this.worker.on(
            'message',
            message => {
                this._handleMessage(
                    message
                )
            }
        )

        // Worker crash
        this.worker.on(
            'error',
            err => {
                console.error(
                    '[FS Worker Crash]',
                    err
                )
            }
        )
    }

    // Handle worker message
    _handleMessage(message) {
        const {
            type,
            requestId
        } = message

        // FS events
        if (type === 'events') {
            this.onEvents(
                message.events
            )

            return
        }

        // RPC response
        if (
            type === 'response'
        ) {
            const pending =
                this.pendingRequests.get(
                    requestId
                )

            if (!pending) {
                return
            }

            this.pendingRequests.delete(
                requestId
            )

            if (message.error) {
                pending.reject(
                    message.error
                )
            }
            else {
                pending.resolve(
                    message.result
                )
            }
        }
    }

    // RPC call
    _call(method, params = {}) {
        return new Promise(
            (resolve, reject) => {
                const requestId =
                    ++this.requestId

                this.pendingRequests.set(
                    requestId,
                    {
                        resolve,
                        reject
                    }
                )

                this.worker.postMessage({
                    type: 'call',
                    method,
                    params,
                    requestId
                })
            }
        )
    }

    // Watch workspace
    watchWorkspace(dirPath) {
        if (dirPath && dirPath !== ''){
            return this._call(
                'watchWorkspace',
                { dirPath }
            )
        }
    }

    // Unwatch workspace
    unwatchWorkspace() {
        return this._call(
            'unwatchWorkspace',
        )
    }

    // Get directory tree inside workspace
    getDirectoryTree(targetPath) {
        return this._call(
            'getDirectoryTree',
            { targetPath }
        )
    }

    // Watch a node
    watchDirectoryNode(targetPath) {
        return this._call(
            'watchDirectoryNode',
            { targetPath }
        )
    }

    // Collapse directory tree inside workspace
    collapseDirectoryTree(targetPath) {
        return this._call(
            'unwatchDirectoryNode',
            { targetPath }
        )
    }

    // Create file
    createFile(filePath, encoding = 'utf-8') {
        return this._call(
            'createFile',
            { filePath, encoding }
        )
    }

    // Delete file
    deleteFile(filePath) {
        return this._call(
            'deleteFile',
            { filePath }
        )
    }

    // Read file
    readFile(filePath, encoding = 'utf-8') {
        return this._call(
            'readFile',
            { filePath, encoding }
        )
    }

    // reRead file
    reReadFile(filePath, version, baseContent = '', encoding = 'utf-8') {
        return this._call(
            'reReadFile',
            { filePath, version, baseContent, encoding }
        )
    }

    // Write file
    writeFile(filePath, content, encoding = 'utf-8') {
        return this._call(
            'writeFile',
            { filePath, content, encoding }
        )
    }

    // Search files
    searchFiles(cwd) {
        return this._call(
            'searchFiles',
            { cwd }
        )
    }

    // Create directory
    createDirectory(dirPath) {
        return this._call(
            'createDirectory',
            { dirPath }
        )
    }

    // Delete directory
    deleteDirectory(dirPath) {
        return this._call(
            'deleteDirectory',
            { dirPath }
        )
    }

    // Rename
    rename(oldPath, newPath) {
        return this._call(
            'rename',
            { oldPath, newPath }
        )
    }

    // Search text
    searchText(keyword, cwd) {
        return this._call(
            'searchText',
            { keyword, cwd }
        )
    }

    // Search text
    createSkillFolder(atPath, skillName) {
        return this._call(
            'createSkillFolder',
            { atPath, skillName }
        )
    }

    // Search text
    compressFolder(atPath) {
        return this._call(
            'compressFolder',
            { atPath }
        )
    }

    // Dispose
    async dispose() {
        await this.worker.terminate()
    }
}