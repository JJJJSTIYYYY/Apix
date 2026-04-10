# import io
from pathlib import Path
# import re
from typing import Annotated, Optional
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

# from unidiff import PatchSet
# from unidiff.patch import PatchedFile
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langgraph.config import get_stream_writer

from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.sandbox_manager.file_system_manager import file_system




# class PatchApplyError(Exception):
#     pass


# @dataclass
# class AppliedFileResult:
#     file_path: str
#     updated_text: str
#     changed_ranges: list[tuple[int, int]]  # 1-based inclusive line ranges in updated file


# @dataclass
# class FileWritePlan:
#     file_path: str
#     host_path: Path
#     updated_text: str | None  # None means delete file
#     preview_text: str


# def _strip_diff_fence(patch: str) -> str:
#     patch = patch.strip()
#     if patch.startswith("```"):
#         patch = re.sub(r"^```(?:diff)?[^\n]*\n", "", patch, count=1)
#         patch = re.sub(r"\n```$", "", patch).strip()
#     return patch


# def _detect_newline(text: str) -> str:
#     return "\r\n" if "\r\n" in text else "\n"


# def _read_text_preserve_newlines(path: Path) -> str:
#     with open(path, "r", encoding="utf-8", newline="") as f:
#         return f.read()


# def _write_text_atomic(path: Path, text: str) -> None:
#     path.parent.mkdir(parents=True, exist_ok=True)
#     with NamedTemporaryFile(
#         "w",
#         encoding="utf-8",
#         newline="",
#         delete=False,
#         dir=path.parent,
#     ) as tmp:
#         tmp.write(text)
#         tmp_path = Path(tmp.name)
#     tmp_path.replace(path)


# def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
#     if not ranges:
#         return []

#     ranges = sorted(ranges)
#     merged = [ranges[0]]

#     for start, end in ranges[1:]:
#         last_start, last_end = merged[-1]
#         if start <= last_end + 1:
#             merged[-1] = (last_start, max(last_end, end))
#         else:
#             merged.append((start, end))

#     return merged


# def _expand_ranges(
#     ranges: list[tuple[int, int]],
#     total_lines: int,
#     context_lines: int,
# ) -> list[tuple[int, int]]:
#     expanded = []
#     for start, end in ranges:
#         if start > end:
#             anchor = min(max(1, start), max(1, total_lines))
#             expanded.append(
#                 (max(1, anchor - context_lines), min(total_lines, anchor + context_lines))
#             )
#         else:
#             expanded.append(
#                 (max(1, start - context_lines), min(total_lines, end + context_lines))
#             )
#     return _merge_ranges(expanded)


# def _render_numbered_lines(lines: list[str], start_line: int) -> str:
#     return "\n".join(
#         f"[{line_no}] {line}"
#         for line_no, line in enumerate(lines, start=start_line)
#     )


# def _render_lines(lines: list[str]) -> str:
#     return "\n".join(
#         f"{line}"
#         for line in lines
#     )


# def _render_preview_block(file_path: str, preview_body: str) -> str:
#     return f"File: {file_path}\n{preview_body}"


# def _render_preview(
#     text: str,
#     changed_ranges: list[tuple[int, int]],
#     *,
#     max_full_lines: int = 200,
#     context_lines: int = 3,
#     max_preview_lines: int = 120,
# ) -> str:
#     lines = text.splitlines(keepends=False)
#     total_lines = len(lines)

#     if total_lines == 0:
#         return "[empty file]"

#     if total_lines <= max_full_lines:
#         # return _render_numbered_lines(lines, 1)
#         return _render_lines(lines)

#     expanded = _expand_ranges(changed_ranges, total_lines, context_lines)

#     rendered_blocks: list[str] = []
#     used_lines = 0

#     for start, end in expanded:
#         block_len = end - start + 1
#         if used_lines + block_len > max_preview_lines:
#             remaining = max_preview_lines - used_lines
#             if remaining <= 0:
#                 break
#             end = start + remaining - 1
#             block_len = remaining

#         block_lines = lines[start - 1:end]
#         # rendered_blocks.append(_render_numbered_lines(block_lines, start))
#         rendered_blocks.append(_render_lines(block_lines))
#         used_lines += block_len

#         if used_lines >= max_preview_lines:
#             break

#     body = "\n...\n".join(rendered_blocks) if rendered_blocks else "[no preview available]"
#     hidden = total_lines - used_lines

#     suffix = ""
#     if hidden > 0:
#         suffix = f"\n... ({hidden} more line(s) omitted)"

