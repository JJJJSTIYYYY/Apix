import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from apix.agent.store.core.server.file_store import file_server as file_module
from apix.agent.store.core.server.file_store.file_server import FileService


def make_skill_zip(path: Path, frontmatter: str | None, *, nested=True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    member = "sample-skill/SKILL.md" if nested else "SKILL.md"
    with zipfile.ZipFile(path, "w") as archive:
        if frontmatter is not None:
            archive.writestr(member, frontmatter)
        else:
            archive.writestr("README.md", "no skill metadata")
    return path


@pytest.mark.asyncio
async def test_save_file_copies_sources_and_returns_workspace_paths(tmp_path):
    source_one = tmp_path / "first.txt"
    source_two = tmp_path / "second.bin"
    source_one.write_text("hello", encoding="utf-8")
    source_two.write_bytes(b"\x00\x01")
    workspace = tmp_path / "workspace"

    result = await FileService().save_file(
        {
            "file_path": [str(source_one), str(source_two)],
            "workspace": str(workspace),
        }
    )

    assert result["success"] is True
    assert result["messages"] == [
        {
            "file_name": "first.txt",
            "saved_path": str(workspace / "user_upload" / "first.txt"),
            "ws_saved_path": "user_upload/first.txt",
        },
        {
            "file_name": "second.bin",
            "saved_path": str(workspace / "user_upload" / "second.bin"),
            "ws_saved_path": "user_upload/second.bin",
        },
    ]
    assert (workspace / "user_upload" / "first.txt").read_text() == "hello"
    assert source_one.exists(), "save_file copies rather than moves uploads"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload_factory",
    [
        lambda root: {"workspace": str(root)},
        lambda root: {"file_path": [str(root / "missing")], "workspace": str(root)},
        lambda root: {"file_path": [str(root)], "workspace": str(root / "ws")},
    ],
)
async def test_save_file_reports_invalid_payloads(tmp_path, payload_factory):
    result = await FileService().save_file(payload_factory(tmp_path))
    assert result["success"] is False
    assert result["messages"].startswith("fail:")


@pytest.mark.asyncio
async def test_handle_skill_package_moves_valid_zip_and_extracts_metadata(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(file_module, "BASE_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "apix.agent.store.core.server.file_store.file_server.uuid4",
        lambda: SimpleNamespace(hex="fixedid")
    )
    source = make_skill_zip(
        tmp_path / "skill.zip",
        "---\nname: demo\ndescription: Demo skill\nversion: 2.1.0\n---\n# Demo\n",
    )
    expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    expected_size = source.stat().st_size

    result = await FileService().handle_skill_package(
        {"user_uid": "user-1", "file_path": [str(source)]}
    )

    assert result["success"] is True
    assert len(result["messages"]) == 1
    info = result["messages"][0]
    assert info == {
        "skill_id": "fixedid",
        "skill_name": "demo",
        "skill_description": "Demo skill",
        "skill_version": "2.1.0",
        "package_path": str(
            tmp_path / "data" / "user-1" / "apix_skills" / "skill.zip"
        ),
        "package_size": expected_size,
        "package_sha256": expected_hash,
    }
    assert not source.exists()
    assert Path(info["package_path"]).is_file()


@pytest.mark.asyncio
async def test_handle_skill_package_uses_default_version(monkeypatch, tmp_path):
    monkeypatch.setattr(file_module, "BASE_DIR", str(tmp_path))
    source = make_skill_zip(
        tmp_path / "skill.zip",
        "---\nname: demo\ndescription: Demo skill\n---\nbody\n",
        nested=False,
    )

    result = await FileService().handle_skill_package(
        {"user_uid": "user-1", "file_path": [str(source)]}
    )

    assert result["success"] is True
    assert result["messages"][0]["skill_version"] == "0.0.1"


@pytest.mark.asyncio
async def test_handle_skill_package_adds_incrementing_index_on_name_conflict(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(file_module, "BASE_DIR", str(tmp_path / "data"))
    skills_dir = tmp_path / "data" / "user-1" / "apix_skills"
    skills_dir.mkdir(parents=True)
    existing = skills_dir / "skill.zip"
    existing.write_bytes(b"existing package must not be overwritten")
    frontmatter = "---\nname: demo\ndescription: Demo skill\n---\nbody\n"
    first = make_skill_zip(tmp_path / "first" / "skill.zip", frontmatter)
    second = make_skill_zip(tmp_path / "second" / "skill.zip", frontmatter)

    result = await FileService().handle_skill_package(
        {"user_uid": "user-1", "file_path": [str(first), str(second)]}
    )

    assert result["success"] is True
    assert [Path(item["package_path"]).name for item in result["messages"]] == [
        "skill_1.zip",
        "skill_2.zip",
    ]
    assert existing.read_bytes() == b"existing package must not be overwritten"
    assert sorted(path.name for path in skills_dir.iterdir()) == [
        "skill.zip",
        "skill_1.zip",
        "skill_2.zip",
    ]


@pytest.mark.asyncio
async def test_same_package_name_is_isolated_by_user(monkeypatch, tmp_path):
    monkeypatch.setattr(file_module, "BASE_DIR", str(tmp_path / "data"))
    frontmatter = "---\nname: demo\ndescription: Demo skill\n---\nbody\n"
    first = make_skill_zip(tmp_path / "first" / "skill.zip", frontmatter)
    second = make_skill_zip(tmp_path / "second" / "skill.zip", frontmatter)
    service = FileService()

    first_result = await service.handle_skill_package(
        {"user_uid": "user-1", "file_path": [str(first)]}
    )
    second_result = await service.handle_skill_package(
        {"user_uid": "user-2", "file_path": [str(second)]}
    )

    assert Path(first_result["messages"][0]["package_path"]) == (
        tmp_path / "data" / "user-1" / "apix_skills" / "skill.zip"
    )
    assert Path(second_result["messages"][0]["package_path"]) == (
        tmp_path / "data" / "user-2" / "apix_skills" / "skill.zip"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frontmatter,error_text",
    [
        (None, "SKILL.md is missing"),
        ("# no frontmatter", "missing YAML frontmatter"),
        ("---\nname: demo\n", "Invalid SKILL.md YAML frontmatter format"),
        ("---\n- item\n---\n", "frontmatter must be an object"),
        ("---\nname: demo\n---\n", "Missing skill metadata: description"),
    ],
)
async def test_invalid_skill_package_is_deleted(
    monkeypatch, tmp_path, frontmatter, error_text
):
    monkeypatch.setattr(file_module, "BASE_DIR", str(tmp_path))
    skills_dir = tmp_path / "user-1" / "apix_skills"
    source = make_skill_zip(tmp_path / "invalid.zip", frontmatter)

    result = await FileService().handle_skill_package(
        {"user_uid": "user-1", "file_path": [str(source)]}
    )

    assert result["success"] is False
    assert error_text in result["messages"]
    assert list(skills_dir.iterdir()) == []
    assert not source.exists(), "the selected archive was moved before validation"


@pytest.mark.asyncio
async def test_handle_skill_package_rejects_non_zip_without_moving_it(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(file_module, "BASE_DIR", str(tmp_path))
    source = tmp_path / "skill.txt"
    source.write_text("not a zip", encoding="utf-8")

    result = await FileService().handle_skill_package(
        {"user_uid": "user-1", "file_path": [str(source)]}
    )

    assert result["success"] is False
    assert "must be a zip file" in result["messages"]
    assert source.exists()
