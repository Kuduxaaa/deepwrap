from __future__ import annotations

import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from pathlib import Path
from typing import Any, Callable

from deepwrap.function_calling import Tool


MAX_OUTPUT_CHARS = 1_000_000


def _trim(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_OUTPUT_CHARS:
        return value, False
    return value[:MAX_OUTPUT_CHARS], True


class NativeTools:
    """Built-in host command, code, search, and filesystem operations."""

    def __init__(self, working_directory: str | Path | None = None, timeout: float = 30.0):
        self.working_directory = Path(working_directory or Path.cwd()).expanduser().resolve()
        self.timeout = timeout
        self._jobs_directory = Path(tempfile.mkdtemp(prefix="deepwrap-jobs-"))
        self._jobs: dict[str, dict[str, Any]] = {}
        self._jobs_lock = threading.RLock()

    def _path(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.working_directory / candidate
        return candidate.resolve()

    def exec(self, command: str, timeout: float | None = None) -> dict[str, Any]:
        """Execute a command through the operating system's default shell."""

        try:
            completed = subprocess.run(
                command,
                cwd=self.working_directory,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                check=False,
            )
            stdout, stdout_truncated = _trim(completed.stdout)
            stderr, stderr_truncated = _trim(completed.stderr)
            return {
                "exit_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "truncated": stdout_truncated or stderr_truncated,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "exit_code": None,
                "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
                "timed_out": True,
            }

    def exec_code(self, code: str, timeout: float | None = None) -> dict[str, Any]:
        """Run Python code in a separate interpreter with installed modules available."""

        try:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                check=False,
            )
            stdout, stdout_truncated = _trim(completed.stdout)
            stderr, stderr_truncated = _trim(completed.stderr)
            return {
                "exit_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "truncated": stdout_truncated or stderr_truncated,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "exit_code": None,
                "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
                "timed_out": True,
            }

    def start_job(
        self,
        command: str,
        working_directory: str | None = None,
    ) -> dict[str, Any]:
        """Start a shell command in its own background process and return immediately."""

        cwd = self._path(working_directory) if working_directory else self.working_directory
        if not cwd.is_dir():
            raise NotADirectoryError(f"Working directory does not exist: {cwd}")
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        stdout_path = self._jobs_directory / f"{job_id}.stdout.log"
        stderr_path = self._jobs_directory / f"{job_id}.stderr.log"
        stdout_handle = stdout_path.open("wb")
        stderr_handle = stderr_path.open("wb")
        popen_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "shell": True,
            "stdout": stdout_handle,
            "stderr": stderr_handle,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        try:
            process = subprocess.Popen(command, **popen_kwargs)
        finally:
            stdout_handle.close()
            stderr_handle.close()

        record = {
            "id": job_id,
            "command": command,
            "cwd": str(cwd),
            "process": process,
            "pid": process.pid,
            "started_at": time.time(),
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }
        with self._jobs_lock:
            self._jobs[job_id] = record
        return self.job_status(job_id)

    def _job(self, job_id: str) -> dict[str, Any]:
        with self._jobs_lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise ValueError(f"Unknown background job: {job_id}")
        return record

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Return the current lifecycle state of a background job."""

        record = self._job(job_id)
        process: subprocess.Popen = record["process"]
        exit_code = process.poll()
        if exit_code is None:
            state = "running"
        elif record.get("stopped"):
            state = "stopped"
        else:
            state = "completed" if exit_code == 0 else "failed"
        return {
            "id": job_id,
            "state": state,
            "pid": record["pid"],
            "command": record["command"],
            "working_directory": record["cwd"],
            "exit_code": exit_code,
            "elapsed_seconds": round(time.time() - record["started_at"], 3),
        }

    def list_jobs(self) -> dict[str, Any]:
        """List all background jobs started by this client."""

        with self._jobs_lock:
            job_ids = list(self._jobs)
        jobs = [self.job_status(job_id) for job_id in job_ids]
        return {"jobs": jobs, "count": len(jobs)}

    def job_output(
        self,
        job_id: str,
        stream: str = "stdout",
        offset: int = 0,
        limit: int = 50_000,
    ) -> dict[str, Any]:
        """Read a bounded byte range from a running or completed job's logs."""

        if stream not in {"stdout", "stderr"}:
            raise ValueError("stream must be 'stdout' or 'stderr'")
        record = self._job(job_id)
        path: Path = record[f"{stream}_path"]
        offset = max(0, offset)
        limit = max(1, min(limit, 200_000))
        with path.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read(limit + 1)
        has_more = len(raw) > limit
        content_bytes = raw[:limit]
        next_offset = offset + len(content_bytes)
        return {
            "id": job_id,
            "stream": stream,
            "content": content_bytes.decode("utf-8", errors="replace"),
            "offset": offset,
            "bytes_returned": len(content_bytes),
            "has_more": has_more,
            "next_offset": next_offset,
            "state": self.job_status(job_id)["state"],
        }

    def stop_job(self, job_id: str, force: bool = False) -> dict[str, Any]:
        """Stop a background job and its process group."""

        record = self._job(job_id)
        process: subprocess.Popen = record["process"]
        if process.poll() is not None:
            return self.job_status(job_id)
        record["stopped"] = True
        if os.name == "nt":
            if force:
                process.kill()
            else:
                process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        status = self.job_status(job_id)
        status["stopped"] = True
        return status

    def read_file(
        self,
        path: str,
        encoding: str = "utf-8",
        offset: int = 0,
        limit: int | None = 400,
    ) -> dict[str, Any]:
        """Read a text file, optionally selecting a line range."""

        file_path = self._path(path)
        text = file_path.read_text(encoding=encoding)
        lines = text.splitlines(keepends=True)
        offset = max(0, offset)
        resolved_limit = 400 if limit is None else max(1, min(limit, 2000))
        selected = lines[offset : offset + resolved_limit]
        content, truncated = _trim("".join(selected))
        next_offset = offset + len(selected)
        return {
            "path": str(file_path),
            "content": content,
            "total_lines": len(lines),
            "offset": offset,
            "lines_returned": len(selected),
            "has_more": next_offset < len(lines),
            "next_offset": next_offset if next_offset < len(lines) else None,
            "truncated": truncated,
        }

    def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_parents: bool = True,
    ) -> dict[str, Any]:
        """Write complete text content to a file."""

        file_path = self._path(path)
        if create_parents:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding=encoding)
        return {"path": str(file_path), "bytes_written": len(content.encode(encoding))}

    def edit_file(
        self,
        path: str,
        old: str,
        new: str,
        replace_all: bool = False,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Safely replace an exact string, rejecting missing or ambiguous matches."""

        if not old:
            raise ValueError("old must not be empty")
        file_path = self._path(path)
        content = file_path.read_text(encoding=encoding)
        occurrences = content.count(old)
        if occurrences == 0:
            raise ValueError(f"Target text was not found in {file_path}")
        if occurrences > 1 and not replace_all:
            raise ValueError(
                f"Target text occurs {occurrences} times in {file_path}; "
                "set replace_all=true or provide a more specific match."
            )
        updated = content.replace(old, new, -1 if replace_all else 1)
        file_path.write_text(updated, encoding=encoding)
        return {
            "path": str(file_path),
            "replacements": occurrences if replace_all else 1,
        }

    def grep(
        self,
        pattern: str,
        path: str = ".",
        glob: list[str] | None = None,
        case_sensitive: bool = True,
        max_results: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search file contents with regex and optional glob filters."""

        search_path = self._path(path)
        offset = max(0, offset)
        max_results = max(1, min(max_results, 2000))
        rg = shutil.which("rg")
        if rg:
            command = [
                rg,
                "--line-number",
                "--color",
                "never",
                "--hidden",
                "--no-ignore",
            ]
            if not case_sensitive:
                command.append("--ignore-case")
            for item in glob or []:
                command.extend(["--glob", item])
            command.extend([pattern, str(search_path)])
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            all_matches = completed.stdout.splitlines()
            matches = all_matches[offset : offset + max_results]
            if completed.returncode not in {0, 1}:
                raise RuntimeError(completed.stderr.strip() or "rg search failed")
            next_offset = offset + len(matches)
            has_more = next_offset < len(all_matches)
            return {
                "matches": matches,
                "count": len(matches),
                "offset": offset,
                "has_more": has_more,
                "next_offset": next_offset if has_more else None,
                "engine": "rg",
            }

        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
        patterns = glob or ["**/*"]
        candidates: set[Path] = set()
        if search_path.is_file():
            candidates.add(search_path)
        else:
            for item in patterns:
                recursive_pattern = item[3:] if item.startswith("**/") else item
                candidates.update(
                    candidate
                    for candidate in search_path.rglob(recursive_pattern)
                    if candidate.is_file()
                )
        all_matches: list[str] = []
        target_count = offset + max_results + 1
        for candidate in sorted(candidates):
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, 1):
                if regex.search(line):
                    all_matches.append(f"{candidate}:{line_number}:{line}")
                    if len(all_matches) >= target_count:
                        break
            if len(all_matches) >= target_count:
                break
        matches = all_matches[offset : offset + max_results]
        has_more = len(all_matches) > offset + len(matches)
        next_offset = offset + len(matches)
        return {
            "matches": matches,
            "count": len(matches),
            "offset": offset,
            "has_more": has_more,
            "next_offset": next_offset if has_more else None,
            "engine": "python",
        }

    @property
    def definitions(self) -> tuple[Tool, ...]:
        object_schema = {"type": "object"}
        return (
            Tool("exec", "Execute any system command using the host shell.", {
                **object_schema, "properties": {"command": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["command"]
            }),
            Tool("grep", "Regex-search text in files with optional glob filters.", {
                **object_schema, "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}, "glob": {"type": "array", "items": {"type": "string"}}, "case_sensitive": {"type": "boolean", "default": True}, "max_results": {"type": "integer", "default": 200}, "offset": {"type": "integer", "default": 0}}, "required": ["pattern"]
            }),
            Tool("read_file", "Read text from any file.", {
                **object_schema, "properties": {"path": {"type": "string"}, "encoding": {"type": "string", "default": "utf-8"}, "offset": {"type": "integer", "default": 0}, "limit": {"type": "integer", "default": 400, "maximum": 2000}}, "required": ["path"]
            }),
            Tool("write_file", "Write complete text content to any file.", {
                **object_schema, "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "encoding": {"type": "string", "default": "utf-8"}, "create_parents": {"type": "boolean", "default": True}}, "required": ["path", "content"]
            }),
            Tool("edit_file", "Perform an exact targeted string replacement in a file.", {
                **object_schema, "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "replace_all": {"type": "boolean", "default": False}, "encoding": {"type": "string", "default": "utf-8"}}, "required": ["path", "old", "new"]
            }),
            Tool("exec_code", "Execute Python code with access to installed modules.", {
                **object_schema, "properties": {"code": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["code"]
            }),
            Tool("start_job", "Start a long-running command in an independent background process and return its job ID immediately. Use only on systems and networks the user is authorized to operate.", {
                **object_schema, "properties": {"command": {"type": "string"}, "working_directory": {"type": "string"}}, "required": ["command"]
            }),
            Tool("job_status", "Check whether a background job is running, completed, or failed.", {
                **object_schema, "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]
            }),
            Tool("job_output", "Read paginated stdout or stderr from a background job.", {
                **object_schema, "properties": {"job_id": {"type": "string"}, "stream": {"type": "string", "enum": ["stdout", "stderr"], "default": "stdout"}, "offset": {"type": "integer", "default": 0}, "limit": {"type": "integer", "default": 50000, "maximum": 200000}}, "required": ["job_id"]
            }),
            Tool("list_jobs", "List all background jobs owned by this DeepWrap client.", object_schema),
            Tool("stop_job", "Stop a running background job and its process tree.", {
                **object_schema, "properties": {"job_id": {"type": "string"}, "force": {"type": "boolean", "default": False}}, "required": ["job_id"]
            }),
        )

    @property
    def functions(self) -> dict[str, Callable[..., Any]]:
        return {
            "exec": self.exec,
            "grep": self.grep,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "exec_code": self.exec_code,
            "start_job": self.start_job,
            "job_status": self.job_status,
            "job_output": self.job_output,
            "list_jobs": self.list_jobs,
            "stop_job": self.stop_job,
        }
