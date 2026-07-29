PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_uid TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_uid TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'default',
    conversation_uid TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT 'New Conversation...',
    last_active_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latest_cursor INTEGER NOT NULL DEFAULT 0,
    has_new_message INTEGER NOT NULL DEFAULT 0,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_cron INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latest_timestamp INTEGER NOT NULL DEFAULT 0,
    work_space TEXT,
    UNIQUE (user_uid, conversation_uid),
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_pinned_active
    ON conversations(user_uid, is_pinned DESC, last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_active
    ON conversations(user_uid, last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_lookup
    ON conversations(user_uid, conversation_uid, is_deleted);

CREATE TABLE IF NOT EXISTS shortterm_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL UNIQUE,
    user_uid TEXT NOT NULL,
    conversation_uid TEXT NOT NULL,
    content TEXT NOT NULL,
    created_timestamp INTEGER NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE,
    FOREIGN KEY (conversation_uid) REFERENCES conversations(conversation_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_shortterm_memory_lookup
    ON shortterm_memory(user_uid, conversation_uid, created_timestamp DESC);

CREATE TABLE IF NOT EXISTS longterm_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL UNIQUE,
    user_uid TEXT NOT NULL,
    title TEXT NOT NULL,
    memory_date TEXT NOT NULL
        CHECK (
            memory_date GLOB
                '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(memory_date) IS NOT NULL
            AND memory_date = date(memory_date)
        ),
    content TEXT NOT NULL,
    source TEXT NOT NULL
        CHECK (source IN ('conversation', 'workspace')),
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_longterm_memory_user_date
    ON longterm_memory(user_uid, is_deleted, memory_date DESC, id DESC);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_uid TEXT NOT NULL UNIQUE,
    msg_cursor INTEGER NOT NULL,
    user_uid TEXT NOT NULL,
    conversation_id INTEGER NOT NULL,
    conversation_uid TEXT NOT NULL,
    generation_id TEXT NOT NULL DEFAULT '',
    node_id TEXT NOT NULL DEFAULT '',
    parent_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('user', 'ai', 'system', 'tool', 'info')),
    name TEXT,
    content TEXT,
    metadata TEXT CHECK (metadata IS NULL OR json_valid(metadata)),
    extensions TEXT CHECK (extensions IS NULL OR json_valid(extensions)),
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE (conversation_id, msg_cursor),
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_user_conversation_cursor
    ON messages(user_uid, conversation_uid, msg_cursor);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_node
    ON messages(conversation_id, node_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_parent
    ON messages(conversation_id, parent_id);

CREATE TABLE IF NOT EXISTS rag_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL UNIQUE,
    document_name TEXT NOT NULL,
    document_description TEXT NOT NULL DEFAULT '',
    embed_engine TEXT CHECK (embed_engine IS NULL OR json_valid(embed_engine)),
    mime_type TEXT NOT NULL DEFAULT 'unknown',
    document_path TEXT NOT NULL,
    document_size INTEGER NOT NULL,
    document_sha256 TEXT,
    user_uid TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    upload_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_user_id
    ON rag_documents(user_uid, document_id);
CREATE INDEX IF NOT EXISTS idx_rag_documents_user_upload
    ON rag_documents(user_uid, upload_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_documents_user_active
    ON rag_documents(user_uid, deleted, upload_at DESC);

CREATE TABLE IF NOT EXISTS agent_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL UNIQUE,
    skill_name TEXT NOT NULL,
    skill_description TEXT NOT NULL,
    skill_version TEXT NOT NULL DEFAULT 'v1.0',
    package_path TEXT NOT NULL,
    package_size INTEGER NOT NULL,
    package_sha256 TEXT,
    user_uid TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    upload_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_skills_user_id
    ON agent_skills(user_uid, skill_id);
CREATE INDEX IF NOT EXISTS idx_agent_skills_user_upload
    ON agent_skills(user_uid, upload_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_skills_user_active
    ON agent_skills(user_uid, deleted, upload_at DESC);

CREATE TABLE IF NOT EXISTS llm_provider (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL UNIQUE,
    user_uid TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'openai' CHECK (type IN ('openai', 'anthropic')),
    endpoint TEXT NOT NULL,
    model_list TEXT NOT NULL CHECK (json_valid(model_list)),
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mcp_server (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mcp_id TEXT NOT NULL UNIQUE,
    user_uid TEXT NOT NULL,
    mcp_name TEXT NOT NULL,
    transport TEXT NOT NULL CHECK (
        transport IN ('stdio', 'http', 'streamable_http', 'websocket', 'sse')
    ),
    endpoint TEXT,
    config TEXT NOT NULL CHECK (json_valid(config)),
    description TEXT,
    tool_count INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cron_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    user_uid TEXT NOT NULL,
    conversation_uid TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    prompt TEXT,
    execute TEXT,
    exec_time TEXT NOT NULL,
    repeat TEXT NOT NULL DEFAULT 'once' CHECK (
        repeat IN ('once', 'day', 'week', 'month', 'year', 'cron')
    ),
    extra_config TEXT CHECK (extra_config IS NULL OR json_valid(extra_config)),
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_uid) REFERENCES users(user_uid) ON DELETE CASCADE,
    FOREIGN KEY (conversation_uid) REFERENCES conversations(conversation_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cron_task_user
    ON cron_task(user_uid, is_deleted, exec_time);
CREATE INDEX IF NOT EXISTS idx_cron_task_enabled
    ON cron_task(is_deleted, enabled, exec_time);
