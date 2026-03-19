"""
FastAPI application entry point.

Registers all routers, sets up CORS, and provides a health check endpoint.
Auto-generated Swagger UI is available at /docs.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import ingestion, evaluations, feedback, suggestions, meta

app = FastAPI(
    title="AI Agent Evaluation Pipeline",
    description=(
        "Automated evaluation pipeline for AI agents. "
        "Ingests conversation logs, scores them using multiple evaluators, "
        "processes human feedback, and auto-generates improvement suggestions."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ingestion.router,    prefix="/ingest",       tags=["Ingestion"])
app.include_router(evaluations.router,  prefix="/evaluations",  tags=["Evaluations"])
app.include_router(feedback.router,     prefix="/feedback",     tags=["Feedback"])
app.include_router(suggestions.router,  prefix="/suggestions",  tags=["Suggestions"])
app.include_router(meta.router,         prefix="/meta",         tags=["Meta-Evaluation"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "AI Agent Evaluation Pipeline"}


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "AI Agent Evaluation Pipeline API",
        "docs": "/docs",
        "health": "/health",
    }
