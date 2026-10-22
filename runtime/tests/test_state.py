"""Issue-name validation (trust boundary) and STATE.json mirroring."""

from __future__ import annotations

import json

import pytest

from runtime.state import REVIEW_AGENTS, mirror_to_disk, new_state, review_agents, validate_issue


@pytest.mark.parametrize("issue", ["auth-api", "todo_api", "feature.42", "a", "x" * 100])
def test_accepts_safe_slugs(issue):
    assert validate_issue(issue) == issue


@pytest.mark.parametrize(
    "issue",
    [
        "../etc/passwd",      # path traversal
        "a/b",                # path separator
        "..",                 # parent ref
        "feature/..",         # embedded parent ref
        "Has Spaces",         # whitespace
        "UPPER",              # uppercase (not a slug)
        "",                   # empty
        "x" * 101,            # too long
        "/abs",               # absolute
    ],
)
def test_rejects_unsafe_issue_names(issue):
    with pytest.raises(ValueError):
        validate_issue(issue)


def test_new_state_validates_issue_and_requirement():
    with pytest.raises(ValueError):
        new_state("../escape", "ok")
    with pytest.raises(ValueError):
        new_state("good-issue", "   ")  # blank requirement
    state = new_state("good-issue", "build a thing")
    assert state["issue"] == "good-issue"
    assert state["phase"] == "codebase"
    assert state["devops"] is False


def test_mirror_to_disk_writes_native_schema(tmp_path):
    state = new_state("demo", "do it")
    target = mirror_to_disk(state, tmp_path)
    data = json.loads(target.read_text())
    assert data["issue"] == "demo"
    assert data["phase"] == "codebase"
    assert "updated_at" in data


def test_review_agents_devops_is_opt_in():
    assert review_agents(new_state("d", "x")) == ("reviewer", "qa")
    assert review_agents(new_state("d", "x", devops=True)) == REVIEW_AGENTS
