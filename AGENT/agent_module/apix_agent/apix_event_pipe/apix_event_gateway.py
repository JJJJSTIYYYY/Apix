import asyncio
import copy
from pathlib import Path
import time
import traceback

import httpx

from apix_agent.apix_platform.register import PLATFORM_REGISTRY
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.agent import ai_agent
from apix_agent.apix_agent_core.generation_manager import generation_manager, GenerationManager
from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
from apix_agent.commons.type_def import AgentConfigSchema, ApixEntryDataSchema, ApixEventEnvelopeTarget, MainAgentState, MinimalEnvelopeData, ApixEventEnvelope, PlatformNotRegister, ProviderNotFound
from apix_agent.commons.file_content_reader import load_from_yaml, write_to_yaml
from apix_agent.global_config import BASE_DIR, BASE_URL, MEMORY_SERVICE_BASE_URL
from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter


# =========================
# Handler
# =========================
class ActionHandler:

    def __init__(self, gen_mgr: GenerationManager):
        self.gen_mgr = gen_mgr

        self.cached_config: AgentConfigSchema | None = None
        self._config_lock = asyncio.Lock()

    def _build_envelope(
        self,
        event: str,
        target: ApixEventEnvelopeTarget,
        data: MinimalEnvelopeData,
        generation_id: str,
    ) -> ApixEventEnvelope:
        return {
            "event": event,
            "target": target,
            "data": data,
            "generation_id": generation_id,
            "timestamp": time.time(),
        }
    
    async def _send_envelope(
        self,
        target: ApixEventEnvelopeTarget,
        envelope: ApixEventEnvelope = None
    ):
        """
        Dispatch envelope to different platform senders.

        - default → websocket
        - extensible via @send_interface
        """

        if not envelope:
            return
        
        client_id = target.get("id")
        platform = target.get("platform")
        sender = PLATFORM_REGISTRY.get(platform)

        if not sender:
            raise PlatformNotRegister(platform=platform)

        await sender.send(client_id, envelope)

    async def _ensure_config(self, config: AgentConfigSchema) -> AgentConfigSchema:
        """
        Ensure config is merged into cache (deep merge) and persisted if changed.

        Behavior:
            - Lazy load yaml cache
            - Deep merge new config into cached_config
            - Only write to file when actual change happens
            - Thread-safe (async lock)
        """
        # Parse config first
        if config.get("models_provider") == 'custom':
            provider_id = config.get("custom_provider_id", "")

            response = httpx.post(
                f"{MEMORY_SERVICE_BASE_URL}/provider/get_llm_provider_by_id",
                json={
                    "provider_id": provider_id,
                },
            )
            response.raise_for_status()
            provider_metas = response.json().get("messages", []) or []
            logger.info(f"[get_models_list]: Custom provider meta: {provider_metas}")
            if provider_metas:
                provider_meta = provider_metas[0]
            else:
                raise ProviderNotFound(provider=provider_id)
            
            provider = 'custom-' + (provider_meta.get("type", "openai") or "openai") + '-' + provider_id
            endpoint = provider_meta.get("endpoint", "")
            config["models_provider"] = provider
            BASE_URL[provider] = endpoint or ""

        cache_file_path = Path(BASE_DIR) / "running_cache" / "config_cache.yaml"

        async with self._config_lock:
            if self.cached_config is None:
                self.cached_config = load_from_yaml(cache_file_path) or {}

            old_config = copy.deepcopy(self.cached_config)

            # Inline deep merge
            stack = [(self.cached_config, config)]

            while stack:
                base, updates = stack.pop()

                for k, v in updates.items():
                    if isinstance(v, dict) and isinstance(base.get(k), dict):
                        stack.append((base[k], v))
                    else:
                        base[k] = copy.deepcopy(v)

            if self.cached_config != old_config and (self.cached_config.get("auto_save_config", False) or not old_config):
                await asyncio.to_thread(
                    write_to_yaml,
                    cache_file_path,
                    self.cached_config
                )

        # Ensure base_url exists (lazy restore for custom provider)
        provider = self.cached_config.get("models_provider", "")

        if (
            isinstance(provider, str)
            and provider.startswith("custom-")
            and BASE_URL.get(provider) is None
        ):
            try:
                _, p_type, p_id = provider.split('-', 2)

                response = httpx.post(
                    f"{MEMORY_SERVICE_BASE_URL}/provider/get_llm_provider_by_id",
                    json={
                        "provider_id": p_id,
                    },
                )
                response.raise_for_status()

                provider_metas = response.json().get("messages", []) or []
                logger.info(f"[ensure_config]: restore custom provider meta: {provider_metas}")

                if not provider_metas:
                    raise ProviderNotFound(provider=p_id)

                provider_meta = provider_metas[0]
                endpoint = provider_meta.get("endpoint", "")

                # Restore BASE_URL mapping
                BASE_URL[provider] = endpoint or ""

            except Exception as e:
                logger.error(f"[ensure_config]: failed to restore BASE_URL for {provider}: {e}")
                raise

        return self.cached_config
        

    async def chat_with_llm(self, payload: ApixEntryDataSchema):
        logger.trace('[ActionHandler] chat_with_llm Enter')

        data = payload.get("data") or {}
        client_id = data.get("client_id")
        session_id = data.get("session_id", "")
        history_id = data.get("history_id", "")
        platform = data.get("platform", "")
        target: ApixEventEnvelopeTarget = {
            "id": client_id,
            "platform": platform,
            "conversation_id": history_id,
        }

        try:
            generation_id = await generation_manager.create_generation(client_id, history_id, platform)
        except Exception as e:
            logger.error(f"[chat_with_llm] create_generation failed client={client_id}: {e}")

        gen = self.gen_mgr.get_generation(client_id, generation_id)
        if not gen:
            logger.error(f"[chat_with_llm] Please create a generation first. client_id={client_id}, generation_id={generation_id}")
            return

        try:
            message = data.get("messages", {})
            re_generate = data.get("re_generate", False)
            config = await self._ensure_config(data.get("config", {}) or {})
            work_dir = config.get("work_dir", "")

            enable_agent_assign = bool(config.get("enable_agent_assign", False))
            enable_agent_swarm = bool(config.get("enable_agent_swarm", False))
            agent_role = "agent"
            if enable_agent_assign:
                agent_role = "main_agent"
            if enable_agent_swarm:
                agent_role = "team_leader"

            if not isinstance(message, dict):
                class_name = type(message).__name__
                raise ValueError(f"[chat_with_llm] Unexpected data type: message is {class_name}, expected dict.")

            timestamp = int(time.time() * 1000)
            initial_state: MainAgentState = {
                "agent_name": "APIX",
                "agent_role": agent_role,
                "client_id": client_id,
                "session_id": session_id,
                "history_id": history_id,
                "target": target,
                "node_id": generation_id[-12:] + "-apix",
                "generation_id": generation_id,
                "config": config,
                "timestamp": timestamp,
                "input": message,
                "re_generate": re_generate,
                "messages": [],
                "current_tool_calls": [],
                "longterm_memory": None,
                "shortterm_memory": "",
                "rule_prompt": None,
                "runtime_prompt": None,
                "llm_calls": 0,
                "sandbox": '',
                "todos": [],
                "memorandum": [],
                "skills": [],
                "loaded_skills_cache": [],
                "documents": [],
                "llm_retry_count": 0,
                "context_compress_level": 0,
                "context_fold_split_mark": [],
                "error": "",
                "error_detail": ""
            }

            agent = await ai_agent.submit_agent_task(agent_role, "APIX", config)
            astream = agent.astream(initial_state, {"recursion_limit": 1024}, stream_mode="custom")

            async for achunk in astream:
                # achunk is already an ApixEventEnvelope.
                chunk_event = achunk.get("data") or {}
                action = chunk_event.get("event_name")

                if action == 'parent_id_return':
                    content = chunk_event.get("content")
                    gen.parent_node_id = content

                    # Getting the parent node id means a agent stream start.
                    envelop = self._build_envelope(
                        event="msg_stream_start",
                        target=target,
                        data={
                            "event_name": "msg_stream_start",
                            "content": {
                                "node_id": generation_id[-12:] + "-apix",
                                "parent_id": content
                            }
                        },
                        generation_id=generation_id,
                    )
                    await self._send_envelope(target, envelop)

                if await self.gen_mgr.is_generation_aborted(client_id, generation_id):
                    await astream.aclose()
                    envelop = self._build_envelope(
                        event="msg_stream_abort",
                        target=target,
                        data={
                            "event_name": "msg_stream_abort",
                            "content": ""
                        },
                        generation_id=generation_id,
                    )
                    await self._send_envelope(target, envelop)
                    logger.warning(f"[chat_with_llm] this generation has been aborted, generation_id = {generation_id}")
                    return

                await self.gen_mgr.update_cache_tokens(client_id, generation_id, achunk)
                await asyncio.sleep(0.06)
                await self._send_envelope(target, achunk)

            envelop = self._build_envelope(
                event="msg_stream_end",
                target=target,
                data={
                    "event_name": "msg_stream_end",
                    "content": None
                },
                generation_id=generation_id,
            )
            await self._send_envelope(target, envelop)
            gen.status = 'finished'

        except Exception as e:
            logger.error(f"[chat_with_llm error] {client_id}: {traceback.format_exc()}")

            if client_id:
                await self.gen_mgr.abort_generation(client_id, generation_id)

            envelop = self._build_envelope(
                event="msg_stream_abort",
                target=target,
                data={
                    "event_name": "msg_stream_abort",
                    "content": f"{e.__class__.__name__}: {str(e)}"
                },
                generation_id=generation_id,
            )
            await self._send_envelope(target, envelop)

        finally:
            await ai_agent.done(agent)
            await agent_sandbox.done(client_id=client_id, conversation_id=history_id, work_dir=work_dir)


    async def resolve_block(self, payload: ApixEntryDataSchema):
        logger.trace('[ActionHandler] resolve_block Enter')

        data = payload.get('data')
        block_id = data.get('block_id')
        message = data.get('messages')
        target: ApixEventEnvelopeTarget = {
            'id': data.get('client_id'),
            'platform': data.get('platform'),
            'conversation_id': data.get('history_id')
        }
        if not block_id: 
            raise ValueError(f"[abort_generation] Missing required fields in payload: {data}")
        
        AgentStreamWriter.resolve_block(target=target, block_id=block_id, result=message)


    async def abort_generation(self, payload: ApixEntryDataSchema):
        logger.trace('[ActionHandler] abort_generation Enter')

        data = payload.get("data") or {}
        client_id = data.get("client_id")
        history_id = data.get("history_id", "")
        platform = data.get("platform", "")

        if not client_id or not history_id or not platform:
            raise ValueError(f"[abort_generation] Missing required fields in payload: {data}")

        await generation_manager.abort_by_history_id(client_id, history_id, platform)



action_handler = ActionHandler(generation_manager)