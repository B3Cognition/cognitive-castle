# Focused private-temp preparation review

Reviewed manifest canonical SHA-256:
`b652014ab8d08883445e1ad9f3c1d9e147e249231492361f221b9f7356a82b7f`.
Packet remains immutable and unrun. Static file inspection only; no model/engine,
installed source/weights read, native operation or test was performed.

## P2 — Python rename destinations bypass the lifetime temporary-name bound

Location: `reranker-source-private-temp-preparation/stock_source_probe.py:185–206`
(the `install_guards()` audit handler).

The new policy reserves file names only on `open` and directory names only on
`os.mkdir`. It does not handle the Python `os.rename` audit event, which is also
emitted by `os.replace`. An admitted Python caller can create `private-tmp/a`,
rename it to `private-tmp/b`, then recreate `private-tmp/a`; only `a` is charged
to `TEMP_FILES`. Repeating with new rename destinations creates more than eight
lifetime names and more than eight simultaneously retained files without the
stated Python admission refusal. The 1 MiB per-file RLIMIT does not bound the
aggregate of these files. `temp_inventory()` detects the overage only at a later
stage/post-cleanup checkpoint; the README/manifest claim a lifetime Python-name
admission bound in addition to those checkpoint inspections.

Smallest correction: account for Python rename/replace destinations touching
this fixed temporary subtree. Validate their resolved source/destination paths,
charge each new destination to the appropriate lifetime file/directory set,
retain old names in the lifetime sets, and deny moves outside `private-tmp`.
Keep this limited to the new temporary-artifact policy; no generic sandbox
expansion is needed. Any fix must be prepared and sealed as a reviewed successor
rather than changing this sealed packet or its prior evidence.

No other actionable defect found in this narrow review. The supplied diff
exactly matches the two actual workers; the new worker and all sealed small-file
hashes match the receipt, and the canonical manifest hash matches the requested
seal. `infer()` is byte-identical to the prior executed candidate (the recorded
`43dcfbc3…` hash includes the separator before `worker()`). The existing guard
bindings, CPU/F32/eager settings, limits/deadline, import policy and first-result
retention remain intact. Post-supervisor temp-check errors retain the original
supervisor result in `stages` and preserve the subtree. This review grants no
runtime permission or source fit/parity qualification.
