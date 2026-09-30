# Verification record

This file is updated with observed checks during publication. The CI badge links to the current remote run; a configured workflow alone is not evidence of success.

- Local Docker: engine unavailable during initial inspection. Docker and PostgreSQL integration verification runs in GitHub CI, not on this workstation.
- Live model requests and automated GitHub issue-to-PR publication: not run. The optional adapters are implemented, but live compatibility and model repair quality remain unverified.
- Synthetic fixture: original code, four unittest cases, no external dataset or private user information.
- Local CLI demo: completed with `ready_for_review` after two repair attempts. Baseline: three failures; first repair: two failures; second repair: four tests passing. Original fixture remains unchanged. Sanitized [HTML report](demo-report.html) preserves the observed test output.
- Local static checks: Ruff and Git whitespace checks passed. Publication candidate files were scanned for common token/private-key patterns and local user paths; only the intentional Windows path-rejection fixture and public GitHub account links matched the broader path/name scan.
- Local tests: 17 passed, 2 integration tests skipped in the initial local run. A third optional integration test was subsequently added for Docker runtime boundaries.
- [Initial CI run](https://github.com/dileepreddy27/repoforge-agent/actions/runs/36650461748): 19 passed, including PostgreSQL event roundtrip and the Docker two-attempt vertical slice. The additional Docker boundary test failed because its mounted pytest temporary root had mode 0700. Its fixture now mounts a normal readable project directory and includes runner logs on failure. The CI badge tracks the final rerun, including all 20 tests and the Docker CLI demo.
