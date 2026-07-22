"""Runtime configuration sourced from environment variables.

Production server use authenticates with ``ANTHROPIC_API_KEY`` (the
service-account path). A Claude Pro/Max subscription (OAuth login) is only
appropriate for local development; if no key is set we fall back to whatever
credentials the local Claude Code install already holds.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    """Repository root = the directory that contains ``.claude/``.

    Walks up from this file so the package works regardless of the current
    working directory (CLI, server, tests).
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".claude").is_dir():
            return parent
    # Fall back to the parent of the runtime/ package.
    return here.parent.parent


@dataclass(frozen=True)
class Config:
    repo_root: Path
    anthropic_api_key: str | None
    checkpoint_backend: str  # "sqlite" | "postgres"
    db_url: str | None
    sqlite_path: Path
    max_iterations: int
    # Model tiering (agent-swarm economics): a role maps to a tier, a tier to a
    # concrete model. These env-driven values layer *over* each agent's
    # frontmatter default so a whole model mix can be swapped for one run and
    # compared by cost — see runtime.agent_loader.resolve_model.
    model_smart: str | None = None
    model_worker: str | None = None
    model_overrides: dict[str, str] = field(default_factory=dict)

    @property
    def agents_dir(self) -> Path:
        return self.repo_root / ".claude" / "agents"

    @property
    def rules_dir(self) -> Path:
        return self.repo_root / ".claude" / "rules"

    @property
    def docs_dir(self) -> Path:
        return self.repo_root / "docs"

    def docs_for(self, issue: str) -> Path:
        return self.docs_dir / issue


def load_config() -> Config:
    repo_root = Path(os.environ.get("ASDLC_REPO_ROOT", "")).resolve() if os.environ.get(
        "ASDLC_REPO_ROOT"
    ) else _repo_root()

    backend = os.environ.get("CHECKPOINT_BACKEND", "sqlite").strip().lower()
    if backend not in ("sqlite", "postgres"):
        raise ValueError(f"CHECKPOINT_BACKEND must be 'sqlite' or 'postgres', got {backend!r}")

    db_url = os.environ.get("DB_URL")
    if backend == "postgres" and not db_url:
        raise ValueError("CHECKPOINT_BACKEND=postgres requires DB_URL to be set")

    sqlite_path = Path(
        os.environ.get("ASDLC_SQLITE_PATH", str(repo_root / ".asdlc" / "checkpoints.sqlite"))
    )

    raw_iterations = os.environ.get("ASDLC_MAX_ITERATIONS", "3")
    try:
        max_iterations = int(raw_iterations)
    except ValueError:
        raise ValueError(
            f"ASDLC_MAX_ITERATIONS must be an integer, got {raw_iterations!r}"
        ) from None
    if max_iterations < 1:
        raise ValueError(f"ASDLC_MAX_ITERATIONS must be >= 1, got {max_iterations}")

    # Deferred import: agent_loader imports this module, so keep it out of the
    # module top-level. By call time config is fully loaded, so this is safe.
    from .agent_loader import AGENT_FILE

    model_overrides = {
        node: os.environ[f"ASDLC_MODEL_{node.upper()}"]
        for node in AGENT_FILE
        if os.environ.get(f"ASDLC_MODEL_{node.upper()}")
    }

    return Config(
        repo_root=repo_root,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        checkpoint_backend=backend,
        db_url=db_url,
        sqlite_path=sqlite_path,
        max_iterations=max_iterations,
        model_smart=os.environ.get("ASDLC_MODEL_SMART") or None,
        model_worker=os.environ.get("ASDLC_MODEL_WORKER") or None,
        model_overrides=model_overrides,
    )
