"""FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import alpha_vantage_runtime
from api.logging import configure_logging
from api.routes import router as runs_router
from api.settings import get_settings


def create_app() -> FastAPI:
    configure_logging()
    alpha_vantage_runtime.install()
    settings = get_settings()
    app = FastAPI(title="tradingagents-api", version="0.1.0")

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Cache-Control", "Last-Event-ID"],
        expose_headers=["Content-Type"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(runs_router)
    return app


app = create_app()
