# Task 3 separate tail fixture static review

Candidate reviewed: `tests/test_layout_native_tail.py`, 25633 bytes, SHA256 `a800351ce2c196b9ac4b0ada2d491c7ae78aa60aad7a718fb2968162795635bf`. Root's five-case helper remains separately owned and frozen. This review reads code only; no tests, engine imports, DB/source access or native work.

The fixture is preparation only. Root's separately frozen first-five run stopped at the shared deadline before any Lance import and did not qualify these tail cases.

## Findings and scope

One required assertion correction is with the original author: the first case claims index maintenance leaves source progress unchanged, but its final checks omit staging/completed cursors, last ACK and semantic-pending equality. Reuse the following real history tick's captured initial queue state to check the first maintenance against the existing baseline. Capture a queue state after the real history publication, before the second maintenance, and compare its full frontier with the existing final state. This proposed correction adds one call, changing case 1 from 33 to 34 starts.

The numerical tail schedule also needs the author's explicit serialization derivation, not merely a count of rows: source packing is constrained by decoded384 KiB, encoded480 KiB with its existing headroom, and the outer512 KiB frame as well as256 entries. I have not established a packing defect; an earlier concern used stale smaller limits and was withdrawn. The source contains520 one-character historical chunks and the proposed19 field pages plus1040 membership/record entries. The stated three256-entry stages must still follow from those actual fixed bytes.

The retained-tree diagnostic is per case:2048 entries,128 MiB logical and allocated, depth10. Five retained roots therefore have a conservative aggregate ceiling of10240 entries and640 MiB, plus pytest parent/alias, code and output metadata. This code does not establish a128 MiB whole-family ceiling. Root must bind the combined artifact scope explicitly before any run; no aggregate allowance or native grant is inferred here.

## Reviewed behavior

- The fixed520 source builder runs in a separate guarded SQLite child at128/192 MiB/2 seconds with the existing32 MiB source heap. It writes real original history/chunk/member/alias/attempt rows and a content/schema-bound descriptor. Original occurrence identity, ordinal chunk starts, source cursor and following cursor are populated consistently; it does not fabricate an exported intent or native proof in the host.
- Bootstrap and existing-index optimization use real metadata prepare, actual facade maintenance, a newly spawned exact worker reopening the persisted pin, and metadata confirmation. The first32-row page is explicitly index confirmation, not a complete enumeration when more rows exist.
- The underestimated-plan fault changes only the returned planning reservation. The subsequent real source export must refuse with the specific plan-mismatch reason, unchanged cursors, no export and no native write. A generic resource failure cannot satisfy the asserted result.
- The retained-temp case writes a fixed6 MiB file, then requires the real4 MiB working reservation to fail under the unchanged9 MiB allowance. It preserves the real prepared pending intent and claims; it does not infer publication. Partition and retained-temp fingerprints must remain unchanged.
- The changed-provenance frame remains otherwise structurally valid but must conflict with the pending digest/candidates. A separate real source cannot bind while the original staged owner holds the gate. Both failures preserve the original native tree and pending frontier; only exact original cold replay may ACK.
- The tail case keeps fixed source slices. After the proposed771 rows, the fourth257-row append must refuse before native work; maintenance confirms a real index at version4, after which the identical original interval resumes. The final actual owner proof and ACK must account for520 members, full text, expected field pages and version6. Public readback preserves the original first record's ID/text/provenance.
- Each positive tick uses the existing shared five-second session. Maintenance/reconstruction calls are separate bounded stages, not hidden within the publication tick. The fixture imports no engine into the host and does not modify the frozen core or source profiles.

## Candidate start accounting

| Case | Candidate starts | Decomposition |
|---|---:|---|
| Bootstrap then optimize | 33 | setup2 + LIVE10 + state1 + maintenance4 + new HISTORY9 + maintenance4 + state1 + public reads2 |
| Underestimated owner plan | 8 | setup2 + before state1 + state/plan/bind/refused export4 + after state1 |
| Retained temp | 10 | setup2 + before state1 + state/plan/bind/export/prepare/refused import6 + after state1 |
| Foreign stage and provenance | 24 | setup2 + lost append6 + state1 + changed import1 + source attach2 + refused foreign tick3 + states2 + cold LIVE6 + final state1 |
| Fixed exact tail | 47 | setup2 + staging8/6/6 + before state1 + refused tick3 + state1 + maintenance4 + resume6 + final7 + final state/owner/source3 |
| Total before correction | 122 | No retries or native execution authorized |

With the proposed single extra maintenance baseline call the schedule becomes34+8+10+24+47=123. Running this separate file in its own process keeps its imported root helper's150-start ceiling meaningful; a combined first-five-plus-tail process would exceed that helper ceiling and is not this reviewed schedule.

## Final correction and arithmetic closure

Re-read final `tests/test_layout_native_tail.py`,25943 bytes, SHA256 `8dabadb2f8c7bd69fd73aa021f93caf41f5b437181229d22f1fd8dcdfc5b9140`. It now compares the complete frontier around both maintenance operations using the next history tick's actual initial state and one explicit post-history baseline. The fixed520 case also compares source-tree identities and full file hashes before/after. The assertion finding is closed; no worker beyond the one baseline was added.

Read the preserved standalone stdlib serialization calculation and its recorded output in `layout-exact-report.md`, section `Tail review correction and deterministic byte arithmetic`. The row/page/pointer/provenance structures match the current source/codec definitions. Placeholder IDs and hashes keep exact fixed widths; real ordinal/end widths0..520 are represented. The maximum one-page8192-byte ASCII descriptor placeholder plus a further8192-byte escaping allowance is conservative for this fixed short-path fixture. Root's final path/scope freeze must preserve that one-page descriptor premise; the actual test also asserts its page count.

The first256 rows have decoded upper bound312211 bytes and conservative encoded bound364155 bytes, below393216 and475136 respectively. Later full256-row batches are182144 decoded/215938 encoded. The final35 entries plus the bounded final owner fit the remaining fixed frame limits. Thus256/256/256/256/35 is supported by the fixed serialized bytes, not just total row arithmetic. The earlier packing suspicion is resolved without a source-shape or limit change.

Final exact starts: **34 + 8 + 10 + 24 + 47 = 123**. The existing retained diagnostic bounds still sum conservatively to **640 MiB and10240 case-tree entries**, plus independently bounded outer pytest/code/log metadata; this is not a128 MiB aggregate claim.

Decision: **scoped static preparation approved**, with no remaining blocker found in the reviewed fixture. Root still must freeze the combined retained-artifact/outer execution scope before granting any native run. No tests, product imports, DBs or native engines were executed by this reviewer. Neither this approval nor the author's byte arithmetic repairs or supersedes the stopped first-five native evidence.
