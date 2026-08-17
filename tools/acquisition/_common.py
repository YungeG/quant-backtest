from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
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
    if output.exists():
        raise AcquisitionError(f"output directory already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for relative, source_bytes in files.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source_bytes)
        os.replace(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def require_new_output(output_dir: str | Path) -> None:
    output = Path(output_dir).resolve()
    if output.exists():
        raise AcquisitionError(f"output directory already exists: {output}")


Fetch = Callable[[str], tuple[int, bytes]]
Post = Callable[[str, dict[str, object]], tuple[int, bytes]]
