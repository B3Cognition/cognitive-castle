# Capture-priority hotfix: independent static review

Status: **no static blocker; approved for the two focused root-owned process/queue tests**. Runtime outcomes and deployment are not asserted by this review.

Reviewed isolated worktree `/Users/ladislavbihari/myWorks/cognitive-castle-capture-priority`, base `6402ae52d117b86ce61d8f7b92917c2078a5558a`: complete three-file production delta and complete new test module, with surrounding admission, coordinator, supervisor cleanup and test-parent code. No tests, engines, Castle calls, process launches or source/queue/database reads were performed by this reviewer. This report is outside both the hotfix source tree and sealed capacity packets.

- `cognitive_castle/brain_reader_guardian.py`: 7316 bytes, SHA-256 `5ae996556b487e2eb90f8b44fe404dc4c50eb41ec3e1843a95c72656bf390b83`.
- `cognitive_castle/memory_coordinator.py`: 25034 bytes, SHA-256 `20521740c257d12bd74cc8e3bf0b625ca472de23cede04f19c99e9b86f588eb1`.
- `cognitive_castle/memory_runtime.py`: 16211 bytes, SHA-256 `85c2bb0cadd14e6fa71777ff4c7651f461b06248d3fa0520acb811c4f03da909`.
- `tests/test_memory_capture_priority.py`: 12148 bytes, SHA-256 `9d6d0d16a519e11883a708079f263a4d80d3285fc9cf1849807e510ad5938a8c`.

The reported failure chain is addressed at its origin: capture coordinator calls now explicitly use a trusted Boolean background=True host argument. Existing callers default to foreground; the policy is not added to accepted worker request fields. Background admission checks live foreground intent before and after acquiring the shared lock, returns memory_busy immediately if admission is held, and never creates the interactive waiter marker or enters the foreground retry loop. Its acquired descriptor is closed on refusal. Unsafe waiter metadata fails closed through the existing checker.

Admitted background capture enables supervisor checks before launch and during the event loop. A real foreground waiter produces background_preempted through the unchanged finally path that kills the owned process group, waits for its guardian, closes pipes, and releases admission only after descendants have exited. A waiter racing around the pressure query is checked on both sides. Foreground supervision keeps its existing behavior.

The optional pressure deadline preserves the default 0.5-second helper timeout. Background pressure queries use at most 50 ms and the remaining supervisor deadline; a late normal reading is rejected. The initial pressure query and subsequent work share the same background clock, with a deadline check before spawning. Existing RSS thresholds, operation deadlines, request fields, response limit, durable queue/spool logic and cleanup path are unchanged.

The recorded 13 focused pure cases cover busy/no-marker behavior, live waiter priority, the post-acquire race, foreground default behavior, trusted Boolean validation, pressure-query deadline/default behavior, waiter arrival during a timed-out query, and preserved spool bytes on busy capture. The surrounding coordinator tests inspected accept forwarded keyword arguments, so the added host scheduling keyword does not conflict with those stubs.

The two proposed bounded process tests target the necessary behavior: a live background worker survives another scheduled-capture attempt but is preempted by real foreground work, after which admission is reacquired and the worker is gone; and a queued source plus spooled event survive busy capture and later produce both exact texts after resumption. Both use temporary fixture data. The parent owns sole runtime admission and should retain actual results before any merge/install claim.

Non-blocking test robustness note: the new process test checks `pid_exists(pid)` followed by `Process(pid).status()` without catching NoSuchProcess. A process can disappear between those calls, producing a false test failure. The existing `_process_alive` helper in test_memory_runtime.py already handles that lifecycle race and can be reused. This does not affect production cleanup behavior.