#     return f"{body}{suffix}"


# def _apply_patched_file(original: str, patched_file: PatchedFile) -> AppliedFileResult:
#     """
#     Apply one unidiff PatchedFile to original text using a single forward scan.

#     This preserves:
#     - context validation
#     - multi-hunk correctness
#     - original newline style for existing files
#     """
#     newline = _detect_newline(original)
#     original_has_trailing_newline = original.endswith(("\n", "\r\n"))

#     src_lines = original.splitlines(keepends=False)
#     out_lines: list[str] = []
#     src_idx = 0
#     changed_ranges: list[tuple[int, int]] = []

#     for hunk in patched_file:
#         hunk_start = max(hunk.source_start - 1, 0)

#         if hunk_start < src_idx:
#             raise PatchApplyError(
#                 f"Overlapping or out-of-order hunks in {patched_file.path}."
#             )

#         if hunk_start > len(src_lines):
#             raise PatchApplyError(
#                 f"Hunk start out of range in {patched_file.path}: line {hunk.source_start}."
#             )

#         # copy untouched lines before this hunk
#         out_lines.extend(src_lines[src_idx:hunk_start])
#         src_idx = hunk_start

#         preview_start = len(out_lines) + 1  # 1-based line number in updated output

#         for line in hunk:
#             value = line.value.rstrip("\n")

#             if line.is_context:
#                 if src_idx >= len(src_lines) or src_lines[src_idx] != value:
#                     actual = src_lines[src_idx] if src_idx < len(src_lines) else "<EOF>"
#                     raise PatchApplyError(
#                         f"Patch context mismatch in {patched_file.path} at line {src_idx + 1}: "
#                         f"expected {value!r}, got {actual!r}. "
#                         "Read the file again and regenerate the patch."
#                     )
#                 out_lines.append(src_lines[src_idx])
#                 src_idx += 1

#             elif line.is_removed:
#                 if src_idx >= len(src_lines) or src_lines[src_idx] != value:
#                     actual = src_lines[src_idx] if src_idx < len(src_lines) else "<EOF>"
#                     raise PatchApplyError(
#                         f"Patch remove mismatch in {patched_file.path} at line {src_idx + 1}: "
#                         f"expected {value!r}, got {actual!r}. "
#                         "Read the file again and regenerate the patch."
#                     )
#                 src_idx += 1

#             elif line.is_added:
#                 out_lines.append(value)

#         preview_end = len(out_lines)
#         changed_ranges.append((preview_start, preview_end))

#     out_lines.extend(src_lines[src_idx:])
#     updated = newline.join(out_lines)

#     if out_lines and original_has_trailing_newline:
#         updated += newline
#     elif not original and out_lines:
#         updated += newline

#     return AppliedFileResult(
#         file_path=patched_file.path,
#         updated_text=updated,
#         changed_ranges=_merge_ranges(changed_ranges),
#     )


# def _build_file_write_plan(
#     patched_file: PatchedFile,
#     sandbox_root: str,
# ) -> FileWritePlan:
#     file_path = patched_file.path
#     if not file_path:
#         raise PatchApplyError("Invalid patch: missing target file path")

#     host_path = file_system.get_file_path_in_host(
#         file_path=file_path,
#         container_workdir="/workspace",
#         host_root=sandbox_root,
#         must_exist=False,
#     )

#     if getattr(patched_file, "is_removed_file", False):
#         return FileWritePlan(
#             file_path=file_path,
#             host_path=host_path,
#             updated_text=None,
#             preview_text=_render_preview_block(file_path, "[deleted]"),
#         )

#     original = ""
#     if host_path.exists():
#         original = _read_text_preserve_newlines(host_path)

#     applied = _apply_patched_file(original, patched_file)

#     preview_body = _render_preview(
#         text=applied.updated_text,
#         changed_ranges=applied.changed_ranges,
#     )

#     return FileWritePlan(
#         file_path=file_path,
#         host_path=host_path,
#         updated_text=applied.updated_text,
#         preview_text=_render_preview_block(applied.file_path, preview_body),
#     )


# @tool
# async def apply_workspace_patch(
#     patch: str,
#     state: Annotated[dict, InjectedState],
#     tool_call_id: Annotated[str, InjectedToolCallId],
# ) -> Command:
#     """
#     Apply unified diff patch(es) to files inside the sandbox workspace.

