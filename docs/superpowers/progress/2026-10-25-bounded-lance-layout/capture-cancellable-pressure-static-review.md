# Cancellable background pressure probe: static review

Approved code and prepared two-child process fixture for root's one scoped runtime grant. Installation still needs that actual-process evidence; static review does not establish process cleanup or natural capture progress.

Reviewed base7b095171e877fa3d56523541f81b404f174d1d4c and the complete candidate delta. Verified production and affected-test bindings; final native-test platform guard was reread after the original report hash changed:

- memory_runtime.py: f501317a3965cc2498d6e25a9ff32911ad72753a75b6c85b7e50bba56774ad4b
- memory_coordinator.py: 7b16c7376b66c836a4304658cd759212214b1d296ac64c6bf003a681e6428143
- test_cancellable_pressure_probe.py: fb24d01f71e4da931a75c75332f22c234d9930a9e72b463c4e246326bf4e98c0
- test_capture_pressure_attribution.py: 1609b03e02bf0f7aea8003f0a1bbbc22f070f59a37018c71e6bde8c643a5750d
- test_memory_capture_priority.py: a7a0d0cf977ca2db75b65e375d5462cc7d8b24078298cca56c05caa77aa7c9e3

The background path issues exactly one fixed sysctl command, reads at most65 bytes to enforce64 bytes, requires complete output and exit0, and waits in intervals at most10ms. Its cutoff is the earlier original operation deadline or original0.5-second probe ceiling. A seen waiter remains sticky through exact-child cleanup. Selector/stdout close, kill-if-live and bounded50ms reap occur before normal acceptance; an unconfirmed reap propagates, never becoming a clean success/refusal. Normal output after spawn/cleanup consumes the deadline is refused. Foreground and guardian boolean probe paths remain unchanged.

Periodic waits retain original RSS sampling and additionally charge the unreaped host pressure child, avoiding a new half-second monitoring gap. Fixed diagnostic metadata remains body-free. The final background result gate discards success payload if its acceptance clock has expired. Existing guardian cleanup still runs after that gate with its original cleanup allowance: this patch does not establish a hard end-to-end scheduling/cleanup wall guarantee.

Read author-recorded34 guarded pure passes, including78.45ms healthy acceptance, cancellation during/after reading, short overall/probe expiry, slow spawn/cleanup, invalid/oversized output, resource refusal and failed reap. Reviewer did not run them. The native fixture substitutes only the exact sysctl argv with two literal Python stubs; one returns normal after80ms, one is cancelled by a real waiter marker. It records clean/reaped/closed status before its emergency cleanup and verifies both captured process identities are gone. It holds admission, has no DB/model/source operations, and now skips non-macOS before admission imports (the sole review correction).

No runtime, process fixture, pressure probe, installation, source DB access or product edit by reviewer. Root controls the proposed single30s/256MiB safe-runner node and subsequent natural launchd observation.
