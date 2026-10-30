# Independent reranker input/output audit — 2026-10-24

**Result: no concrete static input/output bug explains the unchanged short-K10 relevance failure.** The ten cached pairs contain the exact frozen query and documents, in the correct original candidate indices. Both scorers feed these rows by their declared ONNX input names and restore their scores correctly. This is not source-Torch parity proof, and it does not qualify either export. Mars remains the required top candidate at index 2.

This was an independent read-only investigation except for this report. It used shell source reads and Python `-S` standard-library inspection only: no native/model/SQLite imports, inference, services, product edits, git writes, or subagents. The tokenizer vocabulary was streamed line by line and only its 99 used entries retained; neither the giant tokenizer JSON nor model weights were loaded wholesale. Root coordinates any later runtime experiment.

## Evidence path abbreviations

- `BASE` = `/Users/ladislavbihari/.castle/backups/durable-memory-20261024/relocation/reranker-models/280bcc27a84e0b898c251e06fddb25171bd9b101`
- `PKG` = `/Users/ladislavbihari/.echelon/venv/lib/python3.12/site-packages`
- `CACHE` = `/Users/ladislavbihari/.cache/huggingface/hub/models--BAAI--bge-reranker-base/blobs`
- `TOK` = `CACHE/9eb652ac4e40cc093272bbbe0f55d521cf67570060227109b5cdc20945a4489e`
- `TCFG` = `CACHE/059214673d9d6d2ee319411e2ffec8c024b816d5`
- `MCFG` = `CACHE/ff248a5f7d76e27b10778b3c593c9fba1df4c448`

The machine-readable fixtures/receipts below are single-line JSON, so `:1` plus the exact JSON member identifies their evidence.

## Actual cached rows and configuration

`BASE/external-runtime-probes-v1/manifest.json:1` (`scenarios[id=short-10]`) fixes the question “Which planet is known as the Red Planet?”, ten documents, and `expected_top=2`. `BASE/external-runtime-probes-v1/receipts/short-10--tokenize_only.json:1` (`result.page.rows`) contains ten rows of 33 token positions.

A fresh streamed vocabulary check in this audit independently reconstructed all ten query/document strings and compared them exactly with that manifest. All 20 comparisons passed. In every row: position 0 is ID 0 (`<s>`), positions 1–9 reconstruct the question, positions 10 and 11 are ID 2 (`</s></s>`), position 12 begins the intended document, and the last unmasked position is ID 2. All later IDs are 1 and all later attention entries are zero. Nonpadding lengths by original candidate index are `[26, 27, 33, 27, 29, 25, 29, 30, 30, 27]`. There is no truncation in this fixture. The Mars row has 33 nonpadding positions; Saturn has 27. This rules out a swapped, missing, or shortened document in the observed page.

The inspected official template is `<s> A </s></s> B </s>` with **all type IDs zero**, including B (`TOK:95`, `TOK:120`, `TOK:133`). Special IDs are 0/1/2/3/250001 for `<s>/<pad></s>/<unk>/<mask>` (`TOK:5`). Vocabulary anchor checks include `<s>` at `TOK:164`, `<pad>` at `TOK:168`, `</s>` at `TOK:172`, `▁Mars` at `TOK:93532`, `▁Saturn` at `TOK:474768`, and `▁Which` at `TOK:520476`.

`TCFG:14` fixes maximum length 512, `TCFG:15` fixes `<pad>`, and `TCFG:6` supplies mask-token properties matching `TOK:42`. `MCFG:27` fixes pad ID 1, `MCFG:31` fixes type vocabulary size 1, and `MCFG:33` fixes vocabulary size 250002. Nothing in these small configs requests a query/document prefix, lowercase conversion, reversed pair order, or a second nonzero token type.

`BASE/external_runtime_probe.py:94` verifies these assets, loads the official serialized tokenizer, checks special IDs, explicitly sets longest-first right truncation at 512 and right padding to the batch maximum, and encodes `(query, document)` with special tokens (`:107–114`). Its settings match the frozen manifest. The official FP32 worker contains the same routine but its executed unit reused the cached page. I independently compared the entire `result.page` from `BASE/official-fp32-baseline-v1/receipts/short-10--tokenize_only.json:1` to the original: exact equality.

The validator at `BASE/external_runtime_probe.py:71` and `BASE/official_fp32_baseline.py:71` checks count, equal padded lengths, integer IDs/masks, contiguous right padding and outer special tokens. It does **not** itself validate the inner pair separator or decode text. The independent row check above closes those checks for this fixture; the validator's narrower scope is not evidence that the actual page is wrong. Sequence IDs were not emitted, so their runtime values are still not directly observed.

## High-level tokenizer and ST comparison

Installed ST source passes ordinary text pairs through unchanged (`PKG/sentence_transformers/base/modality.py:251`, `:273`), supplies padding and longest-first truncation (`PKG/sentence_transformers/base/modules/transformer.py:905`), and accepts explicit processing overrides at `:917`. The product constructs `CrossEncoder(model_name, device=device)` without custom tokenizer or processing kwargs (`cognitive_castle/reranker.py:40–46`). Right padding/truncation are the Transformers defaults (`PKG/transformers/tokenization_utils_base.py:982`).

There is a **real initialization-path difference that remains a parity gap, not a demonstrated cause**. The probe directly retains the serialized backend. Installed Transformers 5.6.2's `TokenizersBackend.convert_to_native_format` takes a reconstruction path for classes with a custom initializer: it extracts the Unigram vocabulary and the Precompiled charsmap (`PKG/transformers/tokenization_utils_tokenizers.py:118`, `:158`, `:175`). `XLMRobertaTokenizer` constructs a new Unigram backend, a Precompiled normalizer, and `WhitespaceSplit` followed by Metaspace (`PKG/transformers/models/xlm_roberta/tokenization_xlm_roberta.py:81–93`), then sets the expected pair template (`:106`). The serialized file instead declares Precompiled plus a repeated-space Replace normalizer and a single Metaspace pre-tokenizer (`TOK:52–72`). The supplied special-token mapping is compatible; the source retains vocabulary order. The frozen question/documents use ordinary single spaces and the decoded cached rows are exact. Static inspection therefore does not establish any changed token segmentation here, but it cannot certify equality with a fresh high-level tokenizer either. Multispace/Unicode/special-token and full-window cases remain unqualified.

The absence of `token_type_ids` from the feed is consistent with XLM-R's declared input names (`PKG/transformers/models/xlm_roberta/tokenization_xlm_roberta.py:51`), the one-row type vocabulary, and Torch's zero-default type-ID path (`PKG/transformers/models/xlm_roberta/modeling_xlm_roberta.py:103–117`). Position IDs should derive from nonpad IDs starting at 2 (`:146–159`). These source contracts do not prove that every exported internal branch executes equivalently.

## Binding, shape, sorting and output interpretation

Both scorers at `:136–158` verify their model and external-data assets, instantiate the model by **file path**, and use `CPUExecutionProvider`. At `:163–175` they require named int64 `input_ids`/`attention_mask`, create both arrays from the same row permutation, request `logits` explicitly, require finite float32 `(10,1)` output, and assign `original[order] = logits[:,0]`. Their stable descending score ranking is at `:180`. There is no positional feed-dictionary dependence, flattening across candidates, or output-column reversal in this code.

I independently streamed the two small external-data graph protobufs. Both declare int64 `[batch_size, sequence_length]` inputs named `input_ids` and `attention_mask`, and float `[batch_size,1]` output `logits`. Every external initializer resolves to relative `weights.bin` in the corresponding graph directory: 221 INT8-graph external tensors and 201 official-FP32 external tensors. For every descriptor, length equals shape-product times dtype width, the interval lies within that directory's weights file, names are unique, and intervals do not overlap. This check establishes descriptor/input consistency; existing weight-equivalence receipts supply payload provenance, which this audit did not repeat.

ST sorts by summed pair character lengths (`PKG/sentence_transformers/base/model.py:422–436`, `cross_encoder/model.py:671`) and restores using the inverse permutation (`cross_encoder/model.py:694`). The probe's assignment is algebraically the same restoration. Sigmoid at `BASE/external_runtime_probe.py:176–180` and the identical FP32 lines preserves the observed clear top ordering; output sign/activation does not explain Saturn beating Mars.

`BASE/quality_batch_probe.py:168–197` independently assigns each returned row to its original candidate index for length-sorted, identity and reverse permutations and evaluates unchanged padded rows individually. Existing receipts show exact permutation equality. That supports the index conclusion, but neither that experiment nor this static review compares to source-Torch inference. Singleton INT8 behavior cannot establish FP32 batching equivalence.

## Smallest next disambiguation

The smallest remaining input experiment is **one separately supervised tokenizer-only comparison** using the installed high-level tokenizer on the exact local pinned BAAI snapshot and these ten frozen pairs, with the same maximum 512, longest-first right truncation, right batch padding, and no product configuration changes. Disable network/export/model loading and avoid tensor-return options that import Torch. Record the effective tokenizer class/config, IDs, masks, type IDs and sequence IDs; require exact per-original-row equality with the cached page, including its 33-position shape. Preserve the existing 512/640 MiB and shared five-second envelope; a refusal remains a refusal. This report does not authorize or run it.

If exact equality passes, this fixture's high-level tokenization difference is eliminated; it still does not establish source-model output parity. Source-model behavior versus exported/runtime semantics remains unresolved and would need its own discriminating, separately coordinated investigation. This audit proposes only the tokenizer parity comparison above, with Torch disabled where supported; it proposes no new model run, relaxed golden label, larger limit, or inference retry.
