# Single-decode owner proof: independent scoped static review

Status: **approved; the reported public error-normalization regression is fixed and no other scoped blocker remains**. This is product-correctness review of the candidate, not a native five-second fit claim.

Reviewed the complete three-product-file delta, changed pure tests, affected surrounding ordered scanner/proof/legacy paths and the final recorded focused evidence. No tests, engines, probes, Castle calls or database/source reads were performed. Only stdlib hashing/AST parsing accompanied the code reads. Frozen fixture/helper/seal files were not edited by this reviewer.

Final raw bindings independently verified:

- bulk_exact_codec.py:14,386 bytes / `268d554f60340ca61e012fd137b839e11495e8f0dc34fc17225f9dd575133a3c`
- bulk_owner_stream.py:14,469 bytes / `6560ab766d06c02f2bfd9a24765cba1c24039f62843ea61a2138c00a3092f9ed`
- bulk_exact_store.py:40,543 bytes / `fecb8c50c09a7b5fe7340cc1d40330c456607eb256f19198100f7887621dc959`
- test_bulk_owner_stream.py:25,684 bytes / `bccaa90fc3dde4f92fc6c0b85818cf242bb237b3d03743404427ce38f37c65a1`

The central private entry decoder retains all prior raw entry checks while returning the already validated CanonicalRecord/header/member. Public validate_entry still performs those checks and returns the identical original row. Legacy _record, checked_page and receipt decoder remain unchanged.

The private carrier accepts only a raw six-string dict, copies that snapshot and constructs decoded authority internally. It accepts no injected record/header/trust arguments. Raw values and headers/member/scope mappings are read-only; all decoded structures originate from the copied strings and are only consumed internally. Public verify_owner_rows constructs fresh carriers and rejects a predecoded carrier as raw input. The internal typed path checks the exact carrier type. There is no caller-facing checked flag or cross-proof cache.

The ordered scanner still enforces qualified owner/source binding, row geometry/sentinel, receipt uniqueness/count, marker/live constraints and strict32-row ordered scans with unchanged readahead/buffer limits. The removal of _bound_row from this one scan is matched by complete strict decode plus the same qualification checks. Other _bound_row callers remain unchanged. The fixture observer only reads row['kind']/row['id']; the read-only Mapping preserves that interface.

Pending rows decode afresh for every proof, retain bounded current-frame insertion order and reject identity overlap with stored rows. Reused raw originals also decode afresh before record/member validation; the dedicated ordered store still refuses foreign reuse through its empty resolver. The verifier preserves field/page ownership/order/offset checks, pointer ordinal, original membership digest, source exposure/provenance, byte/character counts and complete streaming text SHA. Marker and live-receipt equality retain Mapping semantics. Every independent import still traverses and proves the original bytes; no stored hash or previous proof substitutes for reading them. Live records remain bounded to9, and the iterator remains one-row lookahead plus the bounded frame/batch.

One review finding was corrected: constructing the raw generator expression outside the normalization try could leak TypeError for a non-iterable source. The final generator function defers raw iteration until it is inside the existing corruption boundary. Recorded targeted RED/GREEN cases cover None and a raising __iter__, restoring _StoreError('corrupt').

Recorded evidence comprises14 distinct new and4 affected existing pure cases across focused runs, read but not rerun here. They count actual full CanonicalRecord validations once per member in each of two separate proofs, count entry/receipt decodes by ID, cover stored/pending tails and raw snapshot mutation, and preserve rejection of text/pointer/page/exposure/owner/receipt/order corruption. Existing affected cases cover Unicode/NUL/empty data, missing/duplicate/foreign rows, actual reused bytes and publication boundaries. This is not a full-suite claim.

The change removes duplicated work within each proof without changing memory, stage, shared deadline or storage limits. Native performance and the retained cold-only replay/final ACK remain pending a separately reviewed binding and root-owned execution.
