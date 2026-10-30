# Task3 resolver hooks: scoped static review

Decision: approve the corrected three-file hook packet for integration. No remaining blocker found in this scope. This is not Task3 facade, native parity, resource, or activation acceptance.

Reviewed the full original delta, the corrected namespace/read delta, surrounding instance lookup and writer paths, and all new pure tests. Independently checked the following bytes and SHA256 bindings against the recorded packet:

| File | Bytes | SHA256 |
|---|---:|---|
| task3-resolver-hooks-2.diff | 25016 | aee44998cc91789a11bc76da0efa4691ce8170f845dbea25f065853d3707d917 |
| task3-resolver-hooks-2-pure-results.json | 6108 | 4b82511acdae3bcf3fae5a20be4882b13eb841b96280197a075114be0ad82e4f |
| cognitive_castle/bulk_exact_store.py | 42654 | 8346bcdd6cb639ccb289f041df547c9d0f7acfb1c0a649c24a22fd7cc58032ee |
| cognitive_castle/lance_exact_store.py | 18164 | 031194765e2ecebb526b6a0a6ad658c3cefe9fba4fbdcc7d8a8ea67211a9a65e |
| tests/test_layout_resolver_hooks.py | 11847 | 39df02cb58fc63281b123fe7a22c24c8b3bee8d52c70da604b6d340d95a09589 |

Instance candidate lookup, batch and owner proof, bulk owner/page/receipt reads, legacy receipt/remember/hydration, and visible_source use the new lookup hook. Coverage dispatch is likewise overridable at the relevant store boundaries. Independent AST comparison with base 307b00039f4a8bd3db0104dc4df9b9c2423c29bc confirmed that module lookup_many/coverage, static LanceExactStore._find/_find_many, OrderedBulkExactStore._owner_rows/_verify_owner, _ReplayOutcomeStore, and _require_supervision remain unchanged. The default hooks delegate to the original implementations.

The original guard had two aliases: lexical `0/../0` (root finding) and case variants such as `EXACT/PARTITIONS/0` on case-insensitive Darwin volumes (independent review finding). The correction uses normpath without resolving symlinks, and compares the actual parent device/inode for case aliases. A distinct directory on a case-sensitive filesystem retains legacy behavior. Existing symlink checks remain. Marker lookup uses lexists, so a broken qualification symlink also refuses access.

The root's additional pre-ACK read concern is closed at the legacy access boundary: base _paths and _open and OrderedBulkExactStore._paths invoke the default registered-namespace refusal. Ordinary reads therefore cannot open a registered home to bypass the queue visibility gate. Writer supervision precedes custom path hooks, with mutation checks before creation and again under the writer lock. Private authority overrides remain the facade's responsibility; no public caller flag is introduced.

Recorded evidence reports alias/read RED cases and 94 affected pure tests passing in 0.6 seconds, sampled peak 46.2 MiB. The prelaunch BUSY result is retained as a non-attempt. I did not rerun tests, import engines, query databases, or execute native/storage work.

Integration limits: the pure tests use fake datasets and filesystem markers. The later facade/native gate must still show actual append-before-ACK data remains unavailable through ordinary reads while the exact pending-intent proof can read its pinned home, plus bounded remote reuse and registry authority. The marker checks do not establish authority reconstruction or protection against coherent loss of all trusted metadata. Original packets remain retained; this review does not turn old native failures into passes.
