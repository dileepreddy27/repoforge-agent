# Security boundaries

The orchestrator is a developer tool for reviewed repositories on a disposable machine. It is not designed to safely execute arbitrary hostile repositories on a valuable workstation.

## Enforced controls

- Live CLI runs tests only in Docker with network disabled, read-only mounts/root, non-root UID, dropped capabilities, no-new-privileges, and resource/time limits.
- The execution copy excludes `.git`; the orchestrator never injects model keys or GitHub credentials into the container environment.
- Proposed edits target existing Python files under `src/`; traversal, symlinks, ambiguous replacements, oversized edits, and invalid syntax are rejected before writes.
- Test files are hashed before and after each execution. Only source files are copied back to the Git checkout.
- The default live flow does not push. `--publish` is an explicit opt-in; pull requests are drafts and never merged automatically.
- API and external-process exception bodies are not echoed by the CLI, and no plaintext credentials are intentionally stored in run events.

## Remaining risks

Repository content is untrusted input. Prompt instructions are not a security boundary. A model can generate malicious but syntactically valid Python; a passing test suite can miss it. Test output may be spoofed by malicious source, and logs can contain sensitive repository content. A Docker kernel escape remains possible. The Docker daemon itself is privileged.

Clone and AST parsing run on the host. Git clone has no size/time quota in this version. Output capture limits report size but does not cap temporary disk use. Failed container cleanup is best effort. A public repository could already contain embedded secrets, which this tool does not automatically classify or redact. Never submit secret-bearing source to an external model.

Use short-lived hosts, narrowly scoped credentials, reviewed images, and human review. Add a microVM boundary and structured runner protocol before considering hostile multi-tenant use.
