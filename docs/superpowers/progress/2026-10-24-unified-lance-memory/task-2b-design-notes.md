# Task2b preparation — not yet dispatched

Dependencies: reviewed Task2a profile/unit/page contract. Keep this task unfinished
until exact publication -> queue -> vector receipt -> progress is tested durably.

Boundary decisions to resolve in final brief:
- Canonical source is immutable Lance text/provenance; coordination SQLite stores
  references, hashes, scopes, queue state and cursors only, never canonical text.
- Native vector publication must rehydrate and validate the canonical source
  before commit. Each unit binds sourceID/text hash/exposure hash/profile/offsets/
  token input. Validate float32 normalization and hash durable representation,
  not arbitrary pre-cast JSON decimals. Native metadata+vectors and receipt commit
  together; retries validate existing unit/receipt content before ack.
- A bounded queue group binds <=8 exact references, stable input order and hashes;
  <=32 windows/page. Terminal enumeration is not full published coverage until
  all contiguous page receipts are acknowledged. Lost response or lost SQLite
  acknowledgement must replay the durable Lance receipt without duplicates.
- Explicit new/history scheduling, e.g.3new:1history pages, prevents history
  blocking fresh facts and avoids permanent history starvation. Background job
  yields on live interactive intent, including during a long model stage.
- Add a trusted optional preemption boolean to the existing supervisor (default
  unchanged) rather than a second scheduler or longer admission wait. Return
  explicit refusal and kill/reap descendants before releasing admission.
- Vector query uses a pinned dataset generation and profile, validated finite
  384D query, explicit prefilter=True and typed Arrow filters for scopes/grants.
  Policy/scopes before ranking/limit; restricted grants never become postfilters.
  Candidate IDs/hashes/offsets only; final exact hydration/policy epoch check is
  Task4. Lexical/KG/rerank integration remains required, not removed by this step.
- Scope strings come from trusted full authoritative scope registry, not only
  small caller provenance. Historical metadata/columns are separate evidence
  migration Task3, not discarded fields.
- No public operation accepts budgets, model paths or worker commands. Native
  store work still uses192/256MiB and read2s/write3s inside overall semantic5s;
  Task2a model stages512/640. Session extension must not widen native guards.
- Scaling/index construction and bulk migration require actual-corpus
  qualification in Task3, not inference from synthetic vectors. Retain originals.

Open interface: exact receipt replay after a commit/queue crash needs a bounded
durable publication enumeration/reconciliation path, or equivalent pending
coordination intent persisted before exact commit. The latter stores only request
binding/IDs, reconstructs via Lance receipt, and must not require losing caller
text to recover an acknowledged write. Live capture has source checkpoint replay;
manual remember still needs durable outbox recovery. Resolve before dispatch.
