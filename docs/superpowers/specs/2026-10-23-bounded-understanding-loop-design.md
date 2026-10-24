# Castle: article assessment and a bounded problem-understanding loop

Status: **proposed design v2**, adversarially reviewed against code at `b57a84f`.
No production loop is implemented or enabled. This supersedes the v1 design.
See the [edge-case review and acceptance matrix](../../reviews/2026-10-23-understanding-loop-edge-cases.md).

## 1. Intent and limits of the claim

The user wants persistent working memory: `understanding` assesses article
quality; SUE examines the assistant's interpretation of a problem; the findings
must change what the assistant does next. Preserve exact evidence separately
from proposed interpretations, model judgments and independently checked results.

The default proposed examination is **host-assisted**. The active assistant
answers SUE questions; Castle validates the protocol and persists its state.
It is structured self-examination, not independent corroboration. It loads no
additional model and makes no provider call itself. Returning archive content
to a cloud host can still disclose that content externally; section 4 governs
that boundary. Existing explicit provider-based SUE reviews remain separate.

The bundled engine examines interpretations of stated commitments. For a factual
hypothesis, debugging problem or mixed question, it can clarify the problem and
obligations, but cannot establish the empirical answer. Record examination kind:
`commitment_interpretation`, `decision_framing`, `empirical_hypothesis` or `mixed`.
Empirical tests, factual corroboration and implementation checks are separate
obligations. Never relabel an observation as a requirement to obtain RESOLVED.

No metric, citation check, engine terminal or empty search result certifies truth,
complete understanding, archive completeness or authorization to take an action.
The host remains responsible for following the user's instructions and assessing
the argument. The controller returns an advisory, with its exact limits.

## 2. Default workflow and useful feedback

1. Freeze the current problem verbatim; identify the requested outcomes, actors,
   constraints and known unknowns. The interpretation is a separate proposal.
2. Recall narrowly scoped evidence through the model-free, read-only path in
   section 5. If unavailable, start from explicitly supplied evidence and report
   unavailable recall. Zero archive matches is a valid starting condition.
3. Assess explicitly identified articles when relevant. Article readability must
   neither stand in for problem understanding nor suppress conflicting evidence.
4. Begin the SUE examination. `begin` and every accepted `respond` return the next
   operator/question reference/schema reference directly; no polling roundtrip
   is required between questions.
5. If the examination exposes a gap, gather evidence for that named gap, request
   an authoritative decision, or explicitly revise the interpretation. New source
   bytes or material source roles require a linked examination with fresh coverage.
6. Persist the examined interpretation, remaining obligations, issues, sources,
   judgments and outcome as derived records. Do not file these as original memory.
   Later retrieval includes scope, date, source versions and known limitations.

Default frequency is still a product choice: the recommendation is substantive
problem solving, skipping greetings, formatting and straightforward mechanical
requests. Ordinary recall and article assessment do not automatically trigger
SUE. Installing a skill cannot force every host to obey it; the supported-host
integration must be tested. There is no perpetual agent or archive-scanning loop.

## 3. Problem scope, issues and action advisory

Freeze the original request independently of the mutable examined claim. Maintain
an obligation ledger: outcome/constraint, exact request span, actor/scope, status,
and applicability. The ledger is explicitly an assistant interpretation, not a
proof that every implication of prose was captured. Display unrepresented or
ambiguous parts rather than declaring full request coverage.

Every claim revision includes a retained/changed/dropped commitment map and its
impact on obligation IDs. A narrower claim cannot remove a user obligation.
Partial work names its authorized scope and leaves other obligations visible.
An authorized later scope change is recorded separately with provenance.

Maintain an **item-level issue ledger for current and inherited issues**, including
questions, assumptions, counterexamples, conflicts and scope exclusions. IDs are
stable `(origin_session, origin_turn, kind, item_index)` references. Engine
`addresses` means a turn was referenced; it never closes controller issues.

Each disposition identifies one issue, evidence/context citations, a reason,
author, claim/source version and dependencies. Distinguish an attributed answer,
a normative decision, a withdrawn premise and an unresolved/deferred issue.
A relevant dependency change reopens the issue. Deferred or excluded obligations
remain unresolved for the original request. An issue cannot disappear because a
new examination started or an entire parent turn was referenced.

Preserve separate `engine_terminal`, `execution_state`, `citation_fidelity`,
`asserted_support`, `independent_checks`, `coverage` and `advisory` fields. Never
use an unqualified `validated=true`. Exact substring matches do not establish
entailment. Show the complete cited line and accessible surrounding context;
negation-stripped fragments must not be presented as independently supported.

