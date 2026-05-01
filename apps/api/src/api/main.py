"""FastAPI app factory."""
from fastapi import FastAPI

from api.logging import configure_logging
from api.routes import router as runs_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradingagents-api", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(runs_router)
    return app


app = create_app()
