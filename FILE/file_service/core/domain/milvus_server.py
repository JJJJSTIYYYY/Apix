import inspect
from typing import Callable, Dict, List, Union

from langchain_core.documents import Document
from langchain_milvus import Milvus
from pymilvus import MilvusClient

from core.commons.decorator import task_handler
from core.commons.logger import logger
from core.embedding_models import get_embed_model
from global_config import (
    COLLECTION_NAME,
    MILVUS_DOCKER_BASE_URI,
    MILVUS_TOKEN,
)


class MilvusService:
    """
    Milvus service for vector storage and similarity search.

    Design:
    - Single Milvus collection
    - Multi-tenant isolation by partition key: user_id
    - Additional logical filtering by provider / model / document_id
    - No embedding or store cache (stateless & concurrency-safe)
    """

    def __init__(
        self,
        uri: str,
        token: str = "root:Milvus",
        collection_name: str = "rag_documents",
    ):
        self._uri = uri
        self._token = token
        self._collection_name = collection_name

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_store(
        self,
        *,
        provider: str,
        model: str | None,
        api_key: str,
        extra_config: dict | None = None,
    ) -> Milvus:
        """
        Create a Milvus wrapper with a fresh embedding function.
        Always points to the same collection.
        """
        if model is None: 
            embedding = None
        else:
            embedding = get_embed_model(
                provider=provider,
                model=model,
                api_key=api_key,
                extra_config=extra_config,
            )

        return Milvus(
            embedding_function=embedding,
            collection_name=self._collection_name,
            connection_args={
                "uri": self._uri,
                "token": self._token,
            },
            index_params={
                "index_type": "FLAT",
                "metric_type": "L2",
            },
            partition_key_field="user_id",
        )

    def _create_milvus_client(self) -> MilvusClient:
        """
        Create a raw Milvus client for CRUD operations such as delete.
        """
        return MilvusClient(
            uri=self._uri,
            token=self._token,
        )

    @staticmethod
    def _build_filter(
        *,
        user_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        document_id: Union[str, List[str], None] = None,
        split_mode: str | None = None,
    ) -> str:
        clauses: List[str] = []

        # Helper to safely quote string values
        def quote(val: str) -> str:
            # Basic escape for double quotes
            return val.replace('"', '\\"')

        if user_id is not None:
            clauses.append(f'user_id == "{quote(user_id)}"')

        if provider is not None:
            clauses.append(f'provider == "{quote(provider)}"')

        if model is not None:
            clauses.append(f'model == "{quote(model)}"')

        if document_id:
            if isinstance(document_id, list):
                ids = ", ".join([f'"{quote(d)}"' for d in document_id])
                clauses.append(f'document_id in [{ids}]')
            else:
                clauses.append(f'document_id == "{quote(document_id)}"')

        if split_mode is not None:
            clauses.append(f'split_mode == "{quote(split_mode)}"')

        return " && ".join(clauses) if clauses else ""

    # ------------------------------------------------------------------
    # Handler Export
    # ------------------------------------------------------------------

    def export_handlers(self) -> Dict[str, Callable]:
        handlers: Dict[str, Callable] = {}

        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue

            attr = getattr(self, attr_name)
            if not callable(attr):
                continue

            task_name = getattr(attr, "_handler_name", None)
            if not task_name:
                continue

            if not inspect.iscoroutinefunction(attr):
                raise TypeError(
                    f"[MilvusService][export_handlers] "
                    f"Task handler '{task_name}' must be async function"
                )

            handlers[task_name] = attr

        return handlers

    # ------------------------------------------------------------------
    # Vector Operations
    # ------------------------------------------------------------------

    @task_handler("milvus.file.insert_chunks")
    async def insert_file_chunks(self, payload: dict) -> dict:
        """
        Insert pre-split file chunks into Milvus.

        Expected payload:
        - client_id: str
        - document_id: str
        - provider: str
        - model: str
        - api_key: str
        - extra_config: dict | None
        - chunks: List[Document]
        - split_mode: str
        """
        logger.info("[MilvusService][insert_file_chunks] enter.")

        try:
            user_id = payload["client_id"]
            document_id = payload["document_id"]
            provider = payload["provider"]
            model = payload["model"]
            chunks: List[Document] = payload["chunks"]
            split_mode: str = payload["split_mode"]

            store = self._create_store(
                provider=provider,
                model=model,
                api_key=payload["api_key"],
                extra_config=payload.get("extra_config"),
            )

            documents: List[Document] = []
            for doc in chunks:
                new_doc = Document(
                    page_content=doc.page_content,
                    metadata={
                        **(doc.metadata or {}),
                        "user_id": user_id,
                        "document_id": document_id,
                        "split_mode": split_mode,
                        "provider": provider,
                        "model": model,
                    },
                )
                documents.append(new_doc)

            await store.aadd_documents(documents)

            return {
                "success": True,
                "messages": f"inserted {len(documents)} chunks (mode={split_mode})",
            }

        except Exception as e:
            logger.exception(f"[MilvusService][insert_file_chunks] error: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("milvus.search")
    async def similarity_search(self, payload: dict) -> dict:
        """
        Run similarity search in Milvus with partition-based tenant isolation.

        Expected payload:
        - client_id: str
        - document_id: str
        - provider: str
        - model: str
        - api_key: str
        - extra_config: dict | None
        - query: str
        - top_k: int, optional
        """
        logger.info("[MilvusService][similarity_search] enter.")

        try:
            user_id = payload["client_id"]
            document_id = payload["document_id"]
            provider = payload["provider"]
            model = payload["model"]
            query = payload["query"]
            top_k = payload.get("top_k", 5)

            store = self._create_store(
                provider=provider,
                model=model,
                api_key=payload["api_key"],
                extra_config=payload.get("extra_config"),
            )

            filter_expr = self._build_filter(
                user_id=user_id,
                provider=provider,
                model=model,
                document_id=document_id,
            )

            results = await store.asimilarity_search_with_score(
                query=query,
                k=top_k,
                expr=filter_expr,
            )

            return {
                "success": True,
                "messages": [
                    {
                        "text": doc.page_content,
                        "metadata": doc.metadata,
                        "score": score,
                    }
                    for doc, score in results if score < 1
                ],
            }

        except Exception as e:
            logger.exception(f"[MilvusService][similarity_search] error: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("milvus.file.delete")
    async def delete_file_vectors(self, payload: dict) -> dict:
        """
        Delete all vectors associated with a specific file.
        """
        logger.info("[MilvusService][delete_file_vectors] enter.")

        try:
            user_id = payload["client_id"]
            document_id = payload["document_id"]

            client = self._create_milvus_client()

            filter_expr = self._build_filter(
                user_id=user_id,
                document_id=document_id,
            )

            result = client.delete(
                collection_name=self._collection_name,
                filter=filter_expr,
            )

            return {
                "success": True,
                "messages": f"vectors deleted: {result}",
            }

        except Exception as e:
            logger.exception(f"[MilvusService][delete_file_vectors] error: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }


milvus_server = MilvusService(
    uri=MILVUS_DOCKER_BASE_URI,
    token=MILVUS_TOKEN,
    collection_name=COLLECTION_NAME,
)