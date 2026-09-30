import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from repoforge.fixture import ISSUE, create_fixture
from repoforge.providers import DemoProvider, OpenAIProvider
from repoforge.sandbox import Runner
from repoforge.store import EventStore
from repoforge.workflow import run_workflow


def gh(*args, cwd=None):
    return subprocess.run(["gh", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, timeout=90).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="RepoForge: bounded issue-to-patch engineering")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Synthetic fixture, no network or model credentials")
    demo.add_argument("--output", type=Path, default=Path("work/demo"))
    demo.add_argument("--docker", action="store_true", help="Use Docker instead of trusted local fixture")
    live = commands.add_parser("issue", help="Live GitHub issue; Docker and model credentials required")
    live.add_argument("repository", help="owner/repository")
    live.add_argument("number", type=int)
    live.add_argument("--output", type=Path, required=True)
    live.add_argument("--model", required=True, help="An available OpenAI model supporting JSON mode")
    live.add_argument("--publish", action="store_true", help="Push branch and open a draft PR after tests pass")
    live.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output already exists; choose a new directory to preserve earlier runs")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        store = EventStore(os.environ.get("REPOFORGE_DATABASE_URL", "sqlite:///" +
                                         str((args.output.parent / "repoforge.db").resolve())))
        if args.command == "demo":
            fixture = args.output.parent / (args.output.name + "-fixture")
            if fixture.exists():
                raise ValueError("Fixture directory already exists; choose a new output")
            create_fixture(fixture)
            report = run_workflow(str(fixture.resolve()), ISSUE, args.output, DemoProvider(),
                                  Runner("docker" if args.docker else "trusted-demo"), store)
        else:
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository) or args.number <= 0:
                raise ValueError("Expected owner/repository and a positive issue number")
            provider = OpenAIProvider(args.model)
            item = json.loads(gh("issue", "view", str(args.number), "--repo", args.repository,
                                 "--json", "title,body,state"))
            if item["state"] != "OPEN":
                raise ValueError("Issue must be open")
            report = run_workflow("https://github.com/" + args.repository + ".git",
                                  item["title"] + "\n\n" + item["body"], args.output,
                                  provider, Runner(), store, args.max_attempts)
            if args.publish and report["status"] == "ready_for_review":
                checkout = args.output / "checkout"
                subprocess.run(["git", "push", "origin", report["branch"]], cwd=checkout,
                               check=True, timeout=90, capture_output=True)
                url = gh("pr", "create", "--repo", args.repository, "--draft",
                         "--head", report["branch"], "--title", f"fix: address issue #{args.number}",
                         "--body-file", str((args.output / "pull-request.md").resolve()), cwd=checkout)
                print(url)
        print(json.dumps({k: report[k] for k in ["run_id", "status", "attempts", "runner", "provider"]}, indent=2))
        return 0 if report["status"] in {"ready_for_review", "already_passing"} else 1
    except Exception as exc:  # noqa: BLE001 -- CLI boundary redacts external failures.
        # Avoid echoing HTTP responses, authenticated URLs, or external command stderr.
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print("RepoForge stopped: " + detail, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