#     ## When to Use This Tool
#     Use this tool in these scenarios:
#     1. When you already have a valid unified diff patch and need to apply it to files in the workspace
#     2. When the user asks you to modify, update, refactor, or rewrite code/files inside the sandbox
#     3. When one or more workspace files must be edited before continuing execution
#     4. When you need to create a new file, modify an existing file, or delete a file through standard unified diff format

#     ## When NOT to Use This Tool
#     Do NOT use this tool when:
#     1. You do not yet have a valid unified diff patch
#     2. You only want to describe code changes without actually applying them
#     3. You want to read file contents only; use a file-read tool instead

#     ## Patch Format Requirements
#     The patch must follow standard unified diff format.
#     Each file must start with:

#     --- a/<path>
#     +++ b/<path>

#     Example:

#     --- a/example.py
#     +++ b/example.py
#     @@
#     line1
#     -old line
#     +new line
#     line3

#     Rules:

#     • Lines starting with "-" are removed
#     • Lines starting with "+" are added
#     • Lines starting with " " are unchanged context lines
#     • Each modification block starts with @@

#     Rules:
#     - Multiple files may be included in one patch
#     - New files may be created
#     - Existing files may be modified
#     - Files may be deleted
#     - Context lines must match the current file content exactly
#     - The file path from the diff is treated as the workspace-relative path
#     - Markdown fences like ```diff ... ``` are allowed and will be stripped before parsing

#     ## Return Behavior
#     On success, this tool returns structured preview text for all modified files.
#     Each preview block includes:
#     1. The file path
#     2. Line-numbered preview content
#     3. Changed lines plus nearby context, or the whole file if it is small
#     4. You have not yet read the current file content needed to produce a correct patch

#     Preview format:

#         File: path/to/file.py
#         line 1 content
#         line 2 content

#     For deleted files, the preview is:

#         File: path/to/file.py
#         [deleted]

#     ## Important Guidelines
#     - Only apply patches that are necessary for the current objective.
#     - Prefer a single coherent patch over many tiny patch calls when modifying related files.
#     - Do not include file preview prefixes like `[1] `, `[2] ` inside the patch itself.
#     - If patch application fails because context does not match, read the latest file content and regenerate the patch.
#     - Avoid redundant patch applications to the same unchanged content.
#     """

#     writer = get_stream_writer()

#     def fail(message: str) -> Command:
#         writer({
#             "tool_chunk_rtn": {
#                 "tool_call_id": tool_call_id,
#                 "tool_chunk_rtn": "apply_patch",
#                 "content": message,
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         })
#         return Command(update={
#             "messages": [ToolMessage(message, tool_call_id=tool_call_id)]
#         })

#     writer({
#         "tool_chunk_rtn": {
#             "tool_call_id": tool_call_id,
#             "tool_chunk_rtn": "apply_patch",
#             "content": "Applying patch",
#             "chunk_position": "start",
#             "status": "success",
#         }
#     })

#     config = state.get("config", {})
#     sandbox_root = config.get("work_dir")
#     container_id = state.get("sandbox")

#     if not container_id or not sandbox_root:
#         return fail("Sandbox not configured.")

#     try:
#         if not patch or not patch.strip():
#             raise PatchApplyError("Empty patch")

#         normalized_patch = _strip_diff_fence(patch)
#         patch_set = PatchSet(io.StringIO(normalized_patch))
#         if not patch_set:
#             raise PatchApplyError("No valid file patch found")

#         # Phase 1: compute every file result first
#         write_plans: list[FileWritePlan] = []
#         all_previews: list[str] = ["Those files have been modified successfully:"]

#         for patched_file in patch_set:
#             plan = _build_file_write_plan(patched_file, sandbox_root)
#             write_plans.append(plan)
#             all_previews.append(plan.preview_text)

#         # Phase 2: write to disk
#         for plan in write_plans:
#             if plan.updated_text is None:
#                 if plan.host_path.exists():
#                     plan.host_path.unlink()
#                 continue

#             _write_text_atomic(plan.host_path, plan.updated_text)

#         writer({
#             "tool_chunk_rtn": {
#                 "tool_call_id": tool_call_id,
#                 "tool_chunk_rtn": "apply_patch",
#                 "content": f"Patched {len(write_plans)} file(s)",
#                 "chunk_position": "end",
#                 "status": "success",
#             }
#         })

#         preview_text = "\n\n".join(
#             p for p in all_previews if p.strip()
#         ) or "No preview available."

#         return Command(update={
#             "messages": [
#                 ToolMessage(preview_text, tool_call_id=tool_call_id)
#             ]
#         })

