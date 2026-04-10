from pathlib import Path
from typing import List
from urllib.parse import quote
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse

from core.domain.data_server_manager import data_server_manager as dsm
from core.commons.logger import logger


router = APIRouter(tags=["skill_record"])


@router.post("/file/skills/insert_skills")
async def insert_skill_files(
    client_id: str = Form(...),
    files: list[UploadFile] = File(...)
):
    """
    Store skills in service.

    Behavior:
    - Store skill zip files to local.
    - Analysis skills name and describe.
    - Persist skill info to MySQL for each.

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
        curl -X POST /file/skills/insert_skills \\
            -F "client_id=xxx" \\
            -F "files=@a.zip" \\
            -F "files=@b.zip"

    Notes:
        - JSON request body is NOT supported.
        - Base64-encoded file data is NOT supported.
        - Files are streamed to disk and never fully loaded into memory.

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "skill_id": str,
                    "skill_name": str,
                    "skill_description": str,
                    "skill_version": str,
                    "package_size": int,
                    "is_active": bool,
                    "upload_at": str,
                },
                ...
            ]
        }
    """
    logger.info("[API] [insert_skill_files] enter.")
    logger.info(f"[API] [insert_skill_files] client_id={client_id}, files={len(files)}")

    query_id = await dsm.submit_query(
        action="insert_skills",
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


@router.post("/file/skills/update_skill")
async def update_skill(req: Request):
    """
    Update skill info in MySQL.
    This API can be used delete or active target skill.

    Behavior:
    - Update skill info in MySQL.

    Request Body (JSON):
        {
            "client_id": str,
            "skill_id": str,
            "is_active": bool | None,
            "deleted": bool | None,
        }

    Returns:
        {
            "success": bool,
            "messages": "fail: {e}" or "success"
        }
    """
    logger.info("[API] [update_skills] enter.")

    payload = await req.json()
    client_id = payload.get("client_id")
    logger.info(f"[API] [update_skills] client_id={client_id} payload={payload}")

    query_id = await dsm.submit_query(
        action="update_skill",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    return JSONResponse(
        content=jsonable_encoder(result),
        status_code=200,
    )


@router.post("/file/skills/get_available_skills")
async def get_available_skills(req: Request):
    """
    Get skills info from mysql.
    Return skill metadata list.
    Binary skill package is not included.

    Behavior:
    - Fetch skills info from MySQL.

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
                    "skill_id": str,
                    "skill_name": str,
                    "skill_description": str,
                    "skill_version": str,
                    "package_size": int,
                    "is_active": bool,
                    "upload_at": str,
                },
                ...
            ]
        }
    """
    logger.info("[API] [get_available_skills] enter.")

    payload = await req.json()
    client_id = payload.get("client_id")
    logger.info(f"[API] [get_available_skills] client_id={client_id}")

    query_id = await dsm.submit_query(
        action="fetch_skills",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        return JSONResponse(
            content=jsonable_encoder(result),
            status_code=200,
        )
    
    messages = result.get("messages", [])
    skills_list = []
    for skill_meta in messages:
        skills_list.append({
            "skill_id": skill_meta.get("skill_id"),
            "skill_name": skill_meta.get("skill_name"),
            "skill_description": skill_meta.get("skill_description"),
            "skill_version": skill_meta.get("skill_version"),
            "package_size": skill_meta.get("package_size"),
            "is_active": skill_meta.get("is_active"),
            "upload_at": skill_meta.get("upload_at"),
        })

    return JSONResponse(
        content={
            "success": True,
            "messages": skills_list,
        },
        status_code=200,
    )


@router.get("/file/skills/fetch_skill")
async def fetch_skill(
    skill_id: str,
    client_id: str,
):
    """
    Download target skill package.

    Behavior:
    - Fetch skill metadata from MySQL (includes package_path).
    - Stream the skill package (zip) to client.

    Query Params:
        skill_id: str
        client_id: str

    Returns:
        zip file stream
    """
    logger.info(
        "[API][fetch_skill] enter."
        f"[API][fetch_skill] client_id={client_id}, skill_id={skill_id}"
    )

    payload = {
        "client_id": client_id,
        "skill_id": skill_id,
    }

    query_id = await dsm.submit_query(
        action="fetch_target_skill",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("messages"),
        )

    messages = result.get("messages") or []
    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"skill not found: {skill_id}",
        )

    skill_info = messages[0]

    skill_name = skill_info.get("skill_name")
    package_path = skill_info.get("package_path")
    package_size = skill_info.get("package_size")

    if not package_path or not skill_name:
        raise HTTPException(
            status_code=404,
            detail=f"Skill package missing: {skill_id}",
        )

    if not Path(package_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"Skill package not found on disk: {skill_id}",
        )

    filename = f"{skill_name}.zip"
    quoted_filename = quote(filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
        "X-Skill-ID": skill_id,
        "X-Skill-Size": str(package_size) if package_size else "0",
    }

    return FileResponse(
        package_path,
        media_type="application/zip",
        headers=headers,
    )
