"""Fake-process tests; the explicitly named native cleanup fixture needs root's slot."""

import ast
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def subject(
    *,
    ready=0.07845,
    output=b"1\n",
    returncode=0,
    waiter_at=None,
    post_read_waiter=False,
    spawn_delay=0,
    spawn_error=False,
    cleanup_error=False,
    resource_at=None,
    cleanup_delay=0,
):
    clock, children, waits, samples = [100.0], [], [], []
    signals = {"post_read": False, "cancelled_then_gone": False}

    class Pipe:
        closed = False

        def fileno(self):
            return 77

        def close(self):
            self.closed = True

    class Child:
        pid, killed, read_once = 123, False, False

        def __init__(self):
            self.stdout = Pipe()
            self.returncode = None

        def poll(self):
            if self.killed:
                self.returncode = -9
            elif clock[0] >= 100.0 + ready:
                self.returncode = returncode
            return self.returncode

        def kill(self):
            self.killed = True

        def wait(self, timeout):
            assert 0 <= timeout <= 0.05
            if cleanup_error:
                raise subprocess.TimeoutExpired("fixed-pressure-probe", timeout)
            clock[0] += cleanup_delay
            signals["cancelled_then_gone"] = True
            return self.poll()

    def popen(command, **kwargs):
        assert command == ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"]
        assert kwargs == {"stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL}
        clock[0] += spawn_delay
        if spawn_error:
            raise OSError("no probe")
        child = Child()
        children.append(child)
        return child

    class Selector:
        closed = False

        def register(self, *args):
            pass

        def unregister(self, *args):
            pass

        def select(self, timeout):
            assert 0 <= timeout <= 0.010001
            waits.append(timeout)
            clock[0] += min(timeout, max(0, 100.0 + ready - clock[0]))
            if clock[0] >= 100.0 + ready:
                return [(SimpleNamespace(fd=77), 1)]
            return []

        def close(self):
            self.closed = True

    selector = Selector()

    def read(fd, count):
        assert fd == 77 and 0 < count <= 65
        child = children[0]
        if not child.read_once:
            child.read_once = True
            return output[:count]
        signals["post_read"] = post_read_waiter
        return b""

    def waiting():
        return signals["post_read"] or (
            waiter_at is not None
            and clock[0] >= 100.0 + waiter_at
            and not signals["cancelled_then_gone"]
        )

    def resources(pid):
        samples.append(pid)
        return (
            "worker_memory_limit"
            if resource_at is not None and clock[0] >= 100 + resource_at
            else None
        )

    namespace = {
        "time": SimpleNamespace(monotonic=lambda: clock[0]),
        "json": json,
        "os": SimpleNamespace(set_blocking=lambda *args: None, read=read),
        "selectors": SimpleNamespace(DefaultSelector=lambda: selector, EVENT_READ=1),
        "subprocess": SimpleNamespace(
            Popen=popen,
            PIPE=subprocess.PIPE,
            DEVNULL=subprocess.DEVNULL,
            SubprocessError=subprocess.SubprocessError,
        ),
        "interactive_waiting": waiting,
    }
    for file, names in (
        ("brain_reader_guardian.py", {"_record_pressure_failure"}),
        ("memory_runtime.py", {"_background_pressure_refusal", "_close_pressure_probe"}),
    ):
        tree = ast.parse((ROOT / "cognitive_castle" / file).read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in nodes} == names, "cancellable pressure helper missing"
        exec(compile(ast.Module(body=nodes, type_ignores=[]), file, "exec"), namespace)
    return namespace["_background_pressure_refusal"], clock, children, selector, samples, resources


def test_normal_78450us_is_accepted_before_original_half_second_limit():
    probe, _, children, selector, samples, resources = subject()
    assert probe(102.0, {}, "host_periodic", resources) is None
    assert len(children) == 1 and not children[0].killed
    assert children[0].stdout.closed and selector.closed and samples


def test_waiter_during_wait_is_sticky_after_cleanup():
    probe, _, children, selector, _, _ = subject(ready=10, waiter_at=0.03)
    assert probe(102.0, {}, "host_periodic") == "background_preempted"
    assert (
        len(children) == 1 and children[0].killed and children[0].stdout.closed and selector.closed
    )


def test_waiter_after_read_wins_over_normal_output():
    probe, _, children, _, _, _ = subject(post_read_waiter=True)
    assert probe(102.0, {}, "host_periodic") == "background_preempted"
    assert children[0].stdout.closed


def test_ceiling_and_original_overall_deadline_both_refuse():
    for until, reason in ((102.0, "system_pressure_unavailable"), (100.04, "worker_deadline")):
        probe, clock, children, _, _, _ = subject(ready=10)
        detail = {}
        assert probe(until, detail, "host_initial") == reason
        assert clock[0] <= min(until, 100.5) + 0.00001
        assert children[0].killed and children[0].stdout.closed
        assert detail["outcome"] in {"timeout", "deadline_exhausted"}


def test_no_normal_acceptance_after_slow_spawn_consumes_whole_budget():
    probe, _, children, _, _, _ = subject(spawn_delay=0.06)
    assert probe(100.05, {}, "host_initial") == "worker_deadline"
    assert len(children) == 1 and children[0].killed


def test_normal_is_not_accepted_after_cleanup_consumes_remaining_budget():
    probe, _, children, _, _, _ = subject(cleanup_delay=0.02)
    assert probe(100.08, {}, "host_initial") == "worker_deadline"
    assert children[0].stdout.closed


def test_non_normal_nonzero_oversized_and_spawn_errors_fail_closed():
    for config in (
        {"output": b"2"},
        {"returncode": 1},
        {"output": b"1" * 65},
        {"spawn_error": True},
    ):
        probe, _, children, selector, _, _ = subject(**config)
        assert probe(102.0, {}, "host_initial") == "system_pressure_unavailable"
        assert len(children) <= 1 and selector.closed
        assert all(child.stdout.closed for child in children)


def test_resource_sampling_continues_during_wait_and_refusal_cleans_child():
    probe, _, children, _, samples, resources = subject(ready=10, resource_at=0.03)
    assert probe(102.0, {}, "host_periodic", resources) == "worker_memory_limit"
    assert len(samples) >= 3 and 123 in samples and children[0].killed


def test_failed_reap_is_not_swallowed_as_a_clean_refusal():
    probe, _, children, selector, _, _ = subject(ready=10, waiter_at=0.03, cleanup_error=True)
    try:
        probe(102.0, {}, "host_initial")
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError("cleanup failure swallowed")
    assert children[0].killed and children[0].stdout.closed and selector.closed


def test_periodic_sampler_adds_pressure_child_to_original_task_budget():
    tree = ast.parse((ROOT / "cognitive_castle/memory_runtime.py").read_text())
    sampler = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_supervisor_resource_refusal"
    )
    sampler.body = [n for n in sampler.body if not isinstance(n, ast.Import)]
    seen = []

    def process(pid):
        seen.append(pid)
        return SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=40))

    ns = {
        "_group_rss": lambda pid: 100,
        "psutil": SimpleNamespace(Process=process, NoSuchProcess=LookupError),
    }
    exec(
        compile(ast.Module(body=[sampler], type_ignores=[]), "actual-resource-sampler", "exec"), ns
    )
    parent = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=50))
    peaks = [0, 0]
    sample = ns["_supervisor_resource_refusal"]
    assert sample(parent, 999, peaks, 130, 200) is None
    assert sample(parent, 999, peaks, 130, 200, 123) == "worker_memory_limit" and seen == [123]
    assert peaks == [140, 190]


if __name__ == "__main__":
    tests = [
        v
        for k, v in list(globals().items())
        if k.startswith("test_") and not k.startswith("test_native_")
    ]
    for test in tests:
        test()
    print(json.dumps({"pure_passed": len(tests), "actual_probe_or_native_fixture_run": False}))