#     except Exception as e:
#         return fail(str(e))
    










# class ModifyFileError(Exception):
#     pass


# @dataclass
# class FileModifyResult:
#     file_path: str
#     updated_text: str
#     changed_range: tuple[int, int]  # 1-based inclusive range in updated file


# def _detect_newline(text: str) -> str:
#     return "\r\n" if "\r\n" in text else "\n"


# def _read_text_preserve_newlines(path: Path) -> str:
#     with open(path, "r", encoding="utf-8", newline="") as f:
#         return f.read()


# def _write_text_atomic(path: Path, text: str) -> None:
#     path.parent.mkdir(parents=True, exist_ok=True)
#     with NamedTemporaryFile(
#         "w",
#         encoding="utf-8",
#         newline="",
#         delete=False,
#         dir=path.parent,
#     ) as tmp:
#         tmp.write(text)
#         tmp_path = Path(tmp.name)
#     tmp_path.replace(path)


# def _render_numbered_lines(lines: list[str], start_line: int) -> str:
#     return "\n".join(
#         f"[{line_no}] {line}"
#         for line_no, line in enumerate(lines, start=start_line)
#     )


# def _render_preview_block(file_path: str, preview_body: str) -> str:
#     return f"File: {file_path}\n{preview_body}"


# def _render_preview(
#     text: str,
#     changed_range: tuple[int, int],
#     *,
#     max_full_lines: int = 200,
#     context_lines: int = 3,
#     max_preview_lines: int = 120,
# ) -> str:
#     lines = text.splitlines(keepends=False)
#     total_lines = len(lines)

#     if total_lines == 0:
#         return "[empty file]"

#     if total_lines <= max_full_lines:
#         return _render_numbered_lines(lines, 1)

#     start, end = changed_range
#     start = max(1, start - context_lines)
#     end = min(total_lines, end + context_lines)

#     block_lines = lines[start - 1:end]

#     if len(block_lines) > max_preview_lines:
#         block_lines = block_lines[:max_preview_lines]
#         end = start + len(block_lines) - 1

#     body = _render_numbered_lines(block_lines, start)
#     hidden = total_lines - len(block_lines)

#     suffix = ""
#     if hidden > 0:
#         suffix = f"\n... ({hidden} more line(s) omitted)"

#     return f"{body}{suffix}"


# def _apply_line_replacement(
#     *,
#     file_path: str,
#     original: str,
#     content: str,
#     start_line: Optional[int],
#     end_line: Optional[int],
# ) -> FileModifyResult:
#     """
#     Replace lines in a file using 1-based inclusive line numbers.

#     Rules:
#     - If start_line and end_line are both None: replace the whole file with content
#     - Otherwise both must be provided and be 1-based
#     - Replaced range is inclusive: [start_line, end_line]
#     """
#     if start_line == 0 and end_line == 0:
#         start_line = None
#         end_line = None

#     # whole-file replace
#     if start_line is None and end_line is None:
#         updated_text = content
#         updated_lines = updated_text.splitlines(keepends=False)
#         changed_range = (1, max(1, len(updated_lines)))
#         return FileModifyResult(
#             file_path=file_path,
#             updated_text=updated_text,
#             changed_range=changed_range,
#         )

#     assert start_line is not None
#     assert end_line is not None

#     if start_line < 0 or end_line < 0:
#         raise ModifyFileError("start_line and end_line must be >= 0.")

#     if end_line < start_line:
#         raise ModifyFileError("end_line must be greater than or equal to start_line.")

#     newline = _detect_newline(original)
#     original_has_trailing_newline = original.endswith(("\n", "\r\n"))

#     src_lines = original.splitlines(keepends=False)
#     total_lines = len(src_lines)

#     if start_line == 0:
#         start_line = 1

#     if end_line == 0 or total_lines < end_line:
#         end_line = total_lines

#     if total_lines == 0:
#         raise ModifyFileError(
#             "Cannot apply line-based modification to an empty or non-existent file. "
#             "Use full-file replacement instead."
#         )

#     if start_line > total_lines or end_line > total_lines:
#         raise ModifyFileError(
#             f"Line range [{start_line}, {end_line}] is out of range for file with {total_lines} line(s)."
#         )

#     replacement_lines = content.splitlines(keepends=False)

#     updated_lines = (
#         src_lines[: start_line - 1]
#         + replacement_lines
#         + src_lines[end_line:]
#     )

#     updated_text = newline.join(updated_lines)

