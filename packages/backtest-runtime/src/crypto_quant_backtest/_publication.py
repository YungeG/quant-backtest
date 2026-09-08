"""Local cooperative run-publication lock helpers."""

from __future__ import annotations

from contextlib import suppress
import os
from pathlib import Path
import re
import shutil
from types import TracebackType
import unicodedata


_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")


def canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def canonical_hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 identity")
    return value


def optional_canonical_hash(name: str, value: object) -> str | None:
    if value is None:
        return None
    return canonical_hash(name, value)


class RunPublicationLock:
    """Exclusive lockfile with no wall-clock expiry or stale-lock breaking."""

    def __init__(self, *, root: Path, semantic_run_id: str) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be pathlib.Path")
        if type(semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        self.run_directory = root / "runs" / semantic_run_id
        self.path = self.run_directory / ".publication.lock"
        self._held = False
        self.release_error: OSError | None = None

    def __enter__(self) -> RunPublicationLock:
        ensure_directory(self.run_directory)
        descriptor: int | None = None
        created = False
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o444,
            )
            created = True
            with os.fdopen(descriptor, "wb", closefd=True) as file:
                descriptor = None
                file.write(b"cooperative-single-writer-v1\n")
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            if created:
                with suppress(OSError):
                    self.path.unlink(missing_ok=True)
            raise
        self._held = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._held:
            try:
                self.path.unlink()
            except OSError as error:
                self.release_error = error
            finally:
                self._held = False


def ensure_directory(directory: Path) -> None:
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise NotADirectoryError(str(current))
    for path in reversed(missing):
        path.mkdir()
        fsync_directory(path.parent)


def write_file(path: Path, source_bytes: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("xb") as file:
        file.write(source_bytes)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def make_files_read_only(directory: Path) -> None:
    for path in directory.iterdir():
        path.chmod(0o444)


def prepare_read_only_directory(directory: Path) -> None:
    make_files_read_only(directory)
    for path in directory.iterdir():
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    directory.chmod(0o555)
    verify_read_only(directory)
    fsync_directory(directory)


def verify_files_read_only(directory: Path) -> None:
    if any(path.stat().st_mode & 0o222 for path in directory.iterdir()):
        raise PermissionError("publication artifact is writable")


def verify_read_only(directory: Path) -> None:
    if directory.stat().st_mode & 0o222:
        raise PermissionError("publication directory is writable")
    verify_files_read_only(directory)


def fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _set_mode(path: Path, mode: int) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)


def _restore_read_only(directory: Path) -> bool:
    if not os.path.lexists(directory):
        return True
    try:
        paths = tuple(directory.rglob("*"))
        for path in paths:
            _set_mode(path, 0o444 if path.is_file() else 0o555)
        _set_mode(directory, 0o555)
        verify_read_only(directory)
    except OSError:
        return False
    return True


def force_remove(directory: Path) -> bool:
    if not os.path.lexists(directory):
        return True
    try:
        os.chmod(directory, 0o755)
        paths = tuple(directory.rglob("*"))
        for path in paths:
            os.chmod(path, 0o644 if path.is_file() else 0o755)
        shutil.rmtree(directory)
    except OSError:
        _restore_read_only(directory)
        return False
    return not os.path.lexists(directory)


def hide_and_remove(directory: Path) -> bool:
    if not os.path.lexists(directory):
        return True
    hidden = directory.with_name(f".{directory.name}.rollback")
    if os.path.lexists(hidden) and not force_remove(hidden):
        _restore_read_only(directory)
        return False
    try:
        os.replace(directory, hidden)
    except OSError:
        try:
            os.rename(directory, hidden)
        except OSError:
            _restore_read_only(directory)
            return False
    force_remove(hidden)
    return not os.path.lexists(directory)


__all__ = [
    "RunPublicationLock",
    "canonical_hash",
    "canonical_text",
    "ensure_directory",
    "force_remove",
    "fsync_directory",
    "hide_and_remove",
    "make_files_read_only",
    "optional_canonical_hash",
    "prepare_read_only_directory",
    "verify_files_read_only",
    "verify_read_only",
    "write_file",
]
