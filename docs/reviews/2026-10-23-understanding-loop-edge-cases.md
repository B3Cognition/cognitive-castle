# Adversarial review: Castle understanding loop v2

Date: 2026-10-23. Reviewed code baseline: `b57a84f`.
Design: [bounded understanding loop](../superpowers/specs/2026-10-23-bounded-understanding-loop-design.md).

## Result and evidence level

Three independent read-only audits and a root review found material gaps in the
original design. The v2 specification now contains explicit contracts for them.
This is **design verification**, not an implemented fix, complete test coverage,
a live-model evaluation, or a claim that every possible future edge case is known.
All matrix cases below are mandatory future acceptance scenarios, not tests claimed
as passing today. Prior generic builder approval did not establish adversarial safety.

Two bounded deterministic probes against the current vendored engine reproduced:

1. Source: `Only administrators may export data.` A DEFINE answer/claim permitting
   every visitor, while quoting that source exactly and supplying a stated premise,
   is structurally accepted. That confirms citation validation is not entailment.
2. A DEFINE turn raises two questions (export role and consent expiry). A successful
   DISTINGUISH answer about roles with `addresses=[1]` makes the upstream issue group
   `model_addressed` and leaves zero upstream open groups, without answering expiry.

Both probes exited successfully with the expected counterexamples. No model,
storage backend, archive or provider was loaded/called. Sampled child RSS was
21.2 MiB, supervised externally with a 128-MiB/10-second stop and system-pressure
check. That sample is not a peak-memory benchmark of the proposed implementation.

## Primary source findings

| Finding | Evidence in existing code | v2 correction |
|---|---|---|
| Exact quotes can accompany unsupported conclusions | `validate_turn` in [SUE engine](../../cognitive_castle/_vendor/sue/sue_dialectic.py), lines 280–442; direct probe above | Separate fidelity, asserted support and independent evidence; no truth certification |
| One reference can close a whole group of questions | `depth_profile`, same file, lines 466–499; direct probe above | Item-level controller ledger for current and carried issues; dependency-aware reopening |
| A changed claim can omit the original task | `run_dialogue`, same file, lines 576–647 tracks current claim | Frozen request and obligation/commitment map, scoped advisory |
| Fast search still uses models | [searcher](../../cognitive_castle/searcher.py), lines 273–287 and 589–725 | Separate model-free read-only lexical capability, explicit unavailable fallback |
| Opening a collection can index or write metadata | [LanceDB backend](../../cognitive_castle/backends/lancedb_backend.py), constructor and get_collection | Read-only opener, no create/index/stamp, pinned bounded source reads |
| Byte limits were checked after complete document reads | [SUE snapshot](../../cognitive_castle/sue.py), `_snapshot` | Admit text and metadata before materialization against one storage version |
| JSON replacement does not transact state/receipts/budgets | [SUE adapter](../../cognitive_castle/sue.py), `write_json` and `start_review` | Separate controller SQLite transaction and optimistic concurrency |
| Restart marker is not a resumable host-session protocol | [SUE worker](../../cognitive_castle/sue_worker.py), `run_review` | Explicit root/session lifecycle and replay receipts |
| MCP transport reads unbounded frames | [MCP server](../../cognitive_castle/mcp_server.py), `main` | Raw-frame/parser bounds plus actual wire-output accounting |
| Old quality score is requirement-specific for all hits | [quality adapter](../../cognitive_castle/quality_rerank.py), `apply_quality_rerank` | Explicit profile routing; untyped conversations not assessed/boosted |
| NLP load can happen on import and is duplicated | [Markdown parser](../../cognitive_castle/understanding/markdown_parser.py), semantic/entity loaders | Shared optional lazy loader, default path model-free |
| Model-free controller does not imply private host processing | Host receives returned evidence; proposed default used an existing host | Exposure policy applies before every source-bearing return |
| Old storage/output caps were mutually inconsistent | 14 valid and repeated invalid 16-KiB bodies exceeded 512 KiB before overhead | Bounded rejection receipts, separate event/control budgets, terminal reserve and pagination |

## Acceptance matrix

P0 means unsafe or misleading activation must be blocked until addressed. P1 means
required correctness, applicability or operability before supported release. Every
row needs a concrete test/evaluation oracle or an explicit unavailable capability;
none may be dismissed merely because a happy-path unit test passes.

