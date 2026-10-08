"""Fixtures for the staging tests: a throwaway git project and a temp root."""

from pathlib import Path

import pytest

from tests.boilerplate.templates.conftest import commit_all, git, init_repo

PROJECT_NAME = "my-project"
FILES = {"keep.txt": "keep\n", "edit.txt": "one\ntwo\nthree\n", "drop.txt": "drop\n"}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a clean git project named `PROJECT_NAME` with three committed files."""
    root = tmp_path / "work" / PROJECT_NAME
    root.mkdir(parents=True)
    init_repo(root)
    for name, text in FILES.items():
        (root / name).write_text(text, encoding="utf-8", newline="\n")
    commit_all(root, "initial")
    return root


@pytest.fixture
def staging_root(tmp_path: Path) -> Path:
    """Return an empty directory standing in for the system temp directory."""
    root = tmp_path / "system-temp"
    root.mkdir()
    return root


def head(repo: Path) -> str:
    """Return the commit `repo`'s HEAD points at."""
    return git(repo, "rev-parse", "HEAD").strip()
