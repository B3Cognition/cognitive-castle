# Tiny NumPy oracle: independent static review

**Disposition: APPROVED for the single prepared synthetic unit, subject to root's separate native-slot grant.** No blocking findings. Numerical execution remains UNRUN; this is not model parity or production qualification.

Reviewed packet: `reranker-tiny-numpy-oracle-preparation/`, canonical manifest SHA-256 `4e2afa8c1db18134122aa1b80dcdfacf7d8264fcac6bdba778f394ed4818d16f`.

## Equations and oracle

Read all 93 lines of `numpy_equations.py` and 176 lines of `tiny_oracle.py`, and compared their relevant equations with the installed, bound XLM-R embeddings, eager attention, self-output, intermediate/output, classifier, GELU, and eager mask implementations. Weight orientation, cumsum/nonpad position IDs, embedding addition order, key-mask broadcast, last-axis softmax, head scaling/reshape, post-residual population-variance LayerNorm with epsilon inside the square root, exact-form erf GELU, and first-token dense/tanh/output classifier agree for the frozen encoder/eval scope.

The Torch oracle independently uses functional embedding/linear/layer_norm/gelu/softmax plus matmul/tanh. The NumPy block never obtains expected outputs from those operations; shared values are deterministic synthetic inputs and weights. All 27 ordered comparisons gate dtype, shape, finiteness, and the frozen `atol=1e-5, rtol=1e-4`; integer positions gate exact equality. Mixed padding, non-square projection, constant and shifted normalization, GELU zero/tails, block observers, and composite output cover the declared scope. Float64 is used only for tiny error measurements. No checkpoint, real query, tokenizer, ONNX session, or model constructor is present.

## Guard and retention review

Read the full host/worker, private-TMP guard, verifier, manifest, delta, commands, and preparation records. The sole supervisor call retains 512 MiB task / 640 MiB aggregate limits and a shared absolute five seconds, global admission, pressure refusal, background preemption, guardian/session admission, and descendant cleanup. One-thread environment is set before numerical imports; Torch thread counts are checked. Exclusive `attempt.claim` prevents an unrecorded automatic retry. Failure/refusal cannot produce a qualified result.

Independent AST comparison found 13 inherited functions/classes unchanged; only `install_guards` changed. Its delta restricts additional engine imports and known model payload reads. Reviewed temporary mkdir/rename/replace accounting is preserved, including rebased child-name reservations. The fixed artifact census and reservations remain within the declared 16 MiB family; the documentation correctly avoids claiming a filesystem quota or kernel RSS hard cap. Runtime temporary use and fit remain to be measured.

## Independent checks performed

- The stdlib-only sealed-packet verifier passed: 12 sealed files, 17 small source hashes/identities, 6 native stat identities, and 5 current guard hashes. Manifest matched the hash above; result/claim/marker paths and private TMP were still empty.
- AST parsing and compilation without execution passed for all five Python files.
- Inherited helper AST equivalence was independently checked; source review covered the actual changed guard and new execution paths.

No numerical engine imports, native tests, resource-setting calls, model-file reads, source mutation, or product edits were performed by this review. Native identity binding is explicitly stat-only, not complete binary-closure verification. A passing tiny unit would establish only this equation-transcription check; full-depth drift, original-weight mapping, stock-model parity, Mars ranking, and full-model time/RSS fit remain unqualified.
