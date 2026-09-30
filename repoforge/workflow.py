import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import TypedDict

from git import Actor, Repo
from langgraph.graph import END, START, StateGraph

from repoforge.analysis import apply_edits, inventory
from repoforge.report import render_report


class State(TypedDict, total=False):
    run_id: str
    issue: str
    attempt: int
    modules: dict
    sources: dict
    result: dict
    status: str
    error: str


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run_workflow(source: str, issue: str, output: Path, provider, runner, store,
                 max_attempts=3) -> dict:
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be between 1 and 5")
    runner.preflight()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    checkout = output / "checkout"
    repo = Repo.clone_from(source, checkout, multi_options=["--no-hardlinks"])
    branch = "repoforge/" + run_id[:12]
    repo.git.checkout("-b", branch)
    # Never pass .git (which may contain authenticated URLs) into the sandbox.
    execution = output / "execution"
    shutil.copytree(checkout, execution, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    for path in execution.rglob("*"):
        if path.is_symlink():
            raise ValueError("Repositories with symlinks are unsupported")
    if not (execution / "tests").is_dir() or not (execution / "src").is_dir():
        raise ValueError("Supported repositories require src/ and tests/ directories")
    tests_hash = tree_digest(execution / "tests")

    def analyze(state):
        modules = inventory(execution)
        store.record(run_id, "analyze", {"modules": modules, "branch": branch})
        return {"modules": modules}

    def test(state):
        result = runner.run(execution)
        if tree_digest(execution / "tests") != tests_hash:
            result["passed"] = False
            raise ValueError("Test files changed during execution")
        store.record(run_id, "test", {"attempt": state["attempt"], **result})
        return {"result": result}

    def repair(state):
        attempt = state["attempt"] + 1
        sources = {p: (execution / p).read_text(encoding="utf-8")
                   for p in state["modules"] if p.startswith("src/")}
        if sum(map(len, sources.values())) > 150_000:
            raise ValueError("Source context exceeds 150 KB")
        try:
            edits = provider.propose({**state, "attempt": attempt, "sources": sources})
            apply_edits(execution, edits)
            store.record(run_id, "repair", {"attempt": attempt, "files": [e["path"] for e in edits]})
            return {"attempt": attempt, "error": ""}
        except (ValueError, KeyError, SyntaxError, TypeError) as exc:
            # Structured validation failures consume the same bounded retry budget.
            store.record(run_id, "rejected", {"attempt": attempt, "reason": type(exc).__name__})
            return {"attempt": attempt, "error": "Proposal rejected: " + type(exc).__name__}

    def route(state):
        if state["result"]["passed"]:
            return "finish"
        if state["attempt"] >= max_attempts or state["result"]["exit_code"] in {124, 125, 126, 127}:
            return "finish"
        return "repair"

    def finish(state):
        if state["result"]["passed"] and state["attempt"] > 0:
            for path in (execution / "src").rglob("*.py"):
                relative = path.relative_to(execution)
                shutil.copyfile(path, checkout / relative)
            diff = repo.git.diff("--", "src")
            if not diff.strip():
                status = "no_change"
            else:
                (output / "patch.diff").write_text(diff, encoding="utf-8")
                repo.git.add("--", "src")
                actor = Actor("RepoForge Agent", "agent@example.invalid")
                repo.index.commit("fix: repair issue with passing regression tests", author=actor, committer=actor)
                status = "ready_for_review"
        elif state["result"]["passed"]:
            status = "already_passing"
        else:
            status = "exhausted"
        store.record(run_id, "finish", {"status": status, "attempts": state["attempt"]})
        return {"status": status}

    graph = StateGraph(State)
    for name, node in [("analyze", analyze), ("test", test), ("repair", repair), ("finish", finish)]:
        graph.add_node(name, node)
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "test")
    graph.add_conditional_edges("test", route, {"repair": "repair", "finish": "finish"})
    graph.add_edge("repair", "test")
    graph.add_edge("finish", END)
    try:
        state = graph.compile().invoke({"run_id": run_id, "issue": issue, "attempt": 0},
                                       {"recursion_limit": 30})
    except Exception as exc:
        store.record(run_id, "error", {"type": type(exc).__name__})
        raise
    report = {"run_id": run_id, "branch": branch, "status": state["status"],
              "attempts": state["attempt"], "commit": repo.head.commit.hexsha,
              "runner": runner.mode, "provider": type(provider).__name__,
              "events": store.read(run_id)}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "report.html").write_text(render_report(report), encoding="utf-8")
    (output / "pull-request.md").write_text(
        "## Problem\n\n" + issue + "\n\n## Validation\n\n"
        f"- Status: {state['status']}\n- Repair attempts: {state['attempt']}\n"
        f"- Runner: {runner.mode}\n- Provider: {type(provider).__name__}\n"
        "- Existing tests preserved; passing tests do not prove semantic correctness.\n\n"
        "## Review\n\nInspect patch scope, behavior, and missing regression coverage before merging.\n",
        encoding="utf-8",
    )
    return report
