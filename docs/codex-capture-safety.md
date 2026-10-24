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

## Cleaning a palace the old hooks bloated

A palace that ran the directory-wide Stop hook for months holds the same
transcript many times over, plus the whole-file "giant" drawers of the pre-v3
chunker. On one 20 GB palace, 356k of 877k rows and 13.1 of 13.8 GB of text
were superseded revisions; 10k legacy rows of Codex rollouts (up to 142 MB
each) held 12.9 GB of it. The clean-up is four steps, each reversible until
the last:

1. `castle prune-revisions` (dry run), then `--apply`. Rows are deleted
   through Lance deletion files; the data stays readable in the previous
   table versions. A plan over 877k rows takes ~20 s and 2.6 GB.
2. Drop knowledge-graph rows that point at the deleted drawers
   (`mentioned_in` triples and `enrich_scanned` marks); the enricher will
   not re-scan a drawer it has marked, and a dangling pointer is a dead
   search hit.
3. Compact with bounded memory. `castle optimize` uses LanceDB's default
   scan batch; on a palace that still holds giant rows run pylance's
   `compact_files(materialize_deletions=True, num_threads=1, batch_size=16)`
   instead, under a watchdog. A failed or killed compaction commits
   nothing.
4. Reclaim the disk: `castle optimize --skip-fts --prune-older-than 0`
   (or `cleanup_old_versions(older_than=0)`). This is the irreversible step.
   Every long-running `castle-mcp` opened before it is pinned to an old
   version (LanceDB checks consistency only when asked) and must be
   restarted afterwards.

Keep the source transcripts: the kept revision is complete, but a source
file on disk is what lets `castle mine` rebuild a drawer if one is ever
needed again.
