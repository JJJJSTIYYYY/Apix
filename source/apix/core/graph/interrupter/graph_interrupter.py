# import asyncio
# import uuid

# from typing import Any, Optional

# from apix.common.type import ApixIdentity
# from apix.common.utils.logger import logger


# class GraphInterrupter:

#     # run_id -> block_id -> future
#     _blocking_futures: dict[str, dict[str, asyncio.Future]] = {}

#     # Public API
#     async def interrupt(
#         self,
#         *,
#         data: Any = None,
#         timeout: Optional[float] = None,
#     ) -> Any:
#         """
#         Send structured chunk while in graph loop and block the agent graph at the same time.
#         Can be called from inside any graph node.

#         Args:
#             chunk_type: Chunk type enum.
#             target: Chunk receiver.
#             data: Optional chunk data, should contains event_name and content at least if provided.
#             timeout: Optional timeout in seconds for the blocking wait. If None, wait indefinitely.
#         """

#         block_id = uuid.uuid4().hex

#         loop = asyncio.get_running_loop()
#         future = loop.create_future()

#         target_hash = self._target_hash(target)

#         if target_hash not in self._blocking_futures:
#             self._blocking_futures[target_hash] = {}

#         self._blocking_futures[target_hash][block_id] = future

#         data = data or {}
#         data["block_id"] = block_id

#         self._send_chunk(
#             chunk_type=chunk_type,
#             target=target,
#             data=data,
#             blocking=True,
#             block_id=block_id,
#         )

#         logger.warning(
#             f"Stream blocked. "
#             f"target={target_hash} "
#             f"block_id={block_id}"
#         )

#         try:
#             if timeout:
#                 result = await asyncio.wait_for(future, timeout)
#             else:
#                 result = await future

#             logger.success(
#                 f"Get result. "
#                 f"target={target_hash} "
#                 f"block_id={block_id}"
#             )

#             return result

#         finally:

#             target_futures = self._blocking_futures.get(target_hash)

#             if target_futures:
#                 target_futures.pop(block_id, None)

#                 # Auto cleanup empty target bucket
#                 if not target_futures:
#                     self._blocking_futures.pop(target_hash, None)

#     @classmethod
#     def resolve_block(
#         cls,
#         *,
#         target: ApixIdentity,
#         block_id: str,
#         result: Any = None,
#     ) -> bool:
#         """
#         Resolve blocking event by target + block_id.
#         """

#         target_hash = cls._target_hash(target)

#         future = (
#             cls._blocking_futures
#             .get(target_hash, {})
#             .get(block_id)
#         )

#         if not future:
#             return False

#         if future.done():
#             return False

#         future.set_result(result)

#         return True

#     @classmethod
#     def cancel_block(
#         cls,
#         *,
#         target: ApixIdentity,
#         block_id: str,
#     ) -> bool:
#         """
#         Release blocking future with None result.

#         Semantic:
#         - blocking wait ends
#         - no result received
#         - coroutine continues execution
#         """

#         target_hash = cls._target_hash(target)

#         future = (
#             cls._blocking_futures
#             .get(target_hash, {})
#             .get(block_id)
#         )

#         if not future:
#             return False

#         if future.done():
#             return False

#         # Continue execution with empty result
#         future.set_result(None)

#         return True

#     @classmethod
#     def clear_all_block(
#         cls,
#         target: ApixIdentity,
#     ) -> int:
#         """
#         Release all blocking futures with None result.

#         Returns:
#             int: released future count
#         """

#         target_hash = cls._target_hash(target)

#         logger.warning(
#             f"Clear block... "
#             f"target={target_hash} "
#         )

#         target_futures = cls._blocking_futures.get(target_hash)

#         if not target_futures:
#             return 0

#         cleared_count = 0

#         for future in target_futures.values():

#             if future.done():
#                 continue

#             # Continue execution with empty result
#             future.set_result(None)

#             cleared_count += 1

#         cls._blocking_futures.pop(target_hash, None)

#         logger.warning(
#             f"Released {cleared_count} blocking futures "
#             f"for target={target_hash}"
#         )

#         return cleared_count