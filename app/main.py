from fastapi import FastAPI

from app.api import health, search

app = FastAPI(
    title="Snap Forensics — Multi-Application Search API",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(search.router)
