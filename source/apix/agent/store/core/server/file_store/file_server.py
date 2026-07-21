import asyncio
import hashlib
import shutil
import uuid
from pathlib import Path
import zipfile
import yaml

from apix.common.utils.logger import logger
from apix.config.base_config import BASE_DIR


class FileService:
    """
    File system service.
    """

    # --------------------------------------------------
    # Save Files
    # --------------------------------------------------
    
    async def save_file(self, payload: dict) -> dict:
        """
        Copy uploaded files from local paths into the workspace.

        Args:
            payload: Dict, the format is {
                "file_path": list[str],  # local paths of uploaded files
                "workspace": str,        # workspace path
            }

        Returns:
            {
                "success": True,
                "messages": [
                    {
                        "file_name": str,      # file name
                        "saved_path": str,     # absolute path in local filesystem
                        "ws_saved_path": str,  # workspace-relative path
                    },
                    ...
                ],
            }
        """
        logger.trace()

        try:
            source_paths: list[str] = payload["file_path"]
            workspace = Path(payload["workspace"]).expanduser().resolve()

            upload_dir = workspace / "user_upload"
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_info: list[dict] = []

            for source_path in source_paths:
                source = Path(source_path).expanduser().resolve(strict=True)

                if not source.is_file():
                    raise ValueError(f"Source path is not a file: {source}")

                destination = upload_dir / source.name

                # File copying is blocking, so run it outside the event loop.
                await asyncio.to_thread(shutil.copy2, source, destination)

                file_info.append(
                    {
                        "file_name": source.name,
                        "saved_path": str(destination),
                        "ws_saved_path": destination.relative_to(workspace).as_posix(),
                    }
                )

                logger.info(f"Copied source={source} destination={destination}")

            return {
                "success": True,
                "messages": file_info,
            }

        except Exception as error:
            logger.exception(f"Error: {type(error).__name__}: {error}")
            return {
                "success": False,
                "messages": f"fail: {error}",
            }

    # --------------------------------------------------
    # Skills
    # --------------------------------------------------

    @staticmethod
    def _next_available_package_path(skills_dir: Path, file_name: str) -> Path:
        """Return a free path, adding ``_<index>`` before the extension."""
        source_name = Path(file_name)
        candidate = skills_dir / source_name.name
        index = 1

        while candidate.exists():
            candidate = skills_dir / f"{source_name.stem}_{index}{source_name.suffix}"
            index += 1

        return candidate

    async def handle_skill_package(self, payload: dict) -> dict:
        """
        Move and analyze uploaded skill zip files.

        Anthropic skill spec:
            Skill package must contain SKILL.md with YAML frontmatter.

        Args:
            payload = {
                "user_uid": str,
                "file_path": list[str]
            }

        Return:
            {
                "success": bool,
                "user_uid": str,
                "messages": [
                    {
                        "skill_id": str, # skill unique id
                        "skill_name": str, # skill name from yaml head in SKILL.md
                        "skill_description": str, # skill description from yaml head in SKILL.md
                        "skill_version": str, # skill version from yaml head in SKILL.md
                        "package_path": str, # skill zip path in local file system
                        "package_size": int, # skill zip size
                        "package_sha256": str, # zip sha256
                    }
                ]
            }
        """
        logger.trace()

        user_uid = payload["user_uid"]

        try:
            user_uid: str = payload["user_uid"]
            source_paths: list[str] = payload["file_path"]

            skills_dir = (
                Path(BASE_DIR) / user_uid / "apix_skills"
            ).expanduser().resolve()
            skills_dir.mkdir(parents=True, exist_ok=True)

            skills_info: list[dict] = []

            for source_path in source_paths:
                source = Path(source_path).expanduser().resolve(strict=True)

                if not source.is_file():
                    raise ValueError(f"Source path is not a file: {source}")

                if source.suffix.lower() != ".zip":
                    raise ValueError(f"Skill package must be a zip file: {source.name}")

                skill_id = uuid.uuid4().hex

                # Preserve the uploaded name and add an index on conflicts.
                package_path = self._next_available_package_path(
                    skills_dir, source.name
                )

                # Move the selected zip into BASE_DIR/apix_skills.
                await asyncio.to_thread(shutil.move, str(source), str(package_path))

                try:
                    # --------------------------------------------------
                    # Read SKILL.md from zip
                    # --------------------------------------------------
                    with zipfile.ZipFile(package_path, "r") as zip_file:
                        skill_md_path = next(
                            (
                                name
                                for name in zip_file.namelist()
                                if Path(name).name == "SKILL.md"
                            ),
                            None,
                        )

                        if not skill_md_path:
                            raise ValueError("SKILL.md is missing")

                        skill_md = zip_file.read(skill_md_path).decode("utf-8")

                    # --------------------------------------------------
                    # Parse YAML frontmatter
                    # --------------------------------------------------
                    if not skill_md.startswith("---"):
                        raise ValueError(
                            "SKILL.md is missing YAML frontmatter"
                        )

                    parts = skill_md.split("---", 2)

                    if len(parts) < 3:
                        raise ValueError(
                            "Invalid SKILL.md YAML frontmatter format"
                        )

                    metadata = yaml.safe_load(parts[1]) or {}

                    if not isinstance(metadata, dict):
                        raise ValueError(
                            "SKILL.md YAML frontmatter must be an object"
                        )

                    required_fields = {
                        "name": metadata.get("name"),
                        "description": metadata.get("description"),
                        "version": metadata.get("version") or '0.0.1',
                    }

                    missing_fields = [
                        field_name
                        for field_name, field_value in required_fields.items()
                        if not field_value
                    ]

                    if missing_fields:
                        raise ValueError(
                            "Missing skill metadata: "
                            + ", ".join(missing_fields)
                        )

                    skill_name = str(required_fields["name"])
                    skill_description = str(required_fields["description"])
                    skill_version = str(required_fields["version"])

                    # --------------------------------------------------
                    # Calculate package information
                    # --------------------------------------------------
                    package_size = package_path.stat().st_size

                    hasher = hashlib.sha256()

                    with package_path.open("rb") as package_file:
                        while chunk := package_file.read(1024 * 1024):
                            hasher.update(chunk)

                    package_sha256 = hasher.hexdigest()

                except Exception as error:
                    # Remove the moved zip when validation or parsing fails.
                    try:
                        package_path.unlink(missing_ok=True)
                    except Exception as cleanup_error:
                        logger.warning(
                            f"Failed to delete invalid skill package "
                            f"path={package_path}: {cleanup_error}"
                        )

                    raise ValueError(
                        f"Invalid skill package {source.name}: {error}"
                    ) from error

                skills_info.append(
                    {
                        "skill_id": skill_id,
                        "skill_name": skill_name,
                        "skill_description": skill_description,
                        "skill_version": skill_version,
                        "package_path": str(package_path),
                        "package_size": package_size,
                        "package_sha256": package_sha256,
                    }
                )

                logger.info(
                    f"Skill package saved "
                    f"user_uid={user_uid} "
                    f"skill_id={skill_id} "
                    f"skill_name={skill_name} "
                    f"package_path={package_path}"
                )

            return {
                "success": True,
                "messages": skills_info,
            }

        except Exception as error:
            logger.exception(
                f"Error: {type(error).__name__}: {error}"
            )

            return {
                "success": False,
                "messages": f"fail: {error}",
            }



file_server = FileService()
