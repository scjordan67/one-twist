"""Disposable spawn workers with bounded JSON and parent-owned deadlines.

Worker target injection accepts trusted application/test code, never HTTP input.
"""

import json
import logging
import math
import multiprocessing as mp
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

logger = logging.getLogger(__name__)
MAX_MESSAGE_BYTES = 64 * 1024
CLEANUP_GRACE_SECONDS = 0.5
POLL_SECONDS = 0.02


class ComputationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["ping", "analyze"]
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class _Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "timeout", "failed", "result_limit", "cancelled"]
    data: dict[str, JsonValue] | None = None
    error: str | None = None


class _WorkerResult(_Outcome):
    status: Literal["success", "failed", "result_limit"]

    @model_validator(mode="after")
    def consistent_status(self):
        if self.status == "success":
            if self.data is None or self.error is not None:
                raise ValueError("Success requires data and no error")
        elif not self.error or self.data is not None:
            raise ValueError("Failure requires an error and no data")
        return self


@dataclass(frozen=True)
class ComputationResult:
    status: Literal["success", "timeout", "failed", "result_limit", "cancelled"]
    data: dict[str, JsonValue] | None
    error: str | None
    worker_pid: int | None
    exit_code: int | None
    elapsed_seconds: float


class ExecutorUnavailable(RuntimeError):
    """The server cannot admit this computation (HTTP 503 at the API boundary)."""


class CapacityExceeded(ExecutorUnavailable):
    pass


class ExecutorClosed(ExecutorUnavailable):
    pass


class CleanupError(ExecutorUnavailable):
    pass


def _encode_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _send_result(sender: Connection, result: _WorkerResult) -> None:
    message = _encode_json(result.model_dump())
    if len(message) > MAX_MESSAGE_BYTES:
        message = _encode_json({"status": "result_limit", "error": "result_too_large"})
    sender.send_bytes(message)


def _ping(request: ComputationRequest) -> dict[str, JsonValue]:
    return {"pid": os.getpid(), "start_method": mp.get_start_method(), "payload": request.payload}


def _analyze(request: ComputationRequest) -> dict[str, JsonValue]:
    # Import mathematical orchestration in the child when requested. Payload
    # comes from server-owned templates, never a client-supplied proof/verdict.
    from app.engine.classifier import analyze
    from app.models.domain import Perturbation, Template

    template = Template.model_validate(request.payload["template"])
    data = request.payload.get("perturbation")
    perturbation = Perturbation.model_validate(data) if data is not None else None
    return analyze(template, perturbation).model_dump(mode="json")


# Fault injection belongs exclusively to tests, not to this operation registry.
_OPERATIONS: dict[str, Callable[[ComputationRequest], dict[str, JsonValue]]] = {"ping": _ping, "analyze": _analyze}


def _worker_main(sender: Connection, request_json: bytes) -> None:
    try:
        if len(request_json) > MAX_MESSAGE_BYTES:
            raise ValueError("Request exceeds message limit")
        request = ComputationRequest.model_validate_json(request_json)
        data = _OPERATIONS[request.operation](request)
        _send_result(sender, _WorkerResult(status="success", data=data))
    except Exception:
        logger.exception("Isolated worker failed")
        try:
            _send_result(sender, _WorkerResult(status="failed", error="worker_exception"))
        except (OSError, ValueError):
            logger.exception("Could not send isolated worker failure")
    finally:
        sender.close()


@dataclass(eq=False)
class _Job:
    stop: threading.Event = field(default_factory=threading.Event)
    received: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    process: BaseProcess | None = None
    connection: Connection | None = None
    reader: threading.Thread | None = None
    message: bytes | None = None
    read_error: str | None = None
    pid: int | None = None
    exit_code: int | None = None


def _rebuild_windows_writer(handle: int):
    from multiprocessing.connection import PipeConnection
    return PipeConnection(handle, readable=False)


class _WindowsSpawnWriter:
    """Duplicate directly into the spawned child, not into a parent escrow.

    CPython's default PipeConnection reducer creates a parent-owned DupHandle
    which the child later steals. Killing the child before unpickling would
    strand that writer in the parent and prevent the result reader seeing EOF.
    The spawn process launcher already supports child-owned handle duplication.
    """

    def __init__(self, connection: Connection):
        self.connection = connection

    def __reduce__(self):
        from multiprocessing.context import get_spawning_popen
        handle = get_spawning_popen().duplicate_for_child(self.connection.fileno())
        return _rebuild_windows_writer, (handle,)


def _receive(job: _Job) -> None:
    try:
        job.message = job.connection.recv_bytes(MAX_MESSAGE_BYTES)
    except EOFError:
        job.read_error = "missing_result"
    except OSError as exc:
        # CPython recv_bytes(maxlength) rejects an oversized frame this way.
        job.read_error = "result_too_large" if str(exc) == "bad message length" else "pipe_error"
    finally:
        job.received.set()


def _reject_nonfinite(value: str):
    raise ValueError(f"Non-finite JSON constant: {value}")


def _decode_result(message: bytes) -> _WorkerResult:
    try:
        data = json.loads(message, parse_constant=_reject_nonfinite)
        return _WorkerResult.model_validate(data)
    except (ValueError, TypeError, RecursionError):
        return _WorkerResult(status="failed", error="invalid_result")