#     if updated_lines and original_has_trailing_newline:
#         updated_text += newline

#     changed_end = start_line + max(len(replacement_lines), 1) - 1

#     return FileModifyResult(
#         file_path=file_path,
#         updated_text=updated_text,
#         changed_range=(start_line, changed_end),
#     )


# @tool
# async def modify_workspace_file(
#     file_path: str,
#     content: str,
#     start_line: int = 0,
#     end_line: int = 0,
#     state: Annotated[dict, InjectedState] = None,
#     tool_call_id: Annotated[str, InjectedToolCallId] = None,
# ) -> Command:
#     """
#     Modify a workspace file directly by replacing a line range or the whole file.

#     ## When to Use This Tool
#     Use this tool in these scenarios:
#     1. When you already know the target file path and the exact replacement content
#     2. When the user asks you to modify, update, refactor, or rewrite code/files inside the sandbox
#     3. When one or more workspace files must be edited before continuing execution
#     4. When patch generation is unnecessary or unreliable

#     ## How Line Replacement Works
#     - Line numbers are 1-based
#     - start_line and end_line are inclusive
#     - start_line=0 means the beginning of the file
#     - end_line=0 means the end of the file
#     - start_line=0 and end_line=0 replaces the entire file

#     Args:
#         file_path (str): File path inside container workspace
#         content (str): Replacement text to write into the file or target line range
#         start_line (int): 1-based inclusive start line. Use 0 to start from the beginning of the file.
#         end_line (int): 1-based inclusive end line. Use 0 to replace until the end of the file.

#     Returns:
#         Updated file preview with file path and resulting content

#     ## Important Guidelines
#     - Read the latest file content before modifying line ranges
#     - Use exact workspace-relative paths
#     - Do not include preview prefixes like `[12] ` inside the replacement content
#     - Prefer whole-file replacement when the change is large or line positions are uncertain
#     - Only one file can be modified at the same time
#     """

#     writer = get_stream_writer()

#     def fail(message: str) -> Command:
#         writer({
#             "tool_chunk_rtn": {
#                 "tool_call_id": tool_call_id,
#                 "tool_chunk_rtn": "modify_file",
#                 "content": message,
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         })
#         return Command(update={
#             "messages": [ToolMessage(message, tool_call_id=tool_call_id)]
#         })

#     writer({
#         "tool_chunk_rtn": {
#             "tool_call_id": tool_call_id,
#             "tool_chunk_rtn": "modify_file",
#             "content": (
#                 f"Modifying file: {file_path}\n"
#                 f"Range: {start_line} - {end_line}\n\n"
#                 f"'''text\n{content}\n'''"
#             ),
#             "chunk_position": "start",
#             "status": "success",
#         }
#     })

#     config = (state or {}).get("config", {})
#     sandbox_root = config.get("work_dir")
#     container_id = (state or {}).get("sandbox")

#     if not container_id or not sandbox_root:
#         return fail("Sandbox not configured.")

#     if not file_path or not file_path.strip():
#         return fail("File path cannot be empty.")

#     if content is None:
#         return fail("Content cannot be null.")

#     try:
#         host_path = file_system.get_file_path_in_host(
#             file_path=file_path,
#             container_workdir="/workspace",
#             host_root=sandbox_root,
#             must_exist=False,
#         )

#         if not isinstance(host_path, Path):
#             return fail("Failed to resolve workspace file path.")

#         async with file_system.file_lock(host_path, state.get("agent_name", "Unnamed agent"), "modify"):
#             original = ""
#             if host_path.exists():
#                 original = _read_text_preserve_newlines(host_path)

#             result = _apply_line_replacement(
#                 file_path=file_path,
#                 original=original,
#                 content=content,
#                 start_line=start_line,
#                 end_line=end_line,
#             )

#             _write_text_atomic(host_path, result.updated_text)

#         preview_text = _render_preview_block(
#             result.file_path,
#             _render_preview(
#                 text=result.updated_text,
#                 changed_range=result.changed_range,
#             ),
#         )

#         writer({
#             "tool_chunk_rtn": {
#                 "tool_call_id": tool_call_id,
#                 "tool_chunk_rtn": "modify_file",
#                 "content": f"Modified file successfully: {file_path}",
#                 "chunk_position": "end",
#                 "status": "success",
#             }
#         })

#         return Command(update={
#             "messages": [
#                 ToolMessage(preview_text, tool_call_id=tool_call_id)
#             ]
#         })

#     except Exception as e:
#         return fail(str(e))