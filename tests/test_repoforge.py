import json
import os
import subprocess

import pytest

from repoforge.analysis import apply_edits, inventory
from repoforge.fixture import ISSUE, SOURCE, create_fixture
from repoforge.providers import DemoProvider, OpenAIProvider
from repoforge.report import render_report
from repoforge.sandbox import Runner
from repoforge.store import EventStore
from repoforge.workflow import run_workflow


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "fixture"
    create_fixture(path)
    return path


def store_at(tmp_path):
    return EventStore("sqlite:///" + str(tmp_path / "events.db"))


def test_full_repair_loop(source, tmp_path):
    report = run_workflow(str(source), ISSUE, tmp_path / "run", DemoProvider(),
                          Runner("trusted-demo"), store_at(tmp_path))
    assert report["status"] == "ready_for_review"
    assert report["attempts"] == 2
    tests = [event["payload"] for event in report["events"] if event["stage"] == "test"]
    assert [result["passed"] for result in tests] == [False, False, True]
    assert "Ran 4 tests" in tests[-1]["log"]
    assert (source / "src/stats.py").read_text() == SOURCE
    assert (tmp_path / "run/patch.diff").exists()
    assert json.loads((tmp_path / "run/report.json").read_text())["commit"] == report["commit"]


def test_budget_exhaustion_no_patch(source, tmp_path):
    report = run_workflow(str(source), ISSUE, tmp_path / "run", DemoProvider(),
                          Runner("trusted-demo"), store_at(tmp_path), max_attempts=1)
    assert report["status"] == "exhausted"
    assert not (tmp_path / "run/patch.diff").exists()


@pytest.mark.parametrize("path", ["../outside.py", "tests/test_stats.py", "/tmp/x.py", "src/../../x.py", "C:\\x.py"])
def test_reject_unsafe_paths(source, path):
    with pytest.raises(ValueError):
        apply_edits(source, [{"path": path, "before": "return 0", "after": "return 1"}])


def test_atomic_validation(source):
    with pytest.raises(SyntaxError):
        apply_edits(source, [
            {"path": "src/stats.py", "before": "return 0", "after": "return 1"},
            {"path": "src/stats.py", "before": "return 1", "after": "return ("},
        ])
    assert (source / "src/stats.py").read_text() == SOURCE


def test_ambiguous_match(source):
    with pytest.raises(ValueError):
        apply_edits(source, [{"path": "src/stats.py", "before": "return", "after": "yield"}])


def test_inventory_does_not_execute(source):
    (source / "src/danger.py").write_text('raise RuntimeError("must not execute")\nimport math\n')
    result = inventory(source)
    assert result["src/stats.py"]["functions"] == ["mean"]
    assert result["src/danger.py"]["imports"] == ["math"]


def test_docker_security_flags(tmp_path):
    command = Runner().command(tmp_path, "test-run")
    for flag in ["--network=none", "--read-only", "--cap-drop=ALL", "--pids-limit=64", "--memory=256m"]:
        assert flag in command
    assert command[-7:] == ["python", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"][-7:]


def test_timeout(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("test", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    result = Runner("trusted-demo", timeout=1).run(tmp_path)
    assert result["timed_out"] and not result["passed"]


def test_empty_suite_rejected(tmp_path):
    (tmp_path / "tests").mkdir()
    result = Runner("trusted-demo").run(tmp_path)
    assert result["exit_code"] == 0
    assert not result["passed"]


def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="required"):
        OpenAIProvider("unused")


def test_html_escapes_test_output():
    report = {"status": "ready_for_review", "attempts": 1, "runner": "test",
              "provider": "test", "run_id": "test", "events": [{"stage": "test", "payload": {
                  "attempt": 1, "passed": True, "log": '<script>alert("x")</script>'}}]}
    html = render_report(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_cli_demo_relative_path(tmp_path, monkeypatch):
    from repoforge.cli import main
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("REPOFORGE_DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["repoforge", "demo", "--output", "run/demo"])
    assert main() == 0
    assert (tmp_path / "run/demo/report.html").is_file()


def test_invalid_proposals_are_bounded(source, tmp_path):
    class BadProvider:
        def propose(self, state):
            return [{"path": "tests/test_stats.py", "before": "test", "after": "skip"}]
    report = run_workflow(str(source), ISSUE, tmp_path / "run", BadProvider(),
                          Runner("trusted-demo"), store_at(tmp_path), max_attempts=2)
    assert report["status"] == "exhausted"
    assert len([e for e in report["events"] if e["stage"] == "rejected"]) == 2


@pytest.mark.skipif(not os.environ.get("REPOFORGE_TEST_POSTGRES"), reason="PostgreSQL not configured")
def test_postgres_roundtrip():
    import uuid
    store = EventStore(os.environ["REPOFORGE_TEST_POSTGRES"])
    run_id = uuid.uuid4().hex
    store.record(run_id, "test", {"passed": True})
    assert store.read(run_id) == [{"stage": "test", "payload": {"passed": True}}]


@pytest.mark.skipif(not os.environ.get("REPOFORGE_TEST_DOCKER"), reason="Docker not configured")
def test_docker_vertical_slice(source, tmp_path):
    report = run_workflow(str(source), ISSUE, tmp_path / "run", DemoProvider(),
                          Runner(), store_at(tmp_path))
    assert report["status"] == "ready_for_review"
    assert report["attempts"] == 2


@pytest.mark.skipif(not os.environ.get("REPOFORGE_TEST_DOCKER"), reason="Docker not configured")
def test_docker_runtime_boundaries(tmp_path):
    # pytest's temp root is mode 0700; mount a normal readable project directory.
    root = tmp_path / "execution"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_boundary.py").write_text('''import os
import socket
import unittest
from pathlib import Path

class BoundaryTests(unittest.TestCase):
    def test_restrictions(self):
        self.assertEqual(os.getuid(), 65534)
        self.assertNotIn("OPENAI_API_KEY", os.environ)
        with self.assertRaises(OSError):
            Path("/workspace/forbidden").write_text("no")
        with self.assertRaises(OSError):
            socket.create_connection(("1.1.1.1", 443), timeout=1)
''', encoding="utf-8")
    result = Runner().run(root)
    assert result["passed"], result["log"]
