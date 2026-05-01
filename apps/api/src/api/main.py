"""FastAPI app factory."""
from fastapi import FastAPI

from api.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradingagents-api", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
