# Verification record

This file is updated with observed checks during publication. The CI badge links to the current remote run; a configured workflow alone is not evidence of success.

- Local Docker: engine unavailable during initial inspection. Docker and PostgreSQL integration verification is delegated to the repository's CI job, not claimed from this workstation.
- Live model requests and automated GitHub issue-to-PR publication: not run. The optional adapters are implemented, but live compatibility and model repair quality remain unverified.
- Synthetic fixture: original code, four unittest cases, no external dataset or private user information.
- Local CLI demo: completed with `ready_for_review` after two repair attempts. Baseline: three failures; first repair: two failures; second repair: four tests passing. Original fixture remains unchanged. Sanitized [HTML report](demo-report.html) preserves the observed test output.
- Local static checks: Ruff and Git whitespace checks passed. Publication candidate files were scanned for common token/private-key patterns and local user paths; only the intentional Windows path-rejection fixture and public GitHub account links matched the broader path/name scan.
