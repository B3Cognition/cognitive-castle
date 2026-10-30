# Root independent v5 authority review

Preparation accepted against `task3-authority-3.diff`
(`1396c5ba8336ef267ac85f07083ea8977acc7395b2d8efb4754a05d4e146cfe8`)
and `task3-authority-3-pure-results.json`
(`c270b0ef7ecb8f8a4110737d5016af5456770cd3e99ec3a79f47f7831a2e0e6a`).
Root independently matched all four current file hashes. This is a static review,
not actual SQLite/native acceptance or permission to activate the generation.

Reviewed the closed v5 schema and compatibility changes, trusted initialization,
immutable qualification binding, registry cardinality/identity checks, bounded
claim/route reads, source-job/owner bindings, prepare-before-native claims,
original atomic ACK transaction, spans, registry readiness, tokenized contiguous
reconstruction and index-only confirmation. Existing source-worker and resolver
hook packets remain separately approved; the qualification loader is unchanged.

Two concrete findings were reproduced and corrected by the original author:

- A missing claim with an extant derived route could be reported absent by the
  resolver. A bounded route point lookup now makes that condition unavailable.
  Loss of both trusted authority and derived evidence remains outside the stated
  observation model; no repair is inferred from absence.
- ACK checked reserved claims but could skip a changed reused confirmed claim.
  All seven authoritative identity/hash/version/receipt fields and current gate
  state now match the observation before the original ACK writes begin.

The author recorded RED evidence for both and 12 affected GREEN checks at
41.8MiB/1.4s. The earlier 31-check result remains historical; no unnecessary native
or full-suite rerun was performed. Root reread both corrected branches and their
transaction ordering. No remaining blocker was found in this bounded static scope.

A proposed schema-overflow finding was withdrawn: there are 19 expected v5
objects, so the existing LIMIT20 already probes one excess object. No change was
required for that mistaken count.

Real SQL uniqueness/rollback, actual canonical publication and first-owner
equality, reconstruction, index maintenance and shared-session resource limits
remain prerequisites. The root-owned five-case fixture is prepared and unrun;
the independent core review and the separate tail-fixture preparation must be
included in the final finite qualification scope. No Task3 completion, commit,
production capacity or activation claim follows from this review.
