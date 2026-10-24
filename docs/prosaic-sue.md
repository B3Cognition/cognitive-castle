# Using SUE now, and fitting it into Prosaic

SUA is assumed here to mean SUE, the Socrates Understand Engine. It has not been
removed from Castle. SUE is independent of SOAR and is deliberately outside the
optional memory provider. Installing the memory adapter does not expose or run it.

## Use the existing Castle feature

Find and inspect exact source drawers first. Then explicitly select the
requirements and context you want examined:

```bash
castle --palace /path/to/palace sue review \
  --drawer REQUIREMENT_DRAWER_ID --drawer CONTEXT_DRAWER_ID \
  --decision "Does this interpretation preserve the stated exceptions?"
castle --palace /path/to/palace sue status RUN_ID
```

The default transport is separately provisioned local Ollama, using
`qwen3.5:latest`. Codex and Claude are explicit external-provider choices; the
installed CLI/authentication and permission to send the selected source bundle
are separate operator decisions. No model call is needed just to inspect status.
Restart an old MCP server after upgrading and discover actual available tools.
The corresponding tools are `castle_sue_review` and `castle_sue_status`.

Castle freezes selected text, hashes, source mappings and revisions. Derived
reports, dialogue and call evidence live under `<palace>/.sue/runs/`, separately
from original memories. These are standalone Castle runs; the Prosaic memory
provider does not silently retrieve or resume them as Harness workflows.

Castle also already has a bounded host-assisted route. Discover
`castle_brain_capabilities`, then use `castle_problem_begin`, read its question,
schema and source pages, and submit the active assistant's structured answer via
`castle_problem_respond`. These problem operations require `protocol_version: 1`;
preserve root/session IDs and revisions for status, correction and cancellation.
This route calls no additional model inside Castle. Exposure still depends on
trusted host policy, resource budgets and the tools the connected server offers.
See `docs/brain-loop.md` and `docs/sue-scope.md` for the standalone contracts.

## A separate optional Prosaic review application

| Component | Responsibility |
| --- | --- |
| Castle | Search/fetch authorized evidence and freeze exact, source-linked bundles |
| Optional review consumer | Versioned pure SUE questions, schemas, validation and transitions; derived reports |
| Runtime | One explicitly configured model attempt per invocation, tools disabled, usage evidence |
| Harness | Accepted state, bounded progression, validation retries, receipts, interruption and resume |
| Prosaic Core | Canonical reviewer prose, packages, rendering and configuration |

Use the existing pure reducer in `cognitive_castle/brain_engine.py` as the
starting point. It already exposes incremental state/question/schema/advance
operations over the pinned vendored engine, with cross-lens equivalence tests.
The older optional review plan predates this upstream reducer; qualify and reuse
it rather than implementing another interpretation of the policy.

Do not wrap a whole `castle sue review` subprocess as one Runtime attempt. That
would leave model dispatch, retries and run state in Castle while Harness also
tries to own them. A full dialogue can involve many model calls. Instead:

1. Freeze an explicitly selected source bundle and qualify the pure reducer
   across all nine lenses, claim revisions, invalid quotations and bounded stops.
2. Execute one tool-free answer through Runtime. Keep exact candidate output and
   usage; a Harness validator independently recomputes its proposed transition.
3. Let Harness advance accepted state. Preserve rejected receipts; uncertain
   transport blocks for explicit recovery rather than silently paying twice.
   Test restart around output, receipt save and state acceptance.
4. Export source-linked advisory findings. Compare usefulness, misses, false
   positives, cost and latency with a simple one-pass reviewer before adding a
   mandatory quality gate.

This integration is planned work, not part of the memory-provider release. Keep
it independently disabled and installable; host-supplied specification bundles
need not depend on Castle or SOAR. Existing standalone SUE runs remain readable.

## Where it adds value

Use it to clarify ambiguous requirements before planning, examine conflicting
historical requirements, test an interpretation against exceptions and opposite
hypotheses, and produce concrete questions for the human. Plain memory retrieval
is sufficient for ordinary history questions and should not start a SUE run.

`RESOLVED` means the required dimensions of the current claim were examined;
it does not certify factual truth, implementation correctness, complete corpus
coverage or permission to publish. `BOUNDED_STOP` is not substantive completion.
Reports retain inferred/assumed premises and unresolved questions. A stored source
is evidence of what was said, not automatic proof that the claim is true.

Standalone limitations remain: status expiry reports interruption without
guaranteeing worker cancellation, and the source byte cap does not guarantee
context fit or useful results. Prosaic must enforce its own input/call/time
budgets and durable recovery before treating this as a supported review workflow.
