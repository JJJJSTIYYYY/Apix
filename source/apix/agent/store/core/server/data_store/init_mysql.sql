SET time_zone = '+08:00';

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    user_uid VARCHAR(64) NOT NULL UNIQUE COMMENT 'External user identifier',

    username VARCHAR(64) NOT NULL UNIQUE,

    password VARCHAR(64) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE = utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS conversations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Conversation id used in system',

    user_uid VARCHAR(64) NOT NULL COMMENT 'Owner user uid',
    platform VARCHAR(32) NOT NULL DEFAULT 'default',

    conversation_uid VARCHAR(64) NOT NULL COMMENT 'Conversation uid that exposes to user',
    title VARCHAR(255) NOT NULL DEFAULT 'New Conversation...' COMMENT 'Conversation title',

    last_active_at TIMESTAMP NOT NULL COMMENT 'Last message time',
    latest_cursor BIGINT NOT NULL DEFAULT 0 COMMENT 'Latest message id, Monotonic message cursor for this conversation',
    has_new_message BOOLEAN DEFAULT FALSE,

    is_pinned BOOLEAN DEFAULT FALSE,
    is_cron BOOLEAN DEFAULT  FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    latest_timestamp BIGINT NOT NULL DEFAULT 0,

    work_space VARCHAR(255) DEFAULT NULL COMMENT 'Agent work dir',

    UNIQUE KEY uk_user_conversation (user_uid, conversation_uid),

    UNIQUE KEY uk_conversation_uid (conversation_uid),

    INDEX idx_user_latest_pinned (user_uid, is_pinned DESC, last_active_at DESC),

    INDEX idx_user_last_active (user_uid, last_active_at DESC),

    INDEX idx_user_conversation_active (user_uid, conversation_uid, is_deleted),

    CONSTRAINT fk_conversation_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE = utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS shortterm_memory (
    -- Identity
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Internal auto id',
    memory_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Related message_uid',
    user_uid VARCHAR(64) NOT NULL COMMENT 'External user identifier',
    conversation_uid VARCHAR(64) NOT NULL COMMENT 'External conversation uid',

    -- Memory context
    content TEXT NOT NULL COMMENT 'Memory content',

    -- Time (all microsecond-aligned)
    created_timestamp BIGINT NOT NULL COMMENT 'Unix timestamp * 1_000_000',
    is_deleted BOOLEAN DEFAULT FALSE,

    -- Indexes
    INDEX idx_user_conversation_uid (
        user_uid,
        conversation_uid,
        created_timestamp DESC
    ),

    -- FK
    CONSTRAINT fk_shortterm_memory_user
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE,
    CONSTRAINT fk_shortterm_memory_conversation
        FOREIGN KEY (conversation_uid)
        REFERENCES conversations(conversation_uid)
        ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS longterm_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Internal auto id',
    memory_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Long-term memory id',
    user_uid VARCHAR(64) NOT NULL COMMENT 'Owner user uid',

    title VARCHAR(255) NOT NULL COMMENT 'Memory title',
    memory_date DATE NOT NULL COMMENT 'Memory date',
    content LONGTEXT NOT NULL COMMENT 'Memory content',
    source ENUM('conversation', 'workspace') NOT NULL COMMENT 'Memory source',

    is_deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Soft delete flag',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME DEFAULT NULL COMMENT 'Soft delete time',

    INDEX idx_longterm_memory_user_date (
        user_uid,
        is_deleted,
        memory_date DESC,
        id DESC
    ),

    CONSTRAINT fk_longterm_memory_user
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_uid VARCHAR(64) NOT NULL COMMENT 'Application-level unique message id',
    msg_cursor BIGINT NOT NULL COMMENT 'Message cursor in one conversation',

    user_uid VARCHAR(64) NOT NULL COMMENT 'Owner user uid',
    conversation_id BIGINT NOT NULL COMMENT 'id in table conversations, to make table joins more efficient.',

    conversation_uid VARCHAR(64) NOT NULL COMMENT 'The conversation uid that exposes to user, it will be used to query messages.',
    generation_id VARCHAR(64) NOT NULL COMMENT 'Generation id to identify different llm''s generation task, include user message enter and all ai message triggered by this input.',
    node_id VARCHAR(32) NOT NULL COMMENT 'Unique identifier of the message node.',
    parent_id VARCHAR(32) NOT NULL COMMENT 'Reference to the parent node (previous message in the conversation tree).',

    role ENUM('user', 'ai', 'system', 'tool', 'info') NOT NULL,
    name VARCHAR(255) DEFAULT NULL COMMENT 'Assistant, user, or tool name',
    content LONGTEXT,
    metadata JSON DEFAULT NULL COMMENT 'Usage, model provider, duration, and similar metadata',
    extensions JSON DEFAULT NULL COMMENT 'Reasoning, tool calls, plans, search, files, instructions, references, and other business data',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',

    is_deleted BOOLEAN DEFAULT FALSE,

    UNIQUE KEY uk_message_uid (message_uid),
    UNIQUE KEY uk_conversation_cursor (conversation_id, msg_cursor),

    INDEX idx_user_conversation_cursor (
        user_uid,
        conversation_uid,
        msg_cursor
    ),

    INDEX uk_conv_node (conversation_id, node_id),
    INDEX idx_conv_parent (conversation_id, parent_id),

    CONSTRAINT fk_message_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE,

    CONSTRAINT fk_message_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE = utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    document_id VARCHAR(64) NOT NULL COMMENT 'Document id generated by file_service',
    document_name VARCHAR(255) NOT NULL COMMENT 'User display name',
    document_description TEXT NOT NULL COMMENT 'Document description',

    embed_engine JSON DEFAULT NULL,

    mime_type VARCHAR(128) DEFAULT 'unknow' COMMENT 'File mime type',
    document_path VARCHAR(512) NOT NULL COMMENT 'Physical path in file_service',
    document_size BIGINT NOT NULL COMMENT 'Document file size in bytes',
    document_sha256 CHAR(64) DEFAULT NULL COMMENT 'Optional file hash',

    user_uid VARCHAR(64) NOT NULL COMMENT 'Owner user uid',

    is_active BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'If the document is active',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Soft delete flag',
    upload_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Upload time',
    deleted_at DATETIME DEFAULT NULL COMMENT 'Soft delete time',

    UNIQUE KEY uk_document_id (document_id),

    INDEX idx_user_document_id (user_uid, document_id),
    INDEX idx_user_upload (user_uid, upload_at DESC),
    INDEX idx_user_active (user_uid, deleted, upload_at DESC),

    CONSTRAINT fk_document_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS agent_skills (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    skill_id VARCHAR(64) NOT NULL COMMENT 'Skill id generated by file_service',
    skill_name VARCHAR(255) NOT NULL COMMENT 'User display name',
    skill_description TEXT NOT NULL COMMENT 'Skill description',
    skill_version VARCHAR(16) NOT NULL DEFAULT 'v1.0',

    package_path VARCHAR(512) NOT NULL COMMENT 'Physical path in file_service',
    package_size BIGINT NOT NULL COMMENT 'Skill package size in bytes',
    package_sha256 CHAR(64) DEFAULT NULL COMMENT 'Optional file hash',

    user_uid VARCHAR(64) NOT NULL COMMENT 'Owner user uid',

    is_active BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'If the skill is active',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Soft delete flag',
    upload_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Upload time',
    deleted_at DATETIME DEFAULT NULL COMMENT 'Soft delete time',

    UNIQUE KEY uk_skill_id (skill_id),

    INDEX idx_user_skill_id (user_uid, skill_id),
    INDEX idx_user_upload (user_uid, upload_at DESC),
    INDEX idx_user_active (user_uid, deleted, upload_at DESC),

    CONSTRAINT fk_skill_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS llm_provider (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    provider_id VARCHAR(64) UNIQUE NOT NULL,
    user_uid VARCHAR(64) NOT NULL,

    provider_name VARCHAR(64) NOT NULL,
    type ENUM('openai', 'anthropic') NOT NULL DEFAULT 'openai',
    endpoint VARCHAR(256) NOT NULL,
    model_list JSON NOT NULL,
    description TEXT DEFAULT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_provider_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE

) DEFAULT CHARSET=utf8mb4 COLLATE = utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS mcp_server (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    mcp_id VARCHAR(64) UNIQUE NOT NULL,
    user_uid VARCHAR(64) NOT NULL,
    mcp_name VARCHAR(64) NOT NULL,

    transport ENUM(
        'stdio', 'http', 'streamable_http', 'websocket', 'sse'
    ) NOT NULL,
    endpoint VARCHAR(512) DEFAULT NULL,
    config JSON NOT NULL,
    description TEXT DEFAULT NULL,
    tool_count INT NOT NULL DEFAULT 0,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_mcp_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE

) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



CREATE TABLE IF NOT EXISTS cron_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Business ID
    task_id VARCHAR(64) NOT NULL,

    -- ApixIdentity
    user_uid VARCHAR(64) NOT NULL,
    conversation_uid VARCHAR(64) NOT NULL,
    platform VARCHAR(32) NOT NULL DEFAULT 'default',

    -- Task
    name VARCHAR(255) NOT NULL COMMENT 'Task name',
    prompt TEXT DEFAULT NULL COMMENT 'Prompt sent to the agent',
    execute LONGTEXT DEFAULT NULL COMMENT 'Python execute code',
    exec_time DATETIME NOT NULL COMMENT 'Next execution time',
    `repeat` ENUM('once', 'day', 'week', 'month', 'year', 'cron') NOT NULL DEFAULT 'once',
    extra_config JSON DEFAULT NULL,
    description TEXT DEFAULT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Metadata
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE KEY uk_task_id (task_id),

    INDEX idx_user_tasks (
        user_uid,
        is_deleted,
        exec_time
    ),

    INDEX idx_enabled_tasks (
        is_deleted,
        enabled,
        exec_time
    ),

    CONSTRAINT fk_user_uid
        FOREIGN KEY (user_uid)
        REFERENCES users(user_uid)
        ON DELETE CASCADE,

    CONSTRAINT fk_cron_task_conversation
        FOREIGN KEY (conversation_uid)
        REFERENCES conversations(conversation_uid)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



-- Stored Procedure: create_user
DROP PROCEDURE IF EXISTS create_user;
DELIMITER $$

CREATE PROCEDURE create_user (
    IN p_user_uid VARCHAR(64),
    IN p_username VARCHAR(64),
    IN p_password VARCHAR(255)
)
BEGIN
    INSERT INTO users
    SET
        user_uid = p_user_uid,
        username = p_username,
        password = p_password;
END$$

DELIMITER ;



-- Stored Procedure: verify_user
DROP PROCEDURE IF EXISTS verify_user;
DELIMITER $$

CREATE PROCEDURE verify_user (
    IN p_username VARCHAR(64),
    IN p_password VARCHAR(255)
)
BEGIN
    SELECT user_uid, username
    FROM users
    WHERE username=p_username AND password=p_password;
END$$

DELIMITER ;



-- Stored Procedure: ensure_user_exists
DROP PROCEDURE IF EXISTS ensure_user_exists;
DELIMITER $$

CREATE PROCEDURE ensure_user_exists (
    IN p_user_uid VARCHAR(64),
    IN p_user_name VARCHAR(64)
)
BEGIN
    SELECT user_uid, username
    FROM users
    WHERE user_uid = p_user_uid
        OR username = p_user_name;
END$$

DELIMITER ;



-- Stored Procedure: create_conversation
DROP PROCEDURE IF EXISTS create_conversation;
DELIMITER $$

CREATE PROCEDURE create_conversation (
    IN p_user_uid VARCHAR(64),
    IN p_platform VARCHAR(32),
    IN p_conversation_uid VARCHAR(64),
    IN p_title VARCHAR(255),
    IN p_workspace VARCHAR(255),
    IN p_is_cron BOOLEAN
)
BEGIN
    INSERT INTO conversations (
        user_uid,
        platform,
        conversation_uid,
        title,
        work_space,
        last_active_at,
        latest_cursor,
        is_cron
    )
    VALUES (
        p_user_uid,
        p_platform,
        p_conversation_uid,
        COALESCE(p_title, 'New Conversation...'),
        COALESCE(p_workspace, ''),
        CURRENT_TIMESTAMP,
        0,
        p_is_cron
    );
END$$

DELIMITER ;



-- Stored Procedure: update_conversation
DROP PROCEDURE IF EXISTS update_conversation;
DELIMITER $$

CREATE PROCEDURE update_conversation (
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_title VARCHAR(255),
    IN p_workspace VARCHAR(255),
    IN p_is_pinned BOOLEAN,
    IN p_is_deleted BOOLEAN,
    IN p_new_message BOOLEAN
)
BEGIN
    UPDATE conversations
    SET
        title = IF(p_title IS NULL, title, p_title),
        work_space = IF(p_workspace IS NULL, work_space, p_workspace),
        is_pinned = IF(p_is_pinned IS NULL, is_pinned, p_is_pinned),
        is_deleted = IF(p_is_deleted IS NULL, is_deleted, p_is_deleted),
        has_new_message = IF(p_new_message IS NULL, has_new_message, p_new_message)
    WHERE user_uid = p_user_uid
      AND conversation_uid = p_conversation_uid;

    -- Return affected rows so caller knows what happened
#     SELECT ROW_COUNT() AS affected_rows;
END$$

DELIMITER ;



-- Stored Procedure: fetch_conversation_list
DROP PROCEDURE IF EXISTS fetch_conversation_list;
DELIMITER $$

CREATE PROCEDURE fetch_conversation_list (
    IN p_user_uid VARCHAR(64)
)
BEGIN
    SELECT
        conversation_uid,
        title,
        work_space,
        last_active_at,
        created_at,
        latest_cursor,
        is_pinned,
        has_new_message,
        is_cron
    FROM conversations
    WHERE user_uid = p_user_uid
        AND is_deleted != TRUE
    ORDER BY is_pinned DESC, last_active_at DESC;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_conversation_meta_by_id;
DELIMITER $$

CREATE PROCEDURE get_conversation_meta_by_id (
    IN p_conversation_uid VARCHAR(64)
)
BEGIN
    SELECT
        conversation_uid,
        title,
        work_space,
        last_active_at,
        created_at,
        latest_cursor,
        is_pinned,
        has_new_message
    FROM conversations
    WHERE conversation_uid = p_conversation_uid
        AND is_deleted != TRUE
    LIMIT 1;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS insert_shortterm_memory;
DELIMITER $$

CREATE PROCEDURE insert_shortterm_memory (
    IN p_memory_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_content TEXT,
    IN p_created_timestamp BIGINT
)
BEGIN
    -- Insert a new short-term memory record
    INSERT INTO shortterm_memory (
        memory_id,
        user_uid,
        conversation_uid,
        content,
        created_timestamp
    ) VALUES (
        p_memory_id,
        p_user_uid,
        p_conversation_uid,
        p_content,
        p_created_timestamp
    );
END $$

DELIMITER ;



DROP PROCEDURE IF EXISTS delete_shortterm_memory;
DELIMITER $$

CREATE PROCEDURE delete_shortterm_memory (
    IN p_memory_ids JSON,
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64)
)
BEGIN
    UPDATE shortterm_memory stm
    JOIN JSON_TABLE(
        p_memory_ids,
        '$[*]' COLUMNS (
            memory_id VARCHAR(64)
            CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
            PATH '$'
        )
    ) jt
    ON stm.memory_id = jt.memory_id
    SET stm.is_deleted = TRUE
    WHERE stm.user_uid = p_user_uid
      AND stm.conversation_uid = p_conversation_uid
      AND stm.is_deleted = FALSE;
END $$

DELIMITER ;



DROP PROCEDURE IF EXISTS fetch_shortterm_memory;
DELIMITER $$

CREATE PROCEDURE fetch_shortterm_memory (
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64)
)
BEGIN
    -- Fetch the latest short-term memory (limit 1)
    SELECT
        memory_id,
        content,
        created_timestamp
    FROM shortterm_memory
    WHERE user_uid = p_user_uid
      AND conversation_uid = p_conversation_uid
      AND is_deleted = FALSE
    ORDER BY created_timestamp DESC
    LIMIT 1;
