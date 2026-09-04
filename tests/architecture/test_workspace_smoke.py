from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PATH = (
    ROOT / "tests/fixtures/architecture/five-package-workspace-v1.expected.json"
)


def load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def load_expected() -> dict:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def dependency_name(requirement: str) -> str:
    for separator in (" ", "<", ">", "=", "!", "~", "["):
        requirement = requirement.split(separator, 1)[0]
    return requirement


def test_workspace_matches_the_five_package_contract() -> None:
    expected = load_expected()
    root_config = load_toml(ROOT / "pyproject.toml")

    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == expected[
        "python"
    ]["default_minor"]
    assert root_config["project"]["requires-python"] == expected["python"][
        "requires_python"
    ]
    assert root_config["tool"]["uv"]["package"] is False
    assert root_config["tool"]["uv"]["workspace"]["members"] == expected[
        "workspace"
    ]["members"]
    assert any(
        dependency_name(requirement) == "pytest"
        for requirement in root_config["dependency-groups"]["dev"]
    )

    package_directories = sorted((ROOT / "packages").iterdir())
    assert len(package_directories) == expected["workspace"]["package_count"]

    for package in expected["packages"]:
        package_root = ROOT / package["directory"]
        config = load_toml(package_root / "pyproject.toml")
        project = config["project"]

        assert config["build-system"]["build-backend"] == expected["workspace"][
            "build_backend"
        ]
        assert project["name"] == package["project_name"]
        assert project["requires-python"] == expected["python"]["requires_python"]
        assert sorted(map(dependency_name, project.get("dependencies", []))) == sorted(
            package["dependencies"]
        )
        assert config["tool"]["setuptools"]["packages"]["find"]["where"] == [
            "src"
        ]
        assert (
            package_root / "src" / package["module_name"] / "__init__.py"
        ).is_file()

        workspace_sources = config.get("tool", {}).get("uv", {}).get("sources", {})
        for dependency in package["dependencies"]:
            assert workspace_sources[dependency] == {"workspace": True}


def test_root_lock_is_current_for_python_313() -> None:
    assert (ROOT / "uv.lock").is_file()
    completed = subprocess.run(
        ["uv", "lock", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert sys.version_info[:2] == (3, 13)
