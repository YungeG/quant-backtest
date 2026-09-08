from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any


class AcquisitionError(RuntimeError):
    """A provider acquisition failed before publishing any local authority."""


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def publish_directory(
    output_dir: str | Path,
    files: dict[str, bytes],
) -> None:
    output = Path(output_dir).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700)
    except FileExistsError as error:
        raise AcquisitionError(f"output directory already exists: {output}") from error
    try:
        ordered = sorted(
            files.items(), key=lambda item: item[0] == "acquisition-receipt.json"
        )
        for relative, source_bytes in ordered:
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(source_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise
        directory = os.open(output, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise


def require_new_output(output_dir: str | Path) -> None:
    output = Path(output_dir).resolve()
    if output.exists():
        raise AcquisitionError(f"output directory already exists: {output}")


Fetch = Callable[[str], tuple[int, bytes]]
Post = Callable[[str, dict[str, object]], tuple[int, bytes]]