END $$

DELIMITER ;



DROP PROCEDURE IF EXISTS insert_longterm_memory;
DELIMITER $$

CREATE PROCEDURE insert_longterm_memory (
    IN p_memory_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_title VARCHAR(255),
    IN p_date DATE,
    IN p_content LONGTEXT,
    IN p_source ENUM('conversation', 'workspace')
)
BEGIN
    INSERT INTO longterm_memory (
        memory_id,
        user_uid,
        title,
        memory_date,
        content,
        source
    ) VALUES (
        p_memory_id,
        p_user_uid,
        p_title,
        p_date,
        p_content,
        p_source
    );
END $$

DELIMITER ;



DROP PROCEDURE IF EXISTS fetch_longterm_memory;
DELIMITER $$

CREATE PROCEDURE fetch_longterm_memory (
    IN p_user_uid VARCHAR(64)
)
BEGIN
    SELECT
        memory_id,
        title,
        memory_date AS `date`,
        content,
        source
    FROM longterm_memory
    WHERE user_uid = p_user_uid
      AND is_deleted = FALSE
    ORDER BY memory_date DESC, id DESC;
END $$

DELIMITER ;



DROP PROCEDURE IF EXISTS update_longterm_memory;
DELIMITER $$

CREATE PROCEDURE update_longterm_memory (
    IN p_memory_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_title VARCHAR(255),
    IN p_date DATE,
    IN p_content LONGTEXT,
    IN p_source ENUM('conversation', 'workspace'),
    IN p_is_deleted BOOLEAN
)
BEGIN
    UPDATE longterm_memory
    SET
        title = COALESCE(p_title, title),
        memory_date = COALESCE(p_date, memory_date),
        content = COALESCE(p_content, content),
        source = COALESCE(p_source, source),
        is_deleted = COALESCE(p_is_deleted, is_deleted),
        deleted_at = IF(p_is_deleted = TRUE, CURRENT_TIMESTAMP, deleted_at)
    WHERE memory_id = p_memory_id
      AND user_uid = p_user_uid
      AND is_deleted = FALSE;
