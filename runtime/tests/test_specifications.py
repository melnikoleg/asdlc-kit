"""Executable-specification contracts: coverage, immutability, real execution."""
from __future__ import annotations

from runtime.specifications import (
    SPEC_TAMPERED, SpecificationError, contract_sha256,
    load_specifications, preflight, run_specifications,
)
from runtime.state import new_state


def setup_contract(tmp_path, *, command=None):
    docs = tmp_path / "docs" / "demo"
    suite = docs / "specs"
    suite.mkdir(parents=True)
    (docs / "PRD.md").write_text("## Acceptance Criteria\nAC-1: order can be placed\n")
    test = suite / "check.py"
    test.write_text("assert True\n")
    command = command or "python docs/demo/specs/check.py"
    (docs / "SPECIFICATIONS.md").write_text(
        "# Business Specifications\n## AC-1 — order can be placed\n"
        "Given: an empty order\nWhen: a create command is sent\n"
        f"Then: OrderCreated is observed\nSpec: {command}\n"
    )
    return docs, test


def test_happy_path_is_executable(tmp_path):
    docs, _ = setup_contract(tmp_path)
    digest, error = preflight(docs)
    assert not error and len(digest) == 64
    scenarios = load_specifications(docs)
    assert [s.ac_id for s in scenarios] == ["AC-1"]
    res = run_specifications(docs, tmp_path, digest)
    assert len(res) == 1 and all(r["passed"] for r in res.values())


def test_missing_ac_fails_closed(tmp_path):
    docs, _ = setup_contract(tmp_path)
    (docs / "PRD.md").write_text("AC-1: first\nAC-2: second\n")
    sha, error = preflight(docs)
    assert sha is None and "AC coverage mismatch" in error


def test_missing_tests_are_rejected(tmp_path):
    docs, test = setup_contract(tmp_path)
    test.unlink()
    assert preflight(docs)[1]


def test_noop_shell_check_is_rejected(tmp_path):
    docs, _ = setup_contract(tmp_path, command="true")
    assert "must uniquely target" in preflight(docs)[1]


def test_contract_tamper_blocks_before_execution(tmp_path):
    docs, test = setup_contract(tmp_path)
    digest = contract_sha256(docs)
    test.write_text("assert False\n")
    res = run_specifications(docs, tmp_path, digest)
    assert SPEC_TAMPERED in res and not res[SPEC_TAMPERED]["passed"]


def test_compiled_python_cache_does_not_change_contract(tmp_path):
    docs, _ = setup_contract(tmp_path)
    digest = contract_sha256(docs)
    cache = docs / "specs" / "__pycache__"
    cache.mkdir()
    (cache / "check.cpython-313.pyc").write_bytes(b"compiled")
    assert contract_sha256(docs) == digest


def test_spec_test_failure_is_reported(tmp_path):
    docs, test = setup_contract(tmp_path)
    test.write_text("assert False\n")
    res = run_specifications(docs, tmp_path, contract_sha256(docs))
    assert len(res) == 1 and not next(iter(res.values()))["passed"]


def test_opt_in_state():
    assert not new_state("demo", "something").get("specs")
    assert new_state("demo", "something", specs=True)["specs"] is True
