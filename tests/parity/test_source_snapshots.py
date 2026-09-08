from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
FREEZER = ROOT / "tools/migration/freeze_source_snapshot.py"
VERIFIER = ROOT / "tools/migration/verify_legacy_baseline.py"
SOURCE_MAP = ROOT / "docs/migration/source-map.yaml"


def run_freezer(
    source_map: Path, source_id: str, source_root: Path, output_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(FREEZER),
            "--source-map",
            str(source_map),
            "--source-id",
            source_id,
            "--source-root",
            str(source_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def run_verifier(
    source_map: Path, root: Path, report: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--root",
            str(root),
            "--source-map",
            str(source_map),
            "--report",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def fixture_source_map() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "snapshot_manifest_schema_version": 1,
        "allowed_migration_modes": [
            "copy_with_parity",
            "intentional_semantic_change",
            "new_capability",
            "reimplement_with_reference",
        ],
        "sources": [
            {
                "id": "fixture-source",
                "provenance": {
                    "base_commit": "fixture-commit",
                    "remote": None,
                    "worktree_state": "dirty",
                },
                "include_files": ["alpha.txt", "bin/run.sh"],
                "snapshot": None,
            }
        ],
        "migration_units": [],
    }


def complete_fixture_source_map(
    source_map: dict[str, Any], root: Path, summary: dict[str, Any]
) -> Path:
    source = source_map["sources"][0]
    source["snapshot"] = {
        "id": summary["snapshot_id"],
        "archive": str(Path(summary["archive"]).relative_to(root)),
        "manifest": str(Path(summary["manifest"]).relative_to(root)),
        "manifest_sha256": hashlib.sha256(
            Path(summary["manifest"]).read_bytes()
        ).hexdigest(),
    }
    path = root / "source-map.yaml"
    path.write_text(yaml.safe_dump(source_map, sort_keys=False), encoding="utf-8")
    return path


def test_snapshot_archive_is_byte_deterministic_and_normalized(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    (source_root / "bin").mkdir(parents=True)
    (source_root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    executable = source_root / "bin/run.sh"
    executable.write_text("#!/bin/sh\necho fixture\n", encoding="utf-8")
    executable.chmod(0o755)
    source_map_data = fixture_source_map()
    source_map = tmp_path / "scope.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )

    first = run_freezer(source_map, "fixture-source", source_root, tmp_path / "one")
    second = run_freezer(source_map, "fixture-source", source_root, tmp_path / "two")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    first_summary = json.loads(first.stdout)
    second_summary = json.loads(second.stdout)
    assert first_summary["snapshot_id"] == second_summary["snapshot_id"]
    assert Path(first_summary["archive"]).read_bytes() == Path(
        second_summary["archive"]
    ).read_bytes()

    manifest = json.loads(Path(first_summary["manifest"]).read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["files"]] == [
        "alpha.txt",
        "bin/run.sh",
    ]
    assert [item["mode"] for item in manifest["files"]] == ["0644", "0755"]

    with tarfile.open(first_summary["archive"], mode="r:gz") as archive:
        members = archive.getmembers()
    assert [member.name for member in members] == ["alpha.txt", "bin/run.sh"]
    assert all(member.mtime == member.uid == member.gid == 0 for member in members)
    assert all(member.uname == member.gname == "" for member in members)


def test_freezer_rejects_symlink_in_declared_scope(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "target.txt").write_text("target\n", encoding="utf-8")
    (source_root / "link.txt").symlink_to("target.txt")
    source_map_data = fixture_source_map()
    source_map_data["sources"][0]["include_files"] = ["link.txt"]  # type: ignore[index]
    source_map = tmp_path / "scope.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )

    completed = run_freezer(source_map, "fixture-source", source_root, tmp_path / "out")

    assert completed.returncode == 2
    assert "regular file" in completed.stderr


def test_freezer_rejects_parent_symlink_escape(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    outside = tmp_path / "outside"
    source_root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    (source_root / "linked").symlink_to(outside, target_is_directory=True)
    source_map_data = fixture_source_map()
    source_map_data["sources"][0]["include_files"] = ["linked/secret.txt"]  # type: ignore[index]
    source_map = tmp_path / "scope.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )

    completed = run_freezer(source_map, "fixture-source", source_root, tmp_path / "out")

    assert completed.returncode == 2
    assert "escapes source root" in completed.stderr


def test_verifier_detects_snapshot_tampering(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    (source_root / "bin").mkdir(parents=True)
    (source_root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    executable = source_root / "bin/run.sh"
    executable.write_text("#!/bin/sh\necho fixture\n", encoding="utf-8")
    executable.chmod(0o755)
    source_map_data = fixture_source_map()
    scope = tmp_path / "scope.yaml"
    scope.write_text(yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8")
    frozen = run_freezer(scope, "fixture-source", source_root, tmp_path / "fixtures")
    assert frozen.returncode == 0, frozen.stdout + frozen.stderr
    summary = json.loads(frozen.stdout)
    source_map = complete_fixture_source_map(source_map_data, tmp_path, summary)
    archive = Path(summary["archive"])
    archive.write_bytes(archive.read_bytes() + b"tampered")
    report = tmp_path / "report.json"

    completed = run_verifier(source_map, tmp_path, report)

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["violations"][0]["rule"] == "snapshot-hash-mismatch"


def test_unknown_source_map_schema_fails_closed(tmp_path: Path) -> None:
    source_map_data = fixture_source_map()
    source_map_data["schema_version"] = 999
    source_map = tmp_path / "source-map.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )
    report = tmp_path / "report.json"

    completed = run_verifier(source_map, tmp_path, report)

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["violations"][0]["rule"] == "unsupported-source-map-schema"


def test_verifier_rejects_unsafe_archive_member_before_path_comparison(
    tmp_path: Path,
) -> None:
    tar_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=tar_buffer, mode="wb", filename="", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            member = tarfile.TarInfo("../escape.txt")
            value = b"escape\n"
            member.size = len(value)
            member.mode = 0o644
            member.mtime = member.uid = member.gid = 0
            archive.addfile(member, io.BytesIO(value))
    archive_bytes = tar_buffer.getvalue()
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    archive_path = fixtures / f"fixture-source-{archive_hash}.tar.gz"
    archive_path.write_bytes(archive_bytes)
    manifest = {
        "archive_file": archive_path.name,
        "archive_sha256": archive_hash,
        "content_tree_sha256": "unused",
        "files": [
            {
                "mode": "0644",
                "path": "safe.txt",
                "sha256": hashlib.sha256(b"safe\n").hexdigest(),
                "size": 5,
            }
        ],
        "provenance": fixture_source_map()["sources"][0]["provenance"],  # type: ignore[index]
        "schema_version": 1,
        "snapshot_id": f"sha256:{archive_hash}",
        "source_id": "fixture-source",
    }
    manifest_path = fixtures / f"fixture-source-{archive_hash}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    source_map_data = fixture_source_map()
    source_map_data["sources"][0]["include_files"] = ["safe.txt"]  # type: ignore[index]
    source_map_data["sources"][0]["snapshot"] = {  # type: ignore[index]
        "id": f"sha256:{archive_hash}",
        "archive": str(archive_path.relative_to(tmp_path)),
        "manifest": str(manifest_path.relative_to(tmp_path)),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    source_map = tmp_path / "source-map.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )
    report = tmp_path / "report.json"

    completed = run_verifier(source_map, tmp_path, report)

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["violations"][0]["rule"] == "unsafe-archive-member"


def test_intentional_semantic_change_requires_an_adr(tmp_path: Path) -> None:
    source_map_data = yaml.safe_load(SOURCE_MAP.read_text(encoding="utf-8"))
    source_map_data["migration_units"][0]["mode"] = "intentional_semantic_change"
    source_map_data["migration_units"][0].pop("adr", None)
    source_map = tmp_path / "source-map.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )
    report = tmp_path / "report.json"

    completed = run_verifier(source_map, ROOT, report)

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert any(
        item["rule"] == "intentional-change-without-adr"
        for item in payload["violations"]
    )


def test_intentional_semantic_change_rejects_non_adr_reference(tmp_path: Path) -> None:
    source_map_data = yaml.safe_load(SOURCE_MAP.read_text(encoding="utf-8"))
    source_map_data["migration_units"][0]["mode"] = "intentional_semantic_change"
    source_map_data["migration_units"][0]["adr"] = "pyproject.toml"
    source_map = tmp_path / "source-map.yaml"
    source_map.write_text(
        yaml.safe_dump(source_map_data, sort_keys=False), encoding="utf-8"
    )
    report = tmp_path / "report.json"

    completed = run_verifier(source_map, ROOT, report)

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert any(
        item["rule"] == "intentional-change-without-adr"
        for item in payload["violations"]
    )


def test_committed_legacy_source_baseline_is_self_contained(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_verifier(SOURCE_MAP, ROOT, report)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["sources_verified"] == 3
    assert payload["source_repository_reads"] == 0