END $$

DELIMITER ;



-- Stored Procedure: append_message
DROP PROCEDURE IF EXISTS append_message;
DELIMITER $$

CREATE PROCEDURE append_message (
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_message_uid VARCHAR(64),
    IN p_role ENUM('user', 'ai', 'system', 'tool', 'info'),
    IN p_name VARCHAR(255),
    IN p_content LONGTEXT,
    IN p_metadata JSON,
    IN p_extensions JSON,
    IN p_generation_id VARCHAR(64),
    IN p_node_id VARCHAR(32),
    IN p_parent_id VARCHAR(32)
)
BEGIN
    DECLARE v_conversation_id BIGINT;
    DECLARE v_next_cursor BIGINT;
    DECLARE v_not_found INT DEFAULT 0;
    DECLARE v_message_id BIGINT;

    -- Handler: SELECT ... INTO returns NOT FOUND when no row matched
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_not_found = 1;

    START TRANSACTION;

    -- 1. Lock conversation row
    SELECT
        id,
        latest_cursor
    INTO
        v_conversation_id,
        v_next_cursor
    FROM conversations
    WHERE user_uid = p_user_uid
      AND conversation_uid = p_conversation_uid
      AND is_deleted = FALSE
    FOR UPDATE;

    IF v_not_found = 1 THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conversation not found or deleted';
    END IF;

    -- 2. Advance cursor (monotonic)
    SET v_next_cursor = v_next_cursor + 1;

    -- 3. Insert message
    INSERT INTO messages (
        user_uid,
        conversation_id,
        conversation_uid,
        message_uid,
        role,
        name,
        content,
        metadata,
        extensions,
        msg_cursor,
        generation_id,
        node_id,
        parent_id
    )
    VALUES (
        p_user_uid,
        v_conversation_id,
        p_conversation_uid,
        p_message_uid,
        p_role,
        p_name,
        p_content,
        p_metadata,
        p_extensions,
        v_next_cursor,
        p_generation_id,
        p_node_id,
        p_parent_id
    );

    SET v_message_id = LAST_INSERT_ID();

    -- 4. Update conversation
    UPDATE conversations
    SET
        latest_cursor = v_next_cursor,
        last_active_at = CURRENT_TIMESTAMP,
        has_new_message = IF(p_role = 'user', FALSE, TRUE)
    WHERE id = v_conversation_id;

    -- 5. Return result
    SELECT
        v_message_id AS msg_id,
        v_next_cursor AS msg_cursor,
        NOW() AS timestamp;

    COMMIT;
