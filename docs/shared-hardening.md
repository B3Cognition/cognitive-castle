# Shared Castle hardening

This change preserves Castle's LanceDB architecture, verbatim source records,
standalone fast-memory API, four legacy search modes, SUE and optional SOAR.
It introduces no Prosaic provider, host activation or release version change.

The following observable corrections are intentional:

- Pruning only removes explicitly derived, completed revisions in the same
  source/wing/representation. Original and unknown legacy representations survive.
- Incremental import checks distinguish representations and wings. Completion
  requires the associated drawers and closets; a failed import can be retried.
- Diary edits and changed transcript messages retain prior source versions.
- Palace auxiliary state follows the selected palace. Recognized default legacy
  layouts remain readable; ambiguous custom shared state requires explicit
  migration, preserving the original files.
- Writers and maintenance share a mutation lock. An active lock cannot be bypassed
  by deleting its inode or by forcing stale-lock cleanup.
- `castle reindex --palace PATH` rebuilds vectors from stored records, retaining
  IDs, exact text, history and unique backups. `--recover` handles interrupted
  promotion. `--sources` checks source existence; import new material separately
  with `castle mine`. `--yes` never authorizes deleting an existing backup.
  Intent files are flushed on every platform; directory-entry fsync is POSIX-only.
  Recovery is tested across interrupted promotion, without a universal power-loss
  durability guarantee for Windows directory renames.
- The `max` search mode applies SOAR/quality adjustments before the final judge
  permutation; serialization preserves that decision. Optional-engine failure
  preserves the incoming order, and invalid/nonfinite reranker output fails.
- Explicit configuration reaches embeddings and graph lookup. Selected init LLM
  settings persist in global configuration; external endpoints remain explicit.

These are safety and correctness fixes, not a promise that every buggy historical
side effect remains. Supported CLI/MCP call forms and original storage content
remain covered by regression tests. The optional provider and release packaging
are separate dependent changes; memory remains disabled by default in Prosaic.
