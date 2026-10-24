# Castle PR #106 split and CI qualification

User instruction: split shared hardening, optional provider integration and release packaging; preserve existing Castle modes, leave Prosaic memory disabled by default, and resolve CI timeouts before release. Explain SUE separately; do not add it to provider reads.

## Boundaries and order

1. `codex/castle-shared-hardening` targets develop. Include palace path isolation, revision/completion fidelity, mutation locking, recoverable reindex, explicit configuration, shared ranking/failure fixes, their regressions, and CI diagnosis/fixes. No provider worker/adapter, memory profiles, release version bump or model dependency removal. Keep existing standalone fast-memory, SUE and SOAR code/modes. Reindex and conservative pruning fixes deliberately change unsafe behavior; document them rather than claim byte-identical legacy behavior.
2. `codex/castle-optional-memory-provider` targets the hardening branch. Add read-only worker/service/protocol, FTS-first and opt-in dense/recency profiles, Prosaic adapter, examples, benchmarks and original verification records. Keep host activation explicit; use the already disabled Lab configuration. The root entry point belongs here; root release version stays 3.4.1.
3. `codex/castle-release-packaging` targets the provider branch. Add 3.4.2 metadata/plugin alignment, public-index-compatible language model provisioning, source-archive contents and package verification. Retain historical candidate checksums as historical evidence; new split candidates must be rebuilt and qualified before publication.

Original PR #106 stays intact until all three replacement PRs exist, then is closed as superseded with links. Preserve original commits and all local/committed evidence. No merge, tag or package publication is authorized by this split.

## Tasks and gates

- [ ] Save original ad18037 source identity, classify every changed file/hunk, and create stacked branches using apply_patch for edits.
- [ ] Run the shared suite and focused compatibility tests at stage 1, including unchanged standalone/SUE/brain tests. No assertions, supported-platform checks or 85% coverage threshold may be weakened.
- [ ] Diagnose timeout from job steps and retained stack/test logs. Add bounded diagnostics at the failing boundary before a speculative product fix. Run actual GitHub matrix until resolved, retaining failure evidence.
- [ ] Restore full optional provider behavior at stage 2, run root and adapter suites and benchmark, verify default FTS order and forbidden optional engines.
- [ ] Build stage 3 archives, run strict metadata/wheel/sdist smoke checks. Verify final production code matches the original candidate except individually justified CI fixes.
- [ ] Create three draft PRs, attach each, cross-link dependencies, update original PR and Lab release-candidate references without discarding historical verification.
- [ ] Inspect final diff and fresh CI results; rerun native Linux AMD64/ARM64 × PostgreSQL 16/18 qualification when candidate source/archive identities change. Keep release blocked until required evidence is green.
- [ ] Explain existing SUE entry points and propose a separate optional advisory review integration: Castle supplies exact frozen evidence/pure policy, Runtime owns model calls, Harness owns state/budgets/resume. No SUE/SOAR on memory reads.

## Review focus

Existing CLI modes and installed entry points; legacy/default auxiliary paths; historical revisions/manual records through reindex; signed/nonfinite reranker scores and final judge order; optional provider import/startup with no model/engine execution. Each is covered by existing targeted regression files and the full suite, not source-shape-only assertions.

Ruling: execute the user's concrete three-way split directly; no additional design approval is needed. Use existing isolated worktree and retain the original branch. Independent read-only CI and SUE investigations are delegated under the parallel-agent skill; root owns branch mutations.