END$$

DELIMITER ;



-- Stored Procedure: delete_messages
DROP PROCEDURE IF EXISTS delete_messages;
DELIMITER $$

CREATE PROCEDURE delete_messages (
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_generation_id VARCHAR(64),
    IN p_role ENUM('user', 'ai')
)
BEGIN
    START TRANSACTION;

    -- Step 1: Cache target rows and their application message ids.
    CREATE TEMPORARY TABLE tmp_to_delete (
        id BIGINT PRIMARY KEY,
        message_uid VARCHAR(64)
    ) ENGINE=InnoDB;

    INSERT INTO tmp_to_delete (id, message_uid)
    SELECT id, message_uid
    FROM messages
    WHERE user_uid = p_user_uid
      AND conversation_uid = p_conversation_uid
      AND generation_id = p_generation_id
      AND (
            (p_role = 'user' AND role = 'user')
         OR (p_role = 'ai' AND role <> 'user')
      )
    FOR UPDATE; -- lock rows to avoid concurrent modification

    -- Step 2: Update using cached ids
    UPDATE messages m
    JOIN tmp_to_delete t ON m.id = t.id
    SET m.is_deleted = TRUE;

    -- Step 3: Return deleted application message ids.
    SELECT message_uid FROM tmp_to_delete;

    DROP TEMPORARY TABLE tmp_to_delete;

    COMMIT;
