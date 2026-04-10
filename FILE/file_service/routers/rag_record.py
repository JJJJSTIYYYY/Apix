from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.domain.data_server_manager import data_server_manager as dsm
from core.commons.logger import logger


router = APIRouter(tags=["rag_record"])


@router.post("/file/rag/embed_document")
async def embed_document(req: Request):
    """
    Embed a document.

    Behavior:
    - Query document's info from MySQL.
    - If not embeded, embed and store into milvus.
    - Update document's embedding model to MySQL.

    Request Body (JSON):
        {
            "client_id": str,
            "document_id": str,
            "selected_embed_model": str,
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][embed_document] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="embed_document",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )


@router.post("/file/rag/insert_document")
async def insert_document(
    client_id: str = Form(...),
    files: list[UploadFile] = File(...)
):
    """
    Append uploaded file metadata to MySQL.

    Behavior:
    - Receive files via multipart/form-data.
    - Stream file content to local filesystem (chunked, no full in-memory buffering).
    - Persist file metadata (path, size, type) to MySQL.

    Request:
        Content-Type:
            multipart/form-data

        Form Fields:
            client_id (str):
                Client identifier.

        Files:
            files (UploadFile[]):
                One or more files to upload.
                Multiple files must use the same form field name: "files".

    Example (curl):
        curl -X POST /file/rag/insert_document \\
            -F "client_id=xxx" \\
            -F "description=xxx" \\
            -F "files=@a.pdf" \\
            -F "files=@b.docx"

    Notes:
        - JSON request body is NOT supported.
        - Base64-encoded file data is NOT supported.
        - Files are streamed to disk and never fully loaded into memory.

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "document_id": str,
                    "document_name": str,
                },
                ...
            ]
        }
    """
    logger.info("[API][insert_document] enter.")
    logger.info(f"[API][insert_document] client_id={client_id}, files={len(files)}")

    query_id = await dsm.submit_query(
        action="insert_document",
        payload={
            "client_id": client_id,
            "description": "",
            "files": files,
        },
    )

    result = await dsm.wait_result(query_id)

    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )


@router.post("/file/rag/update_document")
async def update_document(req: Request):
    """
    Update document info in mysql.

    Behavior:
    - Update document's delete / active status / description to MySQL.

    Request Body (JSON):
        {
            "client_id": str,
            "document_id": str,
            "selected_embed_model": str,
            "description": str | None,
            "embed_engine": list | None,
            "is_active": bool | None,
            "deleted": bool | None,
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][update_document] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="update_document",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )


@router.post("/file/rag/get_available_documents")
async def get_available_documents(req: Request):
    """
    Get documents info from mysql.
    Return document metadata list.
    Binary document file is not included.

    Behavior:
    - Fetch documents info from MySQL.

    Request Body (JSON):
        {
            "client_id": str,
            "limit": int, // Optional, default 5.
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "document_id": str,
                    "document_name": str,
                    "document_description": str,
                    "embed_engine": list,
                    "mime_type": str,
                    "document_size": int,
                    "is_active": bool,
                    "upload_at": str,
                },
                ...
            ]
        }
    """
    logger.info("[API] [get_available_documents] enter.")

    payload = await req.json()
    client_id = payload.get("client_id")
    logger.info(f"[API] [get_available_documents] client_id={client_id}")

    query_id = await dsm.submit_query(
        action="get_available_documents",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        return JSONResponse(
            content=jsonable_encoder(result),
            status_code=200,
        )
    
    messages = result.get("messages", [])
    documents_list = []
    for document_meta in messages:
        documents_list.append({
            "document_id": document_meta.get("document_id"),
            "document_name": document_meta.get("document_name"),
            "document_description": document_meta.get("document_description"),
            "embed_engine": document_meta.get("embed_engine"),
            "mime_type": document_meta.get("mime_type"),
            "document_size": document_meta.get("document_size"),
            "is_active": document_meta.get("is_active"),
            "upload_at": document_meta.get("upload_at"),
        })

    return JSONResponse(
        content={
            "success": True,
            "messages": jsonable_encoder(documents_list),
        },
        status_code=200,
    )


@router.post("/file/rag/fetch_document_chunks")
async def fetch_document_chunks(req: Request):
    """
    Get top_k document chunks in milvus.

    Behavior:
    - Fetch document metadata from MySQL.
    - Find the top_k chunks in milvus.
    - Return the document chunks content.

    Request Body (JSON):
        {
            "client_id": str,
            "document_ids": list,
            "model": str,
            "api_key": str,
            "query": str,
            "top_k": int, // Optional, default 5.
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "text": str,
                    "metadata": {
                        "document_id": str,
                        "file_name": str
                    },
                },
                ...
            ]
        }
    """
    logger.info("[API][fetch_document_chunks] enter.")

    payload = await req.json()
    client_id = payload.get("client_id")
    logger.info(f"[API] [fetch_document_chunks] client_id={client_id}")

    query_id = await dsm.submit_query(
        action="vector_search",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    # --- Filter metadata fields ---
    allowed_fields = {"document_id", "file_name"}

    if "messages" in result:
        for msg in result["messages"]:
            metadata = msg.get("metadata", {})
            # Keep only required fields
            msg["metadata"] = {
                k: metadata.get(k)
                for k in allowed_fields
                if k in metadata
            }

    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )