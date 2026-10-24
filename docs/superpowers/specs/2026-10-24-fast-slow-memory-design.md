# Fast and slow Castle memory under bounded resource use

User requirement, exact: “I need this Cognitive Castle be your memory like SLow/Fast but with all respect to low memory usage”. This clarifies the existing request to implement, merge, and enable Castle as the assistant's brain. Technical choices below are proposed engineering choices, not words attributed to the user.

## Intended behavior

Fast memory retrieves a few relevant, exact quotations from a durable local index before answering questions about earlier conversations or decisions. Slow reasoning uses the existing bounded host-assisted SUE loop on selected evidence when interpretation needs examination. Article assessment remains separate. Neither path launches a local embedding, reranking, NLP, or answering model. Small tasks do not automatically start SUE.

Both computer RAM and assistant context are budgets. Ordinary recall returns no more than eight short previews, with at most 8 KiB of encoded result; exact text is available in explicit bounded pages. The assistant does not paste the palace into its context. An empty lexical result is not proof that something never happened.

## Storage and provenance

Add a separate private SQLite FTS5 store under the palace. Existing Lance files remain untouched. Store exact UTF-8 text in chunks of at most 8 KiB, without normalization or summarization, with source identity, original offsets, revision, role as attributed by the source, and hashes. Requests to remember text preserve that text exactly. Idempotent writes and source revisions never overwrite the original evidence.

This store is a derived index and a destination for new exact memories, not a claim that all historical drawers have migrated. Status must distinguish indexed, pending, unsupported, oversized, changed, and failed source records. Original files remain available when a record cannot be indexed safely. No broad automatic archive scan or native Lance decoding is a fallback.

## Resource enforcement

Use standard-library SQLite with a small page cache, mmap disabled, disk-backed temporary work, bounded SQL/input/output, and a query progress deadline. Run recall/ingest in a serialized, model-denying supervised subprocess. Initial operational targets: 128 MiB sampled aggregate worker RSS, a 192 MiB parent-plus-task admission/termination tripwire, two seconds per recall, three seconds per ingestion slice, and system-pressure refusal/termination. These are tripwires, not a promise of a kernel-enforced RSS ceiling; measure the real installed path before activation. Chunk admission prevents arbitrarily large source payloads entering SQLite or the host.

There is no resident model and no perpetual indexing daemon. Ingestion is incremental and checkpointed, with small input/record/time budgets. Concurrent requests return a clear busy state. A crash, timeout, memory refusal, disk-full condition, or interrupted transaction leaves existing memories and checkpoints consistent. Index disk growth is capped and reported.

## Historical coverage and future capture

First support exact explicit memories and bounded JSONL ingestion from registered original Codex/Claude transcript sources. Read incrementally; do not call the existing whole-file normalizer. Admit records before decoding with a fixed record-size cap. Oversized records are recorded as pending/unsupported with offsets and hashes, never silently truncated or reported as indexed. Decode recognized text fields exactly and retain original source attribution; do not index arbitrary tool output or embedded commands as trusted user instructions.

Historical backfill is a resumable operator operation over explicitly registered roots. Establish source identity and coverage instead of assuming transcript files reproduce every Lance drawer. The legacy embedding capture path stays paused. Only after installed-path pressure/deadline/crash tests pass may a distinct supervised, model-free incremental capture path be enabled within the user's requested memory scope. It must have its own visible pause/status control and must never fall back to old mining.

## Host and SUE integration

Add bounded exact-memory write/read/status operations and route bounded brain recall to the new source adapter. Memory IDs must be unambiguous; selected complete memory chunks can bind through the existing `archive_ids` mechanism so provenance, exposure revocation, source correction and SUE replay rules remain intact. Ordinary recall must not require creating a SUE root merely to read a quotation.

Retain the trusted, owner-private exposure-policy contract, but bind it to a host selected only by trusted launch configuration (`CASTLE_BRAIN_HOST`, never a tool argument). For configured hosts, store policy and SUE state below `.brain/hosts/<host>/`; validate the host as a short ASCII identifier and reject unsafe directories. Unconfigured legacy clients keep their existing default-deny palace policy. Codex activation grants the requested palace-memory scope only in its own host policy; it does not modify another host's policy. Tool arguments and source labels cannot authorize disclosure. Enabling memory for this assistant is recorded as an operator configuration change under the user's request; do not silently grant other hosts or providers access. All returned excerpts are disclosures to the connected assistant, even though storage and retrieval are local.

Install host guidance that chooses fast recall for history-dependent questions, slow SUE for substantive ambiguity, and neither for greetings or mechanical edits. Preserve unresolved conflicts and cite source versions. No automatic diary summaries, claim of complete archive coverage, or assertion that SUE certifies truth.

## Verification and completion

Required adversarial checks: malformed/oversized UTF-8 and JSONL records; exact chunk reassembly including whitespace and non-ASCII; duplicate retries and changed files; cursor/source revision mismatch; untrusted provenance; policy revocation; read-only query behavior; pressure/deadline/RSS termination and descendant cleanup; busy writers; crash recovery; disk limit; and indexed-coverage reporting.

The installed smoke test must remember an exact synthetic sentence, recall and page it across restart, bind it into SUE, and demonstrate that denial/revocation prevents disclosure. Then perform one narrowly scoped authorized real recall with measured resources. Fast memory is not declared ready until this installed path works; full historical coverage is not declared without a separate reconciliation.

## Builder review

An independent builder identified the missing host-specific policy boundary above; this is resolved as an engineering choice. Existing user authorization covers making Castle this assistant's memory. Expanding ingestion beyond already authorized Castle/conversation roots requires separate authorization. No additional provider, external storage, or model is introduced.