END$$

DELIMITER ;



-- Stored Procedure: delete_messages_node
DROP PROCEDURE IF EXISTS delete_messages_node;
DELIMITER $$

CREATE PROCEDURE delete_messages_node (
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_node_id VARCHAR(32)
)
BEGIN
    START TRANSACTION;

    -- Step 1: Cache target rows and their application message ids.
    CREATE TEMPORARY TABLE tmp_to_delete (
        id BIGINT PRIMARY KEY,
        message_uid VARCHAR(64)
    ) ENGINE=InnoDB;

    INSERT INTO tmp_to_delete (id, message_uid)
    SELECT id, message_uid
    FROM messages
    WHERE user_uid = p_user_uid
      AND conversation_uid = p_conversation_uid
      AND node_id = p_node_id
    FOR UPDATE; -- lock rows to avoid concurrent modification

    -- Step 2: Update using cached ids
    UPDATE messages m
    JOIN tmp_to_delete t ON m.id = t.id
    SET m.is_deleted = TRUE;

    -- Step 3: Return deleted application message ids.
    SELECT message_uid FROM tmp_to_delete;

    DROP TEMPORARY TABLE tmp_to_delete;

    COMMIT;
END$$

DELIMITER ;



-- Stored Procedure: fetch_messages_after_cursor
DROP PROCEDURE IF EXISTS fetch_messages_after_cursor;
DELIMITER $$

CREATE PROCEDURE fetch_messages_after_cursor (
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_after_cursor BIGINT,
    IN p_limit INT
)
BEGIN
    SELECT
        message_uid,
        generation_id,
        role,
        name,
        content,
        node_id,
        parent_id,
        metadata,
        extensions,
        msg_cursor,
        timestamp,
        is_deleted
    FROM messages
    WHERE user_uid = p_user_uid
      AND conversation_uid = p_conversation_uid
      AND msg_cursor >= p_after_cursor
    ORDER BY msg_cursor ASC
    LIMIT p_limit;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS search_messages_by_keyword;
DELIMITER $$

CREATE PROCEDURE search_messages_by_keyword (
    IN p_user_uid VARCHAR(64),
    IN p_keyword TEXT
)
BEGIN
    SELECT
        m.conversation_uid,
        m.generation_id,
        m.role,
        m.content,
        c.title,
        c.last_active_at
    FROM messages m
    INNER JOIN (
        SELECT
            id,
            title,
            last_active_at
        FROM conversations
        WHERE user_uid = p_user_uid
            AND is_deleted = FALSE
        ORDER BY last_active_at DESC
    ) c
        ON c.id = m.conversation_id
    WHERE m.is_deleted = FALSE
        AND m.role IN ('user', 'ai')
        AND m.content LIKE CONCAT('%', p_keyword, '%')
    ORDER BY
        c.last_active_at DESC,
        m.id DESC
    LIMIT 300;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS insert_rag_document;
DELIMITER $$

CREATE PROCEDURE insert_rag_document (
    IN p_document_id VARCHAR(64),
    IN p_document_name VARCHAR(255),
    IN p_document_description TEXT,
    IN p_mime_type VARCHAR(128),
    IN p_document_path VARCHAR(512),
    IN p_document_size BIGINT,
    IN p_document_sha256 CHAR(64),
    IN p_user_uid VARCHAR(64)
)
BEGIN

    INSERT INTO rag_documents (
        document_id,
        document_name,
        document_description,
        mime_type,
        document_path,
        document_size,
        document_sha256,
        user_uid
    )
    VALUES (
        p_document_id,
        p_document_name,
        p_document_description,
        p_mime_type,
        p_document_path,
        p_document_size,
        p_document_sha256,
        p_user_uid
    );

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS update_rag_document;
DELIMITER $$

CREATE PROCEDURE update_rag_document (
    IN p_document_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_is_active BOOLEAN,
    IN p_deleted BOOLEAN,
    IN p_description TEXT,
    IN p_embed_engine JSON
)
BEGIN

    UPDATE rag_documents
    SET
        is_active = COALESCE(p_is_active, is_active),
        deleted = COALESCE(p_deleted, deleted),
        document_description = COALESCE(p_description, document_description),
        embed_engine = COALESCE(p_embed_engine, embed_engine),
        deleted_at = IF(p_deleted = TRUE, NOW(), deleted_at)
    WHERE
        user_uid = p_user_uid
        AND document_id = p_document_id;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS fetch_rag_documents;
DELIMITER $$

CREATE PROCEDURE fetch_rag_documents (
    IN p_user_uid VARCHAR(64),
    IN p_limit INT
)
BEGIN

    SELECT
        document_id,
        document_name,
        document_description,
        embed_engine,
        mime_type,
        document_path,
        document_size,
        document_sha256,
        is_active,
        upload_at
    FROM rag_documents
    WHERE
        user_uid = p_user_uid
        AND deleted = FALSE
    ORDER BY upload_at DESC
    LIMIT p_limit;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS fetch_target_document;
DELIMITER $$

CREATE PROCEDURE fetch_target_document (
    IN p_user_uid VARCHAR(64),
    IN p_document_id VARCHAR(64)
)
BEGIN

    SELECT
        document_id,
        document_name,
        document_description,
        embed_engine,
        mime_type,
        document_path,
        document_size,
        document_sha256,
        is_active,
        deleted,
        upload_at,
        deleted_at
    FROM rag_documents
    WHERE
        user_uid = p_user_uid
        AND document_id = p_document_id
    LIMIT 1;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS insert_agent_skill;
DELIMITER $$

CREATE PROCEDURE insert_agent_skill (
    IN p_skill_id VARCHAR(64),
    IN p_skill_name VARCHAR(255),
    IN p_skill_description TEXT,
    IN p_skill_version VARCHAR(16),
    IN p_package_path VARCHAR(512),
    IN p_package_size BIGINT,
    IN p_package_sha256 CHAR(64),
    IN p_user_uid VARCHAR(64)
)
BEGIN

    DECLARE skill_exists INT DEFAULT 0;

    SELECT COUNT(1)
    INTO skill_exists
    FROM agent_skills
    WHERE skill_id = p_skill_id;

    IF skill_exists > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Skill already exists';
    END IF;

    INSERT INTO agent_skills (
        skill_id,
        skill_name,
        skill_description,
        skill_version,
        package_path,
        package_size,
        package_sha256,
        user_uid,
        is_active
    )
    VALUES (
        p_skill_id,
        p_skill_name,
        p_skill_description,
        p_skill_version,
        p_package_path,
        p_package_size,
        p_package_sha256,
        p_user_uid,
        FALSE
    );

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS update_agent_skill;
DELIMITER $$

CREATE PROCEDURE update_agent_skill (
    IN p_skill_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_is_active BOOLEAN,
    IN p_deleted BOOLEAN
)
BEGIN

    UPDATE agent_skills
    SET
        is_active = COALESCE(p_is_active, is_active),
        deleted = COALESCE(p_deleted, deleted),
        deleted_at = IF(p_deleted = TRUE, NOW(), deleted_at)
    WHERE
        skill_id = p_skill_id
        AND user_uid = p_user_uid
        AND deleted = FALSE;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS fetch_agent_skills;
DELIMITER $$

CREATE PROCEDURE fetch_agent_skills (
    IN p_user_uid VARCHAR(64),
    IN p_limit INT
)
BEGIN

    SELECT
        skill_id,
        skill_name,
        skill_description,
        skill_version,
        package_path,
        package_size,
        is_active,
        upload_at
    FROM agent_skills
    WHERE
        user_uid = p_user_uid
        AND deleted = FALSE
    ORDER BY upload_at DESC
    LIMIT p_limit;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS fetch_target_skill;
DELIMITER $$

CREATE PROCEDURE fetch_target_skill (
    IN p_user_uid VARCHAR(64),
    IN p_skill_id VARCHAR(64)
)
BEGIN

    SELECT
        skill_id,
        skill_name,
        skill_description,
        skill_version,
        package_path,
        package_size,
        is_active,
        upload_at,
        deleted,
        deleted_at
    FROM agent_skills
    WHERE
        user_uid = p_user_uid
        AND skill_id = p_skill_id
        AND deleted = FALSE
    LIMIT 1;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS create_llm_provider;
