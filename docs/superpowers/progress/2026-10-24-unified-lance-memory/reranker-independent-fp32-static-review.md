# Independent original-weight FP32 diagnostic: static review

**Disposition: APPROVED for the single prepared diagnostic, subject to root's separate runtime grant. No blocking findings.** Runtime fit and numerical outcome remain UNRUN; approval does not establish stock-model or production parity.

Reviewed canonical manifest SHA-256: `c1d34f5b453fdbc079f6e16924b00c3eef3756f708c82050263009cdc75433e2`.

## New mapping and forward path

Read the full strict mapper, full-equation driver, execution unit, comparison helper, guard delta, ten pure test methods and recorded results, manifest metadata, preparation records and verifier. The qualified math file is byte-exact SHA `031d72bbe99e2d11b7733ef7d89ccae74514ab9a6f88e578faa4b1bf404950d9`; its unchanged equations were not re-reviewed or rerun.

The bounded header parser rejects duplicate keys at every JSON object level, unknown/missing descriptors, dtype/dimension/offset errors including boolean integer substitutes, invalid byte lengths and alignment, gaps/overlaps/trailing payload, and header length/hash drift. The original 202-descriptor schema includes exactly 201 learned F32 tensors and the unused I64 position buffer. Mapping uses one ACCESS_READ mmap and original-offset C-order little-endian FP32 views; base identity, contiguity and non-writeability are checked. There is no tensor payload conversion or complete vocabulary materialization.

Independently traced every learned alias: five embedding tensors + twelve layers of sixteen tensors + four classifier tensors = 201 distinct exact names. Each name's original absolute source offset, shape and byte span matches the pinned prior byte-equivalence audit metadata, accounting for that audit's transposed target layouts. The source checkpoint identity and known full SHA agree with that audit. Runtime performs its own streaming full checksum before mapping, inside the sole supervised shared five-second unit, followed by identity rechecks after forward.

The driver uses the fixed cached 10x33 batch, original sort/restore order, twelve encoder layers, 12x64 heads, width 768/intermediate 3072, epsilon 1e-5, and unchanged Mars index-2 quality gate. Each loop replaces the prior hidden tensor; parameters are views and no observer or layer-output list retains activations. Vocabulary indexing gathers only requested rows. Classifier/sigmoid output dtype, shape and finiteness are checked; original-order logits and ranking are preserved. ONNX comparisons report exact equality/deltas/rank, with no new parity tolerance. Learned-model mapping, quality labels and batch remain unchanged.

## Guard delta and execution

The only changed inherited guard function is install_guards: four exact resolved asset paths gain read access and Torch joins denied imports. Outside-package writes remain denied, including writes to allowed read assets. The mocked policy test covers both exact-read admission and retained outside-write refusal. No prefix read exception, alternate-model loader, model constructor, activation spool, manual eviction, native loader or backend import is introduced.

New host/worker paths retain one explicit supervisor call, current global admission/pressure/preemption/UID/session/descendant safeguards, fixed 512 MiB task/640 MiB aggregate budgets and one absolute start+5-second deadline. Full checkpoint hash, header/source/config checks, numerical imports, mapping and forward spend that deadline. Exclusive attempt.claim prevents automatic retry. Private-TMP behavior and unchanged helper policy were not redundantly audited; the prepared family census/reservations and post-cleanup inventory remain present. Natural BLAS allocations, page-in/residency, allocator retention and actual time/RSS fit remain unqualified.

## Independent verification

- Stdlib sealed-packet verifier passed: 16 sealed files, 11 small installed source bindings, four native stat identities, five current guard hashes, and small asset hashes. The large checkpoint was stat-only.
- All 201 aliases and original tensor source offsets/shapes/byte spans independently matched the 53,159-byte pinned mapping audit; no original tensor payload was read.
- Both evidence hashes passed. The actual tiny receipt contains 27 passing comparisons and exact positions; no tiny unit was rerun.
- Eight Python files parsed/compiled without execution. AST comparison found only install_guards changed among inherited guard functions.
- Ten pure test methods and their passing report were read; no green test was rerun.

No numerical engine/Castle/runtime import, resource-setting call, production edit, model payload read or native execution occurred in this review. A completed diagnostic can inform whether the independently expressed learned equations reproduce the retained ONNX behavior; it cannot certify stock Torch/historical-exporter parity or general retrieval quality.
