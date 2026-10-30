# One no-op supervisor timing diagnostic — preparation only

Fixed pytest node: `task3-supervisor-timing-diagnostic.py::test_supervisor_timing_attribution`. One `_supervise` call under existing background pressure/preemption,2s stage,128MiB task/192MiB aggregate. Root owns independent fresh preflight, unique basetemp, exclusive output/result creation and actual launch. No retry or qualification attempt; failure emits the same timing record then fails.

The same diagnostic file is the fixed Python `-I --worker` child. It imports only stdlib sys/time/json, consumes the bounded original stdin frame and validates only a positive integer _host_pid, then writes status plus absolute monotonic entry/emit timestamps (<256B), then exits. Entry is after initial interpreter startup and sys/time imports; it is not an OS process-creation timestamp. No database, engine, source, model, network, original path or dataset operation.

Host monkeypatches only existing pressure, RSS-sampling, Popen and finish calls; signatures/return values/limits unchanged. Counters are [calls,total_us,max_us]. Initial/periodic pressure and RSS intervals can overlap because pressure waiting samples RSS: do not add them as exclusive phase totals. Popen counters separate the exact fixed host sysctl and guardian commands. The unchanged guardian owns its normal worker and cleanup. The residual guardian-spawn-to-worker-entry includes guardian interpreter/import/config/pressure and worker startup; this fixture does not separately attribute those child phases.

One stdout `SUPERVISOR_TIMING` JSON record is bounded to2KiB, including full `_supervise` wall time, finish offset, guardian Popen start/end offsets, worker-entry delta from guardian spawn return, and post-finish cleanup delta. Existing stage RSS metrics are retained. Existing `resources.elapsed_seconds` excludes host finally cleanup; full call wall includes it. No guardian/product file is edited and no additional pressure probe/process is added beyond the no-op worker replacing the normal fixed worker.

Root's proposed exact finite selection (no execution by author):

```
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 5 --rss-mib 256 .superpowers/sdd/2026-10-25-bounded-lance-layout/task3-supervisor-timing-diagnostic.py::test_supervisor_timing_attribution --noconftest -x -q -s -p no:cacheprovider --basetemp /private/tmp/castle-task3-supervisor-timing-20261025-v1
```

The safe runner keeps models/network disabled and supplies the outer5s/256MiB sampled guard. Pytest import/test setup is charged to this outer guard; original internal2s/128/192 remain. There are no data fixtures or generated files beyond pytest's unique basetemp and root's externally captured output. Static AST/compile/Ruff only; no runtime has occurred.
