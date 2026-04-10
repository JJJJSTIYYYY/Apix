import os
import json
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    RecursiveJsonSplitter,
    HTMLHeaderTextSplitter,
    Language,
)

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
)

from core.commons.logger import logger


LANGUAGE_MAP = {
    # ------------------------------
    # Programming languages only
    # ------------------------------
    ".c": Language.C,
    ".cpp": Language.CPP,
    ".cs": Language.CSHARP,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".kt": Language.KOTLIN,
    ".py": Language.PYTHON,
    ".rs": Language.RUST,
    ".scala": Language.SCALA,
    ".swift": Language.SWIFT,

    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,

    ".php": Language.PHP,
    ".rb": Language.RUBY,
    ".lua": Language.LUA,
    ".pl": Language.PERL,
    ".ps1": Language.POWERSHELL,

    ".r": Language.R,
    ".hs": Language.HASKELL,
    ".ex": Language.ELIXIR,
    ".vb": Language.VISUALBASIC6,
    ".cbl": Language.COBOL,

    ".proto": Language.PROTO,
    ".sol": Language.SOL,
}


BINARY_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".ppt", ".pptx"
}


class TextSplitter:
    """
    Unified text splitter.

    Public API guarantees:
    - Always returns (chunks, split_mode)
    - Text-based split failures fallback to plain text
    - Binary files never fallback
    """

    def __init__(
        self,
        *,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._default_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self._markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
            ]
        )

        self._html_splitter = HTMLHeaderTextSplitter(
            headers_to_split_on=[
                ("h1", "h1"),
                ("h2", "h2"),
                ("h3", "h3"),
            ]
        )

        self._json_splitter = RecursiveJsonSplitter(
            max_chunk_size=chunk_size
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def split_file(self, file_path: str) -> Tuple[List[Document], str]:
        """
        Split file and return final chunks with the actual split mode used.
        """
        logger.info(f"[TextSplitter][split_file] enter: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        # Binary files: no fallback
        if ext in BINARY_EXTENSIONS:
            chunks = self._split_binary(file_path, ext)
            return chunks, ext.lstrip(".")

        # Text-based files with strong fallback
        try:
            if ext == ".txt":
                return self._split_plain_text(file_path), "text"

            if ext == ".json":
                return self._split_json(file_path), "json"

            if ext in [".md", ".markdown"]:
                return self._split_markdown(file_path), "markdown"

            if ext in [".html", ".htm"]:
                return self._split_html(file_path), "html"

            if ext in LANGUAGE_MAP:
                return self._split_code(file_path, ext), "code"

            raise ValueError(f"Unsupported text file type: {ext}")

        except Exception as e:
            logger.error(
                "[TextSplitter] split failed, fallback to plain text: "
                f"path={file_path}, err={e}"
            )
            chunks = self._split_plain_text_fallback(file_path)
            return chunks, "text_fallback"

    # --------------------------------------------------
    # Loaders
    # --------------------------------------------------

    def _load_text(self, file_path: str) -> List[Document]:
        """
        Load text file with encoding fallback.
        """
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            return loader.load()
        except UnicodeDecodeError:
            logger.warning(
                f"[TextSplitter] utf-8 decode failed, fallback latin-1: {file_path}"
            )
            loader = TextLoader(file_path, encoding="latin-1")
            return loader.load()

    # --------------------------------------------------
    # Text splitters
    # --------------------------------------------------

    def _split_markdown(self, file_path: str) -> List[Document]:
        docs = self._load_text(file_path)
        chunks: List[Document] = []

        for doc in docs:
            parts = self._markdown_splitter.split_text(doc.page_content)
            for part in parts:
                chunks.append(
                    Document(
                        page_content=part.page_content,
                        metadata={
                            **(doc.metadata or {}),
                            **(part.metadata or {}),
                        },
                    )
                )

        return self._attach_metadata(chunks, "markdown")

    def _split_html(self, file_path: str) -> List[Document]:
        docs = self._load_text(file_path)
        chunks: List[Document] = []

        for doc in docs:
            parts = self._html_splitter.split_text(doc.page_content)
            for part in parts:
                chunks.append(
                    Document(
                        page_content=part.page_content,
                        metadata={
                            **(doc.metadata or {}),
                            **(part.metadata or {}),
                        },
                    )
                )

        return self._attach_metadata(chunks, "html")

    def _split_json(self, file_path: str) -> List[Document]:
        docs = self._load_text(file_path)
        chunks: List[Document] = []

        for doc in docs:
            data = json.loads(doc.page_content)
            parts = self._json_splitter.split_text(data)
            for part in parts:
                chunks.append(
                    Document(
                        page_content=part,
                        metadata=doc.metadata,
                    )
                )

        return self._attach_metadata(chunks, "json")

    def _split_code(self, file_path: str, ext: str) -> List[Document]:
        language = LANGUAGE_MAP.get(ext)

        splitter = RecursiveCharacterTextSplitter.from_language(
            language=language,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        docs = self._load_text(file_path)
        chunks = splitter.split_documents(docs)

        for doc in chunks:
            doc.metadata = {
                **(doc.metadata or {}),
                "language": language.name.lower() if language else None,
            }

        return self._attach_metadata(chunks, "code")

    def _split_plain_text(self, file_path: str) -> List[Document]:
        docs = self._load_text(file_path)
        return self._split_documents(docs, "text")

    def _split_plain_text_fallback(self, file_path: str) -> List[Document]:
        """
        Fallback splitter for all failed text-based strategies.
        """
        docs = self._load_text(file_path)
        chunks = self._default_splitter.split_documents(docs)
        return self._attach_metadata(chunks, "text_fallback")

    # --------------------------------------------------
    # Binary splitters
    # --------------------------------------------------

    def _split_binary(self, file_path: str, ext: str) -> List[Document]:
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
            source_type = "pdf"
        elif ext in [".xlsx", ".xls"]:
            loader = UnstructuredExcelLoader(file_path)
            source_type = "excel"
        elif ext in [".ppt", ".pptx"]:
            loader = UnstructuredPowerPointLoader(file_path)
            source_type = "ppt"
        else:
            raise ValueError(f"Unsupported binary file type: {ext}")

        docs = loader.load()
        return self._split_documents(docs, source_type)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _split_documents(self, docs: List[Document], source_type: str) -> List[Document]:
        chunks = self._default_splitter.split_documents(docs)
        return self._attach_metadata(chunks, source_type)

    def _attach_metadata(self, chunks: List[Document], source_type: str) -> List[Document]:
        total = len(chunks)

        for idx, doc in enumerate(chunks):
            doc.metadata = {
                **(doc.metadata or {}),
                "source_type": source_type,
                "chunk_index": doc.metadata.get("chunk_index", idx),
                "chunk_total": doc.metadata.get("chunk_total", total),
            }

        return chunks
