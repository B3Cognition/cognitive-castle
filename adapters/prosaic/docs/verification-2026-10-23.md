# Optional adapter verification

The adapter is a separately installed Runtime dependency. No Castle/Harness engine
code is added to Core, Runtime or Harness by this package. Castle storage and
worker qualification are recorded by the parent implementation separately.

On 2026-10-23, Python 3.11.15:

- Source suite: **66 passed**, 7.11 seconds.
- Full suite against the installed candidate modules with `python -I -m pytest
  -c /dev/null --import-mode=importlib`: **66 passed**, 7.14 seconds. Pytest emitted
  one cache-directory warning because `/dev/null` selected `/dev` as its cache
  root; this did not affect the tests or package behavior.
- `python -m build --no-isolation`: wheel and sdist built successfully.
- Clean Runtime-only installed `python -I scripts/wheel_smoke.py`: passed installed
  ownership, absence of Castle/torch/spaCy/Harness, no Castle imports, private
  worker protocol, contextual safe tools and a scope without a conversation run ID.
- `git diff --check`: passed.

The installed consumer environment uses Core 0.4.1, the generic Runtime 0.9.3
candidate with `custom_tool_errors_v1`, Harness 0.8.2, and this adapter 0.1.0.
The independent Runtime-only installed environment has no Harness or Castle/model
packages. Its interpreter is `/private/tmp/castle-memory-adapter-wheel-env/bin/python`.

Coverage includes denied authorization without process dispatch, immutable host
argv grants, closed model schemas, UTF-8 query limits, exact fetch delegation,
strict snapshot expectations and independent encoded snapshot response bounds;
native and structured safe-error behavior is qualified in Runtime's generic patch.
The adapter's real subprocess fixtures exercise malformed handshakes, mismatched
IDs, duplicate JSON, nonfinite JSON, oversized/no-newline stdout, EOF, bounded
stderr under saturation, cold/local/parent/queue deadlines, queued cancellation,
process-group teardown, restart after failure and close racing process creation.

Public installed consumer tests cover Runtime search then fetch, WorkflowBindings,
ConversationBindings with no run ID, frozen input reuse after source mutation,
saved receipt recovery without duplicate model or memory dispatch, native frozen
assignment data without custom-tool grants, disabled memory and explicitly
unavailable optional memory. Retrieved/frozen text remains tool/user data.

The initial adapter tests were run before implementation (12 failed, 31 import
errors for the missing package). Later targeted RED→GREEN checks caught startup
budget narrowing, malformed fingerprints, close racing startup, snapshot bounds,
worker domain-code alignment and parent cancellation overriding a simultaneous
worker error. The original local teardown test also caught a macOS sandbox EPERM
race for an exiting process group; owned direct children are now always reaped.

Candidate artifacts remain unpublished. SHA-256:

```
49183d9c1f0ec2d87ad40b5582603295c4134ca6b17e957ac5dc78554f9442c5  b3_prosaic_memory_castle-0.1.0-py3-none-any.whl
a807ed5822c2dd06978e70a0f40b73a2544b8e19a8e48bc256f8421505f6c83a  b3_prosaic_memory_castle-0.1.0.tar.gz
```

Runtime prerequisite wheel:

```
a0970de47ce8e064168e1143d7cc8133d35c0be867fd790166271c4da2cdacb5  b3_prosaic_runtime-0.9.3-py3-none-any.whl
```

The unchanged Runtime candidate version alone cannot distinguish an older 0.9.3
wheel, so registration enforces the capability as well. Select a distinct released
Runtime version before deployment. POSIX process groups are required in this
initial adapter. No release, push, live endpoint or user corpus was used.

Logs: `/private/tmp/castle-adapter-full.log`,
`/private/tmp/castle-adapter-installed-full.log`,
`/private/tmp/castle-adapter-build.log` and adjacent focused RED/GREEN logs.

Final repository formatting was applied without behavior changes. The rebuilt
installed adapter suite passed **66 tests in 9.14 seconds** and the Runtime-only
wheel smoke passed again. Final logs use `castle-adapter-installed-qualified.log`
and `castle-adapter-wheel-smoke-qualified.log` under `/private/tmp`.
