"""Runtime configuration sourced from environment variables.

Authentication uses the selected provider CLI login (Claude or Codex).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
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
    provider: str = "claude"
    agent_providers: dict[str, str] = field(default_factory=dict)
    codex_model: str | None = None
    codex_model_smart: str | None = None
    codex_model_worker: str | None = None
    codex_model_overrides: dict[str, str] = field(default_factory=dict)

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


PROVIDERS = ("claude", "codex")


def validate_provider(provider: str) -> str:
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {PROVIDERS}, got {provider!r}")
    return provider


def configure_providers(
    config: Config,
    provider: str | None = None,
    agent_providers: dict[str, str] | None = None,
    *,
    replace_overrides: bool = False,
) -> Config:
    """Select per-run providers; overrides are immutable across resume."""
    from .agent_loader import AGENT_FILE

    selected = validate_provider(provider if provider is not None else config.provider)
    overrides = {} if replace_overrides else dict(config.agent_providers)
    for node, value in (agent_providers or {}).items():
        if node not in AGENT_FILE:
            raise ValueError(f"unknown agent {node!r}; expected one of {', '.join(AGENT_FILE)}")
        overrides[node] = validate_provider(value)
    return replace(config, provider=selected, agent_providers=overrides)


def required_providers(config: Config, *, devops: bool = False) -> set[str]:
    from .agent_loader import AGENT_FILE
    return {
        config.agent_providers.get(node, config.provider)
        for node in AGENT_FILE
        if devops or node != "devops"
    }


def parse_agent_provider_args(entries: list[str]) -> dict[str, str]:
    """Parse repeated --agent-provider NODE=codex|claude values."""
    from .agent_loader import AGENT_FILE
    result: dict[str, str] = {}
    for entry in entries:
        node, separator, provider = entry.partition("=")
        if not separator or node not in AGENT_FILE:
            raise ValueError(f"expected --agent-provider NODE=claude|codex, got {entry!r}")
        result[node] = validate_provider(provider)
    return result


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

    provider = validate_provider(os.environ.get("ASDLC_PROVIDER", "claude"))
    agent_providers = {
        node: validate_provider(os.environ[f"ASDLC_PROVIDER_{node.upper()}"])
        for node in AGENT_FILE
        if os.environ.get(f"ASDLC_PROVIDER_{node.upper()}")
    }
    codex_model_overrides = {
        node: os.environ[f"ASDLC_CODEX_MODEL_{node.upper()}"]
        for node in AGENT_FILE
        if os.environ.get(f"ASDLC_CODEX_MODEL_{node.upper()}")
    }

    return Config(
        repo_root=repo_root,
        checkpoint_backend=backend,
        db_url=db_url,
        sqlite_path=sqlite_path,
        max_iterations=max_iterations,
        model_smart=os.environ.get("ASDLC_MODEL_SMART") or None,
        model_worker=os.environ.get("ASDLC_MODEL_WORKER") or None,
        model_overrides=model_overrides,
        provider=provider,
        agent_providers=agent_providers,
        codex_model=os.environ.get("ASDLC_CODEX_MODEL") or None,
        codex_model_smart=os.environ.get("ASDLC_CODEX_MODEL_SMART") or None,
        codex_model_worker=os.environ.get("ASDLC_CODEX_MODEL_WORKER") or None,
        codex_model_overrides=codex_model_overrides,
    )
