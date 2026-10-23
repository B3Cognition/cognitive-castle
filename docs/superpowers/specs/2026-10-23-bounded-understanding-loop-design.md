# Castle: article assessment and a bounded problem-understanding loop

Status: proposed design, awaiting user review. No automatic runtime activation.

## Intent

The user wants Castle to act as the assistant's persistent working memory:
`understanding` evaluates article quality; SUE examines the assistant's
understanding of a problem. The missing behavior is a feedback loop, not another
archive-wide batch job. Preserve original words and distinguish source evidence,
proposed interpretations, model judgments, and independently checked results.

## Proposed default loop

1. For a substantive problem, the assistant recalls a small relevant set of
   sources and reads their exact revisions. Trivial requests skip the loop.
2. Record the current problem statement verbatim and the assistant's proposed
   interpretation separately. Identify the decision, constraints and unknowns.
   The exact current user request, later user corrections and explicitly supplied
   external evidence can be frozen source records without first becoming drawers.
   Record their provenance and hashes. A session can begin with zero archive
   matches. Assistant interpretations and prior dialogue are derived material,
   never promoted into source authority merely by entering the loop.
3. Castle issues SUE's next question and response schema. The active assistant
   supplies the answer. Castle validates source citations, tracks assumptions,
   and advances the existing SUE examination rules.
4. When evidence is insufficient, the assistant retrieves evidence for the named
   gap or asks the user for a missing decision. It explicitly revises its
   interpretation and starts a linked follow-up examination when sources change.
5. Stop with examined interpretation, unresolved questions and evidence links.
   An examined interpretation permits proceeding with stated limits; a completed
   process, high article score or exhausted budget never means the problem has
   been proven understood. Implementation still requires independent tests.
6. Store the derived record separately from original memory. Later work can
   retrieve it with its source hashes, date, outcome and remaining questions.

The proposed default is **host-assisted SUE**: the already active assistant
answers questions; Castle validates and persists the dialogue. This adds no
local LLM process and no new provider connection. It is a structured self-check,
not an independent second-model assessment. Existing explicit provider-based
SUE reviews remain available, without silently changing provider or enabling
them from hooks. This default is an assistant recommendation, not yet a user
decision. Loop frequency is also pending the user's answer.

## Article assessment

Add a separate article profile. Reuse model-free readability formulas and
sentence-length diagnostics; retain surrounding prose when an article contains
lists. Exclude requirements-specific scores for modal verbs, actor/action
coverage, testability, FR/REQ identifiers and specification volume.

Return profile/version, language applicability, word/sentence counts, source
hash and article/excerpt scope. Explain short-text and English-heuristic limits.
Initially expose measurements and findings, not an uncalibrated universal
quality score or retrieval boost. Unsupported dimensions such as factual
accuracy and completeness must remain unavailable rather than receiving an
invented score. Existing requirements analysis remains explicitly available.

Expose article assessment through a dedicated callable tool/API. Retrieval may
attach it only to explicitly identified articles; do not treat arbitrary
conversation drawers as articles or requirements. Show assessment status even
when it gives no ranking boost. Article quality must not suppress conflicting
evidence needed to examine a problem.

## SUE integration and persistence

Expose begin/respond/status operations for host-assisted examination. Each
problem session contains an immutable source snapshot, proposed interpretation,
validated turn history, current operator, claim version, remaining budget and
compact next action. Responses include the expected turn/revision so concurrent
or repeated submissions cannot advance the dialogue twice.

Use the bundled SUE validators, questions, output schemas, next-step rules and
depth profile. Keep vendored files unchanged. Add parity tests against the
existing dialogue runner so the host adapter cannot silently weaken the rules.
Do not treat `depth_profile.blocking` or execution `completed` as readiness.
RESOLVED also requires no missing dimensions or open issues.

