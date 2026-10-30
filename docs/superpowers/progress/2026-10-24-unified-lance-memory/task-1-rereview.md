# Task 1 scoped re-review

Scope: the original P2 nine-chunk receipt finding and fix `f9751c9..3208aea`. Read the supplied fix diff, appended fix report, Task 1 brief, and original review. This does not reopen the broader review or qualify the integrated system.

## Finding verdict: ADDRESSED

Receipt validation now permits nine IDs. This covers the existing codec's maximum output: an accepted input is at most 65,536 UTF-8 bytes, and a closed 8,192-byte chunk can leave at most three unused bytes, so no accepted input requires more than nine chunks.

The fix retains receipt binding: a nine-record receipt cannot qualify through an import digest; it must match the full canonical `prepare_remember` output and digest for the stored namespace/key. Referenced-record validation and incoming-request conflict checks remain intact. Import batches and individual reads retain their eight-source limits.

## Spec verdict: PASS for this fix

The nine-chunk accepted-input case now supports identical replay, changed-input conflict, and recovery after a committed write loses its response. Canonical IDs, text limits, provenance, atomic publication, and resource profiles are unchanged.

## Code-quality verdict: PASS for this fix

The correction is narrow and explains the cardinality distinction. The two regression variants exercise ordinary and lost-response publication, fresh-process replay, conflict, exact text/hash/byte count, bounded reconstruction, rejection of nine-source read/import requests, and absence of duplicate rows after retries. No new important breakage was found in the fix diff. The original review's sole required correction is closed.

## Evidence and limits

The appended report records the expected pre-fix replay failure and a post-fix focused run of 12 passing tests, including both new variants and existing receipt corruption/import/replay coverage, with a 188.4 MiB guarded aggregate peak and no resource/admission refusals. It also records pinned Ruff and diff checks. These are implementer-reported results; no tests or native/model/database operations were rerun in this review. No product code was edited. Existing full-corpus, migration, integration, and installed-system qualification limits remain.
