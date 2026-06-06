from contextlib import asynccontextmanager
from dataclasses import dataclass
import os
import re
from typing import Iterable, Literal
import uuid
import aiohttp
import asyncio
from urllib.parse import urlparse
from pathlib import Path
import mimetypes

from requests.compat import unquote

from apix_agent.global_config import BASE_DIR, FILE_SERVICE_URL


@dataclass
class FileLockRecord:
    name: str
    event: Literal["create", "delete", "modify", "read", "move", ]
    released: asyncio.Event


class FileLockTimeoutError(TimeoutError):
    pass


class FileSystemManager:

    UNDELETABLE_IN_WORKSPACE = [".", "./agent_bus.log"]

    def __init__(self):
        # flie path -> (name, event)
        self.workspace_file_lock: dict[str, FileLockRecord] = {}
        self.file_lock_registry_lock = asyncio.Lock()
        # url -> downloaded local file path
        self.download_cache: dict[str, str] = {}
        # url -> in-flight future
        self.download_inflight: dict[str, asyncio.Future] = {}
        self.download_lock = asyncio.Lock()
        # workspace path in host -> undeletable path list in host
        self.undeletable_in_host: dict[str, set[Path]] = {}


    def is_undeletable(self, target: str | Path, sandbox_root: str, *, is_host_path = False) -> bool:
        sandbox_root = str(Path(sandbox_root).resolve())
        undeletable = self.undeletable_in_host.get(sandbox_root, None)
        if undeletable is None:
            undeletable = {
                self.get_file_path_in_host(
                    file_path=undel_in_workspace, 
                    container_workdir="/workspace",
                    host_root=sandbox_root,
                    must_exist=False
                ) 
                for undel_in_workspace in FileSystemManager.UNDELETABLE_IN_WORKSPACE
            }
            self.undeletable_in_host[sandbox_root] = undeletable

        host_path = self.get_file_path_in_host(file_path=target, container_workdir="/workspace", host_root=sandbox_root, must_exist=False) if not is_host_path else target
        return host_path in undeletable


    def is_url(self, path: str) -> bool:
        parsed = urlparse(path)
        return parsed.scheme in ("http", "https")
    
    
    async def download_resource_from_url(
        self,
        urls: str | list[str],
        *,
        to_folder: str = "download_cache",
        format_check: bool = True,
        timeout: int | float = 60,
    ) -> str | list[str]:
        """
        Download resource from URL.

        Features:
        - Supports single URL or URL list
        - BASE_DIR based storage
        - In-memory URL download cache
        - Concurrent de-duplication for same URL
        - Content-Disposition filename parsing
        - Content-Type extension guessing
        - Automatic filename generation
        - Duplicate filename avoidance
        - Timeout control

        Args:
            urls: A single URL or a list of URLs.
            to_folder: Destination folder for downloaded files.
            format_check: Whether to validate URL format before downloading.
            timeout: Total timeout in seconds for each request.

        Returns:
            A single file path if input is a single URL, otherwise a list of file paths.
        """

        is_single = isinstance(urls, str)
        if is_single:
            urls = [urls]

        if format_check:
            for url in urls:
                if not self.is_url(url):
                    raise ValueError(f"Invalid URL path: {url}")

        folder_path = os.path.join(BASE_DIR, to_folder)
        os.makedirs(folder_path, exist_ok=True)

        client_timeout = aiohttp.ClientTimeout(total=timeout)

        special_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "image/bmp": ".bmp",
            "image/tiff": ".tif",
            "image/x-icon": ".ico",
            "image/heic": ".heic",
            "image/heif": ".heif",
            "image/avif": ".avif",

            "text/plain": ".txt",
            "text/html": ".html",
            "text/css": ".css",
            "text/javascript": ".js",
            "text/markdown": ".md",
            "text/csv": ".csv",
            "text/xml": ".xml",

            "application/json": ".json",
            "application/ld+json": ".json",
            "application/pdf": ".pdf",
            "application/xml": ".xml",
            "application/zip": ".zip",
            "application/x-zip-compressed": ".zip",
            "application/gzip": ".gz",
            "application/x-tar": ".tar",
            "application/x-7z-compressed": ".7z",
            "application/x-rar-compressed": ".rar",

            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",

            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",

            "application/vnd.ms-powerpoint": ".ppt",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",

            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
            "audio/aac": ".aac",
            "audio/flac": ".flac",

            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "video/x-msvideo": ".avi",
            "video/quicktime": ".mov",
            "video/x-matroska": ".mkv",
            "video/mpeg": ".mpeg",

            "font/ttf": ".ttf",
            "font/otf": ".otf",
            "font/woff": ".woff",
            "font/woff2": ".woff2",
        }

        def guess_extension(content_type: str | None) -> str:
            if not content_type:
                return ""

            mime = content_type.split(";")[0].strip().lower()

            ext = special_map.get(mime)
            if ext:
                return ext

            return mimetypes.guess_extension(mime) or ""

        def parse_content_disposition(header: str | None) -> str | None:
            if not header:
                return None

            match = re.search(r'filename\*?="?([^";]+)"?', header)
            if match:
                return unquote(match.group(1).strip())

            return None

        def build_filename(url: str, resp: aiohttp.ClientResponse) -> str:
            cd = resp.headers.get("Content-Disposition")
            filename = parse_content_disposition(cd)

            if not filename:
                parsed = urlparse(url)
                filename = os.path.basename(unquote(parsed.path))

            if not filename:
                filename = f"download_{uuid.uuid4().hex}"

            name, ext = os.path.splitext(filename)

            if not ext:
                ext = guess_extension(resp.headers.get("Content-Type"))

            return f"{name}{ext}"

        def deduplicate_path(path: str) -> str:
            if not os.path.exists(path):
                return path

            folder, filename = os.path.split(path)
            stem, ext = os.path.splitext(filename)

            i = 1
            while True:
                candidate = os.path.join(folder, f"{stem}_{i}{ext}")
                if not os.path.exists(candidate):
                    return candidate
                i += 1

        async def _download(session: aiohttp.ClientSession, url: str) -> str:
            try:
                async with session.get(url) as resp:
                    resp.raise_for_status()

                    filename = build_filename(url, resp)
                    save_path = deduplicate_path(os.path.join(folder_path, filename))

                    with open(save_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)

                    return save_path

            except asyncio.TimeoutError as e:
                raise TimeoutError(f"Download timeout ({timeout}s): {url}") from e

            except aiohttp.ClientError as e:
                raise RuntimeError(f"Download failed: {url} ({e})") from e

        async def _get_or_download(session: aiohttp.ClientSession, url: str) -> str:
            existing_future: asyncio.Future | None = None
            my_future: asyncio.Future | None = None

            async with self.download_lock:
                cached_path = self.download_cache.get(url)
                if cached_path and os.path.exists(cached_path):
                    return cached_path

                existing_future = self.download_inflight.get(url)
                if existing_future is None:
                    loop = asyncio.get_running_loop()
                    my_future = loop.create_future()
                    self.download_inflight[url] = my_future
                else:
                    my_future = None

            if existing_future is not None:
                return await existing_future

            assert my_future is not None

            try:
                save_path = await _download(session, url)

                async with self.download_lock:
                    self.download_cache[url] = save_path
                    inflight = self.download_inflight.pop(url, None)
                    if inflight is not None and not inflight.done():
                        inflight.set_result(save_path)

                return save_path

            except Exception as e:
                async with self.download_lock:
                    inflight = self.download_inflight.pop(url, None)
                    if inflight is not None and not inflight.done():
                        inflight.set_exception(e)
                raise

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            tasks = [_get_or_download(session, url) for url in urls]
            results = await asyncio.gather(*tasks)

        return results[0] if is_single else results
        

    async def insert_files_to_file_service(
        self,
        client_id: str,
        file_paths: str | list[str] | Path | list[Path],
        *,
        timeout: int | float = 60,
    ) -> dict:
        """
        Upload one or more local files to file service.

        Args:
            client_id: client identifier required by file service.
            file_paths: local file path or list of local file paths.
            timeout: request timeout in seconds.

        Returns:
            dict: response json from file service.
        """
        if isinstance(file_paths, (str, Path)):
            file_paths = [file_paths]

        normalized_paths = [Path(p) for p in file_paths if p]
        if not normalized_paths:
            raise ValueError("No valid file paths provided.")

        for path in normalized_paths:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if not path.is_file():
                raise ValueError(f"Not a file: {path}")

        url = f"{FILE_SERVICE_URL}/file/file/insert_file"
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        form = aiohttp.FormData()
        form.add_field("client_id", client_id)

        opened_files = []
        try:
            for path in normalized_paths:
                f = open(path, "rb")
                opened_files.append(f)
                form.add_field(
                    "files",
                    f,
                    filename=path.name,
                    content_type="application/octet-stream",
                )

            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(url, data=form) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
                    if not result.get("success"):
                        raise RuntimeError(str(result.get("messages")))
                    return result.get("messages")

        except aiohttp.ClientError as e:
            raise RuntimeError(f"File service request failed: {e}") from e
        finally:
            for f in opened_files:
                try:
                    f.close()
                except Exception:
                    pass


    def get_file_path_in_host(
        self,
        *,
        file_path: str,
        container_workdir: str,
        host_root: str,
        must_exist: bool = True,
    ) -> Path:

        if not file_path:
            raise ValueError("Empty file path")

        container_root = Path(container_workdir).resolve()
        host_root = Path(host_root).resolve()

        p = Path(file_path)

        # Convert to container absolute path
        if p.is_absolute():
            container_path = p.resolve(strict=False)
        else:
            container_path = (container_root / p).resolve(strict=False)

        # Ensure container path is inside container root
        if not container_path.is_relative_to(container_root):
            raise PermissionError("No permission to access this file")

        # Map to host path
        relative_path = container_path.relative_to(container_root)
        host_path = (host_root / relative_path).resolve(strict=False)

        # Ensure host path is inside host root
        if not host_path.is_relative_to(host_root):
            raise PermissionError("No permission to access this file")

        # Ensure file exists
        if must_exist and not host_path.exists():
            raise FileNotFoundError("File not found or is empty")

        return host_path
    
    def get_file_path_in_container(
        self,
        *,
        file_path: str,
        container_workdir: str,
        host_root: str,
        must_exist: bool = True,
    ) -> Path:

        if not file_path:
            raise ValueError("Empty file path")

        container_root = Path(container_workdir).resolve()
        host_root = Path(host_root).resolve()

        p = Path(file_path)

        # Convert to host absolute path
        if p.is_absolute():
            host_path = p.resolve(strict=False)
        else:
            host_path = (host_root / p).resolve(strict=False)

        # Ensure host path is inside host root
        if not host_path.is_relative_to(host_root):
            raise PermissionError("No permission to access this file")

        # Map to container path
        relative_path = host_path.relative_to(host_root)
        container_path = (container_root / relative_path).resolve(strict=False)

        # Ensure container path is inside container root
        if not container_path.is_relative_to(container_root):
            raise PermissionError("No permission to access this file")

        # Ensure file exists
        if must_exist and not host_path.exists():
            raise FileNotFoundError("File not found or is empty")

        return container_path
    

    def _format_lock_record(self, locked_path: str, record: FileLockRecord) -> str:
        return (
            f"locked_path={locked_path}, "
            f"owner={record.name}, "
            f"event={record.event}"
        )

    def _build_lock_timeout_message(
        self,
        *,
        requested_path: str,
        requested_event: str | None,
        waited_seconds: float,
        conflict_type: str,
        conflict_path: str,
        conflict_record: FileLockRecord,
    ) -> str:
        return (
            f"Timed out waiting {waited_seconds:.2f}s for file lock. "
            f"requested_path={requested_path}, requested_event={requested_event}, "
            f"conflict_type={conflict_type}, "
            f"conflict_path={conflict_path}, "
            f"lock_owner={conflict_record.name}, "
            f"lock_event={conflict_record.event}"
        )


    def _normalize_lock_path(self, path: str | Path) -> str:
        return str(Path(path).resolve())

    def _is_same_or_parent(self, parent: str, child: str) -> bool:
        """
        Return True if parent == child, or parent is an ancestor of child.
        Both args must already be normalized absolute paths.
        """
        parent_path = Path(parent)
        child_path = Path(child)
        return parent_path == child_path or parent_path in child_path.parents

    def _find_descendant_conflict_unlocked(
        self,
        normalized_target_path: str,
    ) -> tuple[str, FileLockRecord] | None:
        """
        Find a locked path that is the target itself or a descendant of it.

        Must be called only while holding self.file_lock_registry_lock.
        """
        for locked_path, record in self.workspace_file_lock.items():
            if self._is_same_or_parent(normalized_target_path, locked_path):
                return locked_path, record
        return None

    def _find_ancestor_destructive_conflict_unlocked(
        self,
        normalized_target_path: str,
    ) -> tuple[str, FileLockRecord] | None:
        """
        Find a locked ancestor path whose event is delete/move.

        Must be called only while holding self.file_lock_registry_lock.
        """
        target = Path(normalized_target_path)
        for ancestor in (target, *target.parents):
            ancestor_str = str(ancestor)
            record = self.workspace_file_lock.get(ancestor_str)
            if record is not None and record.event in {"delete", "move"}:
                return ancestor_str, record
        return None

    async def lock_file(
        self,
        path: str,
        name: str,
        event: Literal["create", "delete", "modify", "read", "move"],
    ):
        """
        Lock a file or directory path.

        Rules:
        - exact same path cannot be locked twice
        - if any ancestor is locked for delete/move, no new lock may be acquired
        """
        normalized_path = self._normalize_lock_path(path)

        async with self.file_lock_registry_lock:
            ancestor_conflict = self._find_ancestor_destructive_conflict_unlocked(normalized_path)
            if ancestor_conflict is not None:
                locked_path, record = ancestor_conflict
                raise RuntimeError(
                    f"Cannot lock path: {normalized_path}. "
                    f"Ancestor path is locked for destructive operation: {locked_path} "
                    f"(owner={record.name}, event={record.event})"
                )

            record = self.workspace_file_lock.get(normalized_path)
            if record is not None:
                raise RuntimeError(
                    f"Path already locked: {normalized_path} "
                    f"(owner={record.name}, event={record.event})"
                )

            self.workspace_file_lock[normalized_path] = FileLockRecord(
                name=name,
                event=event,
                released=asyncio.Event(),
            )

    async def unlock_file(self, path: str):
        """
        Unlock a file or directory path and notify waiters.
        """
        normalized_path = self._normalize_lock_path(path)

        async with self.file_lock_registry_lock:
            record = self.workspace_file_lock.pop(normalized_path, None)

        if record is not None:
            record.released.set()

    async def get_file_lock(
        self,
        path: str,
        *,
        event: Literal["create", "delete", "modify", "read", "move"] | None = None,
        timeout: float = 30.0,
    ):
        """
        Wait until the path becomes operable.

        Behavior:
        - For delete/move:
        wait until neither the target path nor any descendant path is locked,
        and also until no ancestor path is locked for delete/move.
        - For other events (or event is None):
        wait until the exact path is unlocked,
        and also until no ancestor path is locked for delete/move.

        This blocks only the current coroutine, not the event loop.

        Raises:
            FileLockTimeoutError: if timeout is reached while waiting for lock release.
        """
        normalized_path = self._normalize_lock_path(path)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while True:
            async with self.file_lock_registry_lock:
                conflict_type: str | None = None
                conflict_path: str | None = None
                conflict_record: FileLockRecord | None = None
                released_event: asyncio.Event | None = None

                ancestor_conflict = self._find_ancestor_destructive_conflict_unlocked(normalized_path)
                if ancestor_conflict is not None:
                    conflict_type = "ancestor_destructive_lock"
                    conflict_path, conflict_record = ancestor_conflict
                    released_event = conflict_record.released

                elif event in {"delete", "move"}:
                    descendant_conflict = self._find_descendant_conflict_unlocked(normalized_path)
                    if descendant_conflict is None:
                        return
                    conflict_type = "descendant_lock"
                    conflict_path, conflict_record = descendant_conflict
                    released_event = conflict_record.released

                else:
                    record = self.workspace_file_lock.get(normalized_path)
                    if record is None:
                        return
                    conflict_type = "exact_path_lock"
                    conflict_path = normalized_path
                    conflict_record = record
                    released_event = record.released

            assert released_event is not None
            assert conflict_type is not None
            assert conflict_path is not None
            assert conflict_record is not None

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise FileLockTimeoutError(
                    self._build_lock_timeout_message(
                        requested_path=normalized_path,
                        requested_event=event,
                        waited_seconds=timeout,
                        conflict_type=conflict_type,
                        conflict_path=conflict_path,
                        conflict_record=conflict_record,
                    )
                )

            try:
                await asyncio.wait_for(released_event.wait(), timeout=remaining)
            except asyncio.TimeoutError as e:
                waited_seconds = timeout - max(deadline - loop.time(), 0.0)
                raise FileLockTimeoutError(
                    self._build_lock_timeout_message(
                        requested_path=normalized_path,
                        requested_event=event,
                        waited_seconds=waited_seconds,
                        conflict_type=conflict_type,
                        conflict_path=conflict_path,
                        conflict_record=conflict_record,
                    )
                ) from e

    async def get_file_lock_info(self, path: str) -> tuple[str, str] | None:
        normalized_path = self._normalize_lock_path(path)

        async with self.file_lock_registry_lock:
            record = self.workspace_file_lock.get(normalized_path)
            if record is None:
                return None
            return record.name, record.event

    async def is_file_locked(self, path: str) -> bool:
        normalized_path = self._normalize_lock_path(path)

        async with self.file_lock_registry_lock:
            return normalized_path in self.workspace_file_lock

    async def get_subtree_lock_info(
        self,
        path: str,
    ) -> list[tuple[str, str, str]]:
        """
        Return all locked paths under the target path, including itself.

        Returns:
            [(locked_path, name, event), ...]
        """
        normalized_path = self._normalize_lock_path(path)

        async with self.file_lock_registry_lock:
            result = []
            for locked_path, record in self.workspace_file_lock.items():
                if self._is_same_or_parent(normalized_path, locked_path):
                    result.append((locked_path, record.name, record.event))
            return result

    async def assert_path_operation_allowed(
        self,
        path: str,
        *,
        event: Literal["create", "delete", "modify", "read", "move"],
    ):
        """
        Raise if the requested operation is not currently allowed.

        Rules:
        - any event: blocked if any ancestor is locked for delete/move
        - delete/move: also blocked if target path itself or any descendant is locked
        - others: also blocked if exact path is locked
        """
        normalized_path = self._normalize_lock_path(path)

        async with self.file_lock_registry_lock:
            ancestor_conflict = self._find_ancestor_destructive_conflict_unlocked(normalized_path)
            if ancestor_conflict is not None:
                locked_path, record = ancestor_conflict
                raise RuntimeError(
                    f"Path operation blocked: {event} {normalized_path}. "
                    f"Ancestor path is locked for destructive operation: {locked_path} "
                    f"(owner={record.name}, event={record.event})"
                )

            if event in {"delete", "move"}:
                descendant_conflict = self._find_descendant_conflict_unlocked(normalized_path)
                if descendant_conflict is not None:
                    locked_path, record = descendant_conflict
                    raise RuntimeError(
                        f"Path operation blocked: {event} {normalized_path}. "
                        f"Locked descendant exists: {locked_path} "
                        f"(owner={record.name}, event={record.event})"
                    )
            else:
                record = self.workspace_file_lock.get(normalized_path)
                if record is not None:
                    raise RuntimeError(
                        f"Path operation blocked: {event} {normalized_path}. "
                        f"Path is locked by {record.name} for {record.event}"
                    )

    @asynccontextmanager
    async def file_lock(
        self,
        path: str,
        name: str,
        event: Literal["create", "delete", "modify", "read", "move"],
        *,
        timeout: float = 30.0,
    ):
        """
        Async context manager for path locking.

        Usage:
            async with file_system.file_lock(path, "agent", "read"):
                ...

            async with file_system.file_lock(path, "cleaner", "delete"):
                ...
        """
        await self.get_file_lock(path, event=event, timeout=timeout)
        await self.lock_file(path, name, event)

        try:
            yield
        finally:
            await self.unlock_file(path)


    @asynccontextmanager
    async def multi_file_lock(
        self,
        lock_items: Iterable[tuple[str | Path, Literal["create", "delete", "modify", "read", "move"]]],
        name: str,
        *,
        timeout: float = 30.0,
    ):
        """
        Acquire multiple path locks in a stable global order to avoid deadlocks.

        Args:
            lock_items: iterable of (path, event)
            name: lock owner name
            timeout: total timeout budget for acquiring all locks

        Usage:
            async with file_system.multi_file_lock(
                [
                    (source_host_path, "move"),
                    (target_host_path, "create"),
                ],
                "agent_name",
            ):
                ...
        """
        event_map: dict[str, Literal["create", "delete", "modify", "read", "move"]] = {}

        for raw_path, event in lock_items:
            normalized_path = self._normalize_lock_path(raw_path)

            existing_event = event_map.get(normalized_path)
            if existing_event is not None:
                if existing_event != event:
                    raise RuntimeError(
                        f"Conflicting lock request for same path: {normalized_path}. "
                        f"events=({existing_event}, {event}), owner={name}"
                    )
                continue

            event_map[normalized_path] = event

        normalized_items = sorted(event_map.items(), key=lambda x: x[0])

        acquired: list[str] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        try:
            for path, event in normalized_items:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise FileLockTimeoutError(
                        f"Timed out waiting {timeout:.2f}s for multi-file lock acquisition. "
                        f"current_path={path}, requested_event={event}, owner={name}"
                    )

                await self.get_file_lock(path, event=event, timeout=remaining)
                await self.lock_file(path, name, event)
                acquired.append(path)

            yield

        finally:
            for path in reversed(acquired):
                await self.unlock_file(path)


file_system = FileSystemManager()