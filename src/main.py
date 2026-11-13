from fastapi import FastAPI

from src.api.auth import router as auth_router
from src.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Educational algorithmic trading simulator API.",
)

app.include_router(auth_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Check API availability."""

    return {"status": "healthy"}
