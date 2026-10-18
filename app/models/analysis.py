from typing import Literal

from app.models.domain import (
    Assumption, Identifier, Method, Model, NonEmpty, Perturbation, Problem, Step, ValidityReport,
)


class AnalysisRequest(Model):
    template_id: Identifier
    perturbation: Perturbation | None = None


class PerturbedProblem(Model):
    template_id: Identifier
    perturbation: Perturbation | None = None
    problem: Problem
    assumptions: list[Assumption]


class ExecutionInfo(Model):
    status: Literal["success", "timeout", "failed", "result_limit", "cancelled"]
    error: str | None = None
    worker_pid: int | None = None
    exit_code: int | None = None
    elapsed_seconds: float


class AnalysisResponse(Model):
    template_id: Identifier
    original_problem: Problem
    perturbed: PerturbedProblem
    replayed_steps: list[Step]
    methods: list[Method]
    report: ValidityReport
    explanations: list[NonEmpty]
    execution: ExecutionInfo | None = None
