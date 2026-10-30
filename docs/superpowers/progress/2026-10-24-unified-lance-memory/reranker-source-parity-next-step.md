# Remaining source parity decision — 2026-10-25

**The smallest useful remaining discriminator is one direct, stock XLM-R CPU/FP32 inference on the original ten cached rows, loading the already verified official safetensors through the installed meta/mmap path.** That path is statically plausible, not qualified to finish within 512/640 MiB and five seconds. Current evidence proves neither fit nor universal impossibility. No further ONNX optimization probe would resolve the remaining source/ONNX gap.

This report is analysis only: no harness, preparation, model/runtime import, weights read, inference or retry was performed. Existing graph/tokenizer audits were reused, not repeated. The configured `BAAI/bge-reranker-base` and Mars quality gate remain unchanged and unqualified.

## The fixture does not justify changing the label

The exact frozen question is “Which planet is known as the Red Planet?” Of the ten original documents, index 2 explicitly states “Mars is known as the Red Planet because iron oxide gives its surface a reddish color.” Index 3 states “Saturn is famous for its bright rings of ice and rock.” The other documents concern Jupiter's size/Great Red Spot, Venus as Earth's twin, Mercury's size/orbit, Neptune's winds, Uranus's rotation, Earth, the Moon and Pluto. None supplies an instruction or competing answer that makes Saturn the correct label. The all-ten manifest and audited token page are authoritative; rewriting texts or calling the ranking a fixture ambiguity would discard the observed failure.

The FP32 ONNX path ranks `[3,2,8,4,1,0,7,6,9,5]` with either optimization setting. OFF changes individual logits by at most `1.0013580322265625e-05` and does not repair the roughly 2.49-logit Saturn-over-Mars gap. This closes that optimization-toggle hypothesis for these rows, not source parity.

## Exact proposed stock source route — not prepared or authorized

Use the installed concrete `XLMRobertaForSequenceClassification` from `transformers.models.xlm_roberta.modeling_xlm_roberta`, avoiding `CrossEncoder`, AutoModel routing and every tokenizer/processor call. The unavoidable Torch/Transformers imports remain; this does not claim an import-light framework.

Call its existing `from_pretrained` on the **local snapshot directory** `/Users/ladislavbihari/.cache/huggingface/hub/models--BAAI--bge-reranker-base/snapshots/2cfc18c9415c912f9d8155881c133215df768a70/`, with these fixed choices:

- `local_files_only=True`, `use_safetensors=True`, `disable_mmap=False`, `dtype=torch.float32`, `device_map=None` (CPU), `attn_implementation="eager"`, `use_kernels=False`, `trust_remote_code=False`, `output_loading_info=True`, `ignore_mismatched_sizes=False`.
- Offline/network/child restrictions and one Torch intra/inter-op thread. `HF_DEACTIVATE_ASYNC_LOAD=1` selects the existing synchronous loader instead of its default four-thread pool; it changes loading scheduling, not learned values or arithmetic.
- Retain default eval mode and use `torch.inference_mode()`. No dtype conversion, autocast, quantization, compile, accelerator placement, offloading, replacement weights or new exporter. Inspect returned loading information: no missing/mismatched learned parameter or conversion error is acceptable. The already documented nonlearned saved position buffer is a separate known compatibility detail, not permission to ignore arbitrary unexpected keys.

Read the **original** bound cached page (`BASE/official-fp32-baseline-v1/receipts/short-10--tokenize_only.json`; `BASE` is defined in `reranker-input-audit.md`), canonical page hash `cf395a969972e7c74194e7bd0a455640dc4abc555289b1af20076115b4377bfe`. Build Torch int64 IDs/masks directly from its lists, preserving all ten 33-position rows, existing character-length ordering and restoration; make one forward call and record ten original-order raw logits/ranking. No NumPy/ORT scorer or tokenizer is needed alongside it. Preserve the Mars-at-index-2 gate.

The source checkpoint is the existing 1,112,206,140-byte `model.safetensors`, SHA-256 `ced967c45fd1902eb92716c9ceeca7c95a936770ea9db611f5a841b926e33fbd`. Existing receipts already bind all 201 learned FP32 ONNX tensors exactly to it, including mapped transpose layouts. Preserve source-file identity/hash checks inside the same supervised budget; do not deserialize the ONNX weights into Torch or rebuild a checkpoint. This supplies an independent source execution over the same weights and inputs.

