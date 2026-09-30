# Engineering decisions

**LangGraph rather than an unbounded agent loop.** Test feedback selects repair or finish. A shared attempt budget governs malformed proposals and valid but ineffective repairs. The state graph includes a back edge; it is not a DAG.

**Exact replacements rather than shell-generated patches.** The provider proposes data, not shell commands. All replacements in one response are checked before any are written. Changes accumulate between attempts, so each proposal sees the latest source and test result. Validation is atomic; filesystem write failures are not transactionally rolled back.

**SQLite plus PostgreSQL.** Both use the same SQLAlchemy schema and JSON events. SQLite keeps onboarding free of infrastructure. PostgreSQL integration is exercised in CI. Events are not graph checkpoints and do not resume interrupted runs.

**Scripted demo rather than unmeasured model claims.** A deterministic first repair fixes empty-input handling; a second fixes division. This reliably demonstrates feedback routing. It cannot measure model reasoning, generalized repair, or issue resolution accuracy.

**Fixed unittest contract.** Standard-library fixtures are reproducible offline. Installing arbitrary project dependencies would require image building and supply-chain controls beyond this slice. Supporting pytest projects and dependency manifests is roadmap work.

**Draft PRs.** Existing tests are incomplete specifications. The publish adapter leaves a review checkpoint and does not merge, deploy, or automatically retry duplicate PR creation.
