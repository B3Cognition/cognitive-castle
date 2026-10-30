# Independent original-weight FP32 result

**Resource pass for the one fixed cached batch; unchanged Mars quality failure.** The NumPy/SciPy equations independently reproduce official FP32 ONNX's incorrect ranking. Further ONNX/math runtime probes are closed; no additional model/inference authorization follows.

The actual receipt is [short-10--infer_only.json](reranker-independent-fp32-preparation/receipts/short-10--infer_only.json), 3,175 bytes, SHA-256 `19dae5e0ed7a46e7f378f2e94f58fa0bd377e14ad6733b4a4542872cf515d7b1`, canonical manifest `c1d34f5b453fdbc079f6e16924b00c3eef3756f708c82050263009cdc75433e2`. It binds the original 201 learned tensors and original checkpoint SHA, strict 24,352-byte header/offset mapping, exact qualified math `031d72bbe99e2d11b7733ef7d89ccae74514ab9a6f88e578faa4b1bf404950d9`, and the unchanged cached 10×33 inputs. Torch/Transformers/ONNX were not used by this unit.

| Actual evidence | Result |
|---|---:|
| Shared elapsed / worker guarded elapsed | 1.406467499997234 s / 1.388 s |
| Peak sampled task RSS | 439,861,248 bytes (419.48 MiB) |
| Peak sampled aggregate RSS | 468,516,864 bytes (446.81 MiB) |
| Original-checkpoint/config/header validation | 0.4986519579979358 s |
| Numerical imports and readonly mapping | 0.48448675000690855 s |
| Reported equation-forward interval | 0.27665837499080226 s |
| Retained TMP | Zero files/directories/allocated bytes |

Current reviewed global admission, pressure, UID/session/guardian, background preemption and process cleanup remained active with task 512 MiB, aggregate 640 MiB and the one absolute five-second deadline. Parent observed worker exit and no survivors. RSS is a sampled tripwire, not an unobserved-peak guarantee. This qualifies only the resource behavior of this inference-only fixed short-K10 unit, including its full streaming checkpoint SHA. It does not qualify tokenizer-plus-inference, larger windows/K, other inputs or production use.

Raw logits in original candidate order:

```
[-1.2435206174850464, 0.8965011835098267, 3.454045295715332, 5.947822093963623, 1.5004576444625854, -3.9902005195617676, -2.668583869934082, -2.069091320037842, 2.9014716148376465, -3.142984390258789]
```

Ranking is `[3,2,8,4,1,0,7,6,9,5]`, identical to official FP32 ONNX. Mars index 2 scores `3.454045295715332`; Saturn index 3 scores `5.947822093963623` (gap `2.493776798248291`). Maximum absolute ONNX logit difference is `2.2411346435546875e-05`; logits are not byte-equal. Existing comparison remains report-only exact equality/deltas/rank, with no invented full-model numerical tolerance. `expected_top=2` remains false; actual status is `failed`, reason `synthetic_relevance_mismatch`, qualification `unqualified`.

Independent weight loading/equations and ONNX agree far more closely than the observed top-two gap. This strongly supports the interpretation that the original learned equations produce the failure **on these cached inputs**, rather than an ONNX graph, quantization, optimizer or scorer-order defect. It is not a full stock-Torch source parity proof, high-level tokenizer parity, historical exporter certification or general relevance evaluation. The prior input audit's exact text/row checks remain authoritative; a different valid segmentation by the installed high-level tokenizer has not been observed or excluded.

Recommendation: retain BAAI/bge-reranker-base and the Mars failure exactly as recorded, close further ONNX/math runtime tuning, and treat preservation of learned behavior separately from quality qualification. The Task 4 decision is described in [reranker-task4-quality-decision.md](reranker-task4-quality-decision.md). This report is the only result-summary write; sealed code, manifests, models and receipts remain untouched.
