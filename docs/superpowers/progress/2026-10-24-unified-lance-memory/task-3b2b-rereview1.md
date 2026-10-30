# Task 3b2b scoped re-review — fix round 1

## Verdicts

- **I1: ADDRESSED.** `cognitive_castle/native_source_worker.py:29` and `:30` now require the worker and guardian session IDs to equal the guardian PID. Lines `:32` and `:33` require the guardian and host effective UIDs to equal the worker UID. The host lookup at `:22` supplies the latter observation, and process/query failures remain refusal paths.
- **Spec compliance: ✅ Compliant within the reviewed task scope.** The sole original blocking finding is resolved. The existing fixed guardian command, process-group/parent checks, history-profile admission, source limits and session lease remain intact in the supplied patch context.
- **Task quality: Approved.** No fix-induced Critical or Important issues found in the two changed files.

## Strengths and evidence

- The change adds the four missing admission conditions directly without changing runtime selection, resource profiles, source behavior or public APIs (`native_source_worker.py:13`).
- The focused test checks each of the four omissions independently, retains command/group/parent faults, and adds a valid-chain baseline (`tests/test_native_export_codec.py:183`, `:197`). Separate guardian/host observations let the UID cases test the intended process identities rather than conflating them.
- The appended report explicitly corrects the earlier overclaim and records four RED omission cases, eight GREEN pure chain cases, final post-format GREEN, and one authorized real empty-source smoke. The reported smoke completed in 2.70 seconds with unchanged source artifacts and no resource refusal; native source stage was 0.8462 seconds at 162,824,192 B task / 208,109,568 B aggregate RSS. Root has inspected the exact underlying evidence. No test was repeated for this review.

## Findings

- Critical: none.
- Important: none.
- No additional change is requested for I1.

## Retained boundaries

Real lineage/content qualification, capacity, giant native/destination finalization, reconciliation and production continuation remain outside this fix and remain root's gates. Root's reported operational read-only verification is retained as controller evidence; this reviewer did not independently inspect production processes, services or storage.

## Review scope

Read the appended fix report and complete supplied 5,554-byte diff once: base `a610fad57ce3ee4946b5d863f52bc9390d6d480e`, head `162a94f2e9fed205768fc3b6fa46d26bdeef900a`. Reviewed only original I1 and possible fix-induced breakage in `native_source_worker.py` and its pure fault test. No broader re-review, runtime, tests, engine/model/storage reads, product/git mutations or subagents were performed. This report is the only new review artifact.
