from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def git_status() -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def is_ignored(path: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "--quiet", path],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode == 0


def test_generated_workspace_outputs_are_git_ignored() -> None:
    for path in (
        ".venv/probe",
        "build/acceptance/probe.json",
        "build/coverage/probe.json",
        "build/wheels/probe.whl",
        "dist/probe.whl",
        "runs/probe/result.json",
    ):
        assert is_ignored(path), f"Generated path is not ignored: {path}"


def test_acceptance_outputs_do_not_change_git_status() -> None:
    before = git_status()
    probes = (
        ROOT / "build/acceptance/repository-cleanliness-probe.json",
        ROOT / "build/coverage/repository-cleanliness-probe.json",
        ROOT / "build/wheels/repository-cleanliness-probe.whl",
        ROOT / "runs/probe/repository-cleanliness-probe.json",
    )

    try:
        for probe in probes:
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("generated acceptance output\n", encoding="utf-8")
        assert git_status() == before
    finally:
        for probe in probes:
            probe.unlink(missing_ok=True)
