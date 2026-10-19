"""
ProjectDNA — MCP Server Simulations
Simulates Filesystem, GitHub, Docker, and Database MCP servers.
In the Kaggle notebook these run in-process; replace with real MCP
SDK connections for production use.
"""

from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from .guardrails import GuardrailEngine


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ #
# BASE MCP SERVER                                                      #
# ------------------------------------------------------------------ #

class MCPServer:
    """Base class: logs every tool call to a trajectory list."""

    name: str = "base_mcp"

    def __init__(self):
        self.trajectory: List[Dict[str, Any]] = []

    def _log(self, agent: str, tool: str, params: Dict, result: Any) -> None:
        entry = {
            "timestamp": _timestamp(),
            "server": self.name,
            "agent": agent,
            "tool": tool,
            "params": params,
            "result_status": "ok" if not isinstance(result, Exception) else "error",
        }
        self.trajectory.append(entry)
        print(f"  [MCP:{self.name}] {agent} → {tool}({json.dumps(params)}) → {entry['result_status']}")

    def _error(self, agent: str, tool: str, params: Dict, msg: str) -> Dict:
        err = {"error_code": "MCP_ERROR", "message": msg, "agent": agent}
        self._log(agent, tool, params, Exception(msg))
        return err


# ------------------------------------------------------------------ #
# FILESYSTEM MCP                                                       #
# ------------------------------------------------------------------ #

class FilesystemMCP(MCPServer):
    """
    MCP Server 1 — Filesystem
    Exposes: read_file, write_file, list_directory, delete_file
    Scope: Sandboxed to project_root only.
    """
    name = "filesystem_mcp"

    def __init__(self, project_root: str, guardrail_engine: GuardrailEngine | None = None):
        super().__init__()
        self.root = Path(project_root)
        self.guardrail = guardrail_engine
        self._files: Dict[str, str] = {}   # in-memory virtual FS

    def write_file(self, agent: str, path: str, content: str) -> Dict:
        params = {"path": path, "content_hash": hashlib.md5(content.encode()).hexdigest()}

        # Pre-hook: secret detection
        if self.guardrail:
            result = self.guardrail.check_secret(content, path)
            if not result.allowed:
                self._log(agent, "write_file", params, Exception("BLOCKED"))
                return {"error_code": "SECRET_DETECTED", "message": result.message}

        self._files[path] = content
        self._log(agent, "write_file", params, "ok")
        return {"status": "written", "path": path, "bytes": len(content)}

    def read_file(self, agent: str, path: str) -> Dict:
        params = {"path": path}
        if path not in self._files:
            return self._error(agent, "read_file", params, f"File not found: {path}")
        content = self._files[path]
        self._log(agent, "read_file", params, "ok")
        return {"status": "ok", "path": path, "content": content}

    def list_directory(self, agent: str, path: str = "/") -> Dict:
        params = {"path": path}
        files = [f for f in self._files if f.startswith(path)]
        self._log(agent, "list_directory", params, "ok")
        return {"status": "ok", "files": files}

    def delete_file(self, agent: str, path: str) -> Dict:
        params = {"path": path}
        if path in self._files:
            del self._files[path]
        self._log(agent, "delete_file", params, "ok")
        return {"status": "deleted", "path": path}

    def get_all_files(self) -> Dict[str, str]:
        return dict(self._files)

    def export_to_disk(self, target_dir: str | Path) -> List[str]:
        """Write all virtual in-memory files to an actual directory on disk."""
        dest = Path(target_dir)
        dest.mkdir(parents=True, exist_ok=True)
        written = []
        for vpath, content in self._files.items():
            rel_path = vpath.lstrip("/\\")
            file_path = dest / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            written.append(str(file_path))
        return written


# ------------------------------------------------------------------ #
# GITHUB MCP                                                           #
# ------------------------------------------------------------------ #

class GitHubMCP(MCPServer):
    """
    MCP Server 2 — GitHub
    Exposes: git_commit, git_push, git_read, create_branch
    """
    name = "github_mcp"

    def __init__(self):
        super().__init__()
        self._commits: List[Dict] = []
        self._branches: List[str] = ["main"]

    def git_commit(self, agent: str, message: str, files: List[str]) -> Dict:
        params = {"message": message, "files": files}
        commit = {
            "sha": hashlib.md5(f"{message}{_timestamp()}".encode()).hexdigest()[:8],
            "message": message,
            "files": files,
            "timestamp": _timestamp(),
            "author": agent,
        }
        self._commits.append(commit)
        self._log(agent, "git_commit", params, "ok")
        return {"status": "committed", "sha": commit["sha"], "message": message}

    def git_push(self, agent: str, branch: str = "main") -> Dict:
        params = {"branch": branch}
        self._log(agent, "git_push", params, "ok")
        return {"status": "pushed", "branch": branch, "commits": len(self._commits)}

    def git_read(self, agent: str, path: str) -> Dict:
        params = {"path": path}
        self._log(agent, "git_read", params, "ok")
        return {"status": "ok", "commits": self._commits[-3:]}

    def create_branch(self, agent: str, branch_name: str) -> Dict:
        params = {"branch": branch_name}
        self._branches.append(branch_name)
        self._log(agent, "create_branch", params, "ok")
        return {"status": "created", "branch": branch_name}


