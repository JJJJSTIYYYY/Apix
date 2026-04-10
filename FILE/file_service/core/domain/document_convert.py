import asyncio
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any

import fitz  # PyMuPDF
from PIL import Image


class DocumentConversionService:
    """
    Document conversion service with async task queue.

    Responsibilities:
    - Office -> PDF (LibreOffice)
    - PDF -> compressed JPEG images
    - Package images into ZIP (same name as original file)
    - Control concurrency via async worker pool
    """

    def __init__(self, max_workers: int = 2):
        """
        Args:
            max_workers: Number of concurrent conversion workers.
        """
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._max_workers = max_workers
        self._running = False

    # ==========================================================
    # Lifecycle
    # ==========================================================

    async def start(self):
        """
        Start background workers.
        """
        if self._running:
            return

        self._running = True

        for _ in range(self._max_workers):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def stop(self):
        """
        Gracefully stop workers.
        """
        self._running = False

        # Wait until queue is empty
        await self._queue.join()

        for worker in self._workers:
            worker.cancel()

        self._workers.clear()

    # ==========================================================
    # Public API
    # ==========================================================

    async def convert_document(
        self,
        file_path: str,
        file_type: str,
    ) -> Dict[str, Any]:
        """
        Enqueue document conversion task and wait for result.

        Args:
            file_path: Absolute path to file.
            file_type: Extension without dot (pdf/docx/xlsx/...)

        Returns:
            {
                "zip_path": str,
                "page_count": int
            }
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        await self._queue.put(
            {
                "file_path": file_path,
                "file_type": file_type,
                "future": future,
            }
        )

        return await future

    # ==========================================================
    # Worker
    # ==========================================================

    async def _worker(self):
        """
        Background worker consuming conversion tasks.
        """
        while True:
            task = await self._queue.get()

            file_path = task["file_path"]
            file_type = task["file_type"]
            future: asyncio.Future = task["future"]

            try:
                result = await self._convert(file_path, file_type)

                if not future.cancelled():
                    future.set_result(result)

            except Exception as e:
                if not future.cancelled():
                    future.set_exception(e)

            finally:
                self._queue.task_done()

    # ==========================================================
    # Core conversion logic
    # ==========================================================

    async def _convert(
        self,
        file_path: str,
        file_type: str,
    ) -> Dict[str, Any]:
        """
        Real conversion logic.
        """

        # Office → PDF first
        if file_type in {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}:
            pdf_path = await self._convert_office_to_pdf(file_path)
        else:
            pdf_path = file_path

        # PDF → images → zip
        return await self._convert_pdf_to_zip(pdf_path)

    # ==========================================================
    # Office → PDF (LibreOffice)
    # ==========================================================

    async def _convert_office_to_pdf(self, file_path: str) -> str:
        """
        Convert office document to PDF using LibreOffice.

        Returns:
            Absolute PDF path.
        """

        output_dir = tempfile.mkdtemp()

        try:
            cmd = [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                output_dir,
                file_path,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise RuntimeError(
                    f"LibreOffice conversion failed: {stderr.decode()}"
                )

            original_name = Path(file_path).stem
            pdf_path = os.path.join(output_dir, f"{original_name}.pdf")

            if not os.path.exists(pdf_path):
                raise RuntimeError("Converted PDF not found.")

            return pdf_path

        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

    # ==========================================================
    # PDF → Images → ZIP
    # ==========================================================

    async def _convert_pdf_to_zip(self, pdf_path: str) -> Dict[str, Any]:
        """
        Convert PDF to compressed images and package as ZIP.

        Compression increases as page count increases.

        Returns:
            {
                "zip_path": str,
                "page_count": int
            }
        """

        if not os.path.exists(pdf_path):
            raise RuntimeError("PDF file does not exist.")

        temp_dir = tempfile.mkdtemp()

        try:
            images = []

            with fitz.open(pdf_path) as doc:
                page_count = len(doc)

                # Dynamic scaling:
                # More pages → lower scale (but not too small)
                scale = max(0.6, 1.2 - (page_count * 0.02))
                matrix = fitz.Matrix(scale, scale)

                for i, page in enumerate(doc):
                    pix = page.get_pixmap(matrix=matrix)

                    img = Image.frombytes(
                        "RGB",
                        [pix.width, pix.height],
                        pix.samples,
                    )

                    image_path = os.path.join(
                        temp_dir,
                        f"page_{i + 1}.jpg"
                    )

                    # Moderate compression
                    img.save(
                        image_path,
                        format="JPEG",
                        quality=70,
                        optimize=True,
                    )

                    images.append(image_path)

            # Create ZIP in same directory as PDF
            zip_path = os.path.splitext(pdf_path)[0] + ".zip"

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for img_path in images:
                    arcname = os.path.basename(img_path)
                    zipf.write(img_path, arcname)

            return {
                "zip_path": zip_path,
                "page_count": page_count,
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
