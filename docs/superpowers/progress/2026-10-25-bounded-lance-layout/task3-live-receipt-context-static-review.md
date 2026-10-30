# LIVE receipt context correction — static review

Approved: no blocker found in this minimal correction. No test, DB, source probe or native operation was executed by this reviewer.

Independently matched all raw bindings:

- Delta `task3-live-receipt-context-1.diff`:4457 bytes, SHA256 `8eeaecff0775c56cb45cd25e5edd238f00bb626f298310e88cd6866dd72581ec`.
- Report `task3-live-receipt-context-results-1.json`:3297 bytes, `decdf9559dd25454af6b0c4eea6aad560bd199729bdf5368ac362deb4f664724`.
- `cognitive_castle/partitioned_exact_store.py`:36525 bytes, `9d963772089a305310eb9330e773168dc58e991ba411c2ae9a9b333d7673ee8a`.
- `tests/test_partitioned_exact_store.py`:28115 bytes, `dc2a6638a55bdcccd4f4f01ff320c0aeca607df540bb9682030076a4d48f5200`.

The original codec defines `live_receipt_ids` as the original `memory:` chunk IDs, whereas the requested durable receipt row has a `receipt:` identity derived from namespace/key. Their comparison was an invalid identity-domain gate. The replacement requires the one pending owner's LIVE classification and exact original `source_key == [namespace,key]`. Layout interval construction already requires that key to equal the manifest's original LIVE namespace/key, and candidate validation requires the matching receipt row.

The change does not rename or reinterpret the v1 metadata field. It preserves the one-owner requirement, closed private context, pending intent, selected home/source binding and exact after-version. Opening still verifies the actual batch receipt/source/digest/proof ID set, and receipt lookup still checks the actual registered row hash and inherited original receipt/records proof. Ordinary context-free publication gates are unchanged.

The added tests construct the original LIVE intent through the real pure source/owner/layout codecs and exercise the actual facade boundary. The valid case demonstrates distinct chunk-ID and receipt-ID domains and opens the expected home with the same intent/version. Wrong namespace, wrong key, non-LIVE owner and multiple owners must refuse before the fake storage boundary. The report preserves the original valid-case RED and29 affected pure passes; these tests do not replace actual native receipt verification.

This approves the corrected code for root's newly frozen qualification. The earlier failed first-LIVE run remains failed at receipt context with no ACK; its successful append/replay/owner stages are not promoted to a complete publication result by this review.
