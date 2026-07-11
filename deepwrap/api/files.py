from __future__ import annotations

import mimetypes
import time

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from .base import BaseAPI
from deepwrap.config import Config

if TYPE_CHECKING:
    from deepwrap.client import Client


@dataclass(frozen=True)
class UploadedFile:
    """A file accepted and processed by DeepSeek."""

    id: str
    name: str
    size: int
    status: str
    is_image: bool
    model_kind: str


class FilesAPI(BaseAPI):
    """Upload files and wait for DeepSeek's asynchronous processing."""

    UPLOAD_PATH = "/api/v0/file/upload_file"
    UPLOAD_ENDPOINT = f"{Config.base_url}{UPLOAD_PATH}"
    FETCH_ENDPOINT = f"{Config.base_url}{Config.api_prefix}/file/fetch_files"

    @staticmethod
    def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("code") != 0:
            raise RuntimeError(f"file request failed: {payload}")
        data = payload.get("data", {})
        if data.get("biz_code", 0) != 0:
            raise RuntimeError(f"file request failed: {payload}")
        return data.get("biz_data", {})

    @staticmethod
    def _to_uploaded_file(raw: dict[str, Any]) -> UploadedFile:
        return UploadedFile(
            id=str(raw["id"]),
            name=str(raw.get("file_name", "")),
            size=int(raw.get("file_size", 0)),
            status=str(raw.get("status", "UNKNOWN")),
            is_image=bool(raw.get("is_image", False)),
            model_kind=str(raw.get("model_kind", "")),
        )

    def upload(self, path: str | Path, *, model: str = "vision") -> UploadedFile:
        """Upload one local file and return its initial server record."""

        file_path = Path(path).expanduser()
        if not file_path.is_file():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        size = file_path.stat().st_size
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        headers = {
            "x-thinking-enabled": "true",
            "x-model-type": model,
            "x-file-size": str(size),
            "x-ds-pow-response": self._client.pow.build_header(self.UPLOAD_PATH),
        }
        with file_path.open("rb") as handle:
            response = self._post(
                self.UPLOAD_ENDPOINT,
                files={"file": (file_path.name, handle, mime_type)},
                headers=headers,
            )

        response.raise_for_status()
        return self._to_uploaded_file(self._unwrap(response.json()))

    def fetch(self, file_ids: Iterable[str]) -> list[UploadedFile]:
        """Fetch the current processing state for one or more file IDs."""

        ids = [str(file_id) for file_id in file_ids]
        if not ids:
            return []
        response = self._get(
            self.FETCH_ENDPOINT,
            params={"file_ids": ",".join(ids)},
        )
        response.raise_for_status()
        raw = self._unwrap(response.json())
        return [self._to_uploaded_file(item) for item in raw.get("files", [])]

    def wait_until_ready(
        self,
        file_id: str,
        *,
        timeout: float = 60.0,
        poll_interval: float = 0.5,
    ) -> UploadedFile:
        """Poll until a file succeeds, fails, or the timeout expires."""

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            records = self.fetch([file_id])
            if records:
                record = records[0]
                if record.status == "SUCCESS":
                    return record
                if record.status not in {"PENDING", "PROCESSING"}:
                    raise RuntimeError(
                        f"File processing failed for {file_id}: {record.status}"
                    )
            time.sleep(poll_interval)
        raise TimeoutError(f"Timed out waiting for file processing: {file_id}")

    def upload_and_wait(
        self,
        path: str | Path,
        *,
        model: str = "vision",
        timeout: float = 60.0,
    ) -> UploadedFile:
        """Upload a file and wait until it is ready for use in a prompt."""

        uploaded = self.upload(path, model=model)
        return self.wait_until_ready(uploaded.id, timeout=timeout)
