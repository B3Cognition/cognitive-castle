"""One root-hash-bound, after-only replay diagnostic; never acceptance evidence."""

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time
import types

sys.dont_write_bytecode = True
STARTED = time.monotonic()
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/lance_phase_cost_probe.py"
LAYOUT = ROOT / ".superpowers/sdd/2026-10-25-bounded-lance-layout"
RUN = LAYOUT / "task1b-history-20261025-6fa6659-run1"
SLOT = RUN / "evidence/phase-cost-events.bin"
RESULT = RUN / "evidence/phase-cost-result.json"
BASE = RUN / "evidence/phase-cost-pytest"
CONFIG = (
    ROOT / ".superpowers/sdd/2026-10-24-unified-lance-memory/layout-52mib-qualification-cold.json"
)
PINS = {
    RUN
    / "qualifications/append-171-fb5a90aaf74540004785b61f1066d34e81185cb28f3a35889b653afc408ab992.json": "e28c2ec01addeb15c8eac3cda07c1c2fc294110f762c3d2777ba5723c332b944",
    CONFIG: "d77b87e4adc71266770dc30448cceccb159b1006a060c9be68696dc48418d2dd",
    ROOT
    / "tests/test_lance_owner_stream.py": "d92b740b401683f3775bb96429f17630f2eab99fc1970b19c06b251d5d604a89",
    ROOT
    / "tests/lance_owner_stream_fixture.py": "9969a073f330558f836b46a1214b6fb95a798247121ca617b8faa4dd78161153",
    LAYOUT
    / "task1b_fixture-continuation1/final-seal-cold.json": "3b20063c42a45fa3e59ceea7436a9b3ce20950268e7e7c35989c69b0cf491390",
    LAYOUT
    / "task1b_fixture-continuation1/launch-pin-cold.json": "afd962653bf84abe0fbdf3a729d2f8bb170e278dd168219f9a19e70a6bf63cc7",
    RUN
    / "evidence/events-cold.jsonl": "3b8aa3899da2db30c7e191e2d3a947ce4e7203ef897963f93cd97987f7656094",
    RUN
    / "evidence/peaks-cold.jsonl": "345c53ec876b890ce851b7f1ca9bd3d696e825c5660fc0ef25f5a6eb9afe1362",
    RUN
    / "evidence/first-refusal-cold.json": "7b96a0396e26fb98890d96535a7fc6ce722eff7b1fd3886bc035351f91efc335",
}
NAMES = (
    "setup",
    "imports",
    "open",
    "paths",
    "geometry",
    "batch",
    "lookup",
    "proof",
    "ledger",
    "prior",
    "snapshot",
    "sample",
    "before",
    "after",
)


def script_pin(expected):
    info = SCRIPT.lstat()
    if (
        any(p.is_symlink() for p in [SCRIPT, *SCRIPT.parents])
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o022
        or info.st_size > 65536
        or hashlib.sha256(SCRIPT.read_bytes()).hexdigest() != expected
    ):
        raise ValueError("diagnostic executable pin")
    return tuple(
        getattr(info, key) for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    )


class Phases:
    def __init__(self):
        self.values = {name: [0, 0.0] for name in NAMES}

    def wrap(self, name, function):
        if name not in NAMES:
            raise ValueError("fixed phase name")

        def measured(*args, **kwargs):
            start = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                self.values[name][0] += 1
                self.values[name][1] += time.monotonic() - start

        return measured

    def report(self):
        # Fixed keys, not an iteration over a concurrently mutated dictionary.
        return {
            k: [self.values[k][0], round(self.values[k][1], 6)] for k in NAMES if self.values[k][0]
        }


def overwrite(path, value, offset, size):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > size:
        raise ValueError("bounded phase output")
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        if os.pwrite(fd, raw.ljust(size, b" "), offset) != size:
            raise ValueError("partial phase evidence")
    finally:
        os.close(fd)


