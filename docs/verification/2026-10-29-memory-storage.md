# Memory storage verification, 29 October 2026

The packed migration and published-snapshot paths have real Lance evidence.
The complete unified-memory delivery is **not finished or activated**.
This report does not establish full-corpus capacity, semantic completeness,
ordinary capture/recall integration, or installed Codex/Claude behavior.

## Corrections

- Published reads open the exact registered BEFORE version while an append or
  maintenance operation is pending. Namespace, schema, geometry, index and
  publication checks remain active. A missing snapshot refuses without fallback.
  Internal mutation and proof operations continue to inspect the current version.
- The dedicated append guard previously accepted only its first qualified owner.
  A real packed append therefore returned `corrupt` even though preparation and
  the earlier unit tests passed. The base guard retains its single-owner rules;
  the registered packed override validates the complete ordered candidate set,
  original row hashes and bound batch receipt. Resource checks are unchanged.
- Semantic queries now distinguish text hashes from full-source exposure hashes.
  Exposure grants apply before nearest-neighbor limits and are checked again
  after exact hydration. The original internal text filter remains separate.
  Tests cover identical text from different origins and a closer unauthorized
  candidate. Native vector/exposure prefiltering has also been verified below.
  Host policy-epoch and ordinary-route integration remain outstanding.

## Evidence

