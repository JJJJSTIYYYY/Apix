import asyncio
import base64
import hashlib
from pathlib import Path
from typing import Annotated

import requests
from langchain.messages import HumanMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.config import get_stream_writer

import easyocr
import cv2
import numpy as np

from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.apix_agent_core.sandbox_manager.file_system_manager import file_system
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.global_config import BASE_DIR


DEFAULT_OCR_PROMPT = """
You are an OCR analysis assistant. 
Your task is to analyze the content of the provided image.
You will receive multiple images in order.
Please analyze them jointly and clearly distinguish each image when needed.
Please make sure you describe the content of the image in a clear and concise manner, and extract any text information from it.
"""

_OCR_READER = None
MAX_OCR_FILE_SIZE = 10 * 1024 * 1024
MAX_OCR_FILES = 5
ALLOWED_OCR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def normalize_ocr_file_paths(
    file_path_input: str | list[str],
    *,
    max_files: int = MAX_OCR_FILES,
) -> list[str]:
    if isinstance(file_path_input, str):
        paths = [file_path_input]
    elif isinstance(file_path_input, list):
        paths = file_path_input
    else:
        raise Exception("file_path must be a string or a list of strings")

    paths = [p for p in paths if p]
    if not paths:
        raise Exception("No valid file_path provided")

    if len(paths) > max_files:
        raise Exception(f"Too many files. Maximum {max_files} images are allowed")

    return paths