DELIMITER $$

CREATE PROCEDURE create_llm_provider (
    IN p_provider_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_provider_name VARCHAR(64),
    IN p_type ENUM('openai', 'anthropic'),
    IN p_endpoint VARCHAR(256),
    IN p_model_list JSON,
    IN p_description TEXT
)
BEGIN
    INSERT INTO llm_provider (
        provider_id,
        user_uid,
        provider_name,
        type,
        endpoint,
        model_list,
        description
    )
    VALUES (
        p_provider_id,
        p_user_uid,
        p_provider_name,
        IFNULL(p_type, 'openai'),
        p_endpoint,
        p_model_list,
        p_description
    );
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_llm_providers;
DELIMITER $$

CREATE PROCEDURE get_llm_providers (
    IN p_user_uid VARCHAR(64)
)
BEGIN
    SELECT
        provider_id,
        provider_name,
        type,
        endpoint,
        model_list,
        description,
        created_at
    FROM llm_provider
    WHERE user_uid = p_user_uid
      AND is_deleted = FALSE
    ORDER BY created_at DESC;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_llm_provider_by_id;
DELIMITER $$

CREATE PROCEDURE get_llm_provider_by_id (
    IN p_provider_id VARCHAR(64)
)
BEGIN
    SELECT
        provider_id,
        provider_name,
        type,
        endpoint,
        model_list,
        description,
        created_at
    FROM llm_provider
    WHERE provider_id = p_provider_id
      AND is_deleted = FALSE
    LIMIT 1;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS update_llm_provider;
DELIMITER $$

CREATE PROCEDURE update_llm_provider (
    IN p_provider_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_provider_name VARCHAR(64),
    IN p_type ENUM('openai', 'anthropic'),
    IN p_endpoint VARCHAR(256),
    IN p_model_list JSON,
    IN p_description TEXT,
    IN p_is_deleted BOOLEAN
)
BEGIN
    UPDATE llm_provider
    SET
        provider_name = IF(p_provider_name IS NULL, provider_name, p_provider_name),
        type = IF(p_type IS NULL, type, p_type),
        endpoint = IF(p_endpoint IS NULL, endpoint, p_endpoint),
        model_list = IF(p_model_list IS NULL, model_list, p_model_list),
        description = IF(p_description IS NULL, description, p_description),
        is_deleted = IF(p_is_deleted IS NULL, is_deleted, p_is_deleted)
    WHERE provider_id = p_provider_id
      AND user_uid = p_user_uid
      AND is_deleted = FALSE;

    SELECT ROW_COUNT() AS affected_rows;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS create_mcp_server;
DELIMITER $$

CREATE PROCEDURE create_mcp_server (
    IN p_mcp_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_mcp_name VARCHAR(64),
    IN p_transport ENUM(
        'stdio', 'http', 'streamable_http', 'websocket', 'sse'
    ),
    IN p_endpoint VARCHAR(512),
    IN p_config JSON,
    IN p_description TEXT
)
BEGIN

    INSERT INTO mcp_server (
        mcp_id,
        user_uid,
        mcp_name,
        transport,
        endpoint,
        config,
        description
    )
    VALUES (
        p_mcp_id,
        p_user_uid,
        p_mcp_name,
        p_transport,
        p_endpoint,
        p_config,
        p_description
    );

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_mcp_servers;
DELIMITER $$

CREATE PROCEDURE get_mcp_servers (
    IN p_user_uid VARCHAR(64)
)
BEGIN

    SELECT
        mcp_id,
        mcp_name,
        transport,
        endpoint,
        config,
        description,
        enabled,
        tool_count,
        created_at
    FROM mcp_server
    WHERE user_uid = p_user_uid
      AND is_deleted = FALSE
    ORDER BY created_at DESC;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_enabled_mcp_servers;
DELIMITER $$

CREATE PROCEDURE get_enabled_mcp_servers (
    IN p_user_uid VARCHAR(64)
)
BEGIN

    SELECT
        mcp_id,
        mcp_name,
        transport,
        endpoint,
        config
    FROM mcp_server
    WHERE user_uid = p_user_uid
      AND enabled = TRUE
      AND is_deleted = FALSE
    ORDER BY created_at ASC;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS update_mcp_server;
DELIMITER $$

CREATE PROCEDURE update_mcp_server (
    IN p_mcp_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_mcp_name VARCHAR(64),
    IN p_transport ENUM(
        'stdio', 'http', 'streamable_http', 'websocket', 'sse'
    ),
    IN p_endpoint VARCHAR(512),
    IN p_config JSON,
    IN p_description TEXT,
    IN p_enabled BOOLEAN,
    IN p_tool_count INT,
    IN p_is_deleted BOOLEAN
)
BEGIN

    UPDATE mcp_server
    SET
        mcp_name = IF(p_mcp_name IS NULL, mcp_name, p_mcp_name),
        transport = IF(p_transport IS NULL, transport, p_transport),
        endpoint = IF(p_endpoint IS NULL, endpoint, p_endpoint),
        config = IF(p_config IS NULL, config, p_config),
        description = IF(p_description IS NULL, description, p_description),
        enabled = IF(p_enabled IS NULL, enabled, p_enabled),
        tool_count = IF(p_tool_count IS NULL, tool_count, p_tool_count),
        is_deleted = IF(p_is_deleted IS NULL, is_deleted, p_is_deleted)
    WHERE mcp_id = p_mcp_id
      AND user_uid = p_user_uid
      AND is_deleted = FALSE;

    SELECT ROW_COUNT() AS affected_rows;

