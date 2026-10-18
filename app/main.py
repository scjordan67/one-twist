from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.routes import router
from app.challenges.loader import CHALLENGE_DIRECTORY, SAMPLE_DIRECTORY, load_challenges
from app.core.isolation import ComputationExecutor, ExecutorUnavailable
from app.templates.loader import DEFAULT_DIRECTORY, load_templates


def create_app(
    template_directory: Path = DEFAULT_DIRECTORY,
    *,
    computation_executor: ComputationExecutor | None = None,
    challenge_directory: Path = CHALLENGE_DIRECTORY,
    sample_directory: Path = SAMPLE_DIRECTORY,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.templates = load_templates(template_directory)
        app.state.challenges = load_challenges(app.state.templates, challenge_directory, sample_directory)
        app.state.computations = computation_executor or ComputationExecutor()
        try:
            yield
        finally:
            await run_in_threadpool(app.state.computations.close)

    app = FastAPI(title="One-Twist", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ExecutorUnavailable)
    async def computation_unavailable(request, exc: ExecutorUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    app.include_router(router)
    return app


app = create_app()
