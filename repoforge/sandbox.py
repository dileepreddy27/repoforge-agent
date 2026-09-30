"""Fixed unittest command; Docker execution never receives host credentials."""
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

TEST_COMMAND = ["python", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]


class Runner:
    def __init__(self, mode="docker", timeout=45, image="python:3.11-slim"):
        if mode not in {"docker", "trusted-demo"}:
            raise ValueError("Unknown runner")
        self.mode, self.timeout, self.image = mode, timeout, image

    def preflight(self):
        if self.mode == "docker":
            try:
                result = subprocess.run(["docker", "image", "inspect", self.image],
                                        capture_output=True, timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ValueError("Docker unavailable; start the engine and pull python:3.11-slim") from exc
            if result.returncode:
                raise ValueError("Docker image unavailable; start the engine and pull python:3.11-slim")

    def command(self, root: Path, name: str) -> list[str]:
        if self.mode == "trusted-demo":
            return [sys.executable, *TEST_COMMAND[1:]]
        return [
            "docker", "run", "--rm", "--name", name, "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
            "--memory=256m", "--cpus=1", "--user=65534:65534",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=32m", "--mount",
            f"type=bind,source={root.resolve()},target=/workspace,readonly",
            "--workdir=/workspace", "--env=PYTHONPATH=/workspace/src", self.image, *TEST_COMMAND,
        ]

    def run(self, root: Path) -> dict:
        name = "repoforge-" + uuid.uuid4().hex[:12]
        env = None
        if self.mode == "trusted-demo":
            env = {key: value for key, value in os.environ.items()
                   if key.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}}
            env["PYTHONPATH"] = str(root / "src")
        # File-backed capture prevents unbounded Python memory growth from test output.
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(self.command(root, name), cwd=root, env=env,
                                        stdout=output, stderr=subprocess.STDOUT, timeout=self.timeout,
                                        check=False)
                code, timed_out = result.returncode, False
            except subprocess.TimeoutExpired:
                code, timed_out = 124, True
            except FileNotFoundError as exc:
                raise RuntimeError("Runner unavailable; install/start Docker or use the trusted demo") from exc
            finally:
                if self.mode == "docker":
                    try:
                        subprocess.run(["docker", "rm", "-f", name], capture_output=True,
                                       timeout=10, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            output.seek(0)
            log = output.read(24_000).decode("utf-8", errors="replace").replace("\r\n", "\n")
        # Docker infrastructure failures and empty discovery are never test success.
        passed = code == 0 and "Ran 0 tests" not in log and "Ran " in log and "\nOK" in log
        return {"passed": passed, "exit_code": code, "timed_out": timed_out, "log": log,
                "runner": self.mode}
