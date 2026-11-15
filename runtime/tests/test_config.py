"""Environment-driven config parsing and validation."""

from __future__ import annotations

import pytest

from runtime.config import load_config


def _reset(monkeypatch):
    for var in ("ASDLC_REPO_ROOT", "CHECKPOINT_BACKEND", "DB_URL", "ASDLC_MAX_ITERATIONS",
                "ASDLC_AGENT_BACKEND", "ASDLC_PROVIDER", "ASDLC_CODE_MODE"):
        monkeypatch.delenv(var, raising=False)


def test_defaults(monkeypatch):
    _reset(monkeypatch)
    cfg = load_config()
    assert cfg.checkpoint_backend == "sqlite"
    assert cfg.max_iterations == 3
    assert cfg.provider == "codex"
    assert cfg.code_mode is True


def test_backend_and_code_mode_overrides(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("ASDLC_AGENT_BACKEND", "claude")
    monkeypatch.setenv("ASDLC_CODE_MODE", "off")
    cfg = load_config()
    assert cfg.provider == "claude"
    assert cfg.code_mode is False


def test_invalid_agent_backend(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("ASDLC_AGENT_BACKEND", "other")
    with pytest.raises(ValueError, match="provider"):
        load_config()


def test_invalid_code_mode_value(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("ASDLC_CODE_MODE", "maybe")
    with pytest.raises(ValueError, match="ASDLC_CODE_MODE"):
        load_config()


def test_installed_runtime_finds_current_project(monkeypatch, tmp_path):
    _reset(monkeypatch)
    (tmp_path / ".claude").mkdir()
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.repo_root == tmp_path


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