def get_image_mime_type(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".bmp":
        return "image/bmp"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


async def load_single_image(
    path: str,
    *,
    sandbox_root: str,
    container_workdir: str,
    max_file_size: int = MAX_OCR_FILE_SIZE,
    allowed_extensions: set[str] = ALLOWED_OCR_EXTENSIONS,
    download_timeout: int | float = 20,
) -> tuple[Path, bytes, str]:
    real_path: Path

    if file_system.is_url(path):
        downloaded_path = await file_system.download_resource_from_url(
            path,
            to_folder="download_cache",
            format_check=False,
            timeout=download_timeout,
        )
        real_path = Path(downloaded_path)
    else:
        real_path = file_system.get_file_path_in_host(
            file_path=path,
            container_workdir=container_workdir,
            host_root=sandbox_root
        )

    if not real_path.exists():
        raise Exception(f"File not found: {path}")

    if real_path.suffix.lower() not in allowed_extensions:
        raise Exception(f"Unsupported file type: {path}")

    if real_path.stat().st_size > max_file_size:
        raise Exception(f"File too large (max 10MB allowed): {path}")

    with open(real_path, "rb") as f:
        img_bytes = f.read()

    if not img_bytes:
        raise Exception(f"Image is empty: {path}")

    mime_type = get_image_mime_type(real_path.suffix.lower())
    return real_path, img_bytes, mime_type


def get_reader():
    global _OCR_READER
    if _OCR_READER is None:
        _OCR_READER = easyocr.Reader(lang_list=['ch_sim', 'en'])
    return _OCR_READER


@tool
async def agent_ocr_analysis(
    prompt: str,
    file_path: str | list[str] = None,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Analyze one or more image files and return the recognized text or image analysis result.
    Supported file type: {".png", ".jpg", ".jpeg", ".bmp", ".webp"}.
    Maximum number of input images at a time: 5.

    Args:
        prompt: A prompt describing what should be analyzed. This parameter will be ignored when EasyOCR is used.
        file_path: File path / URL of a single image, or a list of image paths / URLs.

    Returns:
        str: The OCR result produced by EasyOCR or the image analysis result produced by a vision sub-model.

    Note:
        - This tool internally chooses to use EasyOCR or a vision sub-model.
        - EasyOCR is used for text recognition only.
        - A vision sub-model can return recognized text, image description, or other analysis results.
        - The prompt parameter is only effective when a vision sub-model is used.

    ## When to Use This Tool
    Use this tool in these scenarios:
    1. When the user wants to understand the content of one or more images.
    2. When the task requires reading or interpreting images.
    3. When images need to be described for reasoning purposes.
    4. When downstream processing depends on textual or visual information from images.

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. The file is not a supported image.
    2. The task can be solved without viewing the image.

    ## Important Guidelines
    - Ensure the file path or URL is valid before calling this tool.
    - Provide a clear prompt when image understanding or structured analysis is needed.
    - If structured output is required, explicitly specify the expected format.
    - Do not assume the content of an image without analysis.
    """
    writer = get_stream_writer()

    writer({"tool_chunk_rtn": {
        "tool_call_id": tool_call_id,
        "tool_chunk_rtn": "ocr_analysis",
        "content": file_path,
        "chunk_position": "start",
        "status": "success",
    }})

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")
    container_workdir = "/workspace"
    vision_on = config.get("use_model_vision", True)
    provider = config.get("models_provider")
    api_key = config.get("api_key")
    model_name = config.get("model_name")

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please call configure_sandbox first.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    if not file_path:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: No file_path provided.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:
        file_paths = normalize_ocr_file_paths(file_path)

        images: list[dict] = []
        for idx, path in enumerate(file_paths, start=1):
            real_path, img_bytes, mime_type = await load_single_image(
                path,
                sandbox_root=sandbox_root,
                container_workdir=container_workdir,
            )
            images.append({
                "index": idx,
                "input_path": path,
                "real_path": real_path,
                "img_bytes": img_bytes,
                "mime_type": mime_type,
            })

        if vision_on and await LlmNodeAdapter.is_vision_model(provider=provider, model_name=model_name, api_key=api_key, config=config):
            provider = config.get("models_provider")
            model = config.get("model_name")
            api_key = config.get("api_key", "")

            vision_model = LlmNodeAdapter.get_atapted_llm_node(
                provider=provider,
                model=model,
                api_key=api_key,
                config=config,
            )

            human_content = [{"type": "text", "text": prompt}]

            for item in images:
                b64_data = base64.b64encode(item["img_bytes"]).decode()
                human_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{item['mime_type']};base64,{b64_data}"
                    }
                })

            system_msg = SystemMessage(content=DEFAULT_OCR_PROMPT)
            user_msg = HumanMessage(content=human_content)

            response = await vision_model.ainvoke([system_msg, user_msg])
            content = str(response.content)

        else:
            reader = get_reader()
            loop = asyncio.get_running_loop()

            results = []
            total = len(images)

            for idx, item in enumerate(images, start=1):
                text_list = await loop.run_in_executor(
                    None,
                    reader.readtext,
                    item["img_bytes"],
                    0
                )

                if text_list:
                    extracted_texts = [t[1] for t in text_list if len(t) > 1]
                    text = "\n".join(extracted_texts) if extracted_texts else "No text detected."
                else:
                    text = "No text detected."

                results.append(
                    f"## Image {idx}\n"
                    f"Path: {item['input_path']}\n"
                    f"Extracted text: {text}"
                )

                writer({
                    "tool_chunk_rtn": {
                        "tool_call_id": tool_call_id,
                        "tool_chunk_rtn": "ocr_analysis",
                        "content": f"Analyzed {idx}/{total} files successfully.",
                        "chunk_position": "middle" if idx < total else "end",
                        "status": "success",
                    }
                })

            content = "Vision sub-model is not available, detect to EasyOCR.\n\n"+"\n\n".join(results)

            return Command(update={
                "messages": [
                    ToolMessage(content, tool_call_id=tool_call_id)
                ]
            })

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "ocr_analysis",
                "content": f"Analyzed {len(images)}/{len(images)} files successfully.",
                "chunk_position": "end",
                "status": "success",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(content, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "ocr_analysis",
                "content": f"Error: {e}",
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(f"Error: {str(e)}", tool_call_id=tool_call_id)
            ]
        })
    

@tool
async def send_images_to_user(
    file_path: str | list[str] = None,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Send one or more image files to user.
    Supported file type: {".png", ".jpg", ".jpeg", ".bmp", ".webp"}.
    Maximum number of input images at a time: 5.

    Args:
        file_path: File path / URL of a single image, or a list of image paths / URLs.

    Returns:
        str: The OCR result produced by EasyOCR or the image analysis result produced by a vision sub-model.
    """
    writer = get_stream_writer()

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "send_images",
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    })

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")
    container_workdir = "/workspace"

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please call configure_sandbox first.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    if not file_path:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: No file_path provided.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:
        file_paths = normalize_ocr_file_paths(file_path)

        images: list[dict] = []
        for idx, path in enumerate(file_paths, start=1):
            real_path, _, _ = await load_single_image(
                path,
                sandbox_root=sandbox_root,
                container_workdir=container_workdir,
            )
            images.append({
                "index": idx,
                "input_path": path,
                "real_path": real_path,
            })

        if not state.get("task_id", None):
            client_id = state.get("client_id")
            if not client_id:
                raise Exception("Unknow client_id")
            
            file_meta = await file_system.insert_files_to_file_service(
                client_id=client_id,
                file_paths=[item["real_path"] for item in images],
            )
            image_ids = []
            for meta in file_meta:
                file_id = meta.get("file_id")
                if not file_id: continue
                image_ids.append(file_id)

            if image_ids:
                addtional_info = {"image_meta": image_ids}
                await ai_context_manager.append_info_message(
                    state.get("generation_id"), 
                    state.get("client_id"), 
                    state.get("history_id"), 
                    state.get("timestamp"),
                    addtional_info,
                )
                    
                writer({
                    "tool_chunk_rtn": {
                        "tool_call_id": tool_call_id,
                        "tool_chunk_rtn": "send_images",
                        "content": image_ids,
                        "chunk_position": "end",
                        "status": "success",
                    }
                })

        return Command(update={
            "messages": [
                ToolMessage(
                    "Send success.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    except Exception as e:
        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "send_images",
                "content": f"Error: {e}",
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(f"Error: {str(e)}", tool_call_id=tool_call_id)
            ]
        })