# Durable memory, work context and removal of the native SOAR dependency

User objective, verbatim: "Priorita je teď dokončit zachytávání, obnovu pracovního kontextu a měření úplnosti. Nahrazeni SOARu ktery uplne nepotrebujeme. Potrebuji od tebe dukazy ze to funguje. Treba to testuj v souvislosti se Sixth Sense. Optarne s tokenama"

## Outcome

Deliver the next production slice of Castle as usable persistent memory: dependable incremental capture and reconciliation, bounded evidence-backed context on return to a workspace, inspectable current capture coverage, and pure Python symbolic ranking in place of the native Soar engine. Demonstrate restart, correction, incomplete source and retry behavior using synthetic fixtures plus privately held real Sixth Sense evidence. Do not claim universal 100% retrieval or complete historical migration without reconciliation evidence.

## Architecture and constraints

Use the existing private SQLite sidecar, exact UTF-8 source chunks, isolated model-denying worker and guardian. No resident model, new database service, automatic legacy mining, or external provider. Preserve original records and existing source generations. Runtime worker aggregate RSS remains 128 MiB and parent-plus-task 192 MiB sampled tripwires, not hard kernel guarantees; worker operations remain bounded to 2 seconds reads / 3 seconds writes. Local tests use the guarded runner; the full model-dependent suite runs on CI only. Python >=3.10. All tool responses remain <=32 KiB; ordinary recall and startup context each <=8 KiB encoded, at most eight exact excerpts.

### Capture and coverage

Persist observed sources and their current durable ingest state in the same SQLite store. Distinguish observed bytes, processed bytes, indexed text, deliberately excluded records/blocks, unsupported content, incomplete tails, malformed/oversized records, and failures. Do not count skipped records as captured text. Historical observations stay available, but aggregate current status must not mistake resolved pending attempts for active gaps. Store generation, identity, size/mtime observation, last outcome and latest checkpoint. Freshness is explicitly last-observed, not proof of unchanged historical bytes.

Hooks queue only original files within operator-registered roots; they cannot register arbitrary roots. Use a bounded single-worker coordinator and durable pending queue; retry on later invocations/reconciliation. Process hooks, startup catch-up and explicit CLI reconciliation through this path, leaving the old capture pause marker intact. Provide an independent pause/status for the new path. Discovery and backfill must be paged/checkpointed and deadline-bounded, never read all transcripts into memory. Use current registered Codex/Claude roots; Sixth Sense project sources are separately and explicitly scoped for evaluation. Avoid changing another client's plugin configuration.

### Context restoration

Persist workspace association and source references, not invented diary summaries. On SessionStart, return a bounded exact evidence packet from the same workspace, including recent user intent and assistant outcomes and observable coverage/gaps. For compaction, queue capture in PreCompact and restore context in the following SessionStart with `source: "compact"`. Codex supports additional context on that SessionStart before continuation; PreCompact supports shared output fields, not additional context. See the [official hook lifecycle](https://learn.chatgpt.com/docs/hooks). Label roles as source attribution and historical statements as evidence, not current commands. A session/workspace boundary must be supplied by the host, not guessed from a matching word. Include exact IDs/hashes/offsets for paging. A small explicitly recorded active-work manifest may hold goal/status/open items with supporting source IDs; derived state stays identified and revisioned. Completion/cancellation must not be silently resurrected. Content delivery must respect the existing host exposure policy and remain usable after process restart.

### SOAR replacement

Replace the native kernel/agents/production parsing with deterministic Python rules for recency, project, entity and query-type. Preserve supported ranking behavior and score audit compatibility, resolve custom `.soar` configuration explicitly, and remove native dependencies/imports/rule-loading from production paths. Do not silently claim arbitrary custom Soar programs are supported. Existing Fast/Slow memory stays independent. Regression cases cover multiple tags, no match, invalid time, duplicate source identities, negative scores and input immutability where applicable.

### Evidence and release

Use a private Sixth Sense fixture of exact local source spans with hashes and provenance; never commit organization source text into the public Castle repository. Include questions that distinguish current implementation from design targets, later corrections from stale text, and related API/backend constraints. Record complete supporting evidence recall within the fixed output budget, not just a keyword hit. Public tests use synthetic equivalents. Demonstrate restart, duplicate delivery, pending tail completion, source rotation, pressure refusal, concurrent capture, current coverage and visible exclusions. Verify actual installed CLI and client hook output. Activation must preserve unrelated config and legacy pause, use backups, and expose rollback. Full completion needs code review, green required CI, merge/deployment under existing authorization, and a linked report of measured outcomes and remaining coverage.

The [release evidence](../../reviews/2026-10-24-durable-memory-evidence.md) records
merged CI and installed CLI/MCP verification separately from actual client
dispatch. CLI event payloads exercise the supported lifecycle but do not prove
that an already running client has reloaded hooks or tools. That client check
remains open. Installed measurements also miss the repository's 100 ms startup
target; meeting the two-second read deadline and 500 ms hook budget does not
resolve that target gap.