# ------------------------------------------------------------------ #
# DOCKER MCP                                                           #
# ------------------------------------------------------------------ #

class DockerMCP(MCPServer):
    """
    MCP Server 3 — Docker
    Exposes: docker_build, docker_push, cloud_run_deploy
    """
    name = "docker_mcp"

    def docker_build(self, agent: str, project_path: str, image_tag: str) -> Dict:
        params = {"project_path": project_path, "image_tag": image_tag}
        self._log(agent, "docker_build", params, "ok")
        return {
            "status": "built",
            "image": image_tag,
            "size_mb": 142,
            "layers": 8,
        }

    def docker_push(self, agent: str, image_tag: str, registry: str) -> Dict:
        params = {"image_tag": image_tag, "registry": registry}
        self._log(agent, "docker_push", params, "ok")
        return {"status": "pushed", "registry_url": f"{registry}/{image_tag}"}

    def cloud_run_deploy(self, agent: str, image_tag: str, platform: str) -> Dict:
        params = {"image_tag": image_tag, "platform": platform}
        url = f"https://{image_tag.replace(':', '-')}.{platform}.app"
        self._log(agent, "cloud_run_deploy", params, "ok")
        return {"status": "deployed", "url": url, "platform": platform}


# ------------------------------------------------------------------ #
# DATABASE MCP                                                         #
# ------------------------------------------------------------------ #

class DatabaseMCP(MCPServer):
    """
    MCP Server 4 — Database (Custom)
    Exposes: dna_read, dna_write, dna_validate, memory_get,
             memory_set, eval_log, trajectory_log
    Simulates PostgreSQL + Redis in-memory for Kaggle notebook.
    """
    name = "database_mcp"

    def __init__(self):
        super().__init__()
        self._postgres: Dict[str, Any] = {}   # long-term memory
        self._redis: Dict[str, Any] = {}       # short-term memory
        self._trajectories: Dict[str, List] = {}

    def dna_write(self, agent: str, project_id: str, dna_dict: Dict) -> Dict:
        params = {"project_id": project_id}
        self._postgres[f"dna:{project_id}"] = dna_dict
        self._log(agent, "dna_write", params, "ok")
        return {"status": "saved", "project_id": project_id}

    def dna_read(self, agent: str, project_id: str) -> Dict:
        params = {"project_id": project_id}
        data = self._postgres.get(f"dna:{project_id}")
        if data is None:
            return self._error(agent, "dna_read", params, f"No DNA found for {project_id}")
        self._log(agent, "dna_read", params, "ok")
        return {"status": "ok", "dna": data}

    def memory_set(self, agent: str, key: str, value: Any) -> Dict:
        params = {"key": key}
        self._redis[key] = value
        self._log(agent, "memory_set", params, "ok")
        return {"status": "set", "key": key}

    def memory_get(self, agent: str, key: str) -> Dict:
        params = {"key": key}
        value = self._redis.get(key)
        self._log(agent, "memory_get", params, "ok")
        return {"status": "ok", "key": key, "value": value}

    def eval_log(self, agent: str, project_id: str, status: str, report: Dict) -> Dict:
        params = {"project_id": project_id, "status": status}
        self._postgres[f"eval:{project_id}"] = {
            "status": status, "report": report, "timestamp": _timestamp()
        }
        self._log(agent, "eval_log", params, "ok")
        return {"status": "logged", "eval_status": status}

    def trajectory_log(self, agent: str, run_id: str, entry: Dict) -> Dict:
        params = {"run_id": run_id, "agent": agent}
        if run_id not in self._trajectories:
            self._trajectories[run_id] = []
        self._trajectories[run_id].append({**entry, "timestamp": _timestamp()})
        self._log(agent, "trajectory_log", params, "ok")
        return {"status": "logged", "run_id": run_id}

    def get_trajectory(self, run_id: str) -> List[Dict]:
        return self._trajectories.get(run_id, [])

    def get_eval_status(self, project_id: str) -> str:
        record = self._postgres.get(f"eval:{project_id}", {})
        return record.get("status", "not_run")
