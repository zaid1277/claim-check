"""A warmed-up development environment must not hide stale install locks."""

import re
import tomllib
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]


def package_name(requirement):
    name = re.match(r"[A-Za-z0-9_.-]+", requirement).group()
    return re.sub(r"[-_.]+", "-", name).lower()


@pytest.mark.parametrize("development", [False, True])
def test_install_lock_contains_declared_dependencies(development):
    project = tomllib.loads((API / "pyproject.toml").read_text())["project"]
    requirements = list(project["dependencies"])
    if development:
        requirements += project["optional-dependencies"]["dev"]
    lock = API / ("requirements-dev.lock" if development else "requirements.lock")
    locked = {
        package_name(line)
        for line in lock.read_text().splitlines()
        if line and not line.startswith(("#", " ", "-"))
    }
    missing = {package_name(item) for item in requirements} - locked
    assert not missing, f"Regenerate {lock.name}; missing packages: {sorted(missing)}"
