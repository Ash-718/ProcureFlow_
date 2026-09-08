"""
Uploaded-file storage on the local filesystem.

Port of Java's `FileStorageService`. The stored name is
``<uuid>_<sanitised original>``: the UUID prevents collisions between two
users uploading `certificate.pdf`, and the sanitisation reduces the original to
``[A-Za-z0-9._-]`` so a crafted filename cannot escape the storage root.

Only the generated name is persisted, never a client-supplied path.
"""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import ApiException
from app.utils.logging import get_logger

log = get_logger("services.file_storage")

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9._-]")


class FileStorageService:
    def __init__(self, root: Path | None = None):
        self.root = (root or settings.upload_dir).resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ApiException(500, f"Could not create the storage directory: {exc}") from exc

    def store(self, stream: BinaryIO, original_filename: str | None) -> str:
        """
        Persist an uploaded stream and return the generated relative name.

        An empty upload is a 400 before anything is written, matching Java.
        """
        original = Path(original_filename or "file").name or "file"
        safe_name = f"{uuid.uuid4()}_{_UNSAFE_CHARS.sub('_', original)}"
        destination = self.root / safe_name

        try:
            with destination.open("wb") as handle:
                shutil.copyfileobj(stream, handle)
        except OSError as exc:
            log.exception("Failed to store an upload at %s", destination)
            raise ApiException(500, "Failed to store uploaded file") from exc

        if destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)
            raise ApiException.bad_request("Uploaded file is empty")

        return safe_name

    def resolve(self, relative_path: str) -> Path:
        """
        Absolute path for a stored name, refusing anything outside the root.

        `store` only ever produces safe names, so this guards against a
        tampered database row rather than ordinary input.
        """
        candidate = (self.root / relative_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise ApiException.bad_request("Invalid document path")
        return candidate

    def delete(self, relative_path: str) -> None:
        try:
            self.resolve(relative_path).unlink(missing_ok=True)
        except (OSError, ApiException):
            log.warning("Could not delete stored file %s", relative_path)
