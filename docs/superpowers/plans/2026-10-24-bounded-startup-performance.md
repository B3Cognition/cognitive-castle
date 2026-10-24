# Bounded startup performance implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the CLI change; an independent worker may implement the process-group scan. Keep tests guarded and review the combined change before release.

**Goal:** Reduce measured cold hook startup toward the existing 100 ms target without weakening resource supervision, policy or exact context delivery.

**Architecture:** Avoid constructing process identities for unrelated PIDs during process-group scans. Add a lightweight console entry point for explicitly configured Codex hooks, delegating all other invocations to the existing CLI. No cache, resident worker, new service or provider is introduced.

**Tech stack:** Existing Python >=3.10, psutil and argparse.

**Spec:** `docs/superpowers/specs/2026-10-24-durable-memory-design.md`; `AGENTS.md` performance budgets.

## Global constraints

- Preserve 128 MiB task and 192 MiB parent-plus-task sampled RSS tripwires, pressure checks, deadlines, parent-death handling and process identity checks.
- Retain process-group enumeration, including reparented descendants. Never substitute a parent-only descendant list.
- Preserve hook input limits, encoded 8 KiB output limit, host policy and legacy pause behavior.
- Keep the full CLI fallback and existing public entry point behavior for unsupported forms and legacy harnesses.
- Do not mutate the installed checkout until focused tests, review and required CI pass.

## Review focus

- PID reuse between group filtering and process-object construction must not select an unrelated process.
- Kernel PID zero, disappearing processes and inaccessible process state must retain safe behavior.
- Explicit `--palace` must take precedence; missing trusted configuration must use existing configuration handling.
- Invalid/unknown CLI arguments must not silently invoke a different command.
- Startup measurements must include actual fresh-process execution, not only an already imported function.

## Task 1: Resource scan

Files: `cognitive_castle/brain_reader_guardian.py`, focused guardian tests.

- [x] Add regressions proving correct group membership while avoiding identity lookups for unrelated processes, including a PID-reuse race.
- [x] Run them against the old implementation and retain the failure evidence.
- [x] Enumerate raw PIDs, filter group membership, construct a checked `psutil.Process`, then recheck membership before yielding.
- [x] Run guarded guardian/runtime tests and report unchanged safety behavior.

## Task 2: Hook console dispatch

Files: new `cognitive_castle/entrypoint.py`, `pyproject.toml`, new `tests/test_entrypoint.py`.

- [x] Add subprocess regressions for configured Codex hook execution without importing the full CLI, palace precedence, unsupported options and fallback.
- [x] Observe the missing fast route fail before implementation.
- [x] Implement `main()` as a narrowly recognized hook fast path; retain `cognitive_castle.cli.main()` for everything else. Reuse `hooks_cli.run_hook` and its input/output handling.
- [x] Run focused hook/CLI tests with the guarded runner, keeping native backend tests separate from supervised-memory tests.

## Task 3: Measurement and release

- [x] Compare bounded fresh-process startup against the same private Sixth Sense fixture and event payload; record every successful sample and explicit refusals.
- [x] Keep the 100 ms target marked unmet unless the measurements support it; do not remove safeguards to obtain a favorable result.
- [x] Independent combined review; no blocking correctness findings. Added a synthetic cold enabled-capture regression for the review proof gap.
- [ ] Required CI, authorized merge and installed console-script verification. Remove the temporary worktree afterward.

## Execution evidence

- Guardian regressions: original implementation failed three of eight cases; removing the post-identity group check failed the PID-reuse regression. Restored implementation passed 47 focused guardian/runtime/source tests.
- Console regressions: original configured entry point failed all 14 initial tests; the new route passed. Review added an enabled bounded-memory cold subprocess test; all 15 entry-point tests pass.
- Combined entry point, guardian, memory runtime and Codex plugin selection: 68 passed before the additional enabled-capture regression. Legacy hooks/wrappers: 90 passed, one skipped.
- Six fresh processes per variant, rotating order, same private Sixth Sense fixture: median 187.85 ms baseline, 175.83 ms guardian only, 164.06 ms combined. All 18 returned identical six-source evidence packets after excluding sampled resources. The 100 ms target remains unmet.
- See `docs/reviews/2026-10-24-bounded-startup-performance.md` for scope and limitations. No runtime safeguards or authorization rules changed.
- A later combined rerun was refused before tests started because macOS memory pressure was elevated. No guard was disabled and no success is claimed for that attempt; the earlier completed runs above and required CI are the verification evidence.
