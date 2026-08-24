from fastapi import FastAPI

from app.api import health

app = FastAPI(
    title="Snap Forensics — Multi-Application Search API",
    version="0.1.0",
)

app.include_router(health.router)
# /api/v1/search router lands in the parte2-search branch.
