# CPU reranker feasibility audit — 2026-10-24

## Latest FP32 discriminator: batching and right padding do not explain this fixture's ranking

Root authorized exactly `official-fp32-grouping-v2`, canonical manifest binding
`66d8586721ada0e8d260ca5886bd28039bfb019caa9889e029ba04e875b182d8`.
The one disposable official-FP32 session completed all **21 fixed calls**:
original K10 batch, all ten padded singletons, and all ten right-padding-trimmed
singletons. Model/weights/runtime/optimization/threading, fba868f supervision,
512 MiB task / 640 MiB aggregate and the single five-second deadline stayed fixed.
There was no resource/admission refusal, retry, partial rerun or settings change.
The native slot was released immediately after the completed result was read.

Total supervised elapsed was **2.645742 s**, sampled task peak **440,303,616 bytes
(419.91 MiB)** and aggregate **462,602,240 bytes (441.17 MiB)**. Model/data hash
verification took 0.526313 s, imports 0.150144 s, session loading 0.215917 s and
all inference/observation work 1.620064 s. As elsewhere, sampled RSS is a tripwire,
not proof that no shorter transient peak occurred.

The original K10 logits exactly reproduce the preceding official-FP32 receipt.
Every padded singleton logit is also **exactly equal** to its original batch
logit. Removing only mask-zero right padding changes logits by at most
**0.000010609626770019531**, below the predeclared 1e-4 diagnostic tolerance.
That tolerance does not relax the golden relevance requirement.

| Original candidate | Batch logit | Padded singleton | Trimmed singleton | Trimmed minus padded |
|---|---:|---:|---:|---:|
| 0 | -1.2435117960 | -1.2435117960 | -1.2435109615 | 8.344650269e-07 |
| 1 | 0.8965160847 | 0.8965160847 | 0.8965150118 | -1.072883606e-06 |
| 2 | 3.4540479183 | 3.4540479183 | 3.4540479183 | 0 |
| 3 | 5.9478149414 | 5.9478149414 | 5.9478077888 | -7.152557373e-06 |
| 4 | 1.5004557371 | 1.5004557371 | 1.5004663467 | 1.060962677e-05 |
| 5 | -3.9901907444 | -3.9901907444 | -3.9901919365 | -1.192092896e-06 |
| 6 | -2.6685779095 | -2.6685779095 | -2.6685755253 | 2.384185791e-06 |
| 7 | -2.0690903664 | -2.0690903664 | -2.0690875053 | 2.861022949e-06 |
| 8 | 2.9014940262 | 2.9014940262 | 2.9014873505 | -6.675720215e-06 |
| 9 | -3.1429781914 | -3.1429781914 | -3.1429808140 | -2.62260437e-06 |

All three groupings have identical original-index ranking:
**[3, 2, 8, 4, 1, 0, 7, 6, 9, 5]** — Saturn, Mars, Moon, Mercury, Venus, Jupiter,
Earth, Uranus, Pluto, Neptune. The required top remains **Mars index 2**.
Every grouping therefore **fails `synthetic_relevance_mismatch`**; the receipt
records `diagnostic_completed: true` together with `quality_passed: false`.

For this exact official-FP32 graph, runtime and fixture, ordinary batch grouping
and mask-zero right padding do not explain the wrong top answer. The large INT8
batch/singleton differences (previous maximum 2.37847 logits) are not reproduced
in FP32. This separates the observed grouping sensitivity from the shared wrong
ranking; it does not prove a particular quantization operation caused that
sensitivity, source ST/Torch behavior, high-level tokenizer parity, or the source
of the relevance failure. No golden label or qualification gate was changed.

Evidence: `official-fp32-grouping-v2/receipts/short-10--infer_only.json`,
`observations.jsonl` (23 bounded records: 21 completed calls plus two group
summaries), stage markers and `summary.json` with all raw outputs, per-row
comparisons and file hashes. Original preparation v1 remains unexecuted and
superseded. No further native work, high-level tokenizer retry, product edit or
activation is in progress.


## Official FP32 batch/padding preparation (before the completed diagnostic)

Root authorized preparation only of one fixed official-FP32 session comparing
(1) the original character-length-sorted batch of all ten cached rows, (2) all ten
rows separately with their exact 33-position padding, and (3) all ten rows
separately after removing only the right suffix whose attention mask is zero.
All real/special token IDs remain unchanged. Every original and trimmed input
row is hash-bound before execution; the Mars expected label stays index 2.

The ready plan is `official-fp32-grouping-v2/manifest.json`, canonical binding
`66d8586721ada0e8d260ca5886bd28039bfb019caa9889e029ba04e875b182d8`,
file SHA-256 `80242d448ab1d7fa2a25b751f5bed2eb687ea892d6cd4b1ef4f64598b38a509d`.
Worker `official_fp32_grouping_v2.py` SHA-256:
`76843bb33a147c58cbb82f58766a61b15d07546140e339ce26e3089870cd47cb`.
Version 1 was superseded **before execution** when static review caught a derived
sigmoid-reporting precision discrepancy. Version 2 uses the exact original
float32 sigmoid code; original model calls, raw-logit comparisons, inputs,
settings and limits were unchanged. Both preparation records remain preserved.

There are exactly **21 planned session calls**: one K10 batch plus twenty
singletons, retaining all ten candidates in both singleton groups. The provisional
3.4-second estimate uses the measured 0.637-second FP32 K10 inference, roughly
0.99 seconds of startup/non-inference work, and a 0.5-second per-call overhead
allowance. Singleton scaling is extrapolated, not measured. There is no automatic
reduction, fallback, larger retry, or continuation beyond one five-second unit.
A refusal stops execution and preserves completed bounded per-call observations.

One disposable worker/session will use the unchanged official FP32 external-data
assets, exact cached page, ORT 1.25.1 CPU/default ENABLE_ALL, one thread,
no arena/pattern cache, immutable fba868f supervisor/global admission and
512 MiB task / 640 MiB aggregate. It records raw logits, original-index rankings,
unchanged expected-top checks, input-row hashes, per-row batch/grouping/padding
differences and stage timing/RSS. Raw-logit comparison tolerance is fixed at 1e-4
for diagnosing invariance, not accepting the failed golden. Original-batch logits
will also be compared with the prior FP32 receipt. Small observations are fsynced
after each completed call so an interruption retains useful evidence.

The hypothesis is specifically FP32 sensitivity to batch grouping or masked
right-padding. This can distinguish such behavior from INT8-only dynamic
quantization sensitivity, but it cannot establish source ST/model behavior,
general tokenizer parity, or production correctness. No new tokenizer or
high-level-tokenizer retry is included. Preparation used stdlib/AST checks only;
no execution had occurred at preparation time; the subsequent single authorized
result is recorded above. Evidence: `official-fp32-grouping-v2/preparation-receipt.json`.


## Latest tokenizer parity attempt: memory refusal before encoding

Root released the native slot and authorized exactly the frozen
`highlevel-tokenizer-parity-v1` unit, canonical binding
`5f228e05c1b2b91b54d8251002f8c4656fb49423948ed11e8e5d233b1447aa10`.
It was executed once with the described offline/discovery/import/file guards,
immutable fba868f supervisor, global admission, 512 MiB task / 640 MiB aggregate
and one five-second deadline. **The supervisor refused `worker_memory_limit`
during high-level tokenizer construction. No token rows or parity results were
produced.** No inference, settings change, larger retry or additional attempt
followed. The native slot was released promptly after the refusal.

Elapsed time was **2.425528 s**. Peak sampled task RSS was **548,634,624 bytes
(523.22 MiB)**; aggregate was **576,503,808 bytes (549.80 MiB)**. The task limit,
not the aggregate or deadline, caused refusal. The sampled tripwire can observe
RSS above the configured cutoff before stopping the process; that observation
is not a raised allowance.

Stage markers show asset verification completed at 30,294,016 bytes RSS;
Transformers import then completed in **1.787591 s** at **77,561,856 bytes**.
The final marker is `before_highlevel_tokenizer_load` at the same RSS. There is
no `after_highlevel_tokenizer_load`, `before_encode`, or comparison marker. The
failure boundary is therefore inside `AutoTokenizer.from_pretrained` after its
imports, not an observed token mismatch or a completed tokenizer comparison.
The mandatory offline utility/discovery accommodations got past the initial
import boundary; they did not bypass the resource guard.

**This attempt proves no tokenization parity or difference.** The shared-path
quality failure remains unresolved; it must not be relabeled quantization loss,
source-model behavior, or correct high-level tokenization. Static input checks
and prior numerical/permutation evidence remain valid within their recorded
scope. The official FP32 and INT8 golden failures are unchanged.

Private evidence: `highlevel-tokenizer-parity-v1/receipt.json`, stage markers and
`summary.json` with file hashes; the frozen manifest/worker and preparation notes
are preserved. No product/configuration/activation changes were made.


## High-level tokenizer parity preparation (before the refused attempt)

The independent `reranker-input-audit.md` found no concrete static mapping bug,
but identified a real initialization-path gap between direct tokenizer JSON
loading and installed Transformers 5.6.2's XLM-R backend reconstruction. Root
therefore authorized preparation of one offline tokenizer-only discriminator.
No new inference is authorized or planned in this probe.

Private worker: `highlevel_tokenizer_parity.py`; frozen manifest:
`highlevel-tokenizer-parity-v1/manifest.json`. Canonical manifest binding:
`5f228e05c1b2b91b54d8251002f8c4656fb49423948ed11e8e5d233b1447aa10`;
manifest file SHA-256:
`cd7a3316ca0cc0590f2d20f47138894e340d5b0100e04dd837ffea03a89093a7`;
worker SHA-256:
`ee94ce7742aa39df9c7a0befb5157a06e4757a321461d7040bf448e2e3d14e66`.
The expected page canonical hash is
`cf395a969972e7c74194e7bd0a455640dc4abc555289b1af20076115b4377bfe`.
Original tokenizer receipt file SHA-256 is
`dd31c52aa4199a1da4a546e554feb4e56b5cb571dd221eb265952f4b3edc60cc`.

The single worker will load `AutoTokenizer.from_pretrained` from the exact local
BAAI snapshot at `2cfc18c9415c912f9d8155881c133215df768a70`, with
`local_files_only=True`, `trust_remote_code=False`, no tensor-return option,
right padding/right longest-first truncation, maximum 512 and the same ten
original query/document pairs. IDs and attention masks must equal the cached
10-by-33 page per original row. Effective type IDs and sequence IDs are recorded
and compared with explicit official-template expectations (all type IDs zero;
query/document sequence IDs 0/1; special/pad positions None). Those metadata
expectations are **statically derived**: the original cached receipt did not
record runtime type/sequence IDs. The worker records effective tokenizer class,
small configuration fields, stage RSS markers, timing and per-row mismatches.

