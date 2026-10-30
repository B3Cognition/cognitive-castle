# Task1b continuation 1: independent scoped static review

Status: **approved for final freeze, subject to final raw seal verification and root's native execution grant**. This is not a runtime qualification or final Task1b pass.

Reviewed only the continuation delta against the preserved original worker/helper, the candidate configuration, retained-preemption report, changed ledger and fixed resume boundary, plus the five new pure test cases. No tests, engine imports, source/queue/database reads, Castle calls, or native execution were performed. No sealed packet or product code was changed.

## Reviewed binding

- Candidate: `task-1b-continuation1-candidate.json`, 13,721 bytes, SHA-256 `63a2421fc669584ceb86fa710981cb92db56c8fa2ee2e4bad273c5160ba65fbb`.
- Helper: 79,430 bytes, SHA-256 `beab6fa7a559511e2a226595382d7d814d442a4a3e77bf2c56b4bab383cf7f56`.
- Unfrozen worker: 54,772 bytes, SHA-256 `23e48e369ea236e16669c1c31122745d410c490f2877c4012e973f9153d30f00`.
- Preemption report: 8,847 bytes, SHA-256 `37d744f82c73fc352df403550657bd39d176b98aebf703b6d3187fea3d77f282`.

Independently checked all 29 candidate code pins (557,563 bytes) and all eight prior raw files against their size and SHA claims. Original helper/worker archives match the previously reviewed frozen H1/W1. The worker literal is deliberately None at review time; final C/W/H/S/pin and normalized-worker equality remain to be checked after freeze.

## Evidence and protocol

The only configuration changes are helper code pin, explicit continuation object, mode=resume, new fixed trusted packet root, and new pytest basetemp. Source roots, descriptor/binding, owner manifest, final cursor, run root and numerical resource profile are byte-equivalent values to the original configuration.

`verify_continuation` binds exact old config/seal/pin, archived code, and old event/peak/refusal files. It validates 122 paired sequential starts/ends, 121 successful ends followed by background_preempted, the fixed original refusal and 122 peak records. New logs are separate; the ledger begins at 122, consumes retained new starts when reconstructed, refuses before appending beyond 1,074, and keeps the original attempt immutable. The ceiling is the parent's explicit operator-schedule correction: at most 952 new starts plus 122 consumed starts, not a reset or a resource-limit increase. The old failure remains a failure.

Resume obtains the actual queue state. The unchanged ACK/pending reconstruction binds the persisted registration/cursor and retained ACK qualification; only then does the added gate require ordinal 20 and pre-interval geometry version 21 / physical rows 1,390 / fragments 19. Optional pending interval 20 follows the unchanged coordinator's prepare/replay behavior. No metadata seeds an assumed queue commit result. Already-existing future maintenance qualifications refuse; no extra reconciliation calls are silently added.

## Capacity and refusal accounting

The retained old packet/config/basetemp and new archive files are included in the census; prior attestations add hash/identity checks but do not add their bytes a second time. Current worker bytes are counted once outside the packet and the helper once through the code pins. The stated normal harness entry arithmetic is 245+1+2+2+1+1+3=255, below the unchanged 256 ceiling with only one spare entry. Temp remains 382, and all-family normal entries are 122+610+255+382=1,369. This arithmetic is conditional on the fixed normal artifact shape; runtime census must still refuse any extra artifact that exceeds a limit.

New refusal output uses only the already allocated continuation 4 KiB slot; old refusal remains unchanged. The preserved cold-failure path returns bounded stdout instead of creating an uncharged result. Pre/post-stage hashes and sampled file identities remain intact. All numeric memory, stage time, storage, entry and workspace limits are unchanged. The parent-selected outer timeout is 540 seconds; sampled disk/RSS tripwires are not described as kernel quotas, and source/queue transient unlinked peaks remain unmeasured.

No concrete blocker was found in this scoped continuation delta. Native correctness, final owner publication, fresh-process replay, final ACK and resource fit remain unproven until the root-owned run supplies evidence.
