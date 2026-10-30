## Task 2: bounded semantic runtime and vector publication

Package the qualified staged tokenizer/inference path into fixed workers and a
trusted pinned profile. No changes to the selected model/tokenizer are implicit.
Provide bounded embedding requests with source hash, canonical ID and exact token
window/character offsets. Use one deadline across interactive stages, global
admission and no resident model. Prove multilingual paraphrases, invalid-profile
refusal, stale input rejection, long-tail window coverage and process cleanup.

Add a durable semantic queue and Lance vector store keyed by semantic unit ID,
profile identity and exact input hash. Exact publication enqueues idempotently;
only acknowledged vector publication advances semantic progress. Background work
yields to interactive requests and new facts progress while history is pending.
Qualify larger batches and actual Lance nearest-neighbor reads under guards.