Installed Transformers 5.6.2's `is_torch_available()` does not consult USE_TORCH;
therefore root explicitly authorized a diagnostic-only absent-framework discovery
filter as well as an independent hard import deny. The frozen filtered/denied
root list is `flax`, `gguf`, `jax`, `jaxlib`, `mlx`, `onnx`, `onnxruntime`,
`optimum`, `safetensors`, `sentence_transformers`, `tensorflow`, `torch`.
Concrete Transformers model implementations and `transformers.modeling_utils`
are separately denied. This is **installed-tokenizer parity with optional
frameworks absent**, not source ST/model behavior or a tokenizer implementation
change. USE_TORCH/USE_TF/USE_FLAX remain 0; HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE
remain 1, with telemetry and tokenizer parallelism disabled.

Mandatory offline HTTP-client dependencies and tokenizer utilities
`transformers.modeling_gguf_pytorch_utils` / `transformers.integrations.ggml` may
import; root expressly distinguished utility import from model/network execution.
All socket audit events, child-process actions and model-weight file opens are
blocked independently. The only allowed `.model` data file is the exact pinned
SentencePiece tokenizer artifact. No model weight, download, provider or real
framework execution is permitted. The manifest binds tokenizer/config/source
files, original page, package versions and immutable fba868f supervisor hashes.

The resource/admission contract remains one five-second total unit, 512 MiB task,
640 MiB aggregate, global admission and pressure/descendant supervision; a failure
or refusal gets a receipt and no automatic retry. Worker syntax, fixed metadata
shape and manifest/script/page bindings were checked using stdlib only. The
native slot was requested and remains unassigned at preparation time. At preparation time no high-level tokenizer runtime, inference, product edit
or activation had occurred. The subsequent refused attempt is recorded above.
Preparation evidence: `highlevel-tokenizer-parity-v1/preparation-receipt.json`.


## Latest result: official FP32 fits short K10 but also fails the unchanged relevance gate

After Task 2c released all native children, root authorized exactly the frozen
`official-fp32-baseline-v1` one-unit baseline. It executed once with the existing
cached official short-K10 token page, unchanged expected Mars index 2, immutable
fba868f supervisor, CPU ORT 1.25.1/default ENABLE_ALL, one thread, sequential
execution, no arena/pattern cache, 512 MiB task / 640 MiB aggregate and one shared
five-second deadline. **Runtime completed within the envelope; the quality gate
failed with `synthetic_relevance_mismatch`.** No settings/cap/model retry followed.
The native slot was released immediately after inspecting the receipt.

| Measurement | Result |
|---|---:|
| Total supervised unit elapsed | 1.625612 s |
| Peak sampled task RSS | 439,812,096 bytes / 419.44 MiB |
| Peak sampled aggregate RSS | 457,801,728 bytes / 436.59 MiB |
| Streamed model/data verification | 0.521860 s |
| NumPy/ORT import | 0.105624 s |
| Session construction | 0.232274 s |
| K10 inference | 0.637044 s |

All before/after stage markers are retained. Worker RSS was 53,067,776 bytes
before session construction, 403,931,136 after it and 424,968,192 after inference.
The supervisor's independent samples supplied the higher reported peak above.
These remain sampled RSS tripwires; brief unobserved peaks are possible. There
was no admission, pressure, memory or deadline refusal and no admission retry.

| Candidate | Official FP32 raw logit | FP32 sigmoid | FP32 rank | Prior INT8 rank |
|---|---:|---:|---:|---:|
| 3 — Saturn's rings | 5.9478149414 | 0.9973952770 | 1 | 1 |
| 2 — Mars, explicit Red Planet answer | 3.4540479183 | 0.9693515897 | 2 | 3 |
| 8 — Moon and impact craters | 2.9014940262 | 0.9479202628 | 3 | 2 |
| 4 — Mercury nearest the Sun | 1.5004557371 | 0.8176423907 | 4 | 6 |
| 1 — Venus as Earth's twin | 0.8965160847 | 0.7102330327 | 5 | 7 |
| 0 — Jupiter and Great Red Spot | -1.2435117960 | 0.2238252908 | 6 | 5 |
| 7 — Earth and oceans | -2.0690903664 | 0.1121375784 | 7 | 4 |
| 6 — Uranus rotates on its side | -2.6685779095 | 0.0648531690 | 8 | 8 |
| 9 — Pluto in the Kuiper belt | -3.1429781914 | 0.0413688496 | 9 | 10 |
| 5 — Neptune and winds | -3.9901907444 | 0.0181602892 | 10 | 9 |

The official FP32 weights were proven exact against the cached source, so this is
an independent official FP32 export reference rather than a dequantized INT8
approximation. Both exports nevertheless choose the same wrong top candidate
on the same tokens/runtime path. The failure is therefore **not unique to INT8**,
and the observed wrong top cannot responsibly be attributed solely to quantization.
This does not establish that quantization preserves scores/rankings (it changes
both here), that the original ST/Torch path would produce these outputs, or that
tokenizer/export/runtime semantics are fully qualified. The common diagnostic
input/runtime path remains part of the unresolved boundary. Static token/index
checks and the earlier exact permutation diagnostic narrow that boundary but do
not resolve it. The expected Mars answer and relevance failure remain unchanged.

This result demonstrates that external-data **official FP32** short-K10 inference
can fit the current envelope, without loading a resident 1 GB Torch model. It is
not production selection, complete pipeline qualification, K20 qualification,
full-512 qualification, or permission to weaken the golden relevance expectation.
The original INT8 runtime qualification still has 4 passed, 1 failed and 13
unattempted units. This separate baseline adds a resource-success/quality-failure
receipt and no production configuration or activation change.

Exact baseline canonical manifest binding:
`08a005122e0277f5db1f8bae2ac133d3b27839ba418f02db3ebf0024562096a7`.
Private evidence: `official-fp32-baseline-v1/receipts/short-10--infer_only.json`,
`stage-markers.jsonl` and `summary.json`, including full FP32/INT8 scores and a
file-hash inventory. Original refusals and all successful provenance receipts
remain preserved. No further native experiment is in progress.


## Shared semantics still requiring independent review

The exact private worker paths are `external_runtime_probe.py` (`tokenize`,
`validate_page`, and INT8 `infer`), `official_fp32_baseline.py` (FP32 `infer`),
and `quality_batch_probe.py` (order/grouping diagnostic), all under the private
model directory defined below. Tokenizer settings and fixtures are frozen in
`external-runtime-probes-v1/manifest.json`; the original cached K10 page is
`external-runtime-probes-v1/receipts/short-10--tokenize_only.json` at `result.page`.
The FP32 manifest is `official-fp32-baseline-v1/manifest.json`; its adopted token
receipt links/hash-binds the original page. No retokenization happened for FP32.

- **Special-token template and pair handling:** static checks found the expected
  `<s> query </s></s> document </s>` IDs and decoded the exact fixture text.
  Direct `tokenizers.Tokenizer` JSON loading has not been runtime-compared against
  installed ST/Transformers `AutoTokenizer` initialization and its effective
  configuration. Template inspection is not complete tokenizer parity proof.
- **Sequence assignments:** cached pages retain only `input_ids` and
  `attention_mask`; `sequence_ids` and `type_ids` were not emitted. Segment
  membership was inferred from the known template and decoded text, not directly
  qualified against the high-level tokenizer. The ONNX graph accepts no
  `token_type_ids` input; internal token-type handling remains an export-semantic
  review item. Full-window truncation semantics remain untested.
- **Attention masks and positions:** every cached row has verified contiguous
  valid-token ones, then right-pad zeros with pad ID 1. The short K10 page has
  shape 10 by 33. Static position/mask connections were inspected; no layer-level
  ST-vs-ONNX mask/position parity measurement was performed.
- **Input dtype/shape and output indexing:** both scorers construct NumPy int64
  IDs/masks and check the runtime input signature, finite float32 `(K,1)` logits,
  and candidate restoration. Three K10 permutations produced exactly identical
  restored INT8 logits and reproduced the first failure, strongly excluding the
  ordinary permutation/restoration bug for this fixture. This does not qualify
  every possible batching or export shape path. Sigmoid is monotone and cannot
  explain which raw-logit candidate ranks first.
- **Export/runtime optimization:** weights match the official source exactly for
  FP32, but official PyTorch-2.0.1 export semantics and ORT-1.25.1 default ENABLE_ALL
  execution have not been compared with the installed ST/Torch path or an
  independent evaluator. Both measured references share cached tokens and runtime
  settings. No optimization ablation or layer-output comparison was authorized.

These gaps prevent assigning the common-path relevance failure to source-model
behavior, tokenizer correctness, quantization alone, or a particular runtime
operation. The failed golden remains intact. Native execution is stopped and the
slot returned for independent read-only review.

## Official FP32 reference preparation (before the baseline execution)

