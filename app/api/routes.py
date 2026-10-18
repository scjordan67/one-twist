from fastapi import APIRouter, HTTPException, Request

from app.models import PublicTemplate, TemplateSummary
from app.models.analysis import AnalysisRequest, AnalysisResponse
from app.models.domain import Perturbation
from app.engine.perturbation import InvalidPerturbation
from app.engine.service import analyze_isolated
from app.challenges.grading import ChallengeNotFound, InvalidChallengeAnswer, check_answer
from app.models.challenges import ChallengeAnswer, ChallengeFeedback, ChallengeSummary, PublicChallenge

router = APIRouter(prefix="/api")


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates(request: Request) -> list[TemplateSummary]:
    return [
        TemplateSummary.model_validate(template.model_dump(include=set(TemplateSummary.model_fields)))
        for template in request.app.state.templates.values()
    ]


@router.get("/templates/{template_id}", response_model=PublicTemplate)
def get_template(template_id: str, request: Request) -> PublicTemplate:
    template = request.app.state.templates.get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return PublicTemplate.from_template(template)


def _analyze(template_id: str, perturbation: Perturbation | None, request: Request) -> AnalysisResponse:
    template = request.app.state.templates.get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        return analyze_isolated(template, perturbation, request.app.state.computations)
    except InvalidPerturbation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/perturbations", response_model=AnalysisResponse)
def perturb(body: Perturbation, request: Request) -> AnalysisResponse:
    return _analyze(body.template_id, body, request)


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(body: AnalysisRequest, request: Request) -> AnalysisResponse:
    return _analyze(body.template_id, body.perturbation, request)


@router.get("/challenges", response_model=list[ChallengeSummary])
def list_challenges(request: Request):
    return request.app.state.challenges.public_summaries()


@router.get("/challenges/{challenge_id}", response_model=PublicChallenge)
def get_challenge(challenge_id: str, request: Request):
    detail = request.app.state.challenges.public_detail(challenge_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return detail


@router.post("/challenges/check", response_model=ChallengeFeedback)
def grade_challenge(body: ChallengeAnswer, request: Request):
    try:
        return check_answer(request.app.state.challenges, body, request.app.state.computations)
    except ChallengeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InvalidChallengeAnswer, InvalidPerturbation) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