| ID | Priority | Adversarial scenario | Required observable result |
|---|---|---|---|
| E01 | P0 | One turn contains two questions; a later answer references that turn but answers only one. | Only the explicitly disposed issue can close; the other remains open despite engine model_addressed. |
| E02 | P0 | A source or claim dependency used to close an issue changes. | Reopen the affected controller issue; retain the original closure and engine trace as history. |
| E03 | P0 | A revised administrator-only claim omits auditors and revoked consent from the request. | Those independent obligation IDs remain unfulfilled; whole-request readiness/completion is impossible. |
| E04 | P0 | An opposite claim quotes a source accurately, or removes negation by choosing a substring. | Report citation fidelity separately; never label semantic support or factual truth independently verified. |
| E05 | P0 | An arbitrary inferred premise cites an irrelevant exact line. | Keep inferred support attributed and unverified; expose full context and claim-to-premise links. |
| E06 | P0 | A generated boundary or caller metadata says approved=true. | That material cannot establish source-author assent or satisfy a commitment citation. |
| E07 | P1 | A newer brainstorm conflicts with an older approved policy. | No newest-wins replacement; authority/status/supersession ambiguity remains visible. |
| E08 | P1 | Similar statements concern different tenants, people or effective periods. | Keep entity/scope/time distinctions; do not silently merge them into a contradiction. |
| E09 | P0 | Caller relabels assistant text as user_clarification or supplies an invented URL source. | Provenance remains caller_attributed unless independently bound to trusted origin; enum/hash cannot promote it. |
| E10 | P0 | Seven interpretation questions finish for a slow-deployment debugging problem. | The interpretation may be examined; root cause/performance still needs empirical evidence. |
| E11 | P1 | UNKNOWN has a useful citation showing why a policy omits an actor. | Engine answer stays UNKNOWN; separate issue context retains the citation without converting it to support. |
| E12 | P0 | A successor drops previously known counterevidence to fit eight sources. | An exclusion/coverage issue is retained; dropping evidence cannot manufacture readiness. |
| E13 | P1 | Repeated source copies, nine lenses or repeated self-agreement are counted as corroboration. | Do not increase independence or evidence count as though these were independent sources. |
| E14 | P0 | User permits a prototype despite APORIA. | Preserve APORIA and factual gaps; override applies only to the stated prototype scope, not production. |
| E15 | P1 | Citations use Unicode combining forms, CRLF, emoji or overlapping excerpts. | Preserve source bytes/hashes and explicit ranges; no lossy normalization or wrong line remapping. |
| E16 | P0 | A historical RESOLVED record is returned after a known relevant correction. | Retain historical outcome but mark its advisory stale/inapplicable and expose source-version scope. |
| T01 | P0 | Two valid responses target the same controller revision simultaneously. | Exactly one commits; the other gets a conflict and no duplicated turn or semantic budget debit. |
| T02 | P0 | A commit succeeds, the acknowledgment is lost, and the request is retried. | Same request ID/payload returns the immutable operation receipt without repeated mutation; its current disclosure-safe envelope is regenerated. |
| T03 | P1 | One request ID is reused with a different payload. | Conflict; do not overwrite its receipt or accept a new event. |
| T04 | P1 | One invalid current response is replayed 100 times. | At most one semantic rejection/revision advance; automatic retries may hit the separate request cap, and receipts do not grow without bound. |
| T05 | P1 | Two distinct invalid responses are followed by a valid third response for that turn. | Second invalid response ends the examination; the later response cannot reopen it. |
| T06 | P0 | Two agents create successors while the root has one remaining slot. | Only one child commits; reservation, parent linkage and supersession are one transaction. |
| T07 | P0 | Failed or abandoned runs restart the process or attempt a new automatic root. | Consumed root slots remain spent; no automatic budget reset by new UUID. |
| T08 | P0 | Crash injection at each persistence boundary and immediately before/after acknowledgment. | Reopen sees a complete old or new state, consistent receipts/counters and no partial ready state. |
| T09 | P0 | Disk is full, locked, read-only or an fsync/commit fails. | No success acknowledgment; previous committed state is readable, error is bounded, no destructive rebuild. |
| T10 | P0 | Cancellation races the final response that would resolve the claim. | Once cancel commits, subsequent status cannot advise proceeding for that session. |
| T11 | P0 | User corrects the problem after both examination slots were consumed. | Old advisory becomes inapplicable even when no successor can start; preserve correction/gap. |
| T12 | P1 | Host or process restarts, laptop sleeps, or clock moves backward/forward. | Resume retains counters and revisions; uncertain/expired automatic burst stops, explicit resume does not refund slots. |
| T13 | P0 | Engine/controller/schema versions change while a session is awaiting a response. | Historical bounded reads work; incompatible mutation is rejected without reinterpretation. |
| T14 | P0 | Controller store is malformed or references a missing committed snapshot. | Return corrupt/incompatible; never infer success from incomplete artifacts or delete the source palace. |
| T15 | P0 | Two sessions with different evidence interleave every operator. | No global monkeypatch contamination, shared claims or cross-session citations; each trace stays isolated. |
| T16 | P1 | A fresh host has only session ID and no prior conversation context. | Bounded status/pages reconstruct exact frozen evidence and next step; no archive re-search or model call is needed. |
| T17 | P1 | A revision near the 14-turn limit resets examination coverage. | Previous-version coverage cannot carry forward; exhausted budget reports BOUNDED_STOP, never ready. |
| T18 | P1 | Transport syntax errors, stale revisions and current semantic validation failures mix. | Only distinct current semantic rejections consume that turn budget; malformed frames/stale conflicts do not. |
| R01 | P0 | Run the entire advertised default path with model imports/loaders made fatal. | Begin, lexical recall, article assessment, respond and status load no model; fast dense search is not substituted. |
| R02 | P0 | Existing table/index/identity metadata is missing when sources are opened. | Read path never creates/stamps/migrates/indexes; explicit unavailable result instead. |
| R03 | P0 | Tiny metadata with giant text, or tiny text with giant metadata. | Admission precedes materialization for both; unsupported legacy size/read guarantees fail closed. |
| R04 | P0 | Record changes between admission and source extraction. | Both refer to the same pinned storage version; otherwise abort, never snapshot a different payload. |
| R05 | P1 | FTS index is absent or backend query capability fails. | Return recall_unavailable rather than successful-empty/exhaustive recall; inline-evidence loop remains usable. |
| R06 | P0 | Boundary-sized JSON includes emoji, quotes, backslashes and escaped Unicode. | Check canonical input and actual encoded wire sizes; accepted output including envelope stays within its cap. |
| R07 | P0 | Deep nesting, oversized unknown properties, nonfinite numbers, duplicate keys or malformed Unicode. | Reject at the controlled ingress before dangerous parsing/handler allocation; strict typed result, no mutation. |
| R08 | P0 | An overlong/incomplete frame is followed by bytes resembling another request. | Close that connection safely; never execute its trailing fragment; committed-session reconnect remains possible. |
| R09 | P0 | All legal responses/issues approach maximum size across the full loop. | Prospective transaction admission accounts for total retained bytes and reserved terminal space; no late silent truncation. |
| R10 | P1 | REVISE generates a question larger than the compact output cap. | Return a bounded reference/cursor; all complete text is accessible in bounded pages, with stable counts. |
| R11 | P1 | Invalid responses contain huge/private content and are repeated. | Retain only bounded digest/size/error receipts; errors/status never echo the rejected body. |
| R12 | P0 | A native read/test child allocates memory or forks descendants; system pressure rises. | External aggregate watchdog stops only its owned process group; no surviving children or unrelated process kills. |
| R13 | P0 | Several palaces request native reads concurrently. | One admitted native reader per OS user, bounded busy response elsewhere; no multi-palace worker pile-up. |
| R14 | P1 | Pathological Markdown/lexical query drives expensive parsing or native search. | Input/query limits plus deadline abort safely; no unbounded regex/index operation in the host process. |
| R15 | P1 | Controller disk quota or free-space reserve is exhausted. | New writes are refused predictably; inspection/cancel as possible, no automatic history deletion or source truncation. |
| R16 | P1 | Global framing limits encounter a legitimate older tool client. | Advertised capability/limits and bounded error explain incompatibility; no silent truncation or parser desynchronization. |
| A01 | P1 | Article includes prose before a list and prose after it. | Golden extraction retains both prose regions and list text; counts demonstrate full analyzed-prose coverage. |
| A02 | P1 | Text contains decimals, common abbreviations, URLs and punctuation. | Versioned tokenizer matches hand-checked boundaries; no naive split on every dot. |
| A03 | P1 | Backtick/tilde fences, inline code, tables, HTML, links and quotations are mixed. | Declared extraction policy preserves source bytes, labels analyzed/excluded content and executes nothing. |
| A04 | P1 | Input is code-only, table-only, whitespace or contains no analyzable prose. | Not-applicable/unsupported diagnostics with reasons; no invented zero-quality article. |
| A05 | P1 | Czech, Chinese, mixed or unknown-language article is supplied. | English grade formulas are null with applicability reason; available descriptive counts remain separate. |
| A06 | P1 | Comparable English inputs contain 29 versus 30 analyzed sentences. | SMOG is unavailable below its minimum and only applicable at the boundary with supported language. |
| A07 | P1 | An excerpt is assessed as if it were an entire article. | Result retains excerpt range/source revision and incomplete scope; cannot claim whole-article quality. |
| A08 | P1 | Legacy conversation/untyped drawer enters Stage 6. | No requirements metrics/boost; status explicitly not_assessed. |
| A09 | P1 | An explicitly selected requirement enters the new mixed-content routing. | Existing requirements profile remains available with its own version; no article threshold is silently reused. |
| A10 | P1 | An uncalibrated article looks readable or receives high descriptive scores. | No truth/completeness/understanding certificate and no uncalibrated aggregate or ranking boost. |
| A11 | P0 | Parser, semantic and entity consumers import with use_spacy=False or concurrently enable NLP. | Opt-out makes zero load attempts; opt-in shares one initialized optional pipeline under a lock. |
| A12 | P1 | Optional NLP model is missing, then installed later. | Failure is cached without downloads; explicit reset/restart can recheck, automatic scoring stays model-free. |
| A13 | P1 | Unicode quotation marks, CJK punctuation, combining marks and long unbroken tokens appear. | Bounded deterministic behavior; applicability is explicit and raw bytes remain unchanged. |
| H01 | P0 | Local-only source is requested through cloud/unknown host without authorization. | Begin/status/page/error deny without source text or revealing metadata; no locality inference from localhost. |
| H02 | P0 | A selected-bundle authorization is reused or a successor adds another source. | Reuse approved scope without repeated prompts; do not silently expand disclosure to the new source. |
| H03 | P0 | Evidence contains fake system prompts, tool calls, URLs or permission grants. | Controller routing/permissions do not change; no command execution or automatic outbound action. |
| H04 | P0 | IDs/cursors contain path traversal, symlinks, SQL fragments or cross-session pointers. | Validated namespace and parameterized queries; no arbitrary file/SQL access or session crossover. |
| H05 | P1 | Cached host skill and installed runtime advertise different schema/profile versions. | Capability mismatch is explicit before mutations; no optimistic claim that the new brain workflow is active. |
| H06 | P1 | Editable package, CLI and running MCP processes point at different checkouts. | Installation inventory identifies each actual path/version; no hidden install or automatic hook activation. |
| H07 | P0 | Test or rollout script runs with capture already paused. | Pause marker and hook configuration remain unchanged; no real archive/provider/model operation occurs. |
| H08 | P1 | Host-assisted answers are presented as independent second-model verification. | Execution/exposure/independence fields and user-facing result explicitly identify structured self-check. |
| H09 | P1 | Trivial formatting request or ordinary recall would start many SUE turns. | Frequency policy skips these cases; substantive begin/respond return next action without mandatory polling. |
| H10 | P0 | Each of nine lenses runs success, silence, partial definition, revision and exhaustion. | Raw host-adapter engine output matches bundled runner including stop reasons; stricter controller ledger tested separately. |
| H11 | P0 | A user explicitly requests forgetting content preserved in derived snapshots/caches. | Indexed dependency purge reaches permitted source-bearing derivatives; no deleted secret served from old reports. |
| H12 | P1 | Ordinary archive pruning removes a live drawer referenced by a frozen examination. | Mark live availability appropriately; do not replace frozen evidence or silently reinterpret historical result. |
| H13 | P0 | A new user correction arrives while the host is holding an old next question. | Host records correction before advancing; controller invalidates old advisory and rejects stale responses. |
| H14 | P1 | Host ignores the skill or does not expose the new tools. | Report unsupported/inactive integration; installing a skill is not reported as behavioral enforcement. |
| T19 | P0 | Replay a committed request/old cursor after cancellation, correction, source purge or access revocation. | Operation remains committed once, but current envelope contains no actionable stale advisory or newly forbidden bytes. |
| T20 | P0 | Pause a status read between root/session queries while cancellation or successor creation commits. | One coherent read snapshot yields a wholly old or wholly new revision, never mixed projections or budgets. |
| T21 | P1 | Automatic status/page/recall/retry requests exhaust the 64-request root cap. | Further automatic workflow stops; trusted user-directed inspection and cancellation remain possible without resetting semantic budgets. |
| R17 | P1 | Standalone article API receives oversized or pathological input without MCP framing. | Direct and transport APIs enforce text/provenance/compute/finding bounds before parsing or automatic retention. |
| R18 | P0 | Kill the native-reader guardian while its reader lives; another palace requests a read. | Admission follows actual reader lifetime; owned orphan is boundedly terminated/reclaimed, no duplicate reader or reused-PID kill. |
| R19 | P1 | Client writes the start of an input/worker-IPC frame and keeps the stream open. | First-byte deadline closes the partial frame; idle connections remain valid and committed sessions can reconnect. |
| H15 | P1 | New-loop request omits/mismatches protocol version, or an old skill never calls the new workflow. | Participating incompatible requests fail before mutation; absent participation is an integration limitation, not detectable activation success. |

