from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PATH = (
    ROOT / "tests/fixtures/architecture/five-package-workspace-v1.expected.json"
)
WHEEL_DIRECTORY = ROOT / "build/wheels"
ACCEPTANCE_DIRECTORY = ROOT / "build/acceptance"
MANIFEST_PATH = ACCEPTANCE_DIRECTORY / "wp-00a-package-build-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wheel_project_name(path: Path) -> str:
    with zipfile.ZipFile(path) as wheel:
        metadata_name = next(
            name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = wheel.read(metadata_name).decode("utf-8")
    for line in metadata.splitlines():
        if line.startswith("Name: "):
            return line.removeprefix("Name: ")
    raise AssertionError(f"Wheel has no project Name metadata: {path}")


def test_all_workspace_packages_import_and_build_as_wheels() -> None:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))

    imported = []
    for package in expected["packages"]:
        module = importlib.import_module(package["module_name"])
        imported.append(
            {
                "project_name": package["project_name"],
                "module_name": module.__name__,
                "version": importlib.metadata.version(package["project_name"]),
            }
        )

    shutil.rmtree(WHEEL_DIRECTORY, ignore_errors=True)
    WHEEL_DIRECTORY.mkdir(parents=True)
    completed = subprocess.run(
        [
            "uv",
            "build",
            "--all-packages",
            "--wheel",
            "--out-dir",
            str(WHEEL_DIRECTORY),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    wheels = sorted(WHEEL_DIRECTORY.glob("*.whl"))
    assert len(wheels) == expected["workspace"]["package_count"]
    assert sorted(wheel_project_name(wheel) for wheel in wheels) == sorted(
        package["project_name"] for package in expected["packages"]
    )

    ACCEPTANCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "work_package": "WP-00A",
        "python_version": sys.version.split()[0],
        "lock_sha256": sha256(ROOT / "uv.lock"),
        "imports": sorted(imported, key=lambda item: item["project_name"]),
        "wheels": [
            {
                "file": wheel.name,
                "project_name": wheel_project_name(wheel),
                "sha256": sha256(wheel),
            }
            for wheel in wheels
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    assert manifest["python_version"].startswith("3.13.")
    assert MANIFEST_PATH.is_file()