## Why it might fit, and what remains unknown

The installed loading implementation is materially different from allocating a normal resident model and copying a state dict into it:

| Local source under `PKG/transformers` | Relevant behavior |
|---|---|
| `modeling_utils.py:3643` and `:4159` | Constructs the model in a meta-device context; no initial physical allocation of the 732.43 MiB word table is required. |
| `modeling_utils.py:4320` | CPU safetensors `safe_open` plus lazy `get_slice`, rather than whole-file `_safe_load_bytes`, when mmap is enabled. The hf-mount fallback is Linux-only (`:293`), not this Darwin path. |
| `core_model_loading.py:936`, `:760`, `:1044` | Materializes slices, calls `.to(device,dtype)`, and assigns Parameters; the selected same-CPU/F32, unquantized XLM-R loading path has no explicit whole-weight clone or numerical conversion. |
| `modeling_utils.py:4008`, `:4212` | `low_cpu_mem_usage` is discarded in this version; it is not a useful fix. Loading already ends in eval mode. |

Primary documentation supports the underlying mechanism: [Safetensors documents zero-copy CPU loading through file-backed Torch storage](https://github.com/safetensors/safetensors), and [PyTorch documents meta initialization and storage assignment to avoid duplicate allocations](https://docs.pytorch.org/tutorials/recipes/recipes/module_load_state_dict_tips.html). These describe mechanisms, not this model's RSS or timing guarantee.

The loader visits all tensor descriptors and obtains full-shaped views. That is not evidence that it touches every vocabulary row. No selected Python branch mandates scanning/cloning the entire word table. The native binding, allocator behavior, CPU kernel packing and actual resident pages were **not** measured here; no claim of guaranteed zero-copy throughout execution is made. Conversely, a materialized resident F32 word table alone is 768,006,144 bytes and exceeds both caps: an allocating/copying fallback would be incompatible.

All twelve encoder matrix sets total **339,738,624 bytes = 324 MiB**. They must be read cumulatively during a full pass; if those mapped pages stay resident, less than 188 MiB of the task budget remains for Torch/Transformers, guardian, other parameters, activations and packing. This is a risk calculation, not a formal resident-memory lower bound: mapped pages may be reclaimed. No retained measurement establishes the necessary Torch/source import floor or five-second cold-start fit. Full streaming checkpoint verification adds I/O inside that same budget. The 1.06 GiB checkpoint's disk size alone therefore proves resident loading is unsuitable, but does **not** prove mmap source execution impossible.

Installed versions read from metadata are Torch 2.12.0, Transformers 5.6.2 and Safetensors 0.7.0. Inspected loader SHA-256 values are `modeling_utils.py=b78bf8e138b88c2b0db96c7f2c9686238351ec9b8ea9db93072aaef387959d1c`, `core_model_loading.py=750b52caf5061ef13a64272aab5831242b02076bdc5cf390201583dee3dfc673`, `conversion_mapping.py=1924629e3fb595f30ae22626894971d8cd5236df8cd9a1c2db77bc166ea39d63`.

## Decision value and limit

If separately authorized, recommend **at most one** such direct source unit under the current reviewed absolute deadline, background preemption, admission/pressure checks and 512/640 MiB tripwires; stop on first refusal, with no retry or changed budget. A narrow source-scorer preparation would still need review: the frozen ONNX worker currently forbids Torch/Transformers and cannot simply be launched as this experiment.

| Completed source outcome | Supported conclusion |
|---|---|
| Source also ranks Saturn above Mars | This relevance failure exists in stock source execution on these cached inputs, independently of ONNX. It does not qualify general model quality or the high-level tokenizer/product path. |
| Source ranks Mars first across all ten while ONNX does not | A source/ONNX parity failure is demonstrated; this alone cannot assign blame among historical exporter/source-version differences and runtime arithmetic. |
| Source gives another ranking or a guard refuses | Record the exact result; either the source still fails the same quality gate or parity remains unresolved. A refusal is no evidence of inherent source-model failure. |

The historical exporter Transformers revision remains unknown; config save metadata says 4.30.0, while this proposal uses the installed 5.6.2 eager implementation. Even a successful source result would therefore answer the present stock-source question, not certify historical exporter parity. Until completed source evidence or an explicit product decision exists, the correct state is **unqualified**, without changing the configured model, fixture or limits.