## Second review of v2

A second pass by all three reviewers found further contract conflicts that are now
addressed: old receipt replay after revocation/purge/cancellation, mixed-revision
status reads, automatic read-budget bypass, orphaned native readers, unbounded
standalone article calls, partial-frame stalls and overly broad stale-skill detection
claims. Rows T19–T21, R17–R19 and H15 capture these regressions.

The v2 design now uses content-free immutable receipts and current-policy response
envelopes, coherent snapshots, separately counted automatic requests, actual-reader
lifetime admission, direct-API article caps, first-byte frame deadlines and explicit
protocol compatibility. Platform supervision remains a capability to prove before
enabling native recall, not a promise inferred from a watchdog sketch.

## Implementation and verification sequence

1. Enforce bounded ingress and the genuinely read-only/no-model source interface.
   Tests make model imports and all index/table/identity creation fatal. Preserve
   the existing capture pause before and after every check.
2. Establish controller storage, root budgets, idempotency, cancellation and version
   pinning with transaction-boundary fault injection and synchronized race tests.
3. Prove raw engine parity across nine lenses, then separately exercise stricter
   issues, obligations, provenance, exposure and action-advisory rules.
4. Add article fixtures with hand-checked extraction/counts and applicability;
   characterize ranking changes from explicit profile routing.
5. Validate context-loss resume, actual wire bounds, stale integrations and bounded
   resource failure with a supervisor outside the test process and before imports.
6. Only then evaluate a supported live host on a small deliberately selected corpus,
   under explicit exposure authorization and memory controls. Such evaluation tests
   model behavior; deterministic tests alone cannot establish semantic competence.

No full suite, live model, archive scan, hook activation or provider-based SUE run
was performed for this review. The repository still contains a proposed design,
not an implemented controller. Remaining product choices are host-assisted versus
independent-provider review and how broadly the host should invoke the loop.

## Residual limits to keep visible

A self-examining model can rationalize an incorrect interpretation. Sources can be
wrong, incomplete or selectively chosen; authenticated origin is not factual truth.
No controller can guarantee that a third-party host follows a skill. Native storage
and transport dependencies need measured isolation, not promises inferred from
small JSON inputs. These limits must remain in evaluation reports and user-facing
outcomes even after every deterministic acceptance case passes.

Final targeted reread: the state and resource reviewers found no remaining material
blocker in the revised contracts they rechecked. Two operational-versus-semantic
budget wording points and the matrix table rendering were corrected afterward.
This narrows known design uncertainty; it does not establish implementation or
platform correctness.