| Scope | Evidence | Result |
| --- | --- | --- |
| Snapshot, packed authority, source and original contracts | Runs 40360517545, 40939247023, 40939245885 | 592 tests passed without native storage |
| Actual inherited append guard and regressions | RED 40940016946; GREEN 40940140812, 40940228386, 40940228923 | 628 tests passed; includes 28 original dedicated-owner/reservation cases |
| Guarded source proof-reply budget | [Run 40939650921](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40939650921) | 3 worker starts, 2.2 s, sampled aggregate peak 100.2 MiB |
| Two-owner packed publication and lost ACK | [Run 40940316653](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40940316653) | 21 worker starts; 12.2 s overall; sampled aggregate peak 186.2 MiB |
| Published old snapshot during the next same-home append | Same run | 30 worker starts; 20.5 s overall; sampled aggregate peak 176.5 MiB |
| SQL failure after the second owner span update, then cold recovery | [Run 40941861515](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40941861515) | 26 worker starts; all 14 metadata tables unchanged after rollback; 21.0 s overall; sampled aggregate peak 186.1 MiB |
| Exposure grants and semantic/vector control flow | Guarded local Mac XML in the execution ledger | 36 tests, 0.5 s, sampled aggregate peak 39.5 MiB; 23 additional original contracts, 2.2 s, 60.7 MiB |
| Actual native exposure prefilter and read-only queries | [Run 40943086351](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40943086351) | 8 worker starts; 7.7 s overall; sampled aggregate peak 184.0 MiB |
| Registered exact/semantic routing and original contracts, in separate processes | [Run 40947772091](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40947772091) | 50 + 23 tests passed; 0.8/1.0 s; sampled aggregate peaks 43.5/64.5 MiB |
| Registered original → vector publication → cold receipt → exact hydration | Same run | 20 worker starts; 16.9 s overall; sampled aggregate peak 188.1 MiB; maximum sampled task RSS 138.6 MiB |
| Capture receipt validation, checkpoint replay and original capture/scope contracts | [Run 40950991499](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40950991499) | 74 functional tests passed; 3.0 s overall; sampled aggregate peak 50.2 MiB; disposable SQLite fixtures, no Lance/models or user palace |
| Write-ahead capture intent, exact-ID scope, crash recovery, NUL and fair progress | [Run 40955534530](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40955534530) | 94 functional tests passed; 4.2 s; sampled aggregate peak 65.8 MiB |
| Protected-export and source/packing contracts | [Run 40952949886](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40952949886) | 282 tests passed; 10.3 s; sampled aggregate peak 53.4 MiB |
| Actual three-generation capture recovery and protected journal export | [Run 40956192720](https://github.com/ladislav-bihari/cognitive-castle/actions/runs/40956192720) | 2 supervised worker starts; 0.9 s overall; sampled aggregate peak 94.8 MiB; individual task peaks 51.2/41.5 MiB |

The native packed steps took 2.4696 and 2.6671 seconds. The same-home snapshot
steps took 1.5979, 3.3562, 2.5261 and 3.7995 seconds. Every step retained its
absolute five-second session deadline. Exact workers retained 192 MiB task /
256 MiB aggregate diagnostic limits, two-second reads and three-second writes.
Queue workers retained 128/192 MiB and the 16 MiB SQLite heap limit.
RSS limits use sampled tripwires; transient peaks are possible.

Both native cases verify original text, provenance and LIVE receipts. Owners
remain hidden after Fresh until cold Existing replay, grouped proof and ACK.
Lost-ACK replay does not duplicate counts. Already published source, receipt
and owner reads succeed while the next same-home append is still unpublished.
The original source tree and qualification artifact remain byte-for-byte intact.

The first packed run failed before ACK at the inherited single-owner guard;
its whole fixture archive is retained. The corrected run uses new disposable
fixtures, source snapshot `d3361d43784304686db34dfc97b2974ecc2ff624` and CI snapshot
`854b64b1e5f36d87b0fa753169729df067784435`.
Its complete retained TAR is 1,566,720 bytes, SHA256
`e6b2e93c45aac6149e3eb12a3764a473265bf04c25fa60149cfef7b439ee2c60`.
Only JSON/log members were inspected; failed databases were not reopened.

The first exposure regression selection failed on Linux because an existing,
unmarked Mac-specific session test correctly refused platform supervision.
The same 36 selectors subsequently passed on the actual Mac under the guarded
test runner. No production guard was weakened to make that suite pass.

## Production and completion gates

The successful native runs used the 192/256 MiB exact-memory profile. Observed
exact worker peaks were approximately 135–138 MiB. On 29 October 2026 the user
explicitly approved that profile for production: “povolit produkčně 192/256 MiB”.
The exact guardian/session already enforce these values. SQLite coordination
retains 128/192 MiB, and deadlines/admission/cleanup remain unchanged. This
approval resolves the resource-policy gate; integration and verified activation
are still required before changing the installed ordinary routes.

The actual-SQL fault case used genuine Lance replay/group proofs. After the
second owner span update, the injected failure rolled back all 14 coordination
tables. Both owners remained hidden and the original frontier/counts stayed
unchanged. A subsequent cold replay/group proof and ACK published both owners.
Its three steps took 3.4058, 4.0013 and 4.1028 seconds. The complete 808,960-byte
TAR is retained with SHA256
`ce2c1df6382fb79837546616ae53c70fc095a959d837a49097916f366195e291`.

The native vector-grant case passed with genuine canonical records containing
identical text from two different origins. A closer unauthorized vector did not
displace the authorized result under limit 1. Empty grants, a text hash supplied
as an exposure grant, unrestricted queries and the intersection of both filters
had the expected results. Querying preserved every file fingerprint. This case
uses fixed synthetic vectors, loads no embedding model and proves no relevance
quality. Its 122,880-byte retained TAR has SHA256
`7fad584cb39b8dbbab919366d9a77b9185d0e0138f8157875281149aa08b016b`.

The new internal `LayoutSemanticSession` routes exact reads through the
registered partition authority. Vector publication and vector-receipt recovery
both revalidate those same canonical originals; neither falls back to the flat
exact store. The receipt route needed a separate correction: publication alone
left recovery reading the old authority. A failing regression reproduced that
route before the correction. Queue workers retain their original lower budget.

The native routing case first refuses vector publication while the original is
unpublished, then imports the original two-owner prefix using actual cold
replay/group proof and ACK. It verifies semantic hydration, the original LIVE
receipt, vector publication, cold vector-receipt recovery, exposure-authorized
nearest lookup, exact hydration and idempotent publication. No flat canonical
dataset is created. Original source/qualification bytes and all generation file
fingerprints after publication remain unchanged by recovery/query/replay.
Its two migration steps took 3.2949 and 3.4733 seconds. The 16.9-second total
covers multiple independent bounded sessions, not one interactive query. Fixed
synthetic vectors exercise storage contracts; no model or relevance-quality
qualification is claimed. The complete 829,440-byte retained TAR has SHA256
`fb83b5c1920440716a765a126e600e3fdbf985df70d4e54f7fccc648fcae2f40`.
Source snapshot: `2a5f28d68a4aeba410fcd136378c6b4ca088ce6d`;
CI snapshot: `7f20aa476ff87e32e0317984ad83a93fd6df6649`.

An earlier combined 73-test process passed the first 50 tests, then failed an
original contract's clean-process import assertion because the semantic tests
had loaded SQLite. That failed artifact is retained. Running the two original
selections in separate processes passed all 73 without deleting modules or
weakening guards. These adapters remain explicitly selected internal machinery;
they do not switch ordinary installed capture, recall or context routes.

Capture now verifies the complete ordered canonical IDs, UTF-8 byte count and
text hash in a successful publication receipt before advancing the piece
checkpoint. A bare `status=ok` with a mismatching receipt refuses. An optional
trusted publication observer can persist derived metadata before that checkpoint;
its refusal leaves the piece replayable, and a mutation of the verified receipt
is checked again. Tests use actual disposable storage to verify replay without
duplicate chunks, multichunk originals and the original workspace/crash cases.
The 250 ms capture-slice deadline is unchanged. New functional tests allow at
most four API calls across legitimate no-progress slices; this is not a latency
qualification or an automatic retry of a refused publication.

The feature branch now wires a body-free write-ahead journal into capture.
Before append it records the immutable request identity/digest, expected receipt,
source generation/record location and frozen workspace decision. Expected IDs
are not evidence of publication. Actual append confirmation or a fresh receipt
read from the selected canonical backend authorizes atomic exact-ID scope maps.
New capture attempts do not query body-table rowids. Existing pending watermark
attempts retain their explicit legacy recovery branch; old unmapped evidence
cannot acquire a later workspace hint, and pinned associations never move.

Workspace is conservatively reserved before append. An interrupted or failed
write can leave a pending reservation, which cannot silently broaden access.
Recovery probes at most two intents per call and rotates a durable per-source
keyset cursor. Absent old receipts stay pending without starving later confirmed
requests or fresh capture. Backend/resource refusal still stops the tick.
Checked/recovered/pending counts are separate, and pending or unknown states
remain visible in source selection and prevent a complete-coverage report.
Scope-map insertion and its coordination acknowledgement share a transaction;
a real failure at the second chunk rolls back all ID mappings and the ack.

The existing SQLite backend's new receipt read verifies the committed request
digest and ordered originals, including their text hashes, offsets and caller
provenance, before returning the receipt. SQL projections are byte limited so
valid NUL/Unicode text is preserved and a NUL suffix cannot hide corrupt journal
metadata. This is an explicit backend operation, without a fallback search.
The protected-source exporter recognizes the journal's six-column schema and
preserves original rows verbatim as AUDIT metadata, without treating expected
receipts or applied markers as canonical proof.

The final owned macOS case preserves three original source generations. Two
crashes before append leave unconfirmed intents. The third append contains NUL
and Unicode and loses its committed response; fair fresh receipt recovery reaches
it while the earlier two remain pending. The protected reader exports the actual
original journal row and leaves every fixture file fingerprint unchanged.
Workers retained the original SQLite 128/192 MiB profile and two-second outer
worker deadlines: fixture/recovery took 0.2298 s and export 0.1220 s. The 12-second
test ceiling was unchanged. The complete retained 593,920-byte TAR has SHA256
`25f0170b20642b214209035cedf23f080b09ce8d7feb02e8808d9d73d5d57283`.
Source snapshot: `45f1ceee45866eafbb77218a286923192a136127`;
CI snapshot: `c40907dcce7d9fd1bf573ec5182a2b63da7be876`.

Earlier native tests used incomplete test cursors; the existing source protocol
correctly refused or exported a different owner. Their complete failed archives
are retained. The corrected cursor follows the original descriptor-entry contract
and is covered by a real SQL exporter test before native qualification. No guard,
timeout or resource limit was relaxed.

This journal is wired into branch code, not the installed services. The current
ordinary canonical publisher still uses the existing SQLite backend. A registered
Lance foreground-request writer and ordinary recall/context integration remain
required before cutover. Applied journal metadata is retained; its rows and
indexes must be included in the real retained-capacity audit. No pruning,
installation, hook activation or storage switch was performed.

Remaining delivery gates include ordinary Lance-backed remember/capture and
recall/context, lexical/vector/KG fusion and configured reranking, source and
semantic reconciliation for the complete historical boundary, retained disk
capacity, installed host behavior, independent branch review and B3 integration.
The active GitHub account has read access only to B3, but the separately stored
Testimonial account was verified to have admin/push access. This check used an
ephemeral credential and did not change the active account. Access therefore
does not require user intervention. Feature commits are pushed to the personal
fork; they have not been merged into B3 or installed.