class ComputationExecutor:
    def __init__(
        self,
        *,
        timeout_seconds: float = 3.0,
        max_concurrency: int = 2,
        _worker_target: Callable[[Connection, bytes], None] = _worker_main,
    ):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if not isinstance(max_concurrency, int) or max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer")
        self.timeout_seconds = timeout_seconds
        self.max_concurrency = max_concurrency
        self._worker_target = _worker_target
        self._context = mp.get_context("spawn")
        self._lock = threading.Lock()
        self._jobs: set[_Job] = set()
        self._closed = False
        self._broken = False

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._jobs)

    def run(self, request: ComputationRequest) -> ComputationResult:
        with self._lock:
            if self._closed:
                raise ExecutorClosed("Computation service is shutting down")
            if self._broken:
                raise CleanupError("Computation service requires restart after cleanup failure")
            if len(self._jobs) >= self.max_concurrency:
                raise CapacityExceeded("Computation capacity is full; try again later")
            job = _Job()
            self._jobs.add(job)

        started = time.monotonic()
        deadline = started + self.timeout_seconds
        try:
            request_json = _encode_json(request.model_dump())
            if len(request_json) > MAX_MESSAGE_BYTES:
                raise ValueError("Request exceeds 64 KiB message limit")
            result = self._execute(job, request_json, deadline)
        finally:
            try:
                self._cleanup(job)
            except Exception as exc:
                logger.exception("Isolated worker cleanup failed")
                with self._lock:
                    self._broken = True
                # Keep the occupied slot and refuse new work when resource
                # recovery is uncertain, instead of silently overcommitting.
                raise CleanupError("Could not reclaim isolated computation resources") from exc
            else:
                with self._lock:
                    self._jobs.remove(job)
            finally:
                job.done.set()

        return ComputationResult(
            status=result.status, data=result.data, error=result.error,
            worker_pid=job.pid, exit_code=job.exit_code,
            elapsed_seconds=time.monotonic() - started,
        )

    def _execute(self, job: _Job, request_json: bytes, deadline: float) -> _Outcome:
        if job.stop.is_set():
            return _Outcome(status="cancelled", error="service_shutdown")
        if time.monotonic() >= deadline:
            return _Outcome(status="timeout", error="deadline_exceeded")
        try:
            receiver, sender = self._context.Pipe(duplex=False)
            job.connection = receiver
            try:
                writer = _WindowsSpawnWriter(sender) if os.name == "nt" else sender
                process = self._context.Process(target=self._worker_target, args=(writer, request_json), daemon=True)
                job.process = process
                process.start()
                job.pid = process.pid
            finally:
                # After worker exit, EOF must wake the reader. Retaining a
                # writer copy in the parent would prevent that.
                sender.close()
            reader = threading.Thread(target=_receive, args=(job,), name=f"one-twist-result-{job.pid}", daemon=True)
            reader.start()
            job.reader = reader
        except (OSError, RuntimeError, ImportError, AttributeError):
            logger.exception("Could not start isolated computation")
            return _WorkerResult(status="failed", error="worker_start_failed")

        while True:
            if job.stop.is_set():
                return _Outcome(status="cancelled", error="service_shutdown")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return _Outcome(status="timeout", error="deadline_exceeded")
            if job.received.is_set():
                if job.read_error:
                    if job.read_error == "missing_result":
                        if process.is_alive():
                            job.stop.wait(min(POLL_SECONDS, remaining))
                            continue
                        process.join(0)
                        if process.exitcode != 0:
                            return _WorkerResult(status="failed", error="worker_exit")
                    status = "result_limit" if job.read_error == "result_too_large" else "failed"
                    return _WorkerResult(status=status, error=job.read_error)
                if not process.is_alive():
                    process.join(0)
                    if process.exitcode != 0:
                        return _WorkerResult(status="failed", error="worker_exit")
                    return _decode_result(job.message)
            job.stop.wait(min(POLL_SECONDS, remaining))

    @staticmethod
    def _cleanup(job: _Job) -> None:
        process = job.process
        if process is not None:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                    process.join(CLEANUP_GRACE_SECONDS)
                    if process.is_alive():
                        process.kill()
                        process.join(CLEANUP_GRACE_SECONDS)
                else:
                    process.join(0)
                if process.is_alive():
                    raise CleanupError("Worker is still alive")
                job.exit_code = process.exitcode
            process.close()
        if job.reader is not None:
            job.reader.join(CLEANUP_GRACE_SECONDS)
            if job.reader.is_alive():
                raise CleanupError("Result reader did not exit after worker termination")
        if job.connection is not None:
            job.connection.close()

    def close(self, *, timeout_seconds: float = 3.0) -> None:
        """Stop admission and let each owning supervisor reap its worker."""
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Shutdown timeout must be positive and finite")
        with self._lock:
            self._closed = True
            jobs = list(self._jobs)
            for job in jobs:
                job.stop.set()
        deadline = time.monotonic() + timeout_seconds
        for job in jobs:
            if not job.done.wait(max(0, deadline - time.monotonic())):
                raise CleanupError("Computation shutdown deadline exceeded")
        with self._lock:
            if self._jobs or self._broken:
                raise CleanupError("Computation resources were not fully reclaimed")