Root authorized bounded acquisition and preparation of a trusted FP32 reference.
The [official repository metadata at the exact cached source revision](https://huggingface.co/api/models/BAAI/bge-reranker-base/tree/2cfc18c9415c912f9d8155881c133215df768a70/onnx?expand=true)
lists `onnx/model.onnx`, **1,112,459,588 bytes**, LFS SHA-256
`15b9a8c3da82eddf263df571281166e00e9308fe19d077084b642ebfcaf06d2b`.
Exact acquisition URL:
`https://huggingface.co/BAAI/bge-reranker-base/resolve/2cfc18c9415c912f9d8155881c133215df768a70/onnx/model.onnx`.
The pinned model README also documents the official ONNX artifact. Its example
is not accepted as proof of FP32 parity: both displayed score computations call
the ONNX object. The byte comparisons below supply the weight evidence.

Acquisition used only stdlib HTTP/file streaming, at most 1 MiB per read, a
180-second alarm, private resumable staging and an atomic rename after exact
size/SHA verification. It completed without resume/retry in **96.534359 s** at
**33,816,576 bytes (32.25 MiB)** process peak. This separately authorized download
deadline is not an inference-budget increase. No model/framework import occurred.

A fixed stdlib wire inspection found **1,274 nodes, 201 FLOAT initializers,
opset 11, producer PyTorch 2.0.1**, inputs `input_ids` and `attention_mask`, and
output `logits`. The model remains the official base reranker, with no substituted
weights. All **201 learned tensors** were then byte-compared against the immutable
cached official safetensors: **129 identity layouts and 72 transposed matrices**
mapped through connected named attention/feed-forward MatMul nodes. Classifier
Gemm tensors remain direct with `transB=1`. All **1,112,177,668 learned-weight
bytes match exactly, with zero tolerance**. The only absent source tensor is the
nonlearned `roberta.embeddings.position_ids` buffer; the exported dynamic
non-pad-mask/CumSum position branch is retained. The already successful source
file hash/position-buffer proofs were reused with unchanged file identity, not
rerun. This is weight provenance verification, not a new inference-quality claim.

The comparison plan was frozen before execution with one five-second alarm per
tensor, at most 1 MiB read buffers and 64-row transpose tiles. All 201 receipts
passed: 3.345684 s total, 0.580311 s maximum unit, **24,100,864 bytes (22.98 MiB)**
process peak. No NumPy, tokenizer, ORT, Torch or other model runtime was imported.
Each tensor's exact-byte receipt and hash is retained. Manifest canonical binding:
`a96af64f07f90845396164651bbfe182205acf4239c5b0cc0da7c149b9778b4d`.

The fixed external-data transformation subsequently verified exact payloads of
all 201 initializers, exact bytes of all 1,274 nodes, unchanged other graph/model
fields and validated relative `weights.bin` locations, 16 KiB alignment and
nonoverlapping in-file ranges. No quantization or graph operation changed.
Preparation used 1 MiB buffers, completed in 3.346857 s at **26,443,776 bytes
(25.22 MiB)** peak, and published private 0700 directory / 0400 files atomically.
A separately bounded 30-second stdlib preparation alarm did not change the fixed
five-second runtime deadline.

| External artifact | Bytes | SHA-256 |
|---|---:|---|
| `official-fp32-external-v1/model.onnx` | 293,944 | `57cb6e14e863db46138e3a183866f44212d6cd6771e5c626c39231a20238a9ad` |
| `official-fp32-external-v1/weights.bin` | 1,113,767,936 | `e347d8faf7a0332e97d8d2b02297f6d1031ed7a18160632b7aad008081e5b043` |

`official-fp32-baseline-v1` freezes exactly **one short-K10 inference-only unit**
on the existing official cached token page. The expected answer stays Mars at
index 2; all ten candidates and existing character-length sorting/restoration
remain. ORT 1.25.1 CPU, default ENABLE_ALL optimization, one thread, sequential
execution, no arena/pattern cache, immutable fba868f supervisor, admission/pressure
checks, 512 MiB task / 640 MiB aggregate and one five-second deadline are unchanged.
Both model/data hashes and derivation/equivalence receipts are verified inside
the supervised request. Asset preparation does not prove that FP32 startup will
fit: mapped weights may still be copied or made resident during optimization.
There will be no automatic settings change or larger retry on refusal.

Canonical manifest binding:
`08a005122e0277f5db1f8bae2ac133d3b27839ba418f02db3ebf0024562096a7`;
manifest file SHA-256 including newline:
`c0696754d33facd613ca4c6a3556cdbae78e8403545342159d641a4c2fd22a02`;
worker SHA-256:
`97395732d0ffb94635b6f85e669d00fd0e454dfb1a2674cf6b1fdb04d26f0c60`.
At preparation time the root was asked to allocate the native slot and no FP32
inference had run. The later single authorized result is recorded above.
Evidence inventory is `official-fp32-baseline-v1/preparation-receipt.json`, with
all source, byte-comparison, transformation and probe manifests retained in the
private model directory. Production configuration and activation remain unchanged.


## Latest diagnosis: permutation is exact; batch grouping changes scores but does not fix relevance

Using the systematic-debugging skill, the fixed expected answer remains Mars,
original candidate index 2. No golden label, model, tokenizer, graph setting,
layout, resource ceiling or production code was changed. Static investigation
found no fixture or obvious input/output mapping defect:

- Each of the ten cached token rows decodes through the official vocabulary to
  its exact question and document at the original candidate index. The query is
  first, the document second; the official XLM-R pair template and right-padding
  IDs/masks are present. All rows have length 33, so truncation is inactive here.
- Installed ST 5.4.1 passes text pairs through `InputFormatter`, defaults to
  padding and longest-first truncation, sorts by summed character length, and
  restores scores with the inverse permutation. The diagnostic assignment is
  algebraically equivalent; 21 static permutation checks passed. This is source
  comparison, not full runtime tokenizer parity qualification.
- The Mars row, including attention mask, is exactly identical between the
  earlier single-pair probe and cached K10 page. Position IDs derive from the
  non-pad mask/CumSum path previously checked. All 12 attention layers receive
  `(1 - mask) * -3.4028234663852886e38` before axis-3 Softmax, with constants read
  directly from the frozen protobuf. This verifies connected graph structure,
  not all runtime graph semantics.

The root then authorized one fixed diagnostic wave. The predeclared hypothesis
was that batch composition affects model outputs independently of our candidate
restoration. `quality-batch-probes-v1/manifest.json` canonical-content binding is
`128be8f77f44c664682dcb96d606e125f28369dc757bad44525ecf500e347265`;
the file SHA-256 (including its trailing newline) is
`8116f5515c3ca119c1ee10ab40f956079e38bd9fa428d0860c3e23d1c95eca89`;
worker SHA-256 is
`e20c6d69c37e0b7c99acb77ca897f4194ed4a376da5f5237e48a86882770c51f`.
One disposable session performed length-sorted, identity and reversed K10 batches,
then each of all ten unchanged cached rows individually. Singleton rows retained
all original padding and masks; this did not reduce the candidate set or propose
a production batching change. Comparison tolerance was predeclared as 1e-4 raw
logit solely for permutation diagnosis, not ranking acceptance.

The immutable fba868f supervisor, global admission/pressure checks, 512 MiB task,
640 MiB aggregate and one five-second deadline were unchanged. Execution completed
in **1.308272 s**, sampled task peak **195,280,896 bytes (186.23 MiB)** and aggregate
**223,297,536 bytes (212.95 MiB)**. Session loading took 0.188813 s and all 13
session calls together 0.704650 s. The task memory numbers are sampled tripwires,
not a guarantee against every transient peak. There was no refusal or retry;
the root was notified immediately before execution and the slot released after
reading the result.

| Grouping | Top three original candidate indices | Mars raw logit | Maximum absolute difference from length-sorted K10 |
|---|---|---:|---:|
| Length-sorted K10 | 3 Saturn, 8 Moon, 2 Mars | 3.2183523178 | 0 |
| Identity K10 | 3 Saturn, 8 Moon, 2 Mars | 3.2183523178 | **0 exactly** |
| Reversed K10, restored | 3 Saturn, 8 Moon, 2 Mars | 3.2183523178 | **0 exactly** |
| All ten separately, unchanged token rows | 8 Moon, 2 Mars, 3 Saturn | 3.7215774059 | 2.3784720898 |

Length-sorted logits also reproduce the prior failed receipt **exactly**. The
singleton Mars logit reproduces the earlier one-pair result exactly. This rules
out our score-restoration/permutation logic as the explanation for this fixture
and establishes batch-composition sensitivity. **Every grouping still fails the
unchanged relevance expectation**; singleton execution is not a demonstrated fix.
The diagnostic receipt says `status: ok` only because the diagnostic completed;
its separate `quality_passed: false` must not be read as model qualification.

The graph contains 50 DynamicQuantizeLinear nodes, beginning at embedding
LayerNorm output. ONNX specifies a scalar activation scale/zero point derived
from the tensor's minimum/maximum, so changed batch composition can change
quantization even with identical rows. This is a plausible mechanism for the
observed grouping sensitivity, **not proof that quantization causes the wrong
ranking**, nor proof that the original FP32 model would pass this fixture.
Primary reference: [ONNX DynamicQuantizeLinear semantics](https://onnx.ai/onnx/operators/onnx__DynamicQuantizeLinear.html).

A trusted same-source FP32 reference is still needed to distinguish source-model
behavior from export/quantization/runtime effects. The minimal proposed next
reference is a pinned FP32 ONNX graph with external tensor data, validated against
the already cached official safetensors, using these exact cached rows and the
same 512/640 MiB/five-second supervision. FP32 external-data startup might still
refuse because mapping is not a resident-memory guarantee; feasibility is not
claimed. No FP32 download, model preparation or execution is authorized or done
in this wave, and no larger cap or resident Torch baseline is proposed.

Evidence is retained under the private model directory in
`quality-static-audit.json`, `quality-batch-probes-v1/manifest.json`,
`quality-batch-probes-v1/receipts/short-10--infer_only.json`, stage markers and
`quality-batch-probes-v1/summary.json` (hash-bound evidence inventory plus all raw
outputs). The original runtime qualification remains **4 passed, 1 failed,
13 unattempted**. This diagnostic adds evidence, not qualification credit.


## Latest continuation: short combined passed; ten-pair relevance check failed

The next authorized wave froze `external-runtime-probes-v1/manifest.json`,
SHA-256 `c0a19d97a74d93669e2def1c256c39eaae7425622ec53477b5a4b881751b3cae`,
with the original six scenarios/18-unit plan and unchanged limits, runtime
settings, tokenizer and configured maximum K=20. The verified external-data
layout was the sole model-representation change from the original plan.
Matching short-one-pair tokenizer and external-data inference receipts were
explicitly reused with source receipt/manifest hashes; they were not rerun.

Three new units executed before the frozen failure gate stopped the wave:

| Unit | Outcome | Total elapsed | Peak sampled task / aggregate RSS |
|---|---|---:|---|
| Short 1, combined tokenize + infer | Passed under one shared five-second deadline | 1.104398 s | 454,000,640 / 482,721,792 bytes (432.97 / 460.36 MiB) |
| Short 10, tokenizer only | Passed | 0.449514 s | 453,738,496 / 482,492,416 bytes (432.72 / 460.14 MiB) |
| Short 10, inference only | Computed scores within resources; **failed synthetic relevance** | 0.614208 s | 194,428,928 / 223,264,768 bytes (185.42 / 212.92 MiB) |

The shared short-one-pair deadline covered sequential workers, including startup
and streamed artifact verification. That is a successful **reranker-only**
combined timing result, not the complete ordinary retrieval pipeline. There
were no memory, deadline, pressure or admission refusals in this wave and no
admission retry. The native slot was released immediately on the quality failure.

The fixed question was “Which planet is known as the Red Planet?” Expected top
candidate was index 2, the explicit Mars answer. Actual order and outputs:

| Rank | Candidate | Logit | Sigmoid score |
|---|---|---:|---:|
| 1 | 3 — Saturn's rings | 5.9034309387 | 0.9972774386 |
| 2 | 8 — Moon and impact craters | 3.8713264465 | 0.9795942903 |
| 3 | 2 — Mars is known as the Red Planet | 3.2183523178 | 0.9615191221 |
| 4 | 7 — Earth and oceans | 0.8808125257 | 0.7069905996 |
| 5 | 0 — Jupiter and Great Red Spot | -0.5319720507 | 0.3700570762 |
| 6 | 4 — Mercury nearest the Sun | -1.0214600563 | 0.2647430897 |
| 7 | 1 — Venus as Earth's twin | -1.3041328192 | 0.2134702802 |
| 8 | 6 — Uranus rotates on its side | -3.0992763042 | 0.0431371145 |
| 9 | 5 — Neptune and winds | -3.3847668171 | 0.0327749439 |
| 10 | 9 — Pluto in the Kuiper belt | -4.2735013962 | 0.0137414541 |

The failure is recorded as `synthetic_relevance_mismatch`. Its cause is **not yet
diagnosed**; these outputs alone do not distinguish quantization effects,
tokenizer behavior, graph/runtime behavior or a diagnostic ordering defect.
Do not dismiss the result as harmless because numeric weight derivation passed,
and do not attribute it to a particular model defect without further evidence.
The required relevance quality gate has not passed.

Effective progress is **4 passed units (2 reused), 1 failed, 13 unattempted**.
Unattempted cases are short-10 combined; all short-20 units; and every full-window
1/10/20 tokenizer, inference and combined unit. No configured candidate count was
reduced. No model, tokenizer, graph setting, memory limit or layout was changed
after the result in that qualification wave. The later authorized diagnostic is
recorded separately above.

Evidence: `external-runtime-probes-v1/summary.json`, all five effective receipts,
the explicit reuse bindings in the two adopted receipts, and stage markers.
Full raw logits, scores, documents and ranking are retained in the private
summary. The script and manifest remain frozen. **Current conclusion:** memory
startup and the short-one-pair combined deadline are demonstrated for this
representation, but reranking semantics remain unqualified because the first
multi-candidate sanity test failed. Product configuration and activation remain
unchanged.

## Latest result: same-weight external-data short-pair inference passed

Root authorized exactly one execution of the frozen
`external-startup-probes-v1` plan after Task 2b released the native slot. That
**single short-one-pair inference passed** with unchanged CPU ORT 1.25.1 settings,
default ENABLE_ALL graph optimization, one thread, no arena/pattern cache,
five-second deadline and 512/640 MiB limits. The verified graph/node/weight
equivalence receipt predates this run. No settings retry or additional scenario
was executed. Native slot released immediately afterward.

| Measurement | Result |
|---|---:|
| Pair count / pair tokens | 1 / 33 |
| Total supervised unit elapsed | 0.609955 s |
| Streamed model plus external-data hash checking | 0.133277 s |
| NumPy/ORT import time | 0.130933 s |
| Session construction | 0.187022 s |
| Inference and bounded result processing | 0.022041 s |
| Worker phase total | 0.473273 s |
| Peak sampled task RSS | 175,603,712 bytes = 167.47 MiB |
| Peak sampled parent-plus-task RSS | 204,292,096 bytes = 194.83 MiB |
| Returned logit / sigmoid relevance score | 3.7215774059295654 / 0.9763758182525635 |

Stage markers now reach both formerly missing boundaries: worker RSS is
53,739,520 bytes immediately before session construction, 152,338,432 bytes
after construction, and 157,188,096 bytes after session execution. The unchanged
inline artifact had exceeded the task limit inside the same constructor. Since
the external-data graph and all initializer payloads were independently checked
as identical, and runtime settings/input page remained fixed, this result
supports the hypothesis that the **serialized storage layout** accounts for the
startup-memory difference. The evidence does not identify each internal ORT
allocation or prove which mapping/copy path executed.

Receipts, stage markers and `external-startup-probes-v1/summary.json` bind the run
to manifest `4403e023c8c5e347c1e9ede4789ce6dcf7157456c5c8a75c9ce197e25abedda4`,
the two external file hashes, the equivalence receipt and the immutable `fba868f`
supervisor. One fresh inference process ran; the OS file cache may have been warm.
No tokenizer was rerun: this experiment reused the previously successful official
tokenizer's bound synthetic token page.

**Updated recommendation:** this is now a concrete bounded same-weight reranker
candidate for continued qualification; the earlier inline-startup conflict has
been resolved for this one short-pair case through storage representation alone.
Retain the original refusals as evidence of why the original inline artifact is
unsuitable under this runtime profile. No new model, converter framework,
re-quantization, graph optimization setting or larger budget was required.

This result does **not** qualify the combined tokenizer/inference five-second
deadline, K=10 or K=20, full 512-token pair windows, multilingual token parity,
ranking quality against the original float32 baseline, or the full ordinary
exact+dense+KG+fusion+reranker+hydration pipeline. One candidate cannot establish
ranking quality. Production caps and configuration remain unchanged; no deployment
or activation was performed.

## Startup boundary localized; equivalent external-data artifact prepared

After the first instrumented attempt was refused before spawning anything, root
authorized one new admission attempt. `startup-probes-v2` preserved that separate
attempt and ran the original inline artifact with unchanged settings/caps. It
returned `worker_memory_limit` after 0.501308 seconds. Parent-sampled task RSS
reached 598,884,352 bytes (571.14 MiB), aggregate 627,900,416 bytes (598.81 MiB).
Sampled tripwires can overshoot between checks; these are observed values, not
larger authorized limits. The worker was terminated and the native slot released.

Bounded fsynced markers in `startup-probes-v2/stage-markers.jsonl` establish:

| Boundary | Worker RSS |
|---|---:|
| Before model-file validation | 28,884,992 bytes |
| After streamed model hash verification | 30,392,320 bytes |
| After NumPy import | 39,354,368 bytes |
| After ORT import | 53,379,072 bytes |
| Immediately before `InferenceSession` construction | 53,411,840 bytes |
| After session construction | Never reached |

The observed failure is therefore inside session construction, not ordinary
imports or streamed artifact hashing. This does not identify which internal
allocator/optimization creates the peak. The one tested hypothesis is that
inline protobuf initializer data incurs avoidable startup copies. Primary ONNX
external-data rules and ORT's file-mapping path support testing that storage
representation alone; no alternate quantization or model is involved.

While Task 2b held the native slot, stdlib-only
`externalize_fixed_artifact.py` prepared `external-data-v1/` without importing
ONNX, NumPy, ORT or another framework. It accepts only the pinned original model
hash and exact expected structure. Its reads are at most 1 MiB; a fixed
five-second alarm bounded preparation. Actual preparation took 0.802343 seconds
and peak process RSS was 27,082,752 bytes (25.83 MiB). This was bounded stdlib
preparation, not a native inference measurement or a guardian-supervised query.

The artifact was written privately and published by atomic directory rename only
after independent fresh wire parsing and verification. Directory permissions are
0700 and published files 0400. No original file changed. Relative location is
exactly `weights.bin`; every offset is aligned to the host's 16,384-byte pages,
nonnegative, nonoverlapping and within the verified data file. No absolute path,
parent traversal, symlink or unknown external-data key was introduced.

| Published artifact | Bytes | SHA-256 |
|---|---:|---|
| `external-data-v1/model.onnx` | 422,930 | `c1063d009adef0467aaffe3857407ef248cc029768c994e2805948943359f42a` |
| `external-data-v1/weights.bin` | 280,314,624 | `03ebb9a0c4dd39aeb83f556e3b2133cc1b15f131d3bd0bda91ba2ebe4cc2002a` |

`external-data-v1/equivalence-receipt.json`, SHA-256
`6ad2fd7b3ca4c3e8301333542decec582ffbc19a53401ad6931c67915986695b`,
was committed before any external-data runtime test. It records:

- All **1,204 node message payloads are byte-identical** to the pinned inline
  model. Every noninitializer GraphProto field and every non-graph ModelProto
  field is byte-identical. Only initializer storage descriptors and enclosing
  protobuf lengths changed; the whole GraphProto byte string necessarily differs.
- All **375 initializer names, shapes, data types and payloads** were checked.
  The 221 original `raw_data` payloads were copied unchanged to the aligned data
  file, with individual SHA-256 comparisons. The other 154 initializers use
  typed inline scalar fields; their complete serialized initializer messages
  and payload hashes remain identical. They were not re-encoded or quantized.
- No graph operation, attribute, constant value, bias, weight, scale or zero
  point was changed. Padding bytes between external tensor regions are storage
  alignment only. Model and data-file hashes are verified independently.

One external-data-only short-one-pair probe is prepared as
`external_startup_probe.py` / `external-startup-probes-v1/manifest.json`, manifest
SHA-256 `4403e023c8c5e347c1e9ede4789ce6dcf7157456c5c8a75c9ce197e25abedda4`.
It reuses the original successful token page and identical default graph
optimization, threads, arena/pattern settings, CPU provider and 512/640 MiB /
five-second limits, with the same stage markers. Both external files are hashed
inside the deadline. This preparation preceded the single successful experiment
recorded in the latest-result section above. Its scope remains this short case
only. Production selection and activation remain unchanged.

## Startup-boundary investigation: first instrumented admission refused

An explicitly authorized systematic-debugging follow-up prepared
`startup_probe.py` and `startup-probes-v1/manifest.json` with bounded fsynced
stage/RSS markers around artifact validation, NumPy import, ORT import, session
construction and session execution. It retained the original inline model,
short-one-pair token page, default graph optimization, all runtime settings,
512/640 MiB caps, five-second limit and immutable `fba868f` supervisor.

The first attempt returned **`memory_busy` at global admission**. No guardian or
worker was spawned, no marker was written and no native/model execution took
place. The receipt is preserved at
`startup-probes-v1/receipts/short-01--infer_only.json`; manifest SHA-256 is
`642454e9de6586f9ec49b13efb4c9b7ac6f1aded2bce162112bd7dcdd57c6b6f`.
The run stopped without automatic retry, and root was notified that the slot was
released. A subsequent read-only `lsof` check found no current lock holder;
nothing was unlocked, killed or paused. The startup allocation boundary therefore
remains unmeasured by this attempt.

Primary-source preparation for one storage-layout hypothesis is available:
[ONNX external-data documentation](https://onnx.ai/onnx/repo-docs/ExternalData.html)
defines unchanged raw tensor bytes addressed by relative file location, byte
offset and length, recommending page-aligned offsets for memory mapping.
[ORT 1.25.1 tensor loading source](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.25.1/onnxruntime/core/framework/tensorprotoutils.cc)
attempts file mapping for external data before a copy fallback. These support
investigating whether externalizing the identical initializer data avoids inline
protobuf startup copies. They do not prove that this is the observed cause or
that ORT optimization will fit the cap. No external-data model transformation or
external-data inference probe has yet been performed; obtain the intended
startup-boundary evidence first under coordinated admission.

## Latest runtime outcome: tokenizer passed; inference refused for task memory

The frozen `runtime-probes-v1` plan was executed after root assigned the native
slot. It used unchanged 512 MiB task / 640 MiB aggregate limits, five-second
unit deadlines, the immutable `fba868f` supervisor and the prepared tokenizer/
model/runtime settings. It **stopped at the second unit**, preserving both
receipts. No setting, batch size, tokenizer, model or limit was changed, and no
retry was performed. The native slot has been released.

| Actual unit | Outcome | Total elapsed | Parent-sampled task / aggregate peak |
|---|---|---:|---|
| `short-01--tokenize_only` | Passed, one 33-token pair | 0.490042 s | 453,246,976 / 481,918,976 bytes (432.25 / 459.59 MiB) |
| `short-01--infer_only` | `unavailable: worker_memory_limit` | 0.529750 s | 517,292,032 / 545,931,264 bytes (493.33 / 520.64 MiB) |

The refusal was returned by the independent guardian's task-memory check.
The parent's separately sampled maximum is below 512 MiB because the two
polling loops can observe different moments; it is **not** the actual crossing
peak or evidence that the cap was raised. The guard does not report its exact
crossing value. No total-memory, pressure, admission or time refusal was returned.

The tokenizer-only worker used the official pinned JSON with tokenizers 0.22.2.
It recorded 0.014454 s for asset validation, 0.015506 s for tokenizer import,
0.231664 s for tokenizer load and 0.002251 s for encoding. Worker phase time was
0.263876 s; the authoritative 0.490042 s unit duration also includes process and
supervisor overhead. This measures one short pair only, not all configured K
or a full 512-token pair.

The inference worker returned no final diagnostic frame or scores. Its phase is
known, but finer timings distinguishing import, graph parsing, session
optimization, allocation and actual inference were not captured before the
guardian refused it. Do not assert a specific internal allocation caused the
failure from these receipts alone. The serialized artifact's quantized Gather
layout and verified numeric weights do not prevent runtime loader/optimizer
memory overhead.

Of 18 planned units, **1 passed, 1 was refused, and 16 were not attempted**.
No combined tokenizer/inference deadline test, 10/20-pair scenario, full-window
scenario or ranking-quality test completed. The overall ordinary retrieval
pipeline was not run. Evidence is private `runtime-probes-v1/summary.json`,
`progress.json` and `receipts/short-01--{tokenize_only,infer_only}.json`, bound to
manifest `a8244fcc6c358369acabb13e29d7c7707282364f780474d4bc4dc51d9d3736d8`.

**Current recommendation:** this specific CPU ORT 1.25.1 configuration with
default graph optimization fails the existing memory qualification even for one
short pair. The numerically verified same-weight candidate remains useful
inactive preparation, but it is not safe to activate under this evidence. This
does not prove no compatible local representation can fit; a different loader
or explicit new bounded instrumentation experiment would need a separately
declared qualification plan. Do not silently remove the configured reranker,
substitute a model, increase caps or change settings and call the original plan
successful. Product code, configuration and activation remain unchanged.

## Historical preparation of runtime probes

Private `reranker_probe.py` and `runtime-probes-v1/manifest.json` were prepared for
an explicitly coordinated native slot. Preparation performed only stdlib
metadata inspection, artifact fingerprints, source inspection and AST parsing;
it did not import tokenizers, NumPy or ONNX Runtime and did not run these probes.

- Manifest SHA-256:
  `a8244fcc6c358369acabb13e29d7c7707282364f780474d4bc4dc51d9d3736d8`.
- Worker SHA-256:
  `072e196888bf42384da9b4654688946f7ddee3cf3154764edccfeb9d64d68f2a`.
- The supervisor is the private immutable `fba868f` bundle recorded below.
  Every worker uses its existing guardian-chain admission check; parent
  admission, interactive priority, pressure and descendant accounting remain in
  force. No global or product limits were changed.
- Six fixed synthetic scenarios: 1, 10 and 20 query/document pairs, each at short
  and full 512-token pair windows. The query asks which planet is known as the
  Red Planet; documents contain Mars plus clear astronomy distractors. Full-window
  inputs append fixed neutral filler after the initial fact. These are English
  resource/relevance sanity fixtures, not comprehensive multilingual quality
  acceptance queries; one pair cannot measure ranking quality.
- The frozen plan contains 18 units: tokenizer-only, inference-only and combined
  for each scenario. Every unit uses fresh disposable workers. It stops at the
  first actual refusal/failure, keeps its receipt and refuses automatic retries.
  It never switches graph settings, tokenizer, model, K or batching to force a
  pass. A first tokenizer refusal means inference is not launched.
- Each standalone unit has at most five seconds; **combined units have one
  absolute five-second deadline and one admission lease across both sequential
  workers**, including startup and artifact validation. They do not receive a
  fresh five seconds per phase. Task and aggregate RSS limits are 512/640 MiB.

Tokenizer-only workers load the **official** cached tokenizer JSON, SHA-256
`9eb652ac4e40cc093272bbbe0f55d521cf67570060227109b5cdc20945a4489e`,
with tokenizers 0.22.2. They preserve its normalizer/vocabulary/postprocessor,
add special tokens, use right-side longest-first pair truncation at 512 tokens,
right padding to the batch maximum, pad ID 1/type ID 0, and no input stripping
or lowercasing. This matches the inspected installed ST preprocessing defaults
(`padding=True`, `truncation="longest_first"`) and official model window/settings.
The pair template is `<s> A </s></s> B </s>`. Artifact hashes, special IDs,
padding masks and full-window length are checked. This uses no alternate
SentencePiece implementation; full token-ID parity against the installed wrapper
remains a separate behavioral qualification. NumPy/ORT and framework imports are
forbidden in this phase.

Inference-only workers consume bound token pages; they never load a tokenizer.
They use the numerically verified pinned artifact with **CPU ONNX Runtime 1.25.1**,
one intra/inter-op thread, sequential execution, no CPU arena and no memory
pattern cache. **Graph optimization remains ORT's default ENABLE_ALL**; it is
checked rather than changed. Every scenario is one batch of all 1/10/20 pairs,
matching the configured K bound and remaining below the legacy default batch32;
there is no automatic microbatch fallback. Input character-length sorting and
restoration match the current CrossEncoder path; raw logits, float32 sigmoid
scores, candidate order and expected winner are recorded. No ST, Transformers,
Torch, ONNX package, provider SDK, hidden download or external call is allowed.

Receipts will record supervisor total elapsed and sampled task/aggregate peaks,
plus asset checking, import, tokenizer load/encode, ORT session creation and
inference timings. Full model hash checking is streamed in 1 MiB reads and is
inside the unit deadline. Each process exits, so these are cold-process startup
measurements even if the OS file cache is warm. No claim of a cold disk cache is
made. The combined reranker probe still does **not** include dense embedding,
Lance/KG/fusion or final exact hydration, so success cannot by itself pass the
ordinary pipeline's five-second gate.

Execution, only after root assigns the native slot:

```sh
/Users/ladislavbihari/.echelon/venv/bin/python \
  ~/.castle/backups/durable-memory-20261024/relocation/reranker-models/280bcc27a84e0b898c251e06fddb25171bd9b101/reranker_probe.py run
```

If the tokenizer refuses under its current cap, retain that result and recommend
an explicit tokenizer-serialization/parity qualification; do not load another
model or silently switch tokenizer. Product code and activation remain unchanged.

## Latest outcome: numeric weight derivation passed; inference unqualified

All **204 predeclared audit units** now have successful hash-bound receipts:
66 original successes were preserved unchanged and 138 unfinished units were
completed after a minimal diagnostic serialization fix. No successful unit was
rerun. The final reduction checks manifest identity, every original work unit,
tensor element counts and vocabulary row coverage with no gaps/overlaps.

**Every one of 277,922,304 quantized values across 77 tensors reproduces exactly**
from the pinned official BAAI float32 weights with the frozen per-tensor recipe
and connected transpose/layout mapping. Integer mismatch count is zero; every
stored scale matches the computed float32 scale exactly (0 ULP difference,
within the predeclared 1 ULP tolerance); zero points match exactly; clipping
count is zero. All 124 unquantized parameter tensors also match source float32
bytes exactly. The remaining original position-ID buffer has the separately
validated input-derived branch explanation described below. Thus numeric
correspondence of all learned parameters is established, rather than inferred
from matching architecture or a publisher's model card.

The frozen recipe used signed symmetric INT8 ranges [-127,127] for matrices and
unsigned affine [0,255] for embeddings, including zero in extrema, float32 range
subtraction, float64 scale division stored as float32, float32 division by the
stored scale, nearest-even rounding, zero-point addition and clipping. The
integer mismatch tolerance was zero. The per-tensor reconstruction bound was
`scale / 2 + 8 * float32_epsilon * max(1, abs(source extrema))`; every tensor
passed. Aggregate reconstruction diagnostics:

| Measure | Result |
|---|---:|
| Maximum absolute reconstructed-weight error | 0.009845437481999397 |
| Weighted mean absolute error | 0.0020016672259289903 |
| Weighted RMS error | 0.0024550453879532684 |
| Quantized tensors / elements | 77 / 277,922,304 |
| Exactly unchanged tensors / bytes | 124 / 488,452 |
| Peak sampled task RSS | 77,070,336 bytes = 73.50 MiB |
| Peak sampled parent-plus-task RSS | 105,054,208 bytes = 100.19 MiB |
| Longest admitted unit | 0.6719 seconds |
| Sum of successful supervised unit times | 31.3896 seconds |
| Resumed-run wall time | 22.344 seconds |
| Resource/admission refusals | 0 |

These are **offline numeric audit measurements**, not model inference or a
five-second end-to-end query measurement. The original invalid-frame refusal is
retained in the evidence; it was a diagnostic output bug, not a cap violation.
The tiny supervised reproducer confirmed NumPy 2.4.4 returns `float32` for the
original error-bound expression and JSON raises `TypeError`. Explicit conversion
of the finite bound to Python `float` fixed serialization without altering the
numeric recipe, partitions, caps or tolerances. Its receipt is
`scalar-serialization-proof.json` (0.2266 seconds; under the same caps).

Resumption uses `numeric-manifest-v2.json`, SHA-256
`8ad3d8deb8b2eac01a89ed2bd6f37c660847ff6035e0be7669ab3e2f424ad73d`,
linked to the original manifest. The exact private supervisor bundle comes from
commit `fba868fe873e1ff208ebd9cd47ab5631fa943e27`; no mutable checkout files are
used by resumed workers. `resumed-supervisor.json` records these source hashes:

- `memory_runtime.py`:
  `aa46236e1036427c5d07c023c44935e2899d0880ff4447562f5982d5df46a2bd`
- `brain_reader_guardian.py`:
  `ff5ed978bc2deffe0b57d0630e4f43d9a0af0bc6ae3f18843fea79b879be1002`
- `semantic_worker.py` (admission helper only):
  `d7de3d9e7e1cd8cd1ef52803235af6b7b35cdb2b7ec79683d1d69b58873f9b5d`

The **first run must not be attributed to that clean commit**. It used the active
checkout. Its observation file records dirty/source-file hashes captured during
the run: memory runtime `2534ce16ff00ebacd6ba96d174c9466ddfd5b04fd873bf71a3c8ff1a83954112`
and guardian `05ab6bf3a2165e8aafb08739ad154053c3f9bd714b9b5c47d3f9ec6de372c86b`.
Those observations are not an immutable pre-run bundle or proof of every earlier
spawned file version. The resumed run removes that attribution ambiguity.

Final private evidence: `numeric-summary.json`,
`numeric-per-tensor-summary.json`, `numeric-receipts/`, `numeric-receipts-v2/`,
both manifests, `numeric-resume-proof.json`, `resumed-supervisor.json` and
`summarize_numeric_audit.py`. Receipts include source/target full hashes, exact
unit ranges, per-range hashes, mapping/layout, errors and resource measurements;
they do not emit weight arrays.

**Recommendation now:** retain this pinned artifact as a numerically verified
same-weight quantized candidate for the next bounded qualification. No local
full-model converter is needed. Complete graph semantics, all exporter constants,
tokenizer ID parity, ONNX session startup/optimization peak RSS, CPU latency,
cross-encoder score behavior and ranking quality remain unqualified. No ONNX,
Torch, tokenizer or model inference was run. The native slot is released;
product code, model selection, production caps and activation remain unchanged.

## Historical numeric qualification status — first supervised run

The authorized numeric audit froze `numeric-manifest.json` before execution:
204 work units, SHA-256
`1e03957ab09684b5959ff710883ae35c25dcefa27aa1492a3aa6ca9e181231f4`.
`numeric_audit.py` uses the existing global admission, interactive priority,
pressure refusal and descendant guardian from
`/Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse`. Parent supervisor
code was imported once at runner start. Guardian and worker-admission files were
read per unit; `numeric-supervisor-observation.json` records their hashes/mtimes
observed during the run (not a pre-run snapshot). The parent coordinated a hold
on those two files while this run was active.

**66 of 204 units passed, then the runner stopped** at `tensor-001` with
`worker_invalid_frame`. No larger retry was made and the native slot was released.
Peak observed task RSS was 65,912,832 bytes (62.86 MiB), aggregate 86,261,760 bytes
(82.27 MiB), longest admitted unit 0.6719 seconds, and summed supervision time
9.5479 seconds. Every operation retained a fixed five-second deadline and
512/640 MiB tripwires. No pressure, admission, memory-limit or deadline refusal
was observed; the invalid-frame refusal is retained explicitly.

Successful hash-bound receipts establish:

- The cached official 1,112,206,140-byte safetensors file SHA-256 is
  `ced967c45fd1902eb92716c9ceeca7c95a936770ea9db611f5a841b926e33fbd`, matching
  the pinned official repository's LFS metadata. It was streamed, not loaded.
- The prepared INT8 model's full hash still matches the acquisition receipt.
- All **124 unchanged parameter tensors**, totaling **488,452 bytes**, match
  official source float32 bytes exactly. Per-tensor hashes are in the receipt.
- The original position-ID buffer equals I64 arange(514). The connected ONNX
  input-ID position branch has the expected padding constant, cumsum axis,
  casts, masking and Gather binding. Four padding patterns reproduce the expected
  padding-aware positions through NumPy arithmetic; the token-type buffer is
  all zero. This validates that branch's structural/arithmetic explanation,
  without executing ONNX or proving unrelated graph branches.
- All **62 predeclared vocabulary extrema shards** completed, covering every
  official vocabulary weight. These are range/hash results, not quantized-byte
  comparisons.

No quantized comparison has a successful receipt yet. Source inspection suggests
the comparison response's `error_bound` may be a NumPy float32 passed to the
stdlib JSON encoder outside the exception wrapper. That is a diagnostic-code
hypothesis awaiting a small supervised reproducer, not a model/provenance
failure established by evidence. Preserve `numeric-manifest.json`, the failed
receipt and `numeric-summary-partial.json`; resume only through a recorded
diagnostic fix under the same limits, without rerunning successful comparisons.

## Authorized follow-up asset inspection

Exact pinned acquisition URL verified from the repository revision and file path:
`https://huggingface.co/Xenova/bge-reranker-base/resolve/280bcc27a84e0b898c251e06fddb25171bd9b101/onnx/model_int8.onnx`.
Expected bytes: `278825308`; expected SHA-256:
`2059d8ef0b6e935b4845e11b38c9af9e9e2e7b91f69fc99efe03254e0a7da8d3`.
The parent authorized private bounded acquisition and protobuf metadata
inspection only, with no model/native runtime execution or activation. Results
below supersede the initial audit's statement that no payload was obtained.

### Actual acquisition and structural results

The pinned file was acquired in **24.323 seconds** with 1 MiB streaming reads,
a 60-second whole-operation alarm and a 30-second socket timeout. Exact length
and SHA-256 matched before atomic temporary-file rename. No 1 GB artifact was
downloaded. Private evidence lives under:
`~/.castle/backups/durable-memory-20261024/relocation/reranker-models/280bcc27a84e0b898c251e06fddb25171bd9b101/`.

- `acquisition-receipt.json`: pinned URL, validated size/hash, timing and limits.
- `inspect_protobuf.py`: stdlib-only wire reader. It seeks over initializer
  payloads, reads metadata fields bounded to 64 KiB and rejects invalid field
  bounds; no `onnx`, NumPy, Torch, tokenizers or ORT import.
- `structural-inspection.json`: all 1,204 nodes, 375 initializer names, shapes,
  data types and raw byte offsets/lengths, graph input/output names, opsets and
  metadata. Repeated metadata inspection took 0.0393 seconds; process peak RSS
  was 18,563,072 bytes (17.70 MiB, `resource.getrusage` on macOS). This is the
  metadata inspector's memory, **not inference RSS**.
- `structural-sanity.json`: no mismatched raw initializer length versus
  shape/type, missing input reference at a node, or duplicate node output found.
  These are wire-level sanity checks, not an ONNX checker or runtime proof.
- `tokenizer-config-fingerprints.json`: official-cache hashes compared with
  pinned publisher metadata, and small JSON configuration differences.

The graph declares opset 11, inputs `input_ids` and `attention_mask`, and output
`logits`. Producer metadata is only `onnx.quantize` / `0.1.0`; `onnx.infer` is
`onnxruntime.quant`. It provides no exact converter/ORT version or BAAI revision.
All operators are in the standard empty domain; no subgraph attributes were
found. Initializer types are FLOAT=209, INT64=11, INT32=1, UINT8=6, INT8=148.
All initializers are inline; no external-data references or EXTERNAL locations
were present. The serialized graph therefore offers no external-data mmap
mechanism by itself; runtime loading/copies remain unmeasured.

Observed operator counts:

| Operator | Count | Operator | Count |
|---|---:|---|---:|
| Add | 175 | Cast | 77 |
| Concat | 49 | CumSum | 1 |
| DequantizeLinear | 3 | Div | 49 |
| DynamicQuantizeLinear | 50 | Equal | 2 |
| Erf | 12 | Expand | 1 |
| Gather | 102 | MatMul | 24 |
| MatMulInteger | 74 | Mul | 199 |
| Not | 1 | Pow | 25 |
| ReduceMean | 50 | Reshape | 48 |
| Shape | 49 | Slice | 1 |
| Softmax | 12 | Sqrt | 25 |
| Sub | 26 | Tanh | 1 |
| Transpose | 48 | Unsqueeze | 99 |
| Where | 1 | | |

The large vocabulary initializer is explicitly
`roberta.embeddings.word_embeddings.weight_quantized`, **UINT8** `[250002,768]`,
192,001,536 raw bytes at file offset 802,918. Despite the `model_int8` filename,
the vocabulary table is unsigned 8-bit; transformer matrices include signed
INT8. The vocabulary node takes this quantized initializer and `input_ids`
directly into Gather, then DequantizeLinear receives the **Gather output** and
scalar float scale / UINT8 zero point. The output goes through embedding sums.
This confirms the useful serialized graph ordering; it does not assume that an
actual ORT session will retain the same allocations after optimization.
There is no full vocabulary-table DequantizeLinear in the inspected graph.

Official cached `sentencepiece.bpe.model` SHA-256
`cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865`
matches the pinned Xenova LFS hash. `special_tokens_map.json` and
`tokenizer_config.json` match Git blob fingerprints exactly and parsed JSON is
identical. `config.json` differs only in inspected JSON values for `_name_or_path`,
`transformers_version` and removal of `torch_dtype`; architecture and dimensions
match. `tokenizer.json` does **not** match: official cached size 17,098,107 and
SHA-256 `9eb652ac4e40cc093272bbbe0f55d521cf67570060227109b5cdc20945a4489e`,
publisher size 17,098,079 and SHA-256
`48564c5c7d3fa64d85d95e65414a542385f88b0f128fd8d4163fd7a57f2be05c`.
Its content difference was not inspected. Preserve the official tokenizer rather
than assume these JSON files are interchangeable. Matching SentencePiece bytes
does not prove a different runtime adapter produces identical token IDs.

**At this historical structural-inspection stage:** no tensor values had been compared to the official
safetensors, no quantization recipe has been reproduced, no graph semantic
equivalence has been established, and no tokenizer/model inference, native
runtime import or memory/latency benchmark has run. The now-verified prepared
artifact and Gather ordering make bounded further qualification more credible;
they do not qualify model identity, ranking quality, or the five-second pipeline.

### Follow-up initializer mapping, without native execution

`map_initializers.py` and `initializer-mapping.json` now record an explicit
artifact-specific map, source safetensors byte ranges, target ONNX byte ranges,
scale/zero-point names and values, and the consuming node names. The script uses
only stdlib metadata parsing with a five-second alarm. It does not compare weight
arrays, execute the graph or import NumPy. All scale tensors are scalar, so this
artifact uses **per-tensor** weight quantization in the mapped paths.

| Group | Source/target relationship | Count |
|---|---|---:|
| Transformer linear weights | Node path `/roberta/encoder/layer.N/.../MatMul_quant` identifies source `roberta.encoder.layer.N....weight`; its second input identifies the corresponding `onnx::MatMul_NUMBER_quantized` initializer. ONNX weight is source transpose `[out,in] → [in,out]`, INT8; zero point is 0. | 72 |
| Classifier dense/output weights | `classifier.dense.weight_quantized` and `classifier.out_proj.weight_quantized` feed their named classifier MatMulInteger nodes. Both require source transpose, despite retaining source-like tensor names. | 2 |
| Word/position/token-type embeddings | Same source name plus `_quantized`, same shape/layout, UINT8, used directly by their named Gather nodes. | 3 |
| Candidate unchanged parameters | Same name, shape and FLOAT dtype, comprising 74 linear/classifier biases plus 50 LayerNorm weights/biases. Values have not yet been compared. | 124 |
| Unmapped original buffer | `roberta.embeddings.position_ids`, I64 `[1,514]`. Must be explained by input-derived position-ID behavior, not silently discarded. | 1 |
| Exporter-generated initializers | Constants/buffers beyond mapped model parameters and their 154 scales/zero points; each is inventoried for graph-semantic validation. | 20 |

This accounts for all **202 source tensors** and all **375 target initializers**:
77 quantized parameters × three tensors (data, scale, zero point) + 124 candidate
unchanged parameters + 20 generated constants. There is no ambiguous many-to-one
parameter mapping, unexplained learned source weight or unmatched quantized
initializer in this structural map. Names/connections/shapes establish mapping
candidates, not numeric derivation. The square matrices especially need explicit
transpose comparison; square shapes alone would conceal a wrong layout.

Embedding metadata read directly from the small scalar initializer fields:

| Embedding | Scale | UINT8 zero point |
|---|---:|---:|
| Word | 0.007876603864133358 | 124 |
| Position | 0.008173785172402859 | 124 |
| Token type | 0.0005601089214906096 | 163 |

The original position buffer is not mapped onto `onnx::Slice_211`: that exporter
buffer starts with zeros, while its use is a token-type slicing path. The ONNX
position branch instead uses input IDs → Equal/Not → Cast → CumSum → masked Mul
→ Cast/Add → position Gather. Installed Transformers source generates
padding-aware positions through the corresponding cumsum formula. Full branch
constant/attribute validation and representative token-pattern parity are still
required; this is a plausible explanation of the unused original buffer, not an
assertion that every graph operation is already equivalent.

### Historical proposal for supervised numeric comparison

Use the already authorized resource supervisor with **512 MiB task / 640 MiB
aggregate and a fixed five-second deadline per admitted offline comparison
operation**, pressure refusal and single-flight CPU admission. Wait for the
parent to coordinate the native slot after Task 2a. No ORT/Torch/model execution
is necessary for weight comparison; a NumPy-only disposable worker is sufficient
if approved. Inputs are pinned local files with immutable structural manifests.
No source, model cache or product file is modified.

1. Freeze the recipe candidates from the relevant exporter/ORT source before
   running data checks: scalar signed symmetric matrix quantization and unsigned
   affine embedding quantization, including exact float32 range/scale handling,
   zero inclusion, rounding and clipping. Do not choose loose tolerances after
   observing errors. Current scalar values and zero points are consistent with
   those recipes but do not identify the exact original implementation.
2. Predeclare independent comparison work units: one ordinary parameter tensor
   per unit, and fixed 4,096-row shards for the 250,002-row vocabulary. Each unit
   streams at most 1 MiB source reads and uses bounded scratch arrays. Matrix
   transpose comparison can use a target buffer of at most 2,359,296 bytes;
   source blocks remain bounded. Persist only source identities, range covered,
   extrema, counts and digests in atomic diagnostic receipts.
3. First pass: compute source extrema per tensor/shard with exact finite-value
   checks. Reduce all predeclared vocabulary shards to one global range and
   verify the stored scalar scale/zero point against the frozen recipe. A
   per-shard range must never become a per-shard quantization scale.
4. Second pass: recompute integer values from source float32 and the validated
   recipe/scale, then compare every quantized byte in the correct layout. Report
   exact mismatch count and maximum mismatch; collect dequantization absolute
   error, mean/RMS error and clipping counts as diagnostic quality indicators.
   For the 124 candidate unchanged tensors, compare exact raw float32 bytes.
   Explain/validate the single nonlearned source position buffer separately.
5. A manifest reduction requires every work unit exactly once, unchanged source
   identities, matching counts and full interval coverage with no gaps/overlaps.
   Any mismatch or unknown rounding recipe leaves derivation unproven. Matching
   all parameters still does not prove full graph semantics or retrieval quality.

These partitions are a finite offline artifact-audit job, not successive slices
of one interactive query. Their total wall time and refusal count must be
reported. Partition boundaries are declared before execution; a refusal or
five-second timeout does not authorize a larger deadline/cap, an automatic
smaller-shard retry, or pretending the whole model passed. If this job's finite
aggregate work is not accepted, run only one fixed diagnostic unit and report
partial coverage. The actual semantic query still has **one five-second total
deadline**, never a fresh deadline per model stage.

## Recommendation

Keep `BAAI/bge-reranker-base` and mark reranker qualification unresolved. There is
no demonstrated, ready-to-run route from the current cache to equivalent ranking
within 512 MiB task / 640 MiB aggregate and the shared five-second query deadline.
Do not enable the resident CrossEncoder, omit reranking, substitute a smaller
model, or claim that the embedding worker's success qualifies this stage.

A prepared INT8 derivative of the **same pinned weights**, including the vocabulary
embedding table, is a plausible candidate. Xenova publishes a roughly 266 MiB
export claiming this lineage; its size/hash and quantized Gather graph are now
verified, and the later numeric audit reproduced its weights; inference remains
unverified. **Qualify that prepared artifact before
inventing a converter.** It is not bitwise-equivalent inference and needs quality
evidence. Standard whole-model export/quantization is not a bounded preparation
recipe. A focused tokenizer and artifact-validation experiment is defensible;
implementing a new streaming exporter or inference engine first is not.

The initial audit was read-only apart from this report and inspected only
package metadata, source text, small JSON files, directory metadata and a
24,352-byte safetensors header. The separately authorized follow-up acquired and
hashed the 278.8 MB derived ONNX file and wrote private diagnostic files, as
recorded above. No Torch, tokenizer, ONNX, Lance or model runtime was imported or
executed in either phase. No services or product files were changed. Other
agents' working-tree changes were left untouched.

## Confirmed local contract

- `AGENTS.md` requires local processing and intact verbatim evidence. The semantic
  preservation spec requires dense, exact, KG, fusion and configured reranking;
  preserving dormant legacy code alone does not satisfy it. Failure is a design
  conflict to report, not permission to lower quality or raise budgets.
- `cognitive_castle/config.py:380` selects the CPU model from
  `CASTLE_RERANKER_MODEL_CPU`, then `~/.castle/config.json`, then
  `BAAI/bge-reranker-base`. This audit found no reranker keys in that configuration
  and no `CASTLE_RERANK*` variables in the audit process. This does not establish
  the environment of every separately running service.
- `reranker.py:40` constructs and caches `CrossEncoder(model_name, device=device)`.
  It does not request quantization or an ONNX backend. It keeps the model resident
  until cache clearing/process exit. CPU is selected when CUDA is unavailable;
  this is not a native-runtime measurement of the machine's device availability.
- `searcher.py:752` reranks fused top-K candidates: default K=20 interactive,
  K=10 hook. Scores align with the input rows and descending sorting is stable.
  Reducing K or shortening the existing 512-token pair window to pass is a
  behavior change, not a transparent resource optimization.
- Installed package metadata: sentence-transformers 5.4.1, Transformers 5.6.2,
  ONNX Runtime 1.25.1, ONNX 1.23.2. `sentencepiece` is absent in this environment.
  Installed CrossEncoder source defaults to sigmoid for one output label. Its
  prediction path length-sorts batches and restores output ordering. A replacement
  must preserve its actual preprocessing, activation and order, rather than copy
  a model-card raw-logit example. Sigmoid preserves ideal order but scores are also
  externally exposed and consumed by later stages.

The approved semantic diagnostic envelope is separate from unchanged production
exact/capture ceilings (128/192 MiB). Sequential disposable tokenizer, embedding,
retrieval and reranker workers must share one query deadline. Passing 512/640 MiB
does not establish production approval or compliance with the smaller exact gate.

## Cached artifact evidence

Cache root:
`~/.cache/huggingface/hub/models--BAAI--bge-reranker-base/snapshots/2cfc18c9415c912f9d8155881c133215df768a70/`.

| Item | Observed size / contract |
|---|---|
| `model.safetensors` | 1,112,206,140 bytes; tensor payload 1,112,181,780 bytes, 1,060.66 MiB |
| Word embeddings | `[250002, 768]`, F32, 768,006,144 bytes, 732.43 MiB |
| `tokenizer.json` | 17,098,107 bytes |
| `sentencepiece.bpe.model` | 5,069,051 bytes |
| `config.json` | XLMRobertaForSequenceClassification; 12 layers; width 768; intermediate 3072; 12 heads; one label; float32 |
| `tokenizer_config.json` | `model_max_length=512`; XLMRobertaTokenizer |

The safetensors header identifies the classifier dense/output weights and biases;
there is no embedding pooling step that can substitute for the classification
head. Cache presence and header structure are not full integrity verification.
The [official repository](https://huggingface.co/BAAI/bge-reranker-base/tree/main)
currently resolves to the same revision and lists these artifacts. Its
[ONNX directory](https://huggingface.co/BAAI/bge-reranker-base/tree/main/onnx)
lists only the approximately 1.11 GB floating-point model. No official quantized
artifact was found there; no compatible quantized reranker was found in this
model's cache snapshot. This is not a claim that no community derivative exists.

## Why a normal INT8 conversion is insufficient

The resident float32 payload exceeds the cap before runtime and activations.
Full float16 payload would still be approximately 530.33 MiB before overhead.
Quantizing transformer MatMul weights while leaving the 732.43 MiB word table
float32 cannot solve the problem. Disk size is never a measured RSS result.

If all large weights are represented in INT8, a crude payload estimate is
265.16 MiB before float biases, scales, graph, allocator, runtime, prepacked
copies and activations. This leaves possible headroom, not proof of fit. Loading
two copies of even that payload exceeds 512 MiB. Twenty long pairs can also
consume substantial activation memory; sequential microbatches may reduce peak
memory while increasing latency and must preserve all candidates.

ONNX Runtime 1.25.1's [operator registry](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.25.1/onnxruntime/python/tools/quantization/registry.py)
includes Gather in the dynamic quantization operators. Its
[Gather implementation](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.25.1/onnxruntime/python/tools/quantization/operators/gather.py)
can gather from a quantized initializer and propagate quantization parameters.
That supports a useful graph shape: keep the large table quantized, gather token
rows, then dequantize only the small selected output. A graph that dequantizes
the whole table first would lose this advantage. Actual graph transformations
and CPU execution must be inspected and measured.

The stock [dynamic conversion entry point](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.25.1/onnxruntime/python/tools/quantization/quantize.py)
loads a shape-inferred ModelProto before quantization. Installed
`onnxruntime/quantization/quant_utils.py:1004` calls `onnx.load()` with normal
external-data loading. External-data *output* is not a streaming-input guarantee.
The [Sentence Transformers backend documentation](https://sbert.net/docs/cross_encoder/usage/efficiency.html)
supports ONNX and quantization, but provides no 512 MiB conversion guarantee and
can automatically export absent ONNX files. Do not trigger that fallback here.

## Bounded preparation: possible component, missing complete route

### Prepared public derivative is the preferable next lead

The [Xenova model card](https://huggingface.co/Xenova/bge-reranker-base) explicitly
describes its model as an ONNX conversion of `BAAI/bge-reranker-base`. Its
configuration matches the classifier architecture, dimensions, vocabulary and
label count. Hugging Face repository API metadata inspected during this audit
reported revision `280bcc27a84e0b898c251e06fddb25171bd9b101` and:

| Prepared file | Bytes | Hub LFS SHA-256 |
|---|---:|---|
| `onnx/model_int8.onnx` | 278,825,308 | `2059d8ef0b6e935b4845e11b38c9af9e9e2e7b91f69fc99efe03254e0a7da8d3` |
| `onnx/model_quantized.onnx` | 279,301,077 | `dd98f3e67837d23210a6b7550c08cced4f61845b940ac45be3565840a10f3244` |
| `onnx/model_uint8.onnx` | 278,825,337 | `e62181cc56d06ce71e4e4ba08dbf66ea5f1e181488b42bc6276446d810c8982a` |

Metadata also lists a 1,112,459,588-byte float32 graph, a 556,462,150-byte fp16
graph, and roughly 820–826 MB q4/bnb4 graphs. The INT8-sized candidates are the
useful lead; a lower-bit name alone does not mean a smaller complete model.
At initial metadata inspection these were publisher-reported hashes. The
`model_int8.onnx` content hash was subsequently verified locally, as recorded above;
the other candidates were not downloaded.

Repository history records a June 2025 update for Transformers.js v3 quantized
models. The public [Transformers.js 3.0.0 quantization script](https://raw.githubusercontent.com/huggingface/transformers.js/3.0.0/scripts/quantize.py)
uses dynamic ONNX quantization with all IntegerOpsRegistry operators, including
Gather in the inspected ORT implementation. This makes a quantized vocabulary
table plausible. Neither file size nor that script proves the actual graph
contains the expected Gather path. No exact upstream BAAI revision, conversion
command, tool-lock manifest or artifact-specific quantization settings were
established from the inspected card/config/commit messages. The follow-up
structural results above resolve the Gather-layout uncertainty, not the missing
weight-derivation and conversion provenance.

An independently verified same-weight export would be a runtime representation
change, not necessarily a model substitution. Do not establish that by changing
the configured model name to Xenova and trusting the card. Pin the source BAAI
identity and record this separately as a derived runtime artifact.

The minimal next preparation is a bounded acquisition and **validation** of one
pinned INT8 artifact, not a local full-model export. Stream its hash and inspect
the graph and initializer metadata without constructing multiple 266 MiB copies.
Check all graph operators/attributes, tensor names/shapes, classifier head,
inputs/outputs and absence of unrecognized custom operators. Establish the
quantization recipe and compare each stored quantized initializer against the
result of applying that recipe to fixed-size chunks of the cached official
safetensors: account for transpose/layout, per-channel axes, scale/zero point,
rounding/clipping and float biases. Recompute ranges/scales where necessary;
merely accepting arbitrary supplied scales or a loose reconstruction-error
threshold is insufficient. Include every tensor, not only the word table.

This can establish reproducible correspondence to official weights without
loading or downloading another 1 GB artifact and is materially simpler than
creating a new model exporter. It still needs a carefully bounded ONNX reader
(large inline protobuf initializers can otherwise duplicate memory), full graph
mapping and a verified quantization recipe. Unknown recipe or unmatched tensors
is a stop condition. Weight derivation proof does not establish retrieval quality
or runtime memory. The subsequent bounded download and structural inspection
were performed; the proposed per-weight validation was not.

### Local conversion remains a fallback research problem

Safetensors offsets allow deterministic fixed-size reads of the cached source
without allocating the whole model. A two-pass chunk algorithm can compute
per-tensor/per-channel ranges, then round, clip and emit INT8 blocks plus scales
in stable order. [Safetensors documents partial tensor access](https://huggingface.co/docs/safetensors/main/en/index).
Plain bounded file reads are preferable to assuming a whole-file mmap stays
outside RSS. A complete plan would pin rounding, axis, zero point, symmetric
range, tensor layout, input/output hashes and converter version; chunk boundaries
must not change the result.

However, quantized weight bytes are not an executable cross-encoder. This cache
does not provide a small uninitialized ONNX graph. Producing and verifying the
correct graph/head, handling external initializers, avoiding full-table
dequantization, and avoiding loader/prepack duplicates remain unresolved. Stock
export from the 1.11 GB checkpoint does not solve these under the cap. A custom
streaming graph conversion is substantial new tooling, not a verified small
change. Do not start it as an implicit extension of Task 2.

An exact sparse lookup of only needed float32 vocabulary rows before a smaller
encoder graph is another theoretical decomposition. It would require graph
surgery/export and equivalence tests; it is not a ready alternative either.
Layer-streaming a full model would add still more engineering and latency risk.

## Tokenizer serialization alternative

First try the existing fast `tokenizer.json` in its own disposable tokenizer-only
process, matching the successful embedder worker separation. Reranker tokenizer
RSS has **not** been measured; the embedder's measurement cannot be reused.

The cached 5.07 MB SentencePiece file is a second candidate, not a drop-in proof.
A dedicated SentencePiece runtime plus a thin XLM-R adapter could avoid a large
JSON vocabulary construction path. It must reproduce vocabulary offsets, unknown
and mask handling, normalization, whitespace behavior, pair separators
(`<s> A </s></s> B </s>`), attention masks, padding and the effective pair
truncation policy exactly. Special-token text, Unicode normalization, mixed
scripts, empty inputs and near-window-boundary pairs are essential fixtures.
Using another serialization alone does not guarantee lower runtime RSS.

Current Transformers 5.6.2's `XLMRobertaTokenizer` is implemented with the
`tokenizers` Unigram backend. Merely selecting that class or asking for a slow
tokenizer is not evidence of an independent low-memory SentencePiece path.
Installing a new runtime and adapter would be separate reviewed preparation.

## Smallest useful experiment and stop conditions

This is a proposal, not an execution result or authorization to run native work.

1. Under existing pressure refusal and the approved 512/640 MiB diagnostic
   supervision, run only the pinned fast tokenizer on fixed synthetic pairs in a
   disposable worker. Record token arrays, cold latency and aggregate peak RSS.
   Stop immediately on refusal/cap. Do not import ST/Torch/ONNX in that worker.
   Test the alternative tokenizer only if the first path fails or consumes
   prohibitive query time; require exact token-array equality on the frozen
   adversarial fixtures before considering it compatible.
2. Prefer the pinned public INT8 artifact validation described above, after its
   bounded download/preparation scope is accepted. Before applying a streaming
   validator to it, begin with a tiny deterministic synthetic
   embedding Gather + linear graph. Compare bounded chunk quantization against
   the pinned stock quantizer on this tiny data; prove the graph gathers INT8
   before dequantizing and does not allocate a full float table. Include
   chunk-boundary and rounding edge cases. This isolates a necessary mechanism;
   it does not qualify real BAAI weights, export, memory or quality. The next
   actual-artifact stage validates provenance and graph structure; it does not
   launch inference as a side effect of loading metadata.
3. Stop before local full conversion unless a reviewed graph/export recipe genuinely
   stays bounded. Do not run the stock converter on the full checkpoint just to
   rediscover an obvious size conflict. Keep conversion scratch space, immutable
   cached inputs and deterministic output receipts explicit. Preparation uses
   its own approved bounded job; it must never run in a search request.
4. Only after an executable same-revision artifact exists, run a disposable
   CPU inference worker with explicit offline paths and no export/download
   fallback. Qualify 1, 10 and 20 pairs, short and full-window inputs, cold and
   repeated fresh processes. Measure startup/optimization peaks and output
   stability, then the entire exact+dense+KG+fusion+rerank+hydration sequence
   under **one** five-second deadline. A standalone five-second reranker test
   cannot pass the end-to-end gate. No model workers overlap or remain resident.

## Quality evidence still needed

INT8 changes arithmetic. Preserve model lineage, tokenizer/window and classifier
semantics, but describe it as a compatible derivative only after evidence.
Compare frozen query/candidate scores, top-1/top-N and pairwise order against a
trusted same-revision float32 baseline, including near ties, multilingual
queries, long pairs, corrections, aliases and irrelevant but lexically similar
documents. Record the incremental retrieval-quality effect versus fused order,
not only cosine similarity or token equality. Exact citations, policy filters,
candidate K and hydration remain unchanged.

No current reference outputs or approved quality tolerance were established in
this audit. Full baseline inference is itself not safe through the existing
resident path under these caps. A trustworthy reference must be obtained through
an explicitly acceptable bounded method or separately agreed validation route;
do not call an external provider or raise limits to manufacture it. Tiny graph
equivalence and weight reconstruction error cannot replace retrieval validation.

Consequently this report supports **bounded investigation**, not a claim that
the configured reranker now fits. If preparation, quality or total latency cannot
be demonstrated within the existing decision, surface the conflict and request
a revised design decision. Leave activation and the stopped converter unchanged.
