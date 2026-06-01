from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from . import models
from .database import engine
from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    # --- Startup ---
    logger.info("BlackBox Regulatory Guardian starting up...")

    # Create DB tables
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    # Start LRR monitoring if enabled
    if settings.LRR_ENABLED:
        try:
            from .services.lrr_scheduler import lrr_scheduler
            lrr_scheduler.start_monitoring()
            logger.info("LRR monitoring scheduler started")
        except Exception as e:
            logger.error(f"Failed to start LRR monitoring: {e}")

    yield

    # --- Shutdown ---
    logger.info("BlackBox Regulatory Guardian shutting down...")

    # Stop LRR monitoring
    try:
        from .services.lrr_scheduler import lrr_scheduler
        lrr_scheduler.stop_monitoring()
        logger.info("LRR monitoring scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping LRR monitoring: {e}")


app = FastAPI(
    title="BlackBox Regulatory Guardian API",
    description=(
        "Explainable, Guardrailed Agentic AI Platform for Multi-Modal Banking "
        "Contract Review and Automated Regulatory Lifecycle Management (LRR). "
        "Features LangGraph multi-agent system, MCP tool servers, LayoutLMv3 "
        "document analysis, Legal-BERT clause extraction, and Guardrails AI."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = [
    "http://localhost:5173",  # Vite default port
    "http://localhost:3000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "message": "Welcome to BlackBox Regulatory Guardian API v2.0",
        "features": [
            "Multi-Agent Regulatory Compliance (LangGraph)",
            "MCP Tool Servers (FastMCP)",
            "LRR Continuous Monitoring",
            "Guardrails AI Validation",
            "Legal-BERT Clause Extraction",
            "LayoutLMv3 Document Layout Analysis",
            "SHAP Explainability (XAI)",
        ],
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected",
        "llm_provider": settings.LLM_PROVIDER,
        "lrr_enabled": settings.LRR_ENABLED,
        "guardrails_strict_mode": settings.GUARDRAILS_STRICT_MODE,
    }


# Import and include routers
from .api.endpoints import contracts, lrr, agent, xai

app.include_router(contracts.router, prefix="/api/contracts", tags=["Contracts"])
app.include_router(lrr.router, prefix="/api/lrr", tags=["LRR - Regulatory Lifecycle"])
app.include_router(agent.router, prefix="/api/agent", tags=["Multi-Agent System"])
app.include_router(xai.router, prefix="/api/xai", tags=["Explainability (XAI)"])
