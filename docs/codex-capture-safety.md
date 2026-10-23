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

## Claude Code hook bounds

The Claude Code Stop/PreCompact hook (`castle hook run --harness claude-code`)
spawns `castle mine <transcript> --mode convos --wing sessions --skip-kg` for
the one transcript it was handed. It never mines the transcript's directory:
that re-read every sibling session and every `tool-results/*.txt` dump on
each fire, and re-filed the growing transcript as a complete new revision
every `SAVE_INTERVAL` exchanges.

Transcripts larger than `CASTLE_HOOK_MAX_TRANSCRIPT_MB` (default 100; `0`
disables the cap) are skipped with a `hook.log` line. A hook fire costs the
size of the whole session so far, because a revision is the whole file.
Mine such sessions explicitly, or on a schedule, when the machine is idle:

```sh
castle mine ~/.claude/projects/<project>/<session>.jsonl --mode convos --wing sessions --skip-kg
```

Superseded revisions of re-mined files are removed by
`castle prune-revisions --apply` (dry run without `--apply`).

The Stop hook still writes the diary checkpoint in the hook process, which
loads the embedding model (about 1.1 GB, ~9 s for MiniLM) once per fire.
That is bounded and transient, but it is the remaining per-fire cost.

## MCP server memory

`castle-mcp` imports in ~50 MB and loads the embedder and cross-encoder on
the first search; after that each Claude Code session's server holds its own
copy of both models for the session's lifetime. Wing/room counts
(`castle_status`, `castle_list_wings`, `castle_list_rooms`,
`castle_get_taxonomy`) stream the `wing` and `room` columns and never load
rows. Metadata-only `get()` calls project away text and vectors.
