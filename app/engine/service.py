"""HTTP-facing boundary: validate the change, then compute only in a child."""

import logging

from pydantic import ValidationError

from app.core.isolation import ComputationExecutor, ComputationRequest
from app.engine.classifier import unverified_response
from app.engine.perturbation import construct_problem
from app.models.analysis import AnalysisResponse, ExecutionInfo
from app.models.domain import Perturbation, Template

logger = logging.getLogger(__name__)


def analyze_isolated(template: Template, perturbation: Perturbation | None, executor: ComputationExecutor) -> AnalysisResponse:
    perturbed = construct_problem(template, perturbation)
    content = template.model_dump(mode="json")
    # Expected content outcomes are test metadata, absent from worker evidence.
    content["expected_failure_mechanisms"] = []
    result = executor.run(ComputationRequest(operation="analyze", payload={
        "template": content,
        "perturbation": perturbed.perturbation.model_dump(mode="json") if perturbed.perturbation else None,
    }))
    response = None
    if result.status == "success":
        try:
            response = AnalysisResponse.model_validate(result.data)
        except ValidationError:
            logger.exception("Worker returned an invalid analysis response")
    if response is None:
        reason = result.error or "invalid_worker_response"
        response = unverified_response(template, perturbed, f"Computation could not verify the mathematics: {reason}.")
    response.execution = ExecutionInfo(
        status=result.status, error=result.error, worker_pid=result.worker_pid,
        exit_code=result.exit_code, elapsed_seconds=result.elapsed_seconds,
    )
    return response
