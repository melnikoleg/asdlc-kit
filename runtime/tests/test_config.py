"""Environment-driven config parsing and validation."""

from __future__ import annotations

import pytest

from runtime.config import load_config


def _reset(monkeypatch):
    for var in ("ASDLC_REPO_ROOT", "CHECKPOINT_BACKEND", "DB_URL", "ASDLC_MAX_ITERATIONS"):
        monkeypatch.delenv(var, raising=False)


def test_defaults(monkeypatch):
    _reset(monkeypatch)
    cfg = load_config()
    assert cfg.checkpoint_backend == "sqlite"
    assert cfg.max_iterations == 3


def test_postgres_requires_db_url(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("CHECKPOINT_BACKEND", "postgres")
    with pytest.raises(ValueError, match="DB_URL"):
        load_config()


def test_unknown_backend_rejected(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("CHECKPOINT_BACKEND", "mysql")
    with pytest.raises(ValueError, match="sqlite.*postgres|postgres.*sqlite"):
        load_config()


def test_non_integer_max_iterations_rejected(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("ASDLC_MAX_ITERATIONS", "lots")
    with pytest.raises(ValueError, match="integer"):
        load_config()


def test_non_positive_max_iterations_rejected(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("ASDLC_MAX_ITERATIONS", "0")
    with pytest.raises(ValueError, match=">= 1"):
        load_config()
