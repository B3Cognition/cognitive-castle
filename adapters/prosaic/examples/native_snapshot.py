"""Native runtime gets an explicit frozen source bundle as assignment data."""

import json


def run_frozen(runtime, artifact, bundle, *, question, cwd, policy):
    """Reuse the same persisted bundle on resume; this function cannot retrieve."""
    assignment = json.dumps(
        {"question": question, "memory": bundle},
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )
    return runtime.run(artifact, assignment, cwd=cwd, policy=policy)
