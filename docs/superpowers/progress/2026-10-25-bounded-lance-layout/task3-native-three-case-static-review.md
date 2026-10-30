# Task3 native fixture: focused three-case recheck

Approve the corrected preparation logic for the first LIVE, lost-append and lost-ACK cases. No remaining blocker found within this narrow review. Observed current file: `tests/test_layout_native_integration.py`, 18525 bytes, SHA256 `fd65a3fac5d9c560abfe122e186a517925df8ce82e688176d8fa2620c15f3e8e`. This is not a final seal, native grant, capacity approval or Task3 acceptance; further cases/core APIs are still being implemented.

The three original skeleton findings are addressed: the proposed temp envelope explicitly separates working and retained space; `_record` requires an exact expected reason (None by default) and one fresh stage metric; the happy case checks identical import calls, Fresh→Existing outcomes, owner/LIVE/ACK order, common intent/version context, full returned owner manifest/version, and an independently generated original nine-chunk digest/receipt.

Two further assertion gaps found during this recheck were also corrected. Arguments are now deep-copied before underlying dispatch, and results after receipt, so comparisons capture call-time data rather than aliases to a reused mutable dictionary. The lost-append case explicitly checks original staging/completed cursors, null last_ack, zero semantic_pending, then exact pending.cursor_after and one semantic_pending after recovery.

Lost append hides only an actual successful Fresh response. Ordinary legacy owner/source/receipt reads and a context-free facade read are separate supervised refusals. Recovery regenerates the same export arguments and fixed import, requires exactly one actual Existing outcome, then performs owner/LIVE proof before ACK. Lost ACK hides an actual successful committed result, retries the exact recorded request, and compares pending, both cursors, counts, last_ack and semantic counters without recounting.

These remain unexecuted assertions. The 9 MiB proposed temp input and other storage charges still need the final concrete qualification. No broader fixture rereview, tests, engine imports, database access, native work or product edits were performed. Earlier review artifacts remain retained.