END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS create_cron_task;
DELIMITER $$

CREATE PROCEDURE create_cron_task (
    IN p_task_id VARCHAR(64),
    IN p_user_uid VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_platform VARCHAR(32),
    IN p_name VARCHAR(255),
    IN p_prompt TEXT,
    IN p_execute LONGTEXT,
    IN p_exec_time DATETIME,
    IN p_repeat ENUM('once', 'day', 'week', 'month', 'year', 'cron'),
    IN p_extra_config JSON,
    IN p_description TEXT
)
BEGIN
    INSERT INTO cron_task (
        task_id,
        user_uid,
        conversation_uid,
        platform,
        name,
        prompt,
        execute,
        exec_time,
        `repeat`,
        extra_config,
        description
    )
    VALUES (
        p_task_id,
        p_user_uid,
        p_conversation_uid,
        IFNULL(p_platform, 'default'),
        p_name,
        p_prompt,
        p_execute,
        p_exec_time,
        IFNULL(p_repeat, 'once'),
        p_extra_config,
        p_description
    );
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_cron_tasks;
DELIMITER $$

CREATE PROCEDURE get_cron_tasks (
    IN p_user_uid VARCHAR(64)
)
BEGIN
    SELECT
        task_id,
        conversation_uid,
        platform,
        name,
        prompt,
        execute,
        exec_time,
        `repeat`,
        extra_config,
        description,
        enabled,
        created_at,
        updated_at
    FROM cron_task
    WHERE user_uid = p_user_uid
      AND is_deleted = FALSE
    ORDER BY exec_time ASC;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_cron_task_by_id;
DELIMITER $$

CREATE PROCEDURE get_cron_task_by_id (
    IN p_task_id VARCHAR(64)
)
BEGIN
    SELECT
        task_id,
        user_uid,
        conversation_uid,
        platform,
        name,
        prompt,
        execute,
        exec_time,
        `repeat`,
        extra_config,
        description,
        enabled,
        created_at,
        updated_at
    FROM cron_task
    WHERE task_id = p_task_id
      AND is_deleted = FALSE
    LIMIT 1;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS get_all_enabled_cron_tasks;
DELIMITER $$

CREATE PROCEDURE get_all_enabled_cron_tasks ()
BEGIN
    SELECT
        task_id,
        user_uid,
        conversation_uid,
        platform,
        name,
        prompt,
        execute,
        exec_time,
        `repeat`,
        extra_config,
        description,
        created_at,
        updated_at
    FROM cron_task
    WHERE enabled = TRUE
      AND is_deleted = FALSE
    ORDER BY exec_time ASC;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS update_cron_task;
DELIMITER $$

CREATE PROCEDURE update_cron_task (
    IN p_task_id VARCHAR(64),
    IN p_conversation_uid VARCHAR(64),
    IN p_platform VARCHAR(32),

    IN p_name VARCHAR(255),
    IN p_prompt TEXT,
    IN p_execute LONGTEXT,
    IN p_exec_time DATETIME,
    IN p_repeat ENUM('once', 'day', 'week', 'month', 'year', 'cron'),
    IN p_extra_config JSON,
    IN p_description TEXT,
    IN p_enabled BOOLEAN,

    IN p_is_deleted BOOLEAN
)
BEGIN
    UPDATE cron_task
    SET
        conversation_uid = IF(p_conversation_uid IS NULL, conversation_uid, p_conversation_uid),
        platform = IF(p_platform IS NULL, platform, p_platform),
        name = IF(p_name IS NULL, name, p_name),
        prompt = IF(p_prompt IS NULL, prompt, p_prompt),
        execute = IF(p_execute IS NULL, execute, p_execute),
        exec_time = IF(p_exec_time IS NULL, exec_time, p_exec_time),
        `repeat` = IF(p_repeat IS NULL, `repeat`, p_repeat),
        extra_config = IF(p_extra_config IS NULL, extra_config, p_extra_config),
        description = IF(p_description IS NULL, description, p_description),
        enabled = IF(p_enabled IS NULL, enabled, p_enabled),
        is_deleted = IF(p_is_deleted IS NULL, is_deleted, p_is_deleted)
    WHERE task_id = p_task_id
      AND is_deleted = FALSE;

    SELECT ROW_COUNT() AS affected_rows;
END$$

DELIMITER ;



DROP PROCEDURE IF EXISTS list_all_tables;
DELIMITER $$

CREATE PROCEDURE list_all_tables()
BEGIN
    SELECT TABLE_NAME AS table_name
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_NAME;
END$$

DELIMITER ;