A compact status has no model calls, search, archive scan or full-report read.
It returns the examined claim, open questions, missing dimensions, source
references and one next action: answer question, gather evidence, clarify with
user, proceed with limits, or stop. Full evidence/trace remains explicitly
retrievable. New evidence starts an immutable linked examination; it does not
inherit old coverage as proof. Earlier open issues must be addressed or retained.

Only `RESOLVED` with no missing dimensions and no current or carried open issues
permits `proceed_with_limits`. APORIA and budget exhaustion stop or request
evidence/clarification; they never authorize proceeding automatically. A user
may choose to proceed separately, but the recorded examination outcome remains.

Carry earlier issues using stable parent-run/turn references outside the engine's
local `addresses` field. A closure proposal must include a disposition, reason,
and citations to current frozen evidence (including an exact user clarification
when applicable). It remains an attributed judgment. An issue without that
record remains open. Do not rewrite the parent's trace or treat a new session
as resolution of its objections.

## Bounds and memory

Proposed initial limits: at most 8 evidence records and 64 KiB of source text;
at most 14 examined turns (to allow explicit revision), 2 invalid submissions
per expected turn, and 2 linked examinations per problem. Reject oversized
inputs without silently truncating source words. Enforce one state transition
per session at a time, idempotent retries and atomic persistence. Identical
inputs cannot trigger an automatic repeat cycle.

Bound the problem and proposed interpretation to 8 KiB each, each submitted
response including nested arrays/metadata to 16 KiB, compact tool responses to
32 KiB, and persisted session state to 512 KiB. Enforce source limits at the
backend boundary before materializing legacy giant drawers; reject a source
when its read cannot be bounded safely. Keep full source/report retrieval
explicit and bounded. Limits are measured on encoded UTF-8 JSON/text, not only
character counts. These are controller limits, not a promise about total host
or retrieval-model RAM.

The controller and article path must never import or load embedding, reranking,
spaCy or LLM models. Current memory retrieval can still use models; this proposal
does not make the existing retrieval pipeline model-free. No whole-archive
processing, model downloads, startup SUE, background self-triggering loops or
automatic hook reactivation is included.

Fix the existing NLP lifecycle independently: one shared lazy spaCy loader,
no model import on parser import, and `use_spacy=False` respected through all
consumers. Article scoring uses the model-free path. Existing paused capture
configuration and its live marker remain unchanged during development.

## Assistant integration and rollout

Update Castle's shared skill, MCP tool descriptions/protocol, CLI help and scope
documentation. The skill must distinguish recall, article assessment and
problem examination, and explain how the result changes the assistant's next
action. Do not promise that installing tools forces every host to use them.

Build in an isolated branch based on the current capture-safety commits. Preserve
unrelated pruning work. Validate with synthetic sources, fake NLP loaders and
the real deterministic SUE engine. Do not read the user's archive for tests or
make real provider calls. Before enabling the new workflow in a live host,
verify its installation target and tool discovery; retain the hook pause.

## Acceptance evidence

- Article analysis imports no model and retains prose around lists; unsupported
  quality dimensions are explicit and requirements scores are excluded.
- All NLP consumers share one optional loader; opting out performs zero loads.
- A synthetic problem with a missing condition produces a named open question;
  an explicit correction can produce a linked revised examination.
- Source quotes, Unicode, whitespace and hashes are preserved, and derived
  interpretations never overwrite source drawers.
- Claim revision resets coverage; APORIA, invalid responses, unresolved issues
  and budget exhaustion cannot become an understood/verified label.
- Replay, stale-turn submission and concurrency do not duplicate transitions.
- Compact status does no model work or full-trace loading.
- No change enables paused hooks, selects a new external provider, or launches
  local models. Test runners abort on elevated system memory pressure, excess
  RSS or a short wall-clock deadline.

## Builder choices

Choose internal module names, lock implementation, JSON schema layout and test
fixtures to match repository conventions. Prefer existing atomic JSON and
source-hash helpers. Keep provider-based review compatibility. If parity with
the vendored engine cannot be maintained, stop and report the concrete gap
instead of substituting an unvalidated assessment algorithm.
