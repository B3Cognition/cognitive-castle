# Task2 native acceptance review

Decision: ACCEPT Task2's scoped metadata-directory milestone for commit. No remaining blocker in the frozen implementation, recorded assertions or captured native observations. This review was static only: no tests, database reads/queries, native engines or probes; no product edits.

All eight source/test file hashes remain identical to the approved preparation. The diff remains081ebfee4d20fc1d78776cf6f2c3489096d819a3ac331e62ec3a725c262cfdcd, preparation result remainsd9f4be9f9ab863273f73995390b89192997a8fc291997208bf58c6fce955946c, and preparation review remainsc741bb67daefe8c429f252164cdb70c1924e123dbdb56dca0539725060972c28. The only command addition, disabling pytest cacheprovider, does not broaden execution.

Independently parsed all94 stage observations directly from captured stdout and confirmed exact equality with the retained JSONL. Calls are sequential1..94, with one fresh resource record each and no admission/runtime reason. Expected statuses are65ok,7conflict,19unavailable,1injected_rollback and2reply_lost. The negative results match their explicit fault/assertion cases; none is a missing-stage resource refusal. Captured pytest reports11 passed in10.60s, and the outer guard reports completed10.8s/87.6MiB under90s/256MiB. Max observed worker task RSS52,494,336B, aggregate91,815,936B, and stage elapsed0.1553s are within unchanged128/192MiB and read2s/write3s limits.

The frozen assertions plus observations cover transactional rollback of route/gate/cursor/count changes, lost content and terminal ACK replies with idempotent recovery, unchanged semantic pending counts, staged visibility and conservative missing-ID results, failed whole-owner reservation without partition creation, private/read-only path refusal, missing/corrupt route/partition/plan/attachment/envelope/schema refusal, oversized attachment rejection, and a genuine legacy pending interval surviving another job's schema3-to4 upgrade and subsequent original ACK replay. Source/body sentinels are excluded from the synthetic SQLite artifact. Existing pure evidence and the preparation review cover the remaining closed schemas, authority bindings, bounded reads and before-CREATE schema validation.

Limits: this is real SQLite metadata transaction qualification using synthetic proof summaries. It is not Lance equality/publication or remote-reuse evidence, a whole-publication shared5s qualification, full migration, semantic completeness, production activation or merge/install approval. The94 operations use independent bounded sessions. RSS remains a sampled tripwire. The unique synthetic basetemp remains retained; no failure history or earlier evidence is reclassified.

Verified native artifacts:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| task2-layout-native-output.txt |18956|d7ad15bf0ffa22ca59389a83813ea5c3da7a8c715ac93bcbd2c4c09781ce3266|
| task2-layout-native-stages.jsonl |17035|e42195e6a2db1c6ca32fa7aa180b01a070f16064f27f58e1f00570ef52777254|
| task2-layout-native-root-result.json |2185|74b96bba73266c74a085ed6ba584c744cef3a65c8fa53ea0ce08616d940e12b5|

Saved outside charged/sealed runtime roots. Existing inputs and results preserved.
