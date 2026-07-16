"""Load Claude Code agent definitions from ``.claude/agents/*.md``.

The agent Markdown files are the single source of truth for prompts, model
selection and tool allowlists. This module parses their YAML frontmatter and
body so the runner can reuse them verbatim — we never re-implement prompts in
Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import Config

# Logical node name -> agent definition file stem. Every entry MUST have a
# matching .claude/agents/<stem>.md (enforced by test_every_agent_loads); the
# graph orchestrates these agents, there is no separate "orchestrator" agent.
AGENT_FILE = {
    "product": "product-agent",
    "planner": "planner-agent",
    "architect": "architect-agent",
    "developer": "developer-agent",
    "reviewer": "reviewer-agent",
    "qa": "qa-agent",
    "devops": "devops-agent",
}


@dataclass(frozen=True)
class AgentDef:
    name: str
    model: str | None
    tools: tuple[str, ...]
    body: str  # Markdown system prompt (frontmatter stripped)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body). Minimal, dependency-free parser.

    Handles the flat ``key: value`` frontmatter used by these agent files,
    including inline list values like ``tools: [Read, Write]``. Values may
    contain colons (e.g. descriptions) — we split on the first colon only.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    # lines[0] == "---"; find the closing fence.
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return fm, body


def _parse_tools(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    raw = raw.strip().strip("[]")
    if not raw:
        return ()
    return tuple(t.strip() for t in raw.split(",") if t.strip())


@lru_cache(maxsize=None)
def _read_rules_context(rules_dir_str: str, claude_md_str: str) -> str:
    """Concatenate always-active rules + CLAUDE.md as shared system context."""
    parts: list[str] = []
    claude_md = Path(claude_md_str)
    if claude_md.is_file():
        parts.append(claude_md.read_text(encoding="utf-8"))
    rules_dir = Path(rules_dir_str)
    if rules_dir.is_dir():
        for rule in sorted(rules_dir.glob("*.md")):
            parts.append(rule.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def load_agent(node: str, config: Config) -> AgentDef:
    stem = AGENT_FILE.get(node, f"{node}-agent")
    path = config.agents_dir / f"{stem}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Agent definition not found: {path}")
    fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return AgentDef(
        name=fm.get("name", stem),
        model=fm.get("model") or None,
        tools=_parse_tools(fm.get("tools")),
        body=body,
    )


def build_system_prompt(agent: AgentDef, config: Config) -> str:
    """Agent body + shared rules/CLAUDE.md context."""
    rules = _read_rules_context(
        str(config.rules_dir), str(config.repo_root / "CLAUDE.md")
    )
    if rules:
        return f"{agent.body}\n\n# Project Rules (always active)\n\n{rules}"
    return agent.body
