# Codex capture safety

Codex Stop and PreCompact hooks file the supplied transcript. They acquire the
same nonblocking per-palace lock used by project mining before loading the
conversation miner. A competing capture exits immediately instead of waiting
with another model instance in memory. The OS releases the lock when the
holder exits, including after an error.

Capture passes `skip_kg=True`, so filing one transcript does not also scan the
archive's knowledge graph backlog. Explicit mining retains its existing KG
behavior. Conversation dry runs never start KG enrichment.

## Pause automatic capture

Create this file without invoking Castle:

```sh
mkdir -p ~/.castle
touch ~/.castle/codex-capture.disabled
```

The adapter checks this marker on every Stop/PreCompact invocation before
loading configuration, storage or the miner. It therefore also protects against
a running harness retaining hook registrations after its settings were edited.
SessionStart and explicit searches are unaffected. Already running workers are
not cancelled by creating the file.

Keep capture paused while investigating memory pressure. Removing the marker
allows subsequent registered hooks to capture again; doing so should be a
deliberate action after validation, not part of a repair or test script.

## Limits and verification

When the palace is busy, capture skips that attempt and leaves the transcript
available for a subsequent hook or manual retry. There is no persistent retry
queue, so the final turn is not guaranteed to be filed without another attempt.
The lock prevents overlapping cooperating miners for the same palace; it is
not a system-wide limit on searches, other palaces or model memory.

The targeted regression suite is:

```sh
python -m pytest tests/test_codex_capture_safety.py tests/test_codex_plugin.py tests/test_palace_locks.py -q
```

It uses temporary storage and a tiny synthetic transcript. The integration test
substitutes small synthetic embedding vectors and rejects model imports while
checking exact text preservation, repeat-capture deduplication and absence of KG
enrichment. The suite also verifies pause enforcement, lock contention and
release after failure. It does not measure peak memory on a production archive
or with real models.