`proceed_with_limits` is advisory only and requires all of:

- engine RESOLVED with no missing dimensions;
- no unresolved current/inherited controller issues or uncovered mandatory
  obligations in the declared work scope;
- an active, non-cancelled, non-superseded session and no known invalidating
  correction or source change;
- explicit frozen-source scope, provenance limits, and any independent checks
  still required before claiming task completion.

For empirical/mixed problems this may permit planning or testing an interpretation;
it never means root cause or factual correctness is verified. APORIA, exhausted
budgets and unresolved issues lead to evidence gathering, clarification or stop.
A user's decision to proceed despite those results is a separately scoped override,
not a changed epistemic outcome, and cannot authorize unrelated deployment.

## 4. Evidence, provenance, authority and host exposure

Sources may be selected archive revisions, the exact current request, exact later
clarifications or explicitly supplied external evidence. No preliminary archive
write is required. An assistant interpretation and prior dialogue remain derived.

Store origin, provenance confidence, source role, issuer, entity/scope, effective
period, status and explicit supersession separately. Distinguish backend-verified
archive provenance, trusted-host message provenance when available, and
`caller_attributed` text. A URL, source-role enum or SHA-256 hash does not authenticate
origin, prove a claim, or turn assistant text into the user's assent. A user's
factual assertion is still an assertion, not a verified system observation.

Use typed source maps for exact bytes, line/range citations, generated separators
and metadata. Generated boundaries and caller metadata cannot support an author's
commitment. Provenance metadata supports only the limited facts it authenticates.
UNKNOWN/SILENT retains upstream semantics; contextual evidence explaining a gap
belongs in the controller issue record, not answer-support citations.

No default newest-wins rule. Compare authority, applicability and explicit
supersession. Retain both sides of a disputed commitment; different actors or
periods may explain an apparent conflict. A newer brainstorm is not automatically
an approved replacement. Hashes prove snapshot identity, not currentness.

Maintain an indexed source-to-derived-record dependency map. Ordinary source removal
makes live availability unknown/unavailable; it does not change the frozen historical
claim. An explicit user request to forget/purge source content must also reach source-
bearing controller snapshots, quotations and derived artifacts according to that
request's scope. Immutability does not override a user's deletion instruction.
Retain only permitted non-revealing tombstones, and withdraw affected advisories;
never serve a deleted secret from a cached issue or report. Purge is explicit and
separate from ordinary analysis, not automatic history deletion. Logical purge
does not promise forensic erasure from filesystem backups or storage snapshots.

Record retrieval scope/queries, selected sources, known relevant exclusions and
selection limits. Prioritize corrections, exceptions and counterevidence. If known
material evidence cannot fit, retain a scope issue and explicitly partition the
problem; do not silently remove the inconvenient source. Repeated sources, runs,
lenses or self-agreement are not independent corroboration.

Record execution mode separately from data-exposure mode. Before a source-bearing
response, enforce the established user-authorized source/host policy, including
quotes, derived issues, paths and metadata. Reuse valid session authorization;
do not prompt again for an already-authorized scope. With a local-only source and
unknown/cloud host without authorization, return a non-revealing denial. Localhost
transport does not establish host locality. Permissions come from trusted local
configuration/host context, never evidence text or an arbitrary tool argument.

All evidence, metadata and past responses are untrusted data. Next actions come
from an allowlisted controller, not embedded commands or URLs. Do not auto-fetch
links, execute source instructions, open arbitrary paths, or accept source-stated
permission. These boundaries constrain the controller; they are not a guarantee
that a general host model is immune to prompt injection.

## 5. Model-free recall and bounded read-only storage

The existing search `mode=fast` still embeds and reranks. It is not the default
safe recall implementation for this feature. Provide a distinct bounded lexical
recall/read capability which never imports model packages or falls back to dense
search. It may use an already existing FTS index. Missing index/capability returns
`recall_unavailable`, not an empty result presented as successful exhaustive recall.

Opening sources must not create a table, index, identity stamp, migration or
cache with mutation side effects. Existing `get_collection(create=False)` is not
sufficient. Bind reads to an existing immutable table version. Return candidate
IDs and bounded provenance before source text; do not project vectors or bulk
text through an ordinary all-column query.

Admission covers text, metadata, decoded form and total selected bytes. Size
checks and extraction must refer to the same storage version. Do not measure
size only after `.to_list()` or Python string materialization. If the backend
cannot prove a bounded read for a legacy record, reject it with a clear reason.
A backend length expression is not assumed to bound native decoder memory;
prove the capability on supported storage versions, otherwise fail closed.

