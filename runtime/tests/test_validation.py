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


# --- e2e app lifecycle -------------------------------------------------------

import socket
import sys

import pytest

from runtime.validation import (
    AppStartError,
    load_strategy,
    main,
    parse_fields,
    run_with_app,
    running_app,
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _server_strategy(port: int) -> dict:
    return {
        "Start": [f"{sys.executable} -m http.server {port} --bind 127.0.0.1"],
        "Healthcheck": [f"http://127.0.0.1:{port}/"],
    }


def test_parse_fields_collects_all_keys():
    text = "Type: http-api\nStart: `run app`\nHealthcheck: http://x/h\nE2E: pytest -q\nE2E: pytest -q\nStop:\n"
    fields = parse_fields(text)
    assert fields["Start"] == ["run app"]
    assert fields["E2E"] == ["pytest -q"]  # de-duplicated
    assert "Stop" not in fields  # empty value dropped


def test_load_strategy_missing_file(tmp_path):
    assert load_strategy(tmp_path / "TEST_STRATEGY.md") == {}


def test_run_with_app_hits_running_server_then_stops_it(tmp_path):
    port = _free_port()
    strategy = _server_strategy(port)
    cmd = f"curl -sf http://127.0.0.1:{port}/ -o /dev/null"
    res = run_with_app([cmd], strategy, tmp_path, start_timeout=30)
    assert res[cmd]["passed"] is True
    with pytest.raises(OSError):  # server is gone afterwards
        socket.create_connection(("127.0.0.1", port), timeout=1).close()


def test_no_start_runs_commands_plainly(tmp_path):
    res = run_with_app(["true", "false"], {}, tmp_path)
    assert res["true"]["passed"] and not res["false"]["passed"]


def test_start_that_exits_early_is_a_failing_record(tmp_path):
    strategy = {"Start": ["echo boom; exit 3"], "Healthcheck": ["http://127.0.0.1:1/"]}
    res = run_with_app(["true"], strategy, tmp_path, start_timeout=10)
    (rec,) = res.values()
    assert rec["passed"] is False and "boom" in rec["output"]


def test_unhealthy_app_times_out_and_is_killed(tmp_path):
    strategy = {"Start": ["sleep 30"], "Healthcheck": [f"http://127.0.0.1:{_free_port()}/"]}
    res = run_with_app(["true"], strategy, tmp_path, start_timeout=1)
    (rec,) = res.values()
    assert rec["passed"] is False and "not healthy" in rec["output"]


def test_stale_server_is_refused(tmp_path):
    port = _free_port()
    strategy = _server_strategy(port)
    with running_app(strategy, tmp_path, start_timeout=30):
        with pytest.raises(AppStartError, match="already answers"):
            with running_app(strategy, tmp_path, start_timeout=5):
                pass


def test_stop_command_runs(tmp_path):
    marker = tmp_path / "stopped"
    port = _free_port()
    strategy = {**_server_strategy(port), "Stop": [f"touch {marker}"]}
    run_with_app(["true"], strategy, tmp_path, start_timeout=30)
    assert marker.exists()


def test_destructive_start_is_blocked(tmp_path):
    res = run_with_app(["true"], {"Start": ["rm -rf / "]}, tmp_path)
    (rec,) = res.values()
    assert rec["passed"] is False and "BLOCKED" in rec["output"]


def test_asdlc_e2e_main_passes_exit_code(monkeypatch, tmp_path, capsys):
    (tmp_path / ".claude").mkdir()
    monkeypatch.setenv("ASDLC_REPO_ROOT", str(tmp_path))
    assert main(["demo", "--", "true"]) == 0
    assert main(["demo", "--", "exit 7"]) == 7
