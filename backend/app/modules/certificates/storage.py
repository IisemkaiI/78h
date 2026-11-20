"""Private local storage for pre-generated certificate PDFs."""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
import uuid
from pathlib import Path

_STORAGE_KEY = re.compile(r"^[a-f0-9]{32}\.pdf$")


class CertificateStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @staticmethod
    def new_key() -> str:
        return f"{uuid.uuid4().hex}.pdf"

    def _path(self, key: str) -> Path:
        if not _STORAGE_KEY.fullmatch(key):
            raise ValueError("Invalid certificate storage key.")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Certificate storage key escaped its private root.")
        return path

    async def write(self, key: str, content: bytes) -> None:
        await asyncio.to_thread(self._write_sync, key, content)

    def _write_sync(self, key: str, content: bytes) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._root, 0o700)
        except OSError:
            pass
        target = self._path(key)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".certificate-",
                suffix=".tmp",
                dir=self._root,
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            try:
                os.chmod(temporary_path, 0o600)
            except OSError:
                pass
            os.replace(temporary_path, target)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._read_sync, key)

    def _read_sync(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError("Certificate PDF is missing.")
        return path.read_bytes()

    async def remove(self, key: str) -> None:
        await asyncio.to_thread(self._remove_sync, key)

    def _remove_sync(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
