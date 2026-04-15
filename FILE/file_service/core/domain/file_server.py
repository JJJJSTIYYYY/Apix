import hashlib
import json
from typing import Dict, Iterable, List, Tuple
import mimetypes
import os
import uuid
from pathlib import Path
import zipfile
import yaml

from langchain_core.documents import Document
from langchain_text_splitters import (
    HTMLHeaderTextSplitter,
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
    RecursiveJsonSplitter,
)

from core.commons.decorator import task_handler
from core.commons.logger import logger
from global_config import FILE_STORE_BASE_DIR


class FileService:
    """
    File system service.

    Responsibilities:
    - Persist uploaded file to local storage
    - Generate file_id
    - Provide access path
    """

    DOCUMENT_TYPE = {
        "txt",
        "json",
        "jsonl",
        "md",
        "markdown",
        "html",
        "htm",
        "cpp",
        "cc",
        "cxx",
        "go",
        "java",
        "kt",
        "kts",
        "js",
        "mjs",
        "cjs",
        "ts",
        "tsx",
        "php",
        "proto",
        "py",
        "rst",
        "rb",
        "rs",
        "scala",
        "sc",
        "swift",
        "tex",
        "sol",
        "cs",
        "cob",
        "cbl",
        "c",
        "h",
        "lua",
        "pl",
        "pm",
        "hs",
        "r",
        "ex",
        "exs",
        "ps1",
        "psm1",
        "bas",
        "cls",
        "frm",
        "vbs",
    }
    ZIP_ONLY = {"zip"}

    def __init__(self, base_dir: str):
        self._base_dir = base_dir

    # ==========================================================
    # Access Path
    # ==========================================================

    def generate_access_path(self, *, file_path: str = None) -> str:
        """
        Generate absolute file path.
        """

        if not file_path:
            raise ValueError("file_path is required")

        return str(Path(file_path).resolve())
    


    # ------------------------------------------------------------------
    # Splitter
    # ------------------------------------------------------------------

    def _get_language_from_extension(self, ext: str) -> Language | None:
        """
        Map file extension to LangChain Language enum.
        """
        mapping = {
            "cpp": Language.CPP,
            "cc": Language.CPP,
            "cxx": Language.CPP,
            "go": Language.GO,
            "java": Language.JAVA,
            "kt": Language.KOTLIN,
            "kts": Language.KOTLIN,
            "js": Language.JS,
            "mjs": Language.JS,
            "cjs": Language.JS,
            "ts": Language.TS,
            "tsx": Language.TS,
            "php": Language.PHP,
            "proto": Language.PROTO,
            "py": Language.PYTHON,
            "rst": Language.RST,
            "rb": Language.RUBY,
            "rs": Language.RUST,
            "scala": Language.SCALA,
            "sc": Language.SCALA,
            "swift": Language.SWIFT,
            "md": Language.MARKDOWN,
            "markdown": Language.MARKDOWN,
            "tex": Language.LATEX,
            "html": Language.HTML,
            "htm": Language.HTML,
            "sol": Language.SOL,
            "cs": Language.CSHARP,
            "cob": Language.COBOL,
            "cbl": Language.COBOL,
            "c": Language.C,
            "h": Language.C,
            "lua": Language.LUA,
            "pl": Language.PERL,
            "pm": Language.PERL,
            "hs": Language.HASKELL,
            "r": Language.R,
            "ex": Language.ELIXIR,
            "exs": Language.ELIXIR,
            "ps1": Language.POWERSHELL,
            "psm1": Language.POWERSHELL,
            "bas": Language.VISUALBASIC6,
            "cls": Language.VISUALBASIC6,
            "frm": Language.VISUALBASIC6,
            "vbs": Language.VISUALBASIC6,
        }
        return mapping.get(ext)

    def _read_text_with_fallback(self, path: Path) -> str:
        """
        Read text file with encoding fallback.
        """
        encodings = ["utf-8", "utf-8-sig", "gbk", "latin-1"]
        last_error = None

        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError as e:
                last_error = e

        raise UnicodeDecodeError(
            getattr(last_error, "encoding", "unknown"),
            getattr(last_error, "object", b""),
            getattr(last_error, "start", 0),
            getattr(last_error, "end", 0),
            f"failed to decode file with supported encodings: {encodings}",
        )


    def splitter_document(
        self,
        file_path: str,
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        strip_headers: bool = False,
    ) -> tuple[List[Document], str]:
        """
        Split a local document into LangChain Document chunks by file extension.

        Supported strategies:
        - Markdown: MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
        - JSON / JSONL: RecursiveJsonSplitter
        - HTML: HTMLHeaderTextSplitter + RecursiveCharacterTextSplitter
        - Code: RecursiveCharacterTextSplitter.from_language(...)
        - Fallback: RecursiveCharacterTextSplitter

        Args:
            file_path: local file path
            chunk_size: max chunk size for recursive splitters
            chunk_overlap: overlap size for recursive splitters
            strip_headers: whether to strip markdown headers from markdown chunks

        Returns:
            tuple[List[Document], str]:
                - documents
                - split_mode
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_path}")

        if not path.is_file():
            raise ValueError(f"not a file: {file_path}")

        ext = path.suffix.lower().lstrip(".")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # ------------------------------------------------------------------
        # Markdown
        # ------------------------------------------------------------------
        if ext in {"md", "markdown"}:
            content = self._read_text_with_fallback(path)
            split_mode = "markdown:header+recursive"

            headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
                ("####", "Header 4"),
            ]

            md_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=headers_to_split_on,
                strip_headers=strip_headers,
            )
            md_docs = md_splitter.split_text(content)
            docs = text_splitter.split_documents(md_docs)

            for doc in docs:
                doc.metadata = {
                    **(doc.metadata or {}),
                    "source": str(path),
                    "file_name": path.name,
                    "file_ext": ext,
                }

            return docs, split_mode

        # ------------------------------------------------------------------
        # JSON
        # ------------------------------------------------------------------
        if ext == "json":
            split_mode = "json:recursive"

            content = self._read_text_with_fallback(path)
            json_data = json.loads(content)

            json_splitter = RecursiveJsonSplitter(max_chunk_size=chunk_size)
            docs = json_splitter.create_documents(texts=[json_data])

            for doc in docs:
                doc.metadata = {
                    **(doc.metadata or {}),
                    "source": str(path),
                    "file_name": path.name,
                    "file_ext": ext,
                }

            return docs, split_mode

        # ------------------------------------------------------------------
        # JSONL
        # ------------------------------------------------------------------
        if ext == "jsonl":
            split_mode = "jsonl:recursive"
            docs: List[Document] = []
            json_splitter = RecursiveJsonSplitter(max_chunk_size=chunk_size)

            content = self._read_text_with_fallback(path)
            for line_no, line in enumerate(content.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue

                obj = json.loads(line)
                line_docs = json_splitter.create_documents(texts=[obj])

                for doc in line_docs:
                    doc.metadata = {
                        **(doc.metadata or {}),
                        "source": str(path),
                        "file_name": path.name,
                        "file_ext": ext,
                        "line_no": line_no,
                    }
                docs.extend(line_docs)

            return docs, split_mode

        # ------------------------------------------------------------------
        # HTML
        # ------------------------------------------------------------------
        if ext in {"html", "htm"}:
            content = self._read_text_with_fallback(path)

            headers_to_split_on = [
                ("h1", "Header 1"),
                ("h2", "Header 2"),
                ("h3", "Header 3"),
            ]

            html_splitter = HTMLHeaderTextSplitter(
                headers_to_split_on=headers_to_split_on,
            )
            html_docs = html_splitter.split_text(content)

            if html_docs:
                docs = text_splitter.split_documents(html_docs)
                split_mode = "html:header+recursive"
            else:
                docs = text_splitter.create_documents([content])
                split_mode = "html:recursive"

            for doc in docs:
                doc.metadata = {
                    **(doc.metadata or {}),
                    "source": str(path),
                    "file_name": path.name,
                    "file_ext": ext,
                }

            return docs, split_mode

        # ------------------------------------------------------------------
        # Code files
        # ------------------------------------------------------------------
        language = self._get_language_from_extension(ext)
        if language is not None:
            content = self._read_text_with_fallback(path)
            split_mode = f"code:{language.value}"

            code_splitter = RecursiveCharacterTextSplitter.from_language(
                language=language,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            docs = code_splitter.create_documents([content])

            for doc in docs:
                doc.metadata = {
                    **(doc.metadata or {}),
                    "source": str(path),
                    "file_name": path.name,
                    "file_ext": ext,
                    "language": language.value,
                }

            return docs, split_mode

        # ------------------------------------------------------------------
        # Fallback for plain text-like files
        # ------------------------------------------------------------------
        content = self._read_text_with_fallback(path)
        docs = text_splitter.create_documents([content])
        split_mode = "text:recursive"

        for doc in docs:
            doc.metadata = {
                **(doc.metadata or {}),
                "source": str(path),
                "file_name": path.name,
                "file_ext": ext,
            }

        return docs, split_mode

    # ==========================================================
    # Save Files
    # ==========================================================

    @task_handler("file.file.guard_file_type")
    def guard_file_type(self, payload: list[dict], allow_type: Iterable[str] | bool | None) -> dict:
        """
        Guard the file type by file extension.
        If a type is not allowed, it will not be contained in return value (filter).

        Args:
            payload: dict with format:
            [
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_path": file_path,
                    "file_size": size_bytes,
                    "file_type": mime_type,
                    "sha256": file_hash
                },
                ...
            ]
            allow_type: FileService.DOCUMENT_TYPE or FileService.ZIP_ONLY

        Return:
            {
                "success": True,
                "messages": [
                    {
                        "file_id": file_id,
                        "file_name": file_name,
                        "file_path": file_path,
                        "file_size": size_bytes,
                        "file_type": mime_type,
                        "sha256": file_hash
                    },
                    ...
                ],
            }
        """
        # Skip validation directly
        if allow_type is True or allow_type is None:
            return {
                "success": True,
                "messages": payload,
            }

        allow_ext = {ext.lower().lstrip(".") for ext in allow_type}
        result = []

        for item in payload:
            file_name = item.get("file_name", "")
            _, ext = os.path.splitext(file_name)
            ext = ext.lower().lstrip(".")

            if not ext:
                continue

            if ext in allow_ext:
                result.append(item)

        return {
            "success": True,
            "messages": result,
        }


    @task_handler("file.file.save_file")
    async def save_file(self, payload: dict) -> dict:
        """
        Save uploaded file to local filesystem using streaming.

        Return:
            {
                "success": True,
                "messages": [
                    {
                        "file_id": file_id,
                        "file_name": file_name,
                        "file_path": file_path,
                        "file_size": size_bytes,
                        "file_type": mime_type,
                        "sha256": file_hash
                    },
                    ...
                ],
            }
        """

        try:
            client_id: str = payload["client_id"]
            files = payload.get("files", [])

            file_info: list[dict] = []
            seen_hashes: set[str] = set()
            chunk_size = 1024 * 1024  # 1MB

            for upload_file in files:
                file_name = os.path.basename(upload_file.filename)
                file_id = uuid.uuid4().hex

                dir_path = os.path.join(self._base_dir, client_id, file_id)
                os.makedirs(dir_path, exist_ok=True)

                file_path = os.path.join(dir_path, file_name)

                hasher = hashlib.sha256()
                size_bytes = 0

                # ------------------------------------------------------------
                # Stream write + hash
                # ------------------------------------------------------------
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await upload_file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        hasher.update(chunk)
                        size_bytes += len(chunk)

                await upload_file.close()

                file_hash = hasher.hexdigest()

                # ------------------------------------------------------------
                # In-request deduplication
                # ------------------------------------------------------------
                if file_hash in seen_hashes:
                    logger.info(
                        "[FileService] duplicated skipped client_id=%s filename=%s",
                        client_id,
                        file_name
                    )

                    try:
                        os.remove(file_path)
                        os.rmdir(dir_path)
                    except Exception:
                        logger.warning(
                            "[FileService] cleanup failed: %s",
                            file_path
                        )
                    continue

                seen_hashes.add(file_hash)

                mime_type, _ = mimetypes.guess_type(file_name)
                if not mime_type:
                    _, mime_type = os.path.splitext(file_name)
                    mime_type = mime_type.lower().lstrip(".")

                # ------------------------------------------------------------
                # Build response
                # ------------------------------------------------------------
                file_info.append(
                    {
                        "file_id": file_id,
                        "file_name": file_name,
                        "file_path": file_path,
                        "file_size": size_bytes,
                        "file_type": mime_type,
                        "sha256": file_hash
                    }
                )

                logger.info(
                    "[FileService] saved client_id=%s file_id=%s path=%s",
                    client_id,
                    file_id,
                    file_path
                )

            return {
                "success": True,
                "messages": file_info,
            }

        except Exception as e:
            logger.exception("[FileService] save_file error: %s", e)
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # ==========================================================
    # Save Skills
    # ==========================================================

    @task_handler("file.file.handle_skill_package")
    async def handle_skill_package(self, payload: dict) -> dict:
        """
        Analysis and save uploaded skill zip files to local filesystem using streaming.
        Anthropic skill spec:
            skill package must contain SKILL.md with YAML frontmatter.

        Args:
            payload = {
                "client_id": str,
                "files": [UploadFile, ...]
            }

        Return:
            {
                "success": bool,
                "client_id": str,
                "messages": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "package_sha256": str
                    }
                ]
            }
        """

        logger.info("[FileService][handle_skill_package] enter.")

        try:
            client_id: str = payload["client_id"]
            files = payload.get("files", [])

            skills_info = []
            seen_hashes: set[str] = set()

            chunk_size = 1024 * 1024  # 1MB

            for upload_file in files:

                file_name = os.path.basename(upload_file.filename)

                if not file_name.endswith(".zip"):
                    raise ValueError(f"skill package must be zip: {file_name}")

                package_id = uuid.uuid4().hex

                dir_path = os.path.join(self._base_dir, "skills", client_id, package_id)
                os.makedirs(dir_path, exist_ok=True)

                file_path = os.path.join(dir_path, file_name)

                hasher = hashlib.sha256()
                size_bytes = 0

                # ------------------------------------------------
                # Stream save zip
                # ------------------------------------------------
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await upload_file.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        hasher.update(chunk)
                        size_bytes += len(chunk)

                await upload_file.close()

                package_hash = hasher.hexdigest()

                # ------------------------------------------------
                # request-level dedup
                # ------------------------------------------------
                if package_hash in seen_hashes:
                    logger.info("[FileService] duplicated skill skipped: %s", file_name)

                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

                    continue

                seen_hashes.add(package_hash)

                # ------------------------------------------------
                # parse SKILL.md (Anthropic spec)
                # ------------------------------------------------
                try:
                    with zipfile.ZipFile(file_path, "r") as zf:

                        # find SKILL.md (may be nested)
                        skill_md_path = None
                        for name in zf.namelist():
                            if name.endswith("SKILL.md"):
                                skill_md_path = name
                                break

                        if not skill_md_path:
                            raise ValueError("SKILL.md missing in skill package")

                        skill_md = zf.read(skill_md_path).decode("utf-8")

                    # ------------------------------------------------
                    # parse YAML frontmatter
                    # ------------------------------------------------
                    if not skill_md.startswith("---"):
                        raise ValueError("SKILL.md missing YAML frontmatter")

                    parts = skill_md.split("---", 2)

                    if len(parts) < 3:
                        raise ValueError("Invalid SKILL.md frontmatter format")

                    meta_yaml = parts[1]

                    meta = yaml.safe_load(meta_yaml)

                    skill_name = meta.get("name")
                    skill_description = meta.get("description")

                    if not skill_name or not skill_description:
                        raise ValueError("skill name/description missing")

                    # Anthropic spec doesn't enforce version
                    skill_version = meta.get("version", "v1.0")

                except Exception as e:
                    logger.error("[FileService] skill package invalid: %s", e)
                    raise ValueError(f"Invalid skill package {file_name}: {e}")

                # ------------------------------------------------
                # deterministic skill_id
                # ------------------------------------------------
                skill_id = package_id

                access_path = self.generate_access_path(file_path=file_path)

                # ------------------------------------------------
                # build response
                # ------------------------------------------------
                skills_info.append(
                    {
                        "skill_id": skill_id,
                        "skill_name": skill_name,
                        "skill_description": skill_description,
                        "skill_version": skill_version,
                        "package_path": access_path,
                        "package_size": size_bytes,
                        "package_sha256": package_hash,
                    }
                )

                logger.info(
                    "[FileService] skill saved client_id=%s skill=%s",
                    client_id,
                    skill_name,
                )

            return {
                "success": True,
                "client_id": client_id,
                "messages": skills_info,
            }

        except Exception as e:
            logger.exception("[FileService] handle_skill_package error: %s", e)

            return {
                "success": False,
                "messages": f"fail: {e}",
            }



file_server = FileService(FILE_STORE_BASE_DIR)