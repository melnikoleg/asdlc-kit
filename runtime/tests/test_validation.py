"""Deterministic validation parsing and execution."""

from __future__ import annotations

import re
from pathlib import Path

from runtime.validation import (
    _DENY_PATTERNS,
    all_passed,
    is_destructive,
    parse_validation_commands,
    run_command,
    run_validation,
)

PLAN = """\
## Phase 1 — setup
- Validation: echo ok
## Phase 2 — build
Validation: `python3 -c "print(1)"`
## Phase 3 — duplicate ignored
Validation: echo ok
"""


def test_parses_inline_and_backticked_commands():
    cmds = parse_validation_commands(PLAN)
    assert cmds == ["echo ok", 'python3 -c "print(1)"']  # de-duplicated, ordered


def test_passing_command(tmp_path):
    res = run_command("true", tmp_path)
    assert res["passed"] and res["exit_code"] == 0


def test_failing_command_is_recorded_not_raised(tmp_path):
    res = run_command("false", tmp_path)
    assert res["passed"] is False
    assert res["exit_code"] == 1


def test_destructive_command_blocked(tmp_path):
    assert is_destructive("rm -rf /")
    res = run_command("rm -rf /", tmp_path)
    assert res["passed"] is False
    assert "BLOCKED" in res["output"]


def test_deny_patterns_match_shell_hook():
    # _DENY_PATTERNS mirrors .claude/hooks/block-destructive.sh; parse the
    # hook's `for pat in "…" "…"` line so any drift fails this test.
    hook = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "block-destructive.sh"
    match = re.search(r'^for pat in (.+); do$', hook.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "could not find deny-pattern list in block-destructive.sh"
    hook_patterns = re.findall(r'"([^"]+)"', match.group(1))
    assert set(hook_patterns) == set(_DENY_PATTERNS)
    for pat in hook_patterns:
        assert is_destructive(f"prefix; {pat} suffix"), pat


def test_timeout_records_partial_output(tmp_path):
    res = run_command("echo partial-marker; sleep 5", tmp_path, timeout=1)
    assert res["passed"] is False
    assert res["exit_code"] == -1
    assert "TIMEOUT" in res["output"]
    assert "partial-marker" in res["output"]


def test_all_passed_semantics():
    assert all_passed({}) is True  # no gate
    assert all_passed({"a": {"passed": True}}) is True
    assert all_passed({"a": {"passed": True}, "b": {"passed": False}}) is False


def test_run_validation_reads_plan(tmp_path):
    plan = tmp_path / "PLAN.md"
    plan.write_text("Validation: true\nValidation: false\n")
    results = run_validation(plan, tmp_path)
    assert results["true"]["passed"] is True
    assert results["false"]["passed"] is False
    assert all_passed(results) is False


def test_missing_plan_returns_empty(tmp_path):
    assert run_validation(tmp_path / "nope.md", tmp_path) == {}
