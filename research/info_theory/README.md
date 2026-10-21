# Information Theory of Verbatim Memory

Phase 1 research artifact for the paper *Measuring Information Content in Verbatim AI Memory*.

## Quickstart

    python -m cli snapshot         # snapshot ~/.castle/palace
    python -m cli pilot            # 5% LME sizing pilot
    python -m cli run --all        # full pipeline (cached)
    python -m cli figures          # produce paper plots
    python -m cli figures --tables # emit appendix LaTeX tables
    python -m cli merge-stats a.json b.json   # compare `castle info-stats --export` files

## Cross-palace validation

Everything in the paper is measured on one palace. To check the structural
claims on another one without seeing its content, ask its owner to run

    castle info-stats --export my-palace.json

and share the file (it holds per-wing counts, novelty histograms, decay
fits and a heterogeneity test: no text, vectors, ids or paths; wing names
only when they choose `--keep-wing-names` or `--wing-alias`). `merge-stats`
puts several exports side by side: novelty medians per palace, which decay
model wins and its parameter, ε² across wings, and the Jensen-Shannon
distance between the pooled novelty histograms. ρ(A, B) cannot be
reproduced from an export — estimator B needs the vectors — so that
comparison still means running the pipeline on a snapshot.

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the manifest.
See `../../docs/superpowers/specs/2026-05-16-information-theory-verbatim-memory-design.md` for the spec.
