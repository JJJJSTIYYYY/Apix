```json
// message struct
// msg_retuen is used to send ai message to client, include errors.
{
    "action": "msg_return",  
    "ts": 1737434471,
    "generation_id": "gen-123", // New selection for stream
    "data": {
        "client_id": "client_id",
        "history_id": "history_id",
        "messages": {
            "role": "ai",
            "content": "Hello! I see you're saying \"hello\". How can I help you today?",
            "think": "",
            "extra": {
                "...": "..."
            },
            "info": {
                "id": "123456",
                "model": "gpt-oss:120b-cloud",
                "total_tokens": 0,
                "model_provider": "ollama",
                "total_duration": "0ms"
            },
            "msg_cursor": 9,
            "created_at": "2026-01-21T10:21:10"
        }
    }
}

// tool_message is used to send the creation/updating/finishing of tool task.
{
    "action": "tool_return",  
    "ts": 1737499923,
    "generation_id": "gen-123", // New selection for stream
    "data": {
        "client_id": "client_id",
        "history_id": "history_id",
        "messages": {
            "role": "tools",
            "content": "",
            "think": "",
            "extra": {
                "...": "..."
            },
            "info": {
                "desc": "Sleep for 5 seconds and print random text",
                "status": "failed",
                "task_id": "14e64da2-e8a3-4223-987d-214a4a92ad41",
                "tool_name": "python_code_runner",
                "id": ""
            },
            "msg_cursor": -1,
            "created_at": "2026-01-21T05:40:12"
        }
    }
}

{
  "action": "msg_stream_start",
  "ts": 1737434479,
  "generation_id": "gen-123",
  "data": {
    "client_id": "client_id",
    "history_id": "history_id",
    "message": {}
  }
}

{
    "action": "think_chunk_rtn",
    "ts": 1737434479,
    "generation_id": "gen-123",
    "data": {
        "client_id": "client_id",
        "history_id": "session_id",
        "messages": {
            "role": "ai",
            "content": "",
            "think": "'think_chunk_rtn'",
            "extra": {},
            "info": {},
            "msg_cursor": null,
            "created_at": null,
        },
    },
}

{
    "action": "content_chunk_rtn",
    "ts": 1737434479,
    "generation_id": "gen-123",
    "data": {
        "client_id": "client_id",
        "history_id": "session_id",
        "messages": {
            "role": "ai",
            "content": "'content_chunk_rtn'",
            "think": "",
            "extra": {},
            "info": {},
            "msg_cursor": null,
            "created_at": null,
        },
    },
}

{
    "action": "info_chunk_rtn",
    "ts": 1737434479,
    "generation_id": "gen-123",
    "data": {
        "client_id": "client_id",
        "history_id": "session_id",
        "messages": {
            "role": "ai",
            "content": "",
            "think": "",
            "extra": {},
            "info": {
                "model": "model_name",
                "total_duration": "{(message.response_metadata.get('total_duration', 0) / 1_000_000_000):.3f}s",
                "model_provider": "model_provider",
                "total_tokens": 0,
                "id": "message.id",
            },
            "msg_cursor": null,
            "created_at": null,
        },
    },
}

{
  "action": "msg_stream_end",
  "ts": 1737434479,
  "generation_id": "gen-123",
  "data": {
    "client_id": "client_id",
    "history_id": "history_id",
    "reason": "think_end | content_end | graph_finish"
  }
}

// New struct for msg_abort is used to send the signal to indicate stream aborted, include errors.
{
  "action": "msg_stream_abort",
  "ts": 1737434475,
  "generation_id": "gen-123",
  "data": {
    "client_id": "client_id",
    "history_id": "history_id",
    "reason": "user_interrupt | error_occurred",
    "content": "Error detail"
  }
}

```


```json
"extra": { // Extra struct in messages. To expose binary data to multimodel. Please ensure selected model is supported.
    "image_data": [
        {
            "type": "image",
            "base64": "...",
            "mime_type": "...", // Required for base64 data (e.g., image/jpeg, image/png).
            "url": "...", // Provider should access.
        },
        // ...
    ],
    "audio_data": [
        {
            "type": "audio"
            "base64": "...",
            "mime_type": "...", // Required for base64 data (e.g., audio/mpeg, audio/wav).
            "url": "...", // Provider should access.
        },
        // ...
    ],
    "video_data": [ // Generic files (PDF, etc)
        {
            "type": "video"
            "base64": "...",
            "mime_type": "...", // Required for base64 data (e.g., video/mp4, video/webm).
            "url": "...", // Provider should access.
        },
        // ...
    ],
    "file_data": [
        {
            "type": "file"
            "base64": "...",
            "mime_type": "...", // Required for base64 data (e.g., application/pdf).
            "url": "...", // Provider should access.
        },
        // ...
    ]
}
```



```json

// longterm memory llm input (delta)
{
  "delta_messages": [
    {
      "role": "human",
      "content": "..."
    },
    {
      "role": "ai",
      "content": "..."
    },
    {
      "role": "human",
      "content": "..."
    }
  ],
  "existing_memory": [
    {
      "memory_id": "uuid4",
      "type": "factual | preference | instruction",
      "content": "..."
    }
  ]
}

// longterm memory llm output
{
  "updates": [
    {
      "action": "insert",
      "type": "factual | preference | instruction",
      "confidence": 0.82,
      "content": "..."
    },
    {
      "action": "modify",
      "target_id": "uuid4",
      "type": "factual | preference | instruction",
      "confidence": 0.75,
      "content": "..."
    },
    {
      "action": "deprecate",
      "target_id": "uuid4",
      "confidence": 0.6,
      "reason": "User explicitly contradicted this memory in the current conversation"
    }
  ]
}

// action convention prompt
// You are a memory auditor.
// You do NOT decide what to store.
// You only propose changes based strictly on delta_messages.

// Do not infer personality traits.
// Do not restate existing memory unless it is explicitly contradicted or refined.
// If a memory is questionable, propose deprecate instead of modify.

```