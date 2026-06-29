"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the repo root (parent of the runtime package) is importable.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.config import Config, load_config  # noqa: E402


@pytest.fixture
def real_config(monkeypatch) -> Config:
    """Config pointing at the real repository (.claude/agents available)."""
    monkeypatch.delenv("ASDLC_REPO_ROOT", raising=False)
    monkeypatch.delenv("CHECKPOINT_BACKEND", raising=False)
    return load_config()


@pytest.fixture
def temp_config(monkeypatch, tmp_path) -> Config:
    """Config pointing at an isolated temp repo (no real agents)."""
    (tmp_path / ".claude").mkdir()
    monkeypatch.setenv("ASDLC_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_BACKEND", "sqlite")
    monkeypatch.setenv("ASDLC_SQLITE_PATH", str(tmp_path / "cp.sqlite"))
    return load_config()
