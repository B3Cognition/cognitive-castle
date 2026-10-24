"""Synthetic supervision only; run with scripts/safe_brain_tests.py."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = str(Path(__file__).resolve().parents[1])
MAC = pytest.mark.skipif(sys.platform != "darwin", reason="macOS supervision only")


def runtime():
    return importlib.import_module("cognitive_castle.memory_runtime")


def parent(script, *args):
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys;sys.path.insert(0,{ROOT!r});" + script, *args],
        capture_output=True,
        text=True,
        timeout=12,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_fixed_budgets():
    r = runtime()
    assert r.WORKER_RSS == 128 * 1024**2
    assert r.TOTAL_RSS == 192 * 1024**2
    assert r.MAX_FRAME == 512 * 1024
    assert r.DEADLINES == dict(
        remember=3, recall=2, read_sources=2, page=2, status=2, ingest_slice=3
    )


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_unsupported_platform_fails_before_storage(tmp_path, monkeypatch, platform):
    r = runtime()
    monkeypatch.setattr(r.sys, "platform", platform)
    assert r.run_memory(tmp_path, "status", {})["reason"] == "platform_supervision_unavailable"
    assert not (tmp_path / ".memory").exists()


def test_invalid_requests_cannot_override_limits(tmp_path):
    r = runtime()
    for op, arguments in [
        ("unknown", {}),
        ("status", {"deadline": 100}),
        ("remember", {"text": "x", "request_id": "r", "rss_limit": 100000}),
    ]:
        with pytest.raises(ValueError):
            r.run_memory(tmp_path, op, arguments)
    assert not (tmp_path / ".memory").exists()


def test_admission_is_per_user():
    r = runtime()
    first = r._admission()
    try:
        with pytest.raises(BlockingIOError):
            r._admission()
    finally:
        os.close(first)


@MAC
def test_exact_store_survives_worker_invocations(tmp_path):
    result = parent(
        "from pathlib import Path;from cognitive_castle.memory_runtime import run_memory as run;"
        'p=Path(sys.argv[1]);text="hello " + "Ž👋"*1000;'
        'a=run(p,"remember",dict(request_id="one",text=text,namespace="codex"));'
        'b=run(p,"recall",dict(query="hello"));'
        'c=run(p,"page",dict(source_id=a["ids"][0],limit=2048));'
        'print(__import__("json").dumps(dict(a=a,b=b,c=c,text=text)))',
        str(tmp_path),
    )
    assert result["a"]["status"] == "ok", result
    assert result["b"]["sources"][0]["text"] == result["text"]
    assert "preview" not in result["b"]["sources"][0]["provenance"]
    assert result["c"]["text"] == result["text"][:2048]
    print(
        "CHAIN_MEASUREMENTS "
        + json.dumps({key: result[key]["resources"] for key in ("a", "b", "c")})
    )
    resources = result["b"]["resources"]
    assert 0 < resources["peak_task_rss_bytes"] <= runtime().WORKER_RSS
    assert 0 < resources["peak_total_rss_bytes"] <= runtime().TOTAL_RSS


@MAC
@pytest.mark.parametrize(
    "code,reason",
    [
        ('print("x"* (512*1024+1))', "worker_output_limit"),
        ('print(\'{"status":\',end="")', "worker_invalid_frame"),
        ("import time;time.sleep(5)", "worker_deadline"),
    ],
)
def test_output_and_time_boundaries(code, reason):
    result = parent(
        "from cognitive_castle import memory_runtime as r;import os,json;fd=r._admission();"
        f'v=r._supervise({{}},fd,worker_command=[sys.executable,"-I","-c",{code!r}],deadline=0.35);'
        "os.close(fd);print(json.dumps(v))"
    )
    assert result["status"] == "unavailable"
    assert result["reason"] == reason, result


def test_pressure_rejects_before_spawn(monkeypatch):
    r = runtime()
    monkeypatch.setattr(r, "_pressure_ok", lambda: False)
    monkeypatch.setattr(r.subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    assert r._supervise({}, -1)["reason"] == "system_pressure_unavailable"


def test_worker_import_and_network_guards():
    result = parent(
        "from cognitive_castle.memory_worker import _install_guards;_install_guards();"
        "import json,socket;out=[];"
        '\nfor action in [lambda: __import__("torch"),lambda: socket.socket(),lambda: __import__("lancedb")]:\n'
        " try: action();out.append(False)\n"
        " except (ImportError,PermissionError):out.append(True)\n"
        "print(json.dumps(out))"
    )
    assert result == [True, True, True]


@MAC
def test_complete_chain_resources_and_maximum_remember_frame(tmp_path):
    result = parent(
        "from pathlib import Path;from cognitive_castle.memory_runtime import run_memory;"
        'import json;v=run_memory(Path(sys.argv[1]),"remember",dict(request_id="large",text="x"*65536));'
        "print(json.dumps(v))",
        str(tmp_path),
    )
    assert result["status"] == "ok", result
    assert result["stored_text_bytes"] == 65536
    assert len(result["ids"]) == 8


@MAC
@pytest.mark.parametrize("death", ["host", "guardian", "deadline"])
def test_owned_descendants_die_before_admission_released(tmp_path, death):
    import time
    import psutil

    pidfile = tmp_path / "child.pid"
    code = (
        "import os,time;pid=os.fork();"
        f'open({str(pidfile)!r},"w").write(str(os.getpid())) if pid==0 else None;'
        "time.sleep(10)"
    )
    script = (
        f"import sys;sys.path.insert(0,{ROOT!r});"
        "from cognitive_castle import memory_runtime as r;"
        "fd=r._admission();"
        f'r._supervise({{}},fd,worker_command=[sys.executable,"-I","-c",{code!r}],deadline={0.6 if death == "deadline" else 3});'
        "import os;os.close(fd)"
    )
    host = subprocess.Popen([sys.executable, "-I", "-c", script], stdout=subprocess.DEVNULL)
    try:
        end = time.monotonic() + 2
        while not pidfile.exists() and time.monotonic() < end:
            time.sleep(0.01)
        assert pidfile.exists()
        descendant = psutil.Process(int(pidfile.read_text()))
        worker = descendant.parent()
        guardian = worker.parent()
        with pytest.raises(BlockingIOError):
            runtime()._admission()
        if death == "host":
            host.kill()
        elif death == "guardian":
            guardian.kill()
        host.wait(timeout=4)
        end = time.monotonic() + 2
        while (
            descendant.is_running()
            and descendant.status() != psutil.STATUS_ZOMBIE
            and time.monotonic() < end
        ):
            time.sleep(0.01)
        assert not descendant.is_running() or descendant.status() == psutil.STATUS_ZOMBIE
        replacement = runtime()._admission()
        os.close(replacement)
    finally:
        if host.poll() is None:
            host.kill()
            host.wait(timeout=2)


@MAC
def test_worker_rss_tripwire_fixed_production_budget():
    result = parent(
        "from cognitive_castle import memory_runtime as r;import os,json;fd=r._admission();"
        'v=r._supervise({},fd,worker_command=[sys.executable,"-I","-c",'
        '"import time;allocation=bytearray(112*1024**2);time.sleep(5)"],deadline=2);'
        "os.close(fd);print(json.dumps(v))"
    )
    assert result["reason"] == "worker_memory_limit", result


@MAC
def test_over_budget_parent_rejects_before_storage(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import psutil

    # Inject only the OS measurement boundary; production budgets stay fixed.
    monkeypatch.setattr(runtime(), "_pressure_ok", lambda: True)
    monkeypatch.setattr(
        psutil,
        "Process",
        lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=192 * 1024**2)),
    )
    monkeypatch.setattr(runtime().subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    result = runtime().run_memory(tmp_path, "remember", dict(request_id="one", text="hello"))
    assert result["reason"] == "parent_memory_limit", result
    assert not (tmp_path / ".memory").exists()


def test_sqlite_heap_setting_never_changes_parent():
    import sqlite3

    conn = sqlite3.connect(":memory:")
    before = conn.execute("PRAGMA hard_heap_limit").fetchone()[0]
    result = parent(
        "from cognitive_castle.memory_worker import _sqlite_heap_limit;"
        'import sqlite3,json;_sqlite_heap_limit();c=sqlite3.connect(":memory:");'
        'print(json.dumps(c.execute("PRAGMA hard_heap_limit").fetchone()[0]))'
    )
    assert 0 < result <= 32 * 1024**2
    assert conn.execute("PRAGMA hard_heap_limit").fetchone()[0] == before
    conn.close()


@MAC
def test_oversized_guardian_config_rejected_before_worker(tmp_path):
    import signal

    guardian = Path(runtime().__file__).with_name("brain_reader_guardian.py")
    proc = subprocess.Popen(
        [sys.executable, "-I", str(guardian)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        try:
            proc.stdin.write(b"x" * (512 * 1024 + 1))
            proc.stdin.flush()
        except BrokenPipeError:
            pass
        proc.wait(timeout=2)
        assert proc.returncode != 0
        assert proc.stdout.read() == b""
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.stdout.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)


@MAC
def test_concurrent_operation_returns_busy_without_storage(tmp_path):
    fd = runtime()._admission()
    try:
        result = runtime().run_memory(tmp_path, "status", {})
        assert result == {"status": "unavailable", "reason": "memory_busy"}
        assert not (tmp_path / ".memory").exists()
    finally:
        os.close(fd)


@MAC
def test_partial_guardian_config_has_deadline():
    import time
    import signal

    guardian = Path(runtime().__file__).with_name("brain_reader_guardian.py")
    proc = subprocess.Popen(
        [sys.executable, "-I", str(guardian)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        started = time.monotonic()
        proc.stdin.write(b'{"request":')
        proc.stdin.flush()
        proc.wait(timeout=2)
        assert time.monotonic() - started < 2
        assert proc.returncode != 0
    finally:
        proc.stdin.close()
        proc.stdout.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)


@MAC
def test_missing_resource_support_fails_before_storage(tmp_path, monkeypatch):
    r = runtime()
    monkeypatch.setattr(r.importlib.util, "find_spec", lambda _: None)
    assert r.run_memory(tmp_path, "status", {})["reason"] == "platform_supervision_unavailable"
    assert not (tmp_path / ".memory").exists()


@MAC
def test_pressure_change_stops_worker():
    # Use a small parent subprocess to avoid charging the pytest harness to the
    # production host budget. Pressure changing is injected only at OS boundary.
    result = parent(
        "from cognitive_castle import memory_runtime as r;import os,json;"
        "checks=iter([True,False]);r._pressure_ok=lambda:next(checks,False);"
        'fd=r._admission();v=r._supervise({},fd,worker_command=[sys.executable,"-I","-c",'
        '"import time;time.sleep(5)"],deadline=2);os.close(fd);print(json.dumps(v))'
    )
    assert result["reason"] == "system_pressure_unavailable"


@MAC
def test_live_total_budget_rejects_before_sidecar_open(tmp_path):
    result = parent(
        "from pathlib import Path;from cognitive_castle.memory_runtime import run_memory;"
        "import json;allocation=bytearray(144*1024**2);"
        'print(json.dumps(run_memory(Path(sys.argv[1]),"remember",dict(request_id="one",text="hello"))))',
        str(tmp_path),
    )
    assert result["status"] == "unavailable", result
    assert result["reason"] == "total_memory_limit", result
    assert not (tmp_path / ".memory").exists()


@MAC
def test_ingest_and_status_dispatch_only_trusted_paths(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "synthetic apricot 👋"}],
                },
            }
        )
        + "\n"
    )
    result = parent(
        "from pathlib import Path;from cognitive_castle.memory_runtime import run_memory as run;"
        "import json;p=Path(sys.argv[1]);"
        'a=run(p,"ingest_slice",dict(path=str(p/"session.jsonl"),allowed_root=str(p),format="codex"));'
        'b=run(p,"status",{});c=run(p,"recall",dict(query="apricot"));'
        'd=run(p,"read_sources",dict(ids=[s["id"] for s in c.get("sources",[])]));'
        "print(json.dumps(dict(a=a,b=b,c=c,d=d)))",
        str(tmp_path),
    )
    assert result["a"]["status"] == "ok", result
    assert result["b"]["indexed_chunks"] == 1
    assert result["c"]["sources"][0]["text"] == "synthetic apricot 👋"
    assert result["d"]["sources"] == result["c"]["sources"]


@MAC
@pytest.mark.parametrize("phase", ["config", "request"])
def test_stalled_large_ipc_write_obeys_deadline(phase):
    setup = ""
    if phase == "config":
        setup = (
            "r._pressure_ok=lambda:True;original=r.subprocess.Popen;"
            "r.subprocess.Popen=lambda command,**kw:original("
            '[sys.executable,"-I","-c","import time;time.sleep(3)"],**kw);'
        )
    result = parent(
        "from cognitive_castle import memory_runtime as r;import os,json,time;"
        + setup
        + "fd=r._admission();started=time.monotonic();"
        'v=r._supervise({"payload":"x"*300000},fd,worker_command='
        '[sys.executable,"-I","-c","import time;time.sleep(3)"],deadline=0.4);'
        "os.close(fd);print(json.dumps(dict(result=v,elapsed=time.monotonic()-started)))"
    )
    assert result["elapsed"] < 1.5, result
    assert result["result"]["reason"] == "worker_deadline", result


@MAC
def test_host_death_during_large_request_forwarding(tmp_path):
    import signal
    import time
    import psutil

    pidfile = tmp_path / "worker.pid"
    code = f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(8)'
    script = (
        f"import sys;sys.path.insert(0,{ROOT!r});"
        "from cognitive_castle import memory_runtime as r;fd=r._admission();"
        'r._supervise({"payload":"x"*300000},fd,worker_command='
        f'[sys.executable,"-I","-c",{code!r}],deadline=2)'
    )
    host = subprocess.Popen([sys.executable, "-I", "-c", script])
    guardian = None
    try:
        end = time.monotonic() + 2
        while not pidfile.exists() and time.monotonic() < end:
            time.sleep(0.01)
        assert pidfile.exists()
        worker = psutil.Process(int(pidfile.read_text()))
        guardian = worker.parent()
        time.sleep(0.1)  # Let forwarding fill the stalled worker's pipe.
        host.kill()
        host.wait(timeout=1)
        end = time.monotonic() + 2.2
        while (
            guardian.is_running()
            and guardian.status() != psutil.STATUS_ZOMBIE
            and time.monotonic() < end
        ):
            time.sleep(0.01)
        assert not guardian.is_running() or guardian.status() == psutil.STATUS_ZOMBIE
        assert not worker.is_running() or worker.status() == psutil.STATUS_ZOMBIE
        fd = runtime()._admission()
        os.close(fd)
    finally:
        if guardian:
            try:
                os.killpg(guardian.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if host.poll() is None:
            host.kill()
            host.wait(timeout=1)


@MAC
def test_guardian_deadline_while_worker_never_reads(tmp_path):
    import signal
    import time

    fd = runtime()._admission()
    guardian = Path(runtime().__file__).with_name("brain_reader_guardian.py")
    code = "import time;time.sleep(3)"
    config = dict(
        request={"payload": "x" * 300000},
        command=[sys.executable, "-I", "-c", code],
        admission=fd,
        deadline=0.4,
        rss_limit=runtime().WORKER_RSS,
        max_frame=runtime().MAX_FRAME,
        parent_pid=os.getpid(),
        total_rss_limit=runtime().TOTAL_RSS,
    )
    proc = subprocess.Popen(
        [sys.executable, "-I", str(guardian)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        pass_fds=(fd,),
    )
    try:
        started = time.monotonic()
        proc.stdin.write(json.dumps(config).encode() + b"\n")
        proc.stdin.flush()  # Keep controller EOF open; only guardian enforces time.
        proc.wait(timeout=1.5)
        assert time.monotonic() - started < 1.5
        assert json.loads(proc.stdout.read())["reason"] == "worker_deadline"
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=1)
        proc.stdin.close()
        proc.stdout.close()
        os.close(fd)
    replacement = runtime()._admission()
    os.close(replacement)
