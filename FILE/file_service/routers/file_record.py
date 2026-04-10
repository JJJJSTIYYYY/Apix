import mimetypes
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse

from core.domain.data_server_manager import data_server_manager as dsm
from core.commons.logger import logger


router = APIRouter(tags=["file_record"])


@router.post("/file/file/insert_file")
async def insert_file(
    client_id: str = Form(...),
    files: list[UploadFile] = File(...)
):
    """
    Append uploaded file metadata to MySQL.
    This API does not support RAG.

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
        curl -X POST /file/file/insert_file \\
            -F "client_id=xxx" \\
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
                    "file_id": str,
                    "file_name": str,
                },
                ...
            ]
        }
    """
    logger.info("[API][insert_file] enter.")
    logger.info(f"[API][insert_file] client_id={client_id}, files={len(files)}")

    query_id = await dsm.submit_query(
        action="insert_file",
        payload={
            "client_id": client_id,
            "files": files,
        },
    )

    result = await dsm.wait_result(query_id)

    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )


@router.post("/file/file/update_file")
async def update_file(req: Request):
    """
    Update files info in mysql.
    This API does not support RAG.
    This method only used to modify single file's detete ststus.

    Behavior:
    - Update file's delete status to MySQL.

    Request Body (JSON):
        {
            "client_id": str,
            "file_id": str,
            "is_deleted": boolean,
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][update_file] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="update_file_status",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )


@router.post("/file/file/get_recent_files")
async def get_recent_files(req: Request):
    """
    Get recent files info from mysql, not include binary.
    Load file path to cache before get files.
    This API does not support RAG.

    Behavior:
    - Fetch recent file metadata from MySQL.
    - Generate temporary access URL for each file via FileService.
    - Do NOT return binary content.

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
                    "file_id": str,
                    "file_name": str,
                    "upload_at": str,
                },
                ...
            ]
        }
    """
    logger.info("[API][get_recent_files] enter.")
    payload = await req.json()
    logger.info(f"[API][get_recent_files] payload:\n{str(payload)[:50]}...")

    query_id = await dsm.submit_query(
        action="get_recent_files",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        return JSONResponse(
            content=jsonable_encoder(result),
            status_code=200,
        )

    rows = result.get("messages", [])

    # Enrich file info with access_url at API layer
    enriched_rows = []
    for row in rows:
        file_id = row.get("file_id")
        file_name = row.get("file_name")
        file_path = row.get("file_path")
        upload_at = row.get("upload_at", "Unknown")
        file_size = row.get("file_size", 0)
        sha256 = row.get("sha256", "")

        if file_size >= 1024 * 1024: 
            file_size = f"{file_size / (1024 * 1024):.2f} MB" 
        else: 
            file_size = f"{file_size / 1024:.2f} KB"

        if not file_id or not file_name:
            continue

        enriched_rows.append(
            {
                "file_id": file_id,
                "file_name": file_name,
                "upload_at": upload_at,
                "file_size": file_size,
            }
        )

    return JSONResponse(
        content={
            "success": True,
            "messages": enriched_rows,
        },
        status_code=200,
    )


@router.get("/file/file/download")
async def download_file(
    file_id: str,
    client_id: str,
):
    """
    Download one file by file_id.

    Query Params:
        file_id: str
        client_id: str

    Returns:
        file stream.
    """
    logger.info(
        "[API][download_file] enter: "
        f"client_id={client_id}, file_id={file_id}"
    )

    payload = {
        "client_id": client_id,
        "file_id": file_id,
    }

    query_id = await dsm.submit_query(
        action="download_file",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("messages")
        )

    messages = result.get("messages") or []
    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"file not found: {file_id}",
        )

    file_info = messages[0]

    file_name = file_info.get("file_name")
    access_path = file_info.get("file_path")
    file_hash = file_info.get("sha256")

    if not access_path or not file_name or not file_hash:
        raise HTTPException(
            status_code=404,
            detail=f"Target file has been destroyed: {file_id}",
        )

    if not Path(access_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"file not found on disk: {file_id}"
        )

    quoted_filename = quote(file_name)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
        "X-File-SHA256": file_hash,
    }

    return FileResponse(
        access_path,
        media_type="application/octet-stream",
        headers=headers,
    )


@router.get("/file/file/load_resource")
async def load_resource(
    file_id: str,
    client_id: str,
):
    """
    Load one file by file_id for browser inline rendering.

    Query Params:
        file_id: str
        client_id: str

    Returns:
        file stream for inline display.
    """
    logger.info(
        "[API][load_resource] enter: "
        f"client_id={client_id}, file_id={file_id}"
    )

    payload = {
        "client_id": client_id,
        "file_id": file_id,
    }

    query_id = await dsm.submit_query(
        action="download_file",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("messages")
        )

    messages = result.get("messages") or []
    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"file not found: {file_id}",
        )

    file_info = messages[0]

    file_name = file_info.get("file_name")
    access_path = file_info.get("file_path")
    file_hash = file_info.get("sha256")

    if not access_path or not file_name or not file_hash:
        raise HTTPException(
            status_code=404,
            detail=f"Target file has been destroyed: {file_id}",
        )

    if not Path(access_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"file not found on disk: {file_id}"
        )

    media_type, _ = mimetypes.guess_type(file_name)
    if not media_type:
        media_type = "application/octet-stream"

    quoted_filename = quote(file_name)

    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{quoted_filename}",
        "X-File-SHA256": file_hash,
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f"\"{file_hash}\"",
    }

    return FileResponse(
        access_path,
        media_type=media_type,
        headers=headers,
    )


@router.get("/file/file/load_resource")
async def load_resource(
    file_id: str,
    client_id: str,
):
    """
    Load one file by file_id for browser inline rendering.

    Query Params:
        file_id: str
        client_id: str

    Returns:
        file stream for inline display.
    """
    logger.info(
        "[API][load_resource] enter: "
        f"client_id={client_id}, file_id={file_id}"
    )

    payload = {
        "client_id": client_id,
        "file_id": file_id,
    }

    query_id = await dsm.submit_query(
        action="download_file",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("messages")
        )

    messages = result.get("messages") or []
    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"file not found: {file_id}",
        )

    file_info = messages[0]

    file_name = file_info.get("file_name")
    access_path = file_info.get("file_path")
    file_hash = file_info.get("sha256")
    mime_type = file_info.get("mime_type")

    if not access_path or not file_name or not file_hash:
        raise HTTPException(
            status_code=404,
            detail=f"Target file has been destroyed: {file_id}",
        )

    file_path = Path(access_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"file not found on disk: {file_id}"
        )

    media_type = mime_type
    if not media_type:
        media_type, _ = mimetypes.guess_type(file_name)

    if not media_type:
        media_type = "application/octet-stream"

    quoted_filename = quote(file_name)

    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{quoted_filename}",
        "X-File-SHA256": file_hash,
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f"\"{file_hash}\"",
    }

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers=headers,
        filename=file_name,
    )