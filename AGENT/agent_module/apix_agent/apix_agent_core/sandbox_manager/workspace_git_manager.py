import os
import asyncio
import time
from typing import List, Dict, Optional


class WorkspaceGitManager:
    """
    Global singleton WorkspaceGitManager.

    Design:
        - Stateless: all methods require explicit repo_path
        - No internal locking (caller must ensure concurrency safety)
        - Lightweight and predictable behavior
    """

    _instance = None

    def __new__(cls):
        # Ensure singleton instance
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Managed .gitignore rules (authoritative source)
        self.gitignore = [
            "__pycache__/",
            "*.pyc",
            ".DS_Store",
            "npm-debug.log*",
            "yarn-debug.log*",
            "yarn-error.log*",
            "pnpm-debug.log*",
            ".env",
            ".env.*",
            "*.local",
            ".vscode/",
            ".idea/",
            ".tmp_exec"
        ]

    async def _run_git(self, repo_path: str, args: List[str]) -> str:
        """
        Execute a git command asynchronously.

        Args:
            repo_path: Target repository path
            args: Git arguments

        Returns:
            stdout output

        Raises:
            FileNotFoundError: if repo_path does not exist
            RuntimeError: if git command fails
        """
        repo_path = os.path.abspath(repo_path)

        if not os.path.exists(repo_path):
            raise FileNotFoundError(f"Repo path not found: {repo_path}")

        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr.decode().strip())

        return stdout.decode().strip()

    async def init_git(self, repo_path: str, *, ensure_parent: bool = False) -> None:
        """
        Initialize git repository.

        Args:
            repo_path: Target directory
            ensure_parent: Create directory if not exists

        Behavior:
            - Initializes git repo if not exists
            - Sets default user config
        """
        repo_path = os.path.abspath(repo_path)

        if ensure_parent:
            os.makedirs(repo_path, exist_ok=True)

        if not os.path.exists(repo_path):
            raise FileNotFoundError(repo_path)

        if not os.path.exists(os.path.join(repo_path, ".git")):
            await self._run_git(repo_path, ["init"])
            await self._run_git(repo_path, ["config", "user.name", "WorkspaceBot"])
            await self._run_git(repo_path, ["config", "user.email", "bot@example.com"])

    async def ensure_gitignore(self, repo_path: str, rewrite: bool = True) -> None:
        """
        Ensure .gitignore matches managed rules.

        Args:
            repo_path: Repository path
            rewrite: Whether to overwrite or append

        Behavior:
            - Enforces controlled ignore rules
        """
        repo_path = os.path.abspath(repo_path)
        gitignore_path = os.path.join(repo_path, ".gitignore")

        existing = set()

        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                existing = set(line.strip() for line in f if line.strip())

        target = set(self.gitignore)

        if rewrite:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                for r in sorted(target):
                    f.write(r + "\n")
        else:
            missing = target - existing
            if missing:
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    for r in sorted(missing):
                        f.write(r + "\n")

    async def commit_all(self, repo_path: str, message: Optional[str] = None) -> Optional[str]:
        """
        Commit all changes (auto-branch if detached).

        Args:
            repo_path: Repository path
            message: Commit message

        Returns:
            New commit id, or None if no changes

        Behavior:
            - Auto creates branch if in detached HEAD
        """
        if message is None:
            message = f"Auto commit at {int(time.time())}"

        if await self.is_detached_head(repo_path):
            current = await self.get_current_commit(repo_path)
            branch = f"branch_{int(time.time())}_{current[:6]}"
            await self._run_git(repo_path, ["checkout", "-b", branch])

        await self._run_git(repo_path, ["add", "."])

        status = await self._run_git(repo_path, ["status", "--porcelain"])
        if not status:
            return None

        await self._run_git(repo_path, ["commit", "-m", message])

        return await self._run_git(repo_path, ["rev-parse", "HEAD"])

    async def is_detached_head(self, repo_path: str) -> bool:
        """
        Check if HEAD is detached.

        Args:
            repo_path: Repository path

        Returns:
            True if detached, False otherwise
        """
        output = await self._run_git(repo_path, ["symbolic-ref", "-q", "HEAD"])
        return output == ""

    async def get_current_commit(self, repo_path: str) -> str:
        """
        Get current commit id.
        """
        return await self._run_git(repo_path, ["rev-parse", "HEAD"])

    async def get_current_branch(self, repo_path: str) -> Optional[str]:
        """
        Get current branch name.

        Returns:
            None if detached
        """
        output = await self._run_git(repo_path, ["branch", "--show-current"])
        return output if output else None

    async def checkout_commit(self, repo_path: str, commit_id: str, force: bool = True):
        """
        Checkout a specific commit.

        Args:
            repo_path: Repository path
            commit_id: Target commit
            force: Discard local changes

        Behavior:
            - Enters detached HEAD
        """
        # Validate commit exists (better error)
        await self._run_git(repo_path, ["rev-parse", "--verify", commit_id])

        if force:
            await self._run_git(repo_path, ["reset", "--hard"])

        await self._run_git(repo_path, ["checkout", commit_id])

    async def get_commit_graph(self, repo_path: str) -> Dict[str, Dict]:
        """
        Build commit DAG.

        Returns:
            commit_id -> { parents, children }
        """
        output = await self._run_git(repo_path, ["rev-list", "--all", "--parents"])

        nodes: Dict[str, Dict] = {}

        for line in output.splitlines():
            parts = line.strip().split()
            commit = parts[0]
            parents = parts[1:]

            nodes[commit] = {
                "id": commit,
                "parents": parents,
                "children": []
            }

        for node in nodes.values():
            for p in node["parents"]:
                if p in nodes:
                    nodes[p]["children"].append(node["id"])

        return nodes
    
    async def get_commit_history(self, repo_path: str, limit: int = 50):
        log_format = "%H|%ct|%s"

        output = await self._run_git(repo_path, [
            "log",
            f"-n {limit}",
            f"--pretty=format:{log_format}"
        ])

        commits = []
        if not output:
            return commits

        for line in output.split("\n"):
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue

            commit_id, timestamp, message = parts
            commits.append({
                "commit_id": commit_id,
                "timestamp": int(timestamp),
                "message": message
            })

        return commits


    async def get_reflog(self, repo_path: str, limit: int = 50):
        log_format = "%H|%ct|%gs"

        output = await self._run_git(repo_path, [
            "reflog",
            f"-n {limit}",
            f"--pretty=format:{log_format}"
        ])

        logs = []
        if not output:
            return logs

        for line in output.split("\n"):
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue

            commit_id, timestamp, message = parts
            logs.append({
                "commit_id": commit_id,
                "timestamp": int(timestamp),
                "message": message
            })

        return logs


workspace_git_manager = WorkspaceGitManager()