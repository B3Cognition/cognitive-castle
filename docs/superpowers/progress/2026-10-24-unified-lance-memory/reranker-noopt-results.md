# FP32 optimization-disabled result — 2026-10-25

**Disabling ORT graph optimization did not resolve the fixed short-K10 ranking failure.** Root executed exactly one revised unit. It completed inference and returned `failed / synthetic_relevance_mismatch`: Saturn at original index 3 remains first; the unchanged required answer is Mars at index 2. No retry or additional probe was run.

## Retained bindings

Paths below are relative to this outer SDD unless marked `BASE` (defined in `reranker-input-audit.md`).

| Evidence | Exact SHA-256 |
|---|---|
| `reranker-noopt-preparation/receipts/short-10--infer_only.json` (1,933 bytes) | `7c7a16b68bb0c2fc1c6c3f045649ec5a898817692d0267a586afb57121a1c15e` |
| `reranker-noopt-preparation/manifest.json` file (13,931 bytes) | `4f2695bdba826ed3fad60e8986c18b511db59a02269e5016a78a9ae1e5043118` |
| Same manifest, canonical request/receipt binding | `4f0a648c4e21bbade1e0c58bb21acb353da10322dc844437c3912d67e1838a0a` |
| Executed `official_fp32_noopt.py` | `e4838267a9893469a2df0bbb5c050e5d23972a2fe2877d8260133f37e53d698c` |
| Retained ENABLE_ALL baseline: `BASE/official-fp32-baseline-v1/receipts/short-10--infer_only.json` | `1a94297f5f7ab3434e47265c74a42b8c0d2748863fc5003c20e9d5aa77aff94e` |

The official FP32 external graph/weights and verified cached short-K10 page were unchanged; page canonical SHA-256 is `cf395a969972e7c74194e7bd0a455640dc4abc555289b1af20076115b4377bfe`. The scorer's only inference-option change was `ORT_DISABLE_ALL`. Root checked the frozen preparation/source/evidence hashes and six asset stat identities, observed fresh pressure level 1 and free admission, then launched the single unit. Runtime retained original evidence, model/data hash, package-version and signature validation.

## Actual execution and comparison

ORT 1.25.1 CPU, one intra/inter-op thread, sequential execution, disabled CPU arena/memory pattern, file-path external-data loading, one ten-pair scorer call and original ordering/restoration were retained. The revised guard used the five hash-bound current worktree files from commit `6fa66595c16fd71c7ec388831c199b839bf93683`, including memory runtime SHA-256 `35e821030d4ebe0c582a5dcbe50207e7bf5f246a312bf671b82b6794a74068cc`. It explicitly passed `absolute_deadline=until` and `background_preempt=True`, with current guardian/session/UID admission checks, pressure/preemption handling, **512 MiB task / 640 MiB aggregate / five seconds**. RSS monitoring remains a sampled tripwire.

Observed unit elapsed time was **1.5585932079993654 s**; sampled task peak **423,608,320 bytes**, aggregate peak **445,792,256 bytes**. There was no guard refusal. Root observed no matching surviving descendants and returned the native slot to FREE. These measurements do not retroactively qualify the historical baseline's weaker guard path.

Root's stdlib comparator reported identical original-index rankings for ENABLE_ALL and DISABLE_ALL:

`[3,2,8,4,1,0,7,6,9,5]`

| Candidate | ENABLE_ALL logit | DISABLE_ALL logit |
|---|---:|---:|
| Mars, index 2 | 3.454047918319702 | 3.4540529251098633 |
| Saturn, index 3 | 5.94781494140625 | 5.947810649871826 |

The maximum absolute logit delta across all ten candidates was **0.000010013580322265625** (`1.0013580322265625e-05`). Logits were not exactly identical; the ranking and failed Mars quality gate were unchanged. No tolerance or golden-label change was introduced.

## Conclusion and scope

This one-pass optimization-toggle hypothesis is closed for this fixed graph, cached page and ranking: switching optimization OFF does not repair it. The result is not source-Torch parity, global numerical certification, or qualification of other inputs/shapes. `BAAI/bge-reranker-base` remains the configured model; its unchanged Mars relevance gate remains failed and the path remains unqualified. Original and new evidence/results are preserved; the first rejected preparation remains an unrun archive. No further runtime, preparation, model or code change is proposed here.