class Evidence:
    def __init__(self, path=SLOT):
        self.path = path

    def rows(self):
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        if len(raw) != 32768:
            raise ValueError("precharged phase slot")
        return [
            json.loads(raw[4096 + i * 3072 : 4096 + (i + 1) * 3072])
            for i in range(9)
            if raw[4096 + i * 3072 : 4096 + (i + 1) * 3072].strip()
        ]

    def starts(self):
        stages = [row["stage"] for row in self.rows() if row.get("phase") == "start"]
        if stages != list(range(1081, 1081 + len(stages))) or len(stages) > 3:
            raise ValueError("fixed diagnostic stage sequence")
        return len(stages)

    def append(self, value, maximum):
        if len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()) + 1 > maximum:
            raise ValueError("original phase line bound")
        count = len(self.rows())
        if count >= 9:
            raise ValueError("three diagnostic calls only")
        overwrite(self.path, value, 4096 + count * 3072, 3072)

    def refusal(self):
        raw = self.path.read_bytes()[:4096]
        return json.loads(raw) if raw.strip() else None

    def refuse(self, stage, reason):
        if self.refusal() is None:
            overwrite(self.path, {"stage": stage, "reason": str(reason)[:512]}, 0, 4096)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_worker(path):
    """Execute the attested executable prelude without importing its pytest tail."""
    tree = ast.parse(path.read_bytes(), filename=str(path))
    dispatch = ast.parse("if __name__ == '__main__':\n _fixture_main()\n raise SystemExit(0)").body[
        0
    ]
    for index, node in enumerate(tree.body):
        if isinstance(node, ast.If) and ast.dump(node.test) == ast.dump(dispatch.test):
            if ast.dump(node) != ast.dump(dispatch):
                raise ValueError("original worker dispatch changed")
            module = types.ModuleType("phase_frozen_worker")
            module.__file__ = str(path)
            exec(
                compile(ast.Module(body=tree.body[:index], type_ignores=[]), str(path), "exec"),
                module.__dict__,
            )
            return module
    raise ValueError("original worker dispatch missing")


def support(expected, phases, *, child=False):
    identity = script_pin(expected)
    for path, digest in PINS.items():
        info = path.lstat()
        if (
            any(p.is_symlink() for p in [path, *path.parents])
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > 4 * 1024**2
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("retained diagnostic input changed")
    h = load(ROOT / "tests/lance_owner_stream_fixture.py", "phase_frozen_helper")
    if child:
        h.verify_continuation = phases.wrap("prior", h.verify_continuation)
    base = h.DiskLedger

    class Ledger(base):
        def __init__(self, config):
            phases.wrap("ledger", super().__init__)(config)
            if self.calls != 1080:
                raise ValueError("exact retained1080 frontier")
            self.calls += Evidence().starts()
            self.events = self.peaks = SLOT
            self.native_phases = None

        def snapshot(self, *args, **kwargs):
            name = (
                "sample"
                if threading.current_thread().name == "fixed-exact-disk-sample"
                else "snapshot"
            )
            value = phases.wrap(name, super().snapshot)(*args, **kwargs)
            if BASE.exists() and any(BASE.iterdir()):
                raise ValueError("diagnostic basetemp must remain empty")
            if kwargs.get("sampling"):
                info = SCRIPT.lstat()
                actual = tuple(
                    getattr(info, k)
                    for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
                )
            else:
                actual = script_pin(expected)
            if actual != identity:
                raise ValueError("diagnostic executable identity changed")
            info = SCRIPT.lstat()
            g = value["groups"]["harness"]
            g["entries"] += 1
            g["files"] += 1
            g["logical_bytes"] += info.st_size
            g["allocated_bytes"] += info.st_blocks * 512
            value["harness"] = max(g["logical_bytes"], g["allocated_bytes"])
            if (
                g["entries"] > 272
                or value["harness"] > 24 * 1024**2
                or sum(value[k] for k in ("source", "destination", "harness", "temp"))
                > 512 * 1024**2
            ):
                raise ValueError("charged diagnostic code envelope")
            return value

        @staticmethod
        def _append(path, value, maximum_line):
            Evidence().append(value, maximum_line)

        def before(self, *args):
            return phases.wrap("before", super().before)(*args)

        def after(self, kind, result, until):
            self.native_phases = result.pop("fixture_phase", self.native_phases)
            return phases.wrap("after", super().after)(kind, result, until)

        def refusal(self, kind, reason):
            Evidence().refuse(self.calls, reason)

    h.DiskLedger = Ledger
    return h


def worker(expected):
    import builtins

    phases = Phases()
    h = support(expected, phases, child=True)
    w = load_worker(ROOT / "tests/test_lance_owner_stream.py")
    w._fixture_support = lambda: h
    from cognitive_castle import bulk_exact_store as b, lance_exact_store as e

    for obj, attr, label in (
        (e.LanceExactStore, "_open", "open"),
        (b.OrderedBulkExactStore, "_paths", "paths"),
        (b.OrderedBulkExactStore, "_geometry", "geometry"),
        (b.BulkExactStore, "_verify_batch", "batch"),
        (b.OrderedBulkExactStore, "_verify_owner", "proof"),
        (b, "lookup_many", "lookup"),
    ):
        setattr(obj, attr, phases.wrap(label, getattr(obj, attr)))
    original_import, active = builtins.__import__, [False]

    def imported(name, *args, **kwargs):
        if name in {"lance", "pyarrow"} and name not in sys.modules and not active[0]:
            active[0] = True
            try:
                return phases.wrap("imports", original_import)(name, *args, **kwargs)
            finally:
                active[0] = False
        return original_import(name, *args, **kwargs)

    builtins.__import__ = imported
    execute = w._ordered_execute

    def ordered(request):
        phases.values["setup"] = [1, time.monotonic() - STARTED]
        result = execute(request)
        script_pin(expected)
        result["fixture_phase"] = phases.report()
        return result

    w._ordered_execute = ordered
    w._fixture_main()


def test_phase_cost_diagnostic(request):
    expected = os.environ.get("CASTLE_PHASE_PROBE_SHA256")
    phases = Phases()
    h = support(expected, phases)
    config = h.load_frozen_config(CONFIG, PINS[CONFIG])
    if Path(request.config.getoption("basetemp") or "").absolute() != BASE:
        raise ValueError("fixed fresh diagnostic basetemp")
    if any(os.path.lexists(p) for p in (SLOT, RESULT, BASE)):
        raise ValueError("fresh phase outputs required")
    h.install_host_guard()
    if not Path(config["pytest_basetemp"]).is_dir():
        raise ValueError("retained basetemp required; no new directory")
    binding = h.prepare_run(config, existing=True)
    h.host_temp(config)
    ledger = h.DiskLedger(config)
    charge = h.reserve_stage(ledger.snapshot(), "source")
    BASE.mkdir(mode=0o700)
    for path, size in ((SLOT, 32768), (RESULT, 4096)):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(b" " * size)
    if ledger.snapshot()["harness"] > charge["harness_resulting_bytes"]:
        raise ValueError("precharged phase bytes")
    book = h.QualificationBook(config, binding)

    class Session(h.FixedSession):
        def _run_stage(self, request, *, worker_command, **kwargs):
            if request.get("operation") == "ordered_import_batch":
                worker_command = [
                    sys.executable,
                    "-I",
                    str(SCRIPT),
                    "--worker",
                    expected,
                    *worker_command[3:],
                ]
            return super()._run_stage(request, worker_command=worker_command, **kwargs)

    summary = {"diagnostic_only": True, "timings_are_inclusive_overlapping_wall": True}
    started = time.monotonic()
    try:
        with Session(config, ledger, book, role="cold") as session:
            state = session.store(
                RUN / "generation", "queue_migration_state", {"job_id": book.registration["job_id"]}
            )
            h.require_resume_boundary(
                book, state, h.read_metadata(RUN / "evidence/publication-loss.json", 4096)
            )
            from cognitive_castle import migration_codec as c

            source = session.sqlite_source(
                book.registration["descriptor"], book.active["cursor_before"]
            )
            c.validate_export(source, book.registration, state["staging_cursor"])
            if c.prepare_interval(book.registration, source) != book.active:
                raise ValueError("actual regenerated pending differs")
            receipt = session.exact(
                RUN / "generation/exact",
                "import_batch",
                dict(
                    batch_id=book.active["intent_id"],
                    source_binding=config["source_binding"],
                    entries=source["entries"],
                    finalizations=source["finalizations"],
                ),
            )
            summary.update(
                receipt_matches=receipt == c.expected_receipt(book.active),
                resources=session.resources,
                fullproofs=session.actual_exact_metrics,
                shared_elapsed=time.monotonic() - started,
            )
            actual = session.actual_exact_metrics
            if len(actual) != 1 or any(
                actual[0].get(key) != value
                for key, value in {
                    "owner_proofs": 1,
                    "owner_stream_rows": [13696],
                    "proof_pending_rows": [0],
                    "batch_receipts": 171,
                    "geometry": {"version": 189, "physical_rows": 13696, "fragments": 171},
                    "verified_owner_hashes": [
                        "c137bf74258837fafd01c9347b13476b339299e2c0ffadea13ac89660dca644d"
                    ],
                }.items()
            ):
                raise ValueError("actual whole-proof evidence missing")
            if not summary["receipt_matches"]:
                raise ValueError("actual replay refused: " + str(receipt))
    except Exception as error:
        Evidence().refuse(ledger.calls, error)
        summary["refusal"] = str(error)[:512]
    script_pin(expected)
    summary.update(calls=ledger.calls, host=phases.report(), child=ledger.native_phases)
    overwrite(RESULT, summary, 0, 4096)
    print("PHASE_COST_DIAGNOSTIC", json.dumps(summary, sort_keys=True), flush=True)
    assert summary.get("receipt_matches") and ledger.calls == 1083 and "refusal" not in summary, (
        summary
    )


if __name__ == "__main__":
    if len(sys.argv) != 8 or sys.argv[1] != "--worker":
        raise SystemExit("fixed guardian diagnostic worker only")
    expected = sys.argv.pop(2)
    sys.argv.pop(1)
    worker(expected)
