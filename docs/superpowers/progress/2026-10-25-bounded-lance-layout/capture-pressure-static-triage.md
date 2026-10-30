# Capture pressure refusal: static triage

Scope: installed commit 0594472692ba5d444e846bb6462af2ef51dd25c3 and the matching capture-priority checkout; static source, launchd configuration and capture-last metadata only. No capture, engine, native test, sysctl probe or production DB read was performed.

## Established code behavior

- `memory_runtime._pressure_refusal` applies a wall deadline of min(operation deadline, now + 0.05) to every background host pressure probe. A live foreground waiter is checked before and after the probe.
- `brain_reader_guardian._pressure_ok` returns false for a timeout, OS/subprocess error, non-normal pressure, or a normal value returned after the caller's deadline. A delayed but normal probe therefore fails closed. Repeated delayed scheduling can prevent all capture progress.
- The guardian independently calls the same helper without a deadline, retaining its original 0.5-second subprocess timeout. Its failure reason is identical to the host's: `system_pressure_unavailable`.
- `memory_coordinator._tick.finish` retains only failure status/reason, dropping the failure resource record. The retained result cannot identify host versus guardian, initial versus periodic check, or timeout versus real non-normal pressure.
- Installed launchd capture uses `ProcessType=Background`, `Nice=10`, and `LowPriorityIO=true`. The significance for actual probe latency remains an inference, not a measurement.

The three installed hashes exactly match the hotfix checkout:

- memory_runtime.py: 85c2bb0cadd14e6fa71777ff4c7651f461b06248d3fa0520acb811c4f03da909
- brain_reader_guardian.py: 5ae996556b487e2eb90f8b44fe404dc4c50eb41ec3e1843a95c72656bf390b83
- memory_coordinator.py: 20521740c257d12bd74cc8e3bf0b625ca472de23cede04f19c99e9b86f588eb1

## Observed metadata and limit of the conclusion

At the read, capture-last had finished_at_ns=1792894661857620000, elapsed_seconds=0.4517, discovery_root=claude, discovery=not_run, successful_slices=0, and reason=system_pressure_unavailable. The parent separately observed repeated refusals and a later normal sysctl result in 0.0063 seconds. Neither observation attributes the refusal to a specific probe site. A genuine non-normal pressure value during the earlier invocation is also not excluded.

## Suggested bounded evidence

Before widening a limit, retain a small fixed diagnostic record: site (host_initial, host_periodic, guardian_initial, guardian_periodic), elapsed probe time, outcome (timeout, late_normal, non_normal, os_error), and numeric pressure when available. Preserve that record through coordinator failure handling; do not include transcript content or source paths.

Existing tests intentionally assert rejection of a late normal response. They do not establish liveness under launchd's low-priority scheduling. Add a deterministic supervisor-level delayed-normal/no-waiter case alongside the existing waiter-arrival case when choosing the desired behavior. Any change must preserve real pressure refusal, foreground preemption, bounded subprocess cleanup, and the whole-operation deadline. Simply increasing 50 ms has not yet been justified by attribution evidence.

This operational capture issue is separate from the Task1b shared five-second cold replay failure.