Explicit excerpts are permitted only with original source revision/hash and
byte/line ranges, marked incomplete. Never silently truncate to satisfy a cap or
claim excerpt analysis covers the whole article/problem. A missing source after
pruning cannot be silently replaced by the nearest/newest drawer.

Bound lexical query length and result count; do not expose arbitrary backend SQL.
Execute native storage reads under a separately killable read-only worker budget
(initially one admitted reader per OS user across palaces, 512 MiB aggregate descendant RSS and a
10-second deadline). The supervisor starts before backend import and stops only
its own process group. These limits supplement byte admission because index/native
decoder allocations are not proven small by a projected text length. Unsupported
platform supervision returns unavailable rather than claiming the same guarantee.
Admission ownership covers the actual reader lifetime, not just its supervisor.
Require a tested parent-death/orphan policy and bounded reclaim before enabling this
capability on a platform: kill an owned orphan without releasing admission early,
using PID plus start identity/process-group ownership to avoid reused-PID kills.
A dead guardian cannot leave an unsupervised reader while a replacement is admitted.
The supervising host and guardian must cover each other's single-process failure;
if the platform cannot provide the tested guarantee, disable native recall and use
inline evidence. Sampled RSS is a tripwire, not a hard prevention of every transient
allocation; do not claim a universal whole-machine memory ceiling.

## 6. Article-quality profile and NLP lifecycle

Use a separate versioned article profile, not the enhanced requirements aggregate.
Return measurements and findings with `quality_score=null` until a meaningful
article-specific aggregate has been defined and calibrated. No retrieval boost
is assigned to that uncalibrated profile. Exclude requirement IDs, modal strength,
actor/action completeness, testability, scenario coverage and requirement volume.

V1 supports UTF-8 plain text and Markdown with a declared prose-extraction policy.
Preserve surrounding prose when lists exist. Distinguish headings, list prose,
block quotes, link labels, destinations, code fences (backticks/tilde), inline code,
HTML and tables. Unsupported or excluded material has counts/reasons; code-only
or empty content is `not_applicable`, never a meaningful zero-quality article.
Keep source counts separate from analyzed-prose counts and retain raw source bytes.

Use deterministic, tested tokenization handling decimals, common abbreviations,
URLs and Unicode boundaries. Report declared language separately from detection
or unknown language. English readability formulas are null with a reason for
non-English/mixed/unknown applicability. SMOG is unavailable below 30 analyzed
sentences. Do not manufacture US-grade estimates for Czech/Chinese. Descriptive
counts can remain available. Do not present an average school grade as quality.

Profile routing is explicit, in both the new API and existing Stage 6. Untyped
historical drawers/conversations are `not_assessed` with no requirements boost;
only explicitly selected requirements receive the old profile. Article, requirement
and generic recall statuses are distinguishable. Updating routing changes ranking
behavior, so characterize it with mixed-content fixtures before release. No bulk
metadata rewrite or archive re-embedding is required.

Share one thread-safe lazy optional spaCy loader among parser, semantic and entity
consumers. Parser/package import never loads a model; `use_spacy=False` reaches
all consumers without consulting the loader. Cache missing-model failure per
process, with an explicit reset/restart for newly installed models. Article analysis
and the default loop use no NLP model or hidden download.

## 7. Durable state, idempotency and lifecycle

Use a **separate local SQLite controller store**, not the original drawers/graph.
Keep root budgets, session revisions, immutable accepted events/source snapshots,
issue/obligation projections and idempotency receipts in one transaction. A small
rollback-journal store with synchronous durability is sufficient; do not invent a
multi-file JSON transaction or reuse the provider worker's permanent started marker.
Limit database lock waiting and return `busy` instead of blocking the host.

