"""Provider-neutral runner with opt-in SkillCache observation and replay hints.

The model remains responsible for every agent verdict; cache cannot bypass
LangGraph approval, contracts, QA, or held-out acceptance.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from .config import Config, validate_provider

CACHEABLE_ROLES = frozenset({
    "codebase", "product", "planner", "architect", "developer", "specification",
    "devops",
})


ISSUE_HEADER = re.compile(r"^Issue: ([a-z0-9][a-z0-9._-]{0,99}?)(?=\. |\n|$)")


def normalize_task(prompt: str) -> str:
    """Lift only the issue identifier. Keep all other task text exact."""
    found = ISSUE_HEADER.match(prompt)
    if not found:
        return prompt
    issue = found.group(1)
    updated = prompt.replace(f"docs/{issue}/", "docs/{issue}/")
    return updated.replace("Issue: " + issue, "Issue: {issue}", 1)


def _task_request(node: str, prompt: str, root: Path) -> str | None:
    from .skill_cache import MAX_FILE_BYTES, ROLE_INPUTS, workspace_fingerprint
    from .state import validate_issue

    request = normalize_task(prompt)
    names = ROLE_INPUTS.get(node, ())
    if not names:
        return request
    match = ISSUE_HEADER.match(prompt)
    if not match:
        return None
    try:
        docs = root / "docs" / validate_issue(match[1])
        if docs.is_symlink() or docs.parent.is_symlink():
            return None
        inputs = {}
        for name in names:
            path = docs / name
            if path.is_symlink():
                return None
            if not path.exists():
                continue
            if name == "specs":
                value = workspace_fingerprint(path)
                if value is None:
                    return None
            else:
                if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                    return None
                value = hashlib.sha256(path.read_bytes()).hexdigest()
            inputs[name] = value
    except (OSError, ValueError):
        return None
    return request + "\nRole input digests: " + json.dumps(inputs, sort_keys=True)


def _instruct_from_capsule(capsule: dict, root: Path) -> str:
    from .skillcache_capsule import capsule_id
    from .skillcache_compiler import _capsule_dir
    path = _capsule_dir(root) / (capsule_id(capsule) + ".json")
    steps = "\n".join(
        f"- {step['instruction']}" for step in capsule["steps"]
        if not step.get("program")
    )[:1500]
    return (
        "\n\n## Optional execution-grounded capsule\n"
        f"Name: {capsule['name']}\nWhen applicable: {capsule['description']}\n"
        "Judge applicability for the *current* request. Never use a capsule "
        "if it differs from current requirements. The complete source skill "
        "remains available for recovery.\n"
        f"Capsule: {path}\n"
        "For a hybrid capsule, use asdlc-skillcache start/continue with "
        "--sandbox docker and JSON bindings; follow needs_bindings/your_steps. "
        "On any program error, timeout, mismatch or missing Docker, do the "
        "failing step with normal tools and source skill. Do not skip required "
        "checks or human approvals.\n"
        + ("Textual steps:\n" + steps if steps else "")
    )


async def run_agent(node: str, prompt: str, config: Config):
    provider = validate_provider(config.agent_providers.get(node, config.provider))
    is_cached = bool(config.skill_cache_full and node in CACHEABLE_ROLES)
    buffer_token = None
    before = None
    request = _task_request(node, prompt, config.repo_root) if is_cached else None
    observations = []
    hit = False
    if is_cached and request is not None:
        from .skill_cache import workspace_fingerprint
        from .skillcache_compiler import find_capsules
        before = workspace_fingerprint(config.repo_root)
        if before:
            prior = find_capsules(
                config.repo_root, node, request, before,
                match_mode=config.skill_cache_match
            )
            if prior:
                hit = True
                prompt += _instruct_from_capsule(prior[0], config.repo_root)
        from .skillcache_capture import BUFFER
        buffer_token = BUFFER.set([])
    try:
        if provider == "codex":
            from .codex_runner import run_agent as underlying
        else:
            from .claude_runner import run_agent as underlying
        result = await underlying(node, prompt, config)
    finally:
        if buffer_token is not None:
            from .skillcache_capture import BUFFER
            observations = list(BUFFER.get() or [])
            BUFFER.reset(buffer_token)
    if not is_cached or hit or not observations or not before or not result.ok:
        return result

    # Never compile a changed source tree, unsuccessful run, or unobserved
    # execution. Qualification is best-effort and cannot alter the verdict.
    from .skill_cache import workspace_fingerprint
    if (workspace_fingerprint(config.repo_root) != before
            or _task_request(node, prompt, config.repo_root) != request):
        return result
    # Automatic qualification requires an actual isolated executor. Never
    # spend extra model calls inventing programs that cannot be safely run.
    import shutil
    if not shutil.which("docker"):
        return result
    from .skillcache_trace import observation
    from .skillcache_compiler import compile_observation
    from .agent_loader import load_agent
    trace = {
        "schema_version": 1, "role": node, "provider": provider,
        "successful": True, "events": observations,
    }
    # Persist only sanitized, bounded evidence, not provider raw JSONL.
    try:
        target = (config.repo_root / ".asdlc" / "skill-cache" / "observations"
                  / (uuid.uuid4().hex + ".json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(trace, ensure_ascii=False)
        if len(data.encode("utf-8")) <= 128 * 1024:
            import os
            with target.open("x", encoding="utf-8") as f:
                f.write(data)
            os.chmod(target, 0o600)
        await compile_observation(
            root=config.repo_root, role=node, provider=provider,
            request=request, workspace_hash=before,
            source_skill=load_agent(node, config).body,
            trace=trace,
        )
    except Exception:
        # Cache is an optimization. Never convert a valid agent result to
        # FAILED because cache infrastructure is unavailable.
        pass
    return result
