"""Fault injection targets. None is registered in the production executor."""

import json
import os
from pathlib import Path

from app.core.isolation import MAX_MESSAGE_BYTES, _send_result, _WorkerResult, _worker_main


def _raise_operation(request):
    raise RuntimeError("private-test-detail-not-for-clients")


def fixture_worker(sender, request_json):
    payload = json.loads(request_json)["payload"]
    mode = payload.get("mode")
    if "ready_path" in payload:
        Path(payload["ready_path"]).write_text(str(os.getpid()), encoding="ascii")
    if mode in {"loop", "result_then_loop"}:
        if mode == "result_then_loop":
            _send_result(sender, _WorkerResult(status="success", data={"premature": True}))
        while True:
            pass
    if mode == "exception":
        import app.core.isolation as isolation
        isolation._OPERATIONS["ping"] = _raise_operation
        _worker_main(sender, request_json)
    elif mode == "crash":
        os._exit(23)
    elif mode == "no_result":
        sender.close()
    elif mode == "result_then_crash":
        _send_result(sender, _WorkerResult(status="success", data={"premature": True}))
        os._exit(23)
    elif mode == "oversize":
        sender.send_bytes(b"x" * (MAX_MESSAGE_BYTES + 1))
        sender.close()
    elif mode == "producer_limit":
        _send_result(sender, _WorkerResult(status="success", data={"text": "x" * MAX_MESSAGE_BYTES}))
        sender.close()
    elif mode == "exact_limit":
        result = _WorkerResult(status="success", data={"text": ""})
        overhead = len(json.dumps(result.model_dump(), separators=(",", ":")).encode())
        result.data["text"] = "x" * (MAX_MESSAGE_BYTES - overhead)
        _send_result(sender, result)
        sender.close()
    elif mode == "invalid_json":
        sender.send_bytes(b"not-json")
        sender.close()
    elif mode == "invalid_result":
        sender.send_bytes(b'{"status":"success","data":null}')
        sender.close()
    elif mode == "nonfinite_result":
        sender.send_bytes(b'{"status":"success","data":{"value":NaN}}')
        sender.close()
    else:
        _worker_main(sender, request_json)


def order_assumption_facts(facts):
    """Exercise a deterministic SymPy query order that exposes raw -1*0."""
    priority = ("zero", "even", "odd", "integer", "hermitian")
    facts.sort(key=lambda fact: (priority.index(fact) if fact in priority else len(priority), fact))


def ordered_assumptions_worker(sender, request_json):
    """Run the real operation with controlled query order, only in this child."""
    import importlib
    assumptions = importlib.import_module("sympy.core.assumptions")
    assumptions.shuffle = order_assumption_facts
    _worker_main(sender, request_json)