SQLite's [atomic-commit documentation](https://www.sqlite.org/atomiccommit.html)
explains the transactional basis and its filesystem assumptions. Local supported
filesystems only; do not promise portable crash guarantees on arbitrary network
or sync mounts. WAL is not required for this low-write controller; its separate
[concurrency/filesystem constraints](https://www.sqlite.org/wal.html) would need
explicit handling if selected later.

A stable problem root has a monotonic revision, one active examination and two
examination slots **total, including the first**. Successor creation atomically
reserves a slot and supersedes the old active examination. Committed abandoned or
failed examinations do not refund slots. Automatic callers cannot evade the bound
by silently creating a new root; an explicit new user task/authorization is needed.

Mutations require a bounded request ID, expected controller revision and canonical
payload digest. Deduplication looks up an immutable, content-free receipt: operation
ID, committed event/revision and disposition. Same ID/same payload never repeats
the mutation; same ID/different payload conflicts. A fresh stale request makes no semantic mutation.
The returned envelope is reconstructed against current lifecycle, exposure policy
and purge tombstones; never replay an old actionable advisory or sensitive bytes.
Historical operation success and the current advisory are separate fields. Source-
bearing pages, cursors, errors and historical inspection obey the same current
policy. A pinned historical exposure grant does not survive revocation.
A rejected current response advances controller revision but not the engine turn.
Two distinct invalid submissions for the same expected engine turn terminate the
examination. Transport retries, stale conflicts and malformed transport frames do
not consume semantic attempts. Bound retained receipts and invalid audit records.

Commit event, revision, counters, compact projection and receipt together; acknowledge
a mutation only after commit. A crash exposes the previous or next complete state.
No provider calls or source-store writes occur inside this transaction. Return
storage errors without claiming success; do not rebuild corrupt state as resolved.
Read root/session projections, budgets, tombstones and page metadata in one coherent
snapshot, binding every envelope to that revision and exposure epoch. Reads linearize
at that snapshot; already delivered bytes cannot be revoked retroactively. The host
must treat a subsequently observed correction as invalidating an older advisory.

Controller directories/files use owner-only access. Resolve the configured palace
once; request IDs/cursors/source metadata never become filesystem paths or executable
SQL. Reject path traversal, symlink substitution and unexpected storage ownership
at controlled boundaries. Use parameterized controller queries and validated backend
query construction. A source URI is descriptive provenance, not fetch permission.

Lifecycle is independent of engine terminal: awaiting_response, terminal, cancelled,
superseded, expired, incompatible or corrupt. Cancel/correction/successor/respond
serialize at the root. A known user correction invalidates the old advisory even
when the next examination cannot be created. Late responses cannot reactivate a
cancelled/superseded session. Keep historical outcomes intact.

Pin controller schema/policy, engine commit and file hashes, lens/schema, profile
versions, exposure policy and limits. An incompatible upgrade permits bounded
historical inspection but no mutation. Any explicit migration preserves budgets,
receipts, issue IDs and prior artifacts; it never silently reinterprets old answers.

The raw engine projection must match the bundled runner for the same scripted
answers: operators, claim versions, coverage, revision budget, terminal and stop
reason. A stricter controller ledger may withhold its advisory while the engine
says RESOLVED; expose both. No process-global transport monkeypatching in the
multi-session host adapter. Keep vendor files untouched.

## 8. Resource accounting, wire safety and resumption

Initial policy bounds (implementation must measure, not merely document them):

| Resource | Bound / behavior |
|---|---|
| Problem / initial interpretation | 8 KiB each |
| Selected evidence | At most 8 records; 64 KiB total text plus 8 KiB total approved provenance |
| Standalone article assessment | 64 KiB text plus 8 KiB provenance before parsing, through direct API and MCP; no automatic retention |
| Article computation / findings | 2-second isolated computation deadline; at most 128 findings, explicit remaining/unavailable status; same wire/page caps |
| Accepted response | 16 KiB canonical UTF-8 JSON; nested structures also bounded |
| Examination budget | 14 accepted turns; second distinct invalid response at a turn ends examination |
| Root budget | 2 examinations total; at most 64 automatic Castle tool requests per root |
| Automatic burst | 30 minutes; explicit user resumption retains consumed turns/slots |
| Raw MCP input frame | 1 MiB before JSON parse; reject deeper than 32 nesting levels |
| Controller collections | At most 128 issues and 64 obligations per examination; excess stops explicitly |
| Compact output | 32 KiB of the actual encoded MCP envelope, including double JSON escaping |
| Page output | Fit the same wire cap; explicit stable cursor, counts and remaining items |
| Controller state | 64 KiB compact projection; source and event bodies referenced, not duplicated |
| Session artifacts | 1 MiB logical retained payload; 16 KiB reserved for terminal records |
| Root artifacts | 2 MiB logical retained payload; SQLite/page/index overhead measured separately |
| Invalid response audit | Digest, byte count and bounded codes, at most 1 KiB; do not retain raw rejected bodies |
| Aggregate store | Configured finite disk quota and free-space admission; no automatic deletion of history |

Worst-case raw accepted bodies are 14 × 16 = 224 KiB per examination. Even
conservatively reserving 28 × 1 = 28 KiB for rejection receipts, evidence 72 KiB,
problem/interpretation 16 KiB and control 64 KiB gives 404 KiB before issue,
receipt and engine-projection overhead. The 1-MiB artifact cap is admission-checked
on the prospective transaction; it is not inferred from turn count. Do not retain
full generated prompts or duplicate entire histories in each receipt. Reserve
terminal space. If admission fails, stop before accepting the response and preserve
all prior evidence; never silently trim it. Filesystem/database overhead and overall
RAM remain separate measured limits, not consequences of UTF-8 size caps.

Raw framing must be bounded before handlers or `json.loads`. A 10-second receive
deadline starts at the first byte, not while a connection is idle; worker IPC is
similarly bounded. Incomplete frames close safely at deadline. Strict types reject
booleans-as-integers, nonfinite numbers, malformed Unicode and unknown properties;
bound all collection sizes. Detect duplicate JSON keys where this server controls
raw decoding. An overlong/incomplete frame closes the offending connection safely;
never reinterpret its trailing fragment as another request. Reconnect can resume
from committed receipts. Bounded syntax errors on complete frames leave following
valid frames usable. Errors must not echo private payloads or arbitrary paths.

Large questions, schemas, issues, source context and traces use bounded immutable
pages, not silent truncation. Status includes root/session revision, expected turn,
remaining budgets, counts, freshness scope and next action. Pagination cannot hide
an unresolved item from the aggregate gate. Cursors bind to session/version and
exposure policy; no arbitrary file reads. A fresh host resumes from session ID,
status and frozen-source pages without re-searching the archive.

Status makes no model call, search, full-trace read or freshness claim. Freshness
is `unknown` absent an explicit bounded check, `snapshot_only` where live checks
are unavailable, and `known_stale` on an observed invalidating change. Clock jumps
or expiry stop automatic advancement conservatively; explicit user resumption does
not replenish semantic budgets. Read-only inspection/cancellation remains possible
when automatic request budgets are exhausted, but only cancellation and explicitly
user-directed inspection are exempt from the automatic request cap. Automatic
status, page, recall and transport-retry requests all count. Operational request
usage is distinct from semantic attempts/revisions: a replay can consume request
usage without repeating a semantic mutation. Admission/usage accounting is atomic;
a status call can update that bounded operational counter but never engine state.
A caller-supplied flag alone cannot establish the user-directed exemption.

The new default path must be model-free end to end, including collection opening
and recall. Admission responds to elevated system memory pressure by declining
retrieval, not killing unrelated processes. Tests have an external watchdog before
imports, aggregate all child RSS, block models/network and use temporary data.
Per-process RSS and payload caps cannot guarantee the entire machine's footprint.

## 9. Rollout and verification gates

Implement in this isolated branch; preserve pruning work and paused capture settings.
No automatic installation, dependency download, hook activation or live archive
processing is part of design approval. Test only synthetic sources and fake loaders.

Inventory Codex, Claude Code and OpenClaw entry points separately: Python editable
path, cached plugin skill, protocol/tool schema, CLI and process version. Update
supported artifacts together or explicitly leave a host unsupported. Capability
handshake reports versions and read-only/model-free availability without opening
palaces or loading models. New-loop mutations must declare a compatible protocol
and policy version; missing/mismatched versions fail before side effects. A server
cannot detect a stale skill that never participates: cached-skill inspection and
actual workflow exercise are rollout checks. Hook pause verification is independent
of tools being discoverable.

Required gates are the matrix in the review document, plus differential engine
parity across all nine lenses and fault injection around each transaction boundary.
Run full advertised default workflow with model imports and index creation made
fatal. A small isolated adversarial corpus must exercise wrong interpretations,
omitted obligations, irrelevant exact quotes, conflicts, non-English articles and
resume after context loss. Separate deterministic protocol tests from any later
real-model quality evaluation. Scripted success cannot certify model competence.

The remaining unavoidable limits are semantic judgment, source selection/completeness,
host compliance and trusted provenance availability. These stay visible in outputs
and evaluation reports; they are not hidden behind a score or a green terminal.

## 10. Decisions still for user review

The implementation recommendation is host-assisted SUE on substantive problems,
with independently requested provider review available separately. These defaults
remain unapproved. Mechanical choices above were resolved conservatively during
review; they do not need another questionnaire. The next implementation plan must
map every mandatory matrix row to a concrete test or explicit blocked capability.
