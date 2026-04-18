import os
import asyncio
import json
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import AIMessageChunk, ToolMessage, AIMessage

from apix_agent.global_config import BASE_DIR
from .context_process import ai_context_manager


class GeneratingCache:
    '''
    Append dialog history for sub_agent to local file system.
    '''

    def __init__(self):
        # Root directory for sub-agent histories
        self.history_root = Path(BASE_DIR) / "team_worker_history"
        self.history_root.mkdir(parents=True, exist_ok=True)

        # Async locks per history file
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_file_key(self, history_id: str, agent_name: str) -> str:
        """Generate unique lock key"""
        return f"{history_id}:{agent_name}"

    def _get_file_path(self, history_id: str, agent_name: str) -> Path:
        """Get history file path"""
        history_dir = self.history_root / history_id
        history_dir.mkdir(parents=True, exist_ok=True)

        return history_dir / f"{agent_name}.jsonl"

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock"""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]


    async def append_message(
        self,
        history_id: str,
        agent_name: str,
        generation_id: str,
        message: AIMessage | AIMessageChunk | ToolMessage,
        timestamp: int,
    ):
        """
        Append LangChain message to history.
        """

        key = self._get_file_key(history_id, agent_name)
        path = self._get_file_path(history_id, agent_name)
        lock = self._get_lock(key)

        msg_dict = ai_context_manager.create_dict_message(
            generation_id,
            message,
            timestamp,
        )

        if not msg_dict:
            return

        async with lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg_dict, ensure_ascii=False) + "\n")


    async def append_dict_message(
        self,
        history_id: str,
        agent_name: str,
        message_dict: dict,
    ):
        """
        Append pre-built dict message.
        """

        key = self._get_file_key(history_id, agent_name)
        path = self._get_file_path(history_id, agent_name)
        lock = self._get_lock(key)

        async with lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(message_dict, ensure_ascii=False) + "\n")


    async def load_history(
        self,
        history_id: str,
        agent_name: str,
    ) -> List[dict]:
        """
        Load full history for a sub-agent.
        """

        path = self._get_file_path(history_id, agent_name)

        if not path.exists():
            return []

        messages: List[dict] = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return messages


    async def rewrite_history(
        self,
        history_id: str,
        agent_name: str,
        messages: list[dict],
    ):
        """
        Atomically rewrite the entire history file.

        This method writes to a temporary file first and then
        replaces the original file atomically to avoid corruption
        in case of crash or interruption.
        """

        key = self._get_file_key(history_id, agent_name)
        path = self._get_file_path(history_id, agent_name)
        lock = self._get_lock(key)

        async with lock:

            tmp_path = path.with_suffix(".jsonl.tmp")

            # Write new content to temporary file
            with open(tmp_path, "w", encoding="utf-8") as f:
                for msg in messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")

                # Ensure data flushed to OS
                f.flush()

                # Ensure data flushed to disk
                os.fsync(f.fileno())

            # Atomic replace (POSIX guarantees atomicity)
            tmp_path.replace(path)


    async def clear_history(
        self,
        history_id: str,
        agent_name: str,
    ):
        """
        Delete history file for a sub-agent.
        """

        path = self._get_file_path(history_id, agent_name)

        if path.exists():
            path.unlink()



generating_cache = GeneratingCache()