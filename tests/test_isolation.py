import multiprocessing as mp
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.isolation import (
    MAX_MESSAGE_BYTES, CapacityExceeded, CleanupError, ComputationExecutor,
    ComputationRequest, ExecutorClosed, _Job,
)
from app.main import create_app
from tests.isolation_workers import fixture_worker


@pytest.fixture
def executor_factory():
    executors = []

    def make(**kwargs):
        executor = ComputationExecutor(**kwargs)
        executors.append(executor)
        return executor

    yield make
    for executor in executors:
        executor.close()


def request(mode=None, **payload):
    if mode is not None:
        payload["mode"] = mode
    return ComputationRequest(operation="ping", payload=payload)


def wait_ready(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(encoding="ascii")
            if text:
                return int(text)
        time.sleep(0.01)
    pytest.fail("Spawn worker did not report ready")


def assert_reaped(executor, *pids):
    assert executor.active_count == 0
    assert not set(pids) & {child.pid for child in mp.active_children()}
    assert not any(
        thread.name in {f"one-twist-result-{pid}" for pid in pids}
        for thread in threading.enumerate()
    )


def test_normal_result_runs_in_a_fresh_spawn_process(executor_factory):
    executor = executor_factory()
    result = executor.run(request(text="__import__('os') is just data", fraction="1/2"))
    assert result.status == "success"
    assert result.worker_pid != os.getpid()
    assert result.data["pid"] == result.worker_pid
    assert result.data["start_method"] == "spawn"
    assert result.data["payload"]["fraction"] == "1/2"
    assert result.exit_code == 0
    assert_reaped(executor, result.worker_pid)


def test_operations_are_allowlisted():
    with pytest.raises(ValidationError):
        ComputationRequest(operation="loop")
    with pytest.raises(ValidationError):
        ComputationRequest(operation="ping", timeout_seconds=999)


def test_oversized_input_releases_capacity_without_a_worker(executor_factory):
    executor = executor_factory()
    before = {child.pid for child in mp.active_children()}
    with pytest.raises(ValueError, match="64 KiB"):
        executor.run(request(text="x" * MAX_MESSAGE_BYTES))
    assert_reaped(executor)
    assert before == {child.pid for child in mp.active_children()}
    assert executor.run(request()).status == "success"


def test_nonfinite_input_is_rejected_without_leaking_capacity(executor_factory):
    executor = executor_factory()
    with pytest.raises(ValueError):
        executor.run(request(value=float("nan")))
    assert_reaped(executor)


@pytest.mark.parametrize("mode,status,error,exit_code", [
    ("exception", "failed", "worker_exception", 0),
    ("crash", "failed", "worker_exit", 23),
    ("no_result", "failed", "missing_result", 0),
    ("result_then_crash", "failed", "worker_exit", 23),
    ("producer_limit", "result_limit", "result_too_large", 0),
    ("oversize", "result_limit", "result_too_large", None),
    ("invalid_json", "failed", "invalid_result", 0),
    ("invalid_result", "failed", "invalid_result", 0),
    ("nonfinite_result", "failed", "invalid_result", 0),
])
def test_failures_are_explicit_and_reaped(executor_factory, mode, status, error, exit_code):
    executor = executor_factory(_worker_target=fixture_worker)
    result = executor.run(request(mode))
    assert result.status == status
    assert result.error == error
    assert result.data is None
    if exit_code is not None:
        assert result.exit_code == exit_code
    assert "private-test-detail" not in result.error
    assert_reaped(executor, result.worker_pid)


def test_exact_64_kib_result_is_drained_without_join_deadlock(executor_factory):
    executor = executor_factory(_worker_target=fixture_worker)
    result = executor.run(request("exact_limit"))
    assert result.status == "success"
    assert len(result.data["text"]) > 60_000
    assert_reaped(executor, result.worker_pid)


@pytest.mark.parametrize("mode", ["loop", "result_then_loop"])
def test_running_loop_is_terminated_and_capacity_recovers(executor_factory, tmp_path, mode, record_property):
    executor = executor_factory(_worker_target=fixture_worker)
    marker = tmp_path / "ready"
    with ThreadPoolExecutor(max_workers=1) as threads:
        task = threads.submit(executor.run, request(mode, ready_path=str(marker)))
        pid = wait_ready(marker)
        assert not task.done(), "The loop must actually be executing before timeout"
        result = task.result(timeout=6)
    assert result.worker_pid == pid
    assert result.status == "timeout"
    assert result.error == "deadline_exceeded"
    assert result.exit_code is not None
    assert result.elapsed_seconds < 5
    record_property("elapsed_seconds", result.elapsed_seconds)
    assert_reaped(executor, pid)
    assert executor.run(request()).status == "success"
    assert_reaped(executor, pid)


def test_deadline_includes_spawn_startup(executor_factory, monkeypatch):
    executor = executor_factory(timeout_seconds=0.05)
    original_process = executor._context.Process

    def delayed_process(*args, **kwargs):
        time.sleep(0.1)
        return original_process(*args, **kwargs)

    monkeypatch.setattr(executor._context, "Process", delayed_process)
    result = executor.run(request())
    assert result.status == "timeout"
    assert result.elapsed_seconds < 2
    assert_reaped(executor, result.worker_pid)


def test_two_workers_fill_capacity_and_third_does_not_queue(executor_factory, tmp_path, record_property):
    executor = executor_factory(timeout_seconds=10, _worker_target=fixture_worker)
    markers = [tmp_path / f"ready-{i}" for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as threads:
        tasks = [threads.submit(executor.run, request("loop", ready_path=str(marker))) for marker in markers]
        try:
            pids = [wait_ready(marker) for marker in markers]
            assert executor.active_count == 2
            started = time.monotonic()
            with pytest.raises(CapacityExceeded):
                executor.run(request())
            elapsed = time.monotonic() - started
            assert elapsed < 0.25
            record_property("rejection_seconds", elapsed)
            assert executor.active_count == 2
        finally:
            executor.close()
        assert all(task.result(timeout=2).status == "cancelled" for task in tasks)
    assert_reaped(executor, *pids)


def test_http_capacity_is_503_and_get_remains_responsive(tmp_path, record_property):
    executor = ComputationExecutor(timeout_seconds=10, _worker_target=fixture_worker)
    app = create_app(computation_executor=executor)

        # This probe route only exists in this test app; production analysis
        # accepts a template-bound request, never an arbitrary fixture command.
    @app.post("/__test__/computation")
    def probe(body: ComputationRequest):
        return app.state.computations.run(body)

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as threads:
        markers = [tmp_path / f"http-ready-{i}" for i in range(2)]
        tasks = [threads.submit(client.post, "/__test__/computation", json=request("loop", ready_path=str(marker)).model_dump()) for marker in markers]
        try:
            pids = [wait_ready(marker) for marker in markers]
            started = time.monotonic()
            response = client.get("/api/templates")
            get_elapsed = time.monotonic() - started
            assert response.status_code == 200 and len(response.json()) == len(app.state.templates)
            assert get_elapsed < 1
            record_property("get_seconds", get_elapsed)
            started = time.monotonic()
            response = client.post("/__test__/computation", json=request().model_dump())
            rejection_elapsed = time.monotonic() - started
            assert response.status_code == 503
            assert rejection_elapsed < 1
            record_property("http_rejection_seconds", rejection_elapsed)
        finally:
            executor.close()
        assert all(task.result(timeout=2).json()["status"] == "cancelled" for task in tasks)
    assert_reaped(executor, *pids)


def test_app_shutdown_reclaims_running_worker(tmp_path):
    executor = ComputationExecutor(timeout_seconds=10, _worker_target=fixture_worker)
    marker = tmp_path / "shutdown-ready"
    with ThreadPoolExecutor(max_workers=1) as threads:
        with TestClient(create_app(computation_executor=executor)):
            task = threads.submit(executor.run, request("loop", ready_path=str(marker)))
            pid = wait_ready(marker)
            assert not task.done()
        assert task.result(timeout=2).status == "cancelled"
    assert_reaped(executor, pid)
    with pytest.raises(ExecutorClosed):
        executor.run(request())
    executor.close()  # Successful shutdown is idempotent.


def test_pipe_creation_failure_releases_capacity(executor_factory, monkeypatch):
    executor = executor_factory()
    before = {child.pid for child in mp.active_children()}

    def broken_pipe(*args, **kwargs):
        raise OSError("simulated pipe resource exhaustion")

    with monkeypatch.context() as patch:
        patch.setattr(executor._context, "Pipe", broken_pipe)
        result = executor.run(request())
    assert result.status == "failed" and result.error == "worker_start_failed"
    assert result.worker_pid is None
    assert_reaped(executor)
    assert before == {child.pid for child in mp.active_children()}
    assert executor.run(request()).status == "success"


@pytest.mark.skipif(os.name != "nt", reason="Windows spawn private-interface regression")
@pytest.mark.parametrize("error_type", [ImportError, AttributeError])
def test_windows_writer_interface_failure_releases_capacity(executor_factory, monkeypatch, error_type):
    import multiprocessing.context

    executor = executor_factory()
    before = {child.pid for child in mp.active_children()}

    def broken_spawning_popen():
        raise error_type("simulated unavailable spawn interface")

    with monkeypatch.context() as patch:
        patch.setattr(multiprocessing.context, "get_spawning_popen", broken_spawning_popen)
        result = executor.run(request())
    assert result.status == "failed" and result.error == "worker_start_failed"
    assert_reaped(executor)
    assert before == {child.pid for child in mp.active_children()}
    assert executor.run(request()).status == "success"


def test_worker_start_failure_releases_capacity(executor_factory, monkeypatch):
    executor = executor_factory()
    original_process = executor._context.Process

    def broken_process(*args, **kwargs):
        process = original_process(*args, **kwargs)

        def fail():
            raise OSError("simulated spawn failure")

        process.start = fail
        return process

    with monkeypatch.context() as patch:
        patch.setattr(executor._context, "Process", broken_process)
        result = executor.run(request())
    assert result.status == "failed" and result.error == "worker_start_failed"
    assert_reaped(executor)
    assert executor.run(request()).status == "success"


@pytest.mark.skipif(os.name != "nt", reason="Windows spawn handle ownership regression")
def test_repeated_early_termination_does_not_leak_windows_handles(executor_factory, record_property):
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetProcessHandleCount.restype = wintypes.BOOL

    def handle_count():
        count = wintypes.DWORD()
        assert kernel32.GetProcessHandleCount(kernel32.GetCurrentProcess(), ctypes.byref(count))
        return count.value

    executor = executor_factory(timeout_seconds=0.05)
    before = handle_count()
    results = [executor.run(request()) for _ in range(8)]
    after = handle_count()
    assert all(result.status == "timeout" for result in results)
    assert all(result.worker_pid is not None for result in results)
    assert_reaped(executor, *(result.worker_pid for result in results))
    # Small allowance for unrelated runtime housekeeping; a stranded writer
    # per termination would grow linearly beyond this bound.
    assert after <= before + 2
    record_property("handle_count_before", before)
    record_property("handle_count_after", after)


def test_cleanup_escalates_when_first_termination_does_not_stop_worker():
    calls = []

    class ProcessNeedingKill:
        pid = 123
        exitcode = None
        alive = True

        def is_alive(self):
            return self.alive

        def terminate(self):
            calls.append("terminate")

        def join(self, timeout):
            calls.append(("join", timeout))
            if "kill" in calls:
                self.alive = False
                self.exitcode = -9

        def kill(self):
            calls.append("kill")

        def close(self):
            assert not self.alive
            calls.append("close")

    job = _Job(process=ProcessNeedingKill())
    ComputationExecutor._cleanup(job)
    assert calls == ["terminate", ("join", 0.5), "kill", ("join", 0.5), "close"]
    assert job.exit_code == -9


def test_cleanup_failure_stops_admission_without_claiming_a_free_slot(monkeypatch):
    executor = ComputationExecutor()
    cleanup = executor._cleanup

    def cleanup_then_report_failure(job):
        cleanup(job)  # Reap real resources even while testing the failure policy.
        raise OSError("simulated cleanup failure")

    monkeypatch.setattr(executor, "_cleanup", cleanup_then_report_failure)
    with pytest.raises(CleanupError):
        executor.run(request())
    assert executor.active_count == 1
    with pytest.raises(CleanupError, match="restart"):
        executor.run(request())
    with pytest.raises(CleanupError, match="not fully reclaimed"):
        executor.close()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_deadlines_are_rejected(value):
    with pytest.raises(ValueError, match="positive and finite"):
        ComputationExecutor(timeout_seconds=value)


def test_invalid_capacity_is_rejected():
    with pytest.raises(ValueError, match="positive integer"):
        ComputationExecutor(max_concurrency=0)
