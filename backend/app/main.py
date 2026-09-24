"""ScopeGuard FastAPI application entry point."""

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.core.config import get_settings
from app.models.analysis_models import HealthResponse, StatusResponse

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        'Intelligent Code Change Impact & Regression Risk Analysis System. '
        'ScopeGuard uses AST analysis, dependency graph traversal, and '
        'deterministic risk scoring to assess the blast radius and '
        'regression risk of every code change — no AI required.'
    ),
    contact={
        'name': 'ScopeGuard',
    },
    license_info={
        'name': 'Proprietary',
    },
    docs_url='/docs' if not settings.is_production else None,
    redoc_url='/redoc' if not settings.is_production else None,
)


# Request timing middleware
@app.middleware('http')
async def add_timing_header(request: Request, call_next) -> Response:
    """Add X-Process-Time header to every response for observability."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers['X-Process-Time'] = f'{elapsed:.4f}'
    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include routers
app.include_router(analysis_router)


@app.get('/', response_model=StatusResponse)
async def root() -> StatusResponse:
    """Return service status information."""
    return StatusResponse(
        name=settings.app_name,
        version=settings.app_version,
    )


@app.get('/health', response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint for liveness probes."""
    return HealthResponse(status='healthy')


@app.get('/ready', response_model=HealthResponse)
async def ready() -> HealthResponse:
    """Readiness check endpoint."""
    return HealthResponse(status='ready')


@app.get('/api/version')
async def version() -> dict:
    """Return application version and build information."""
    return {
        'name': settings.app_name,
        'version': settings.app_version,
        'environment': settings.environment,
        'milestones': 'M1-M8',
        'features': [
            'AST-based code analysis',
            'Dependency graph traversal',
            'Git commit impact analysis',
            'Deterministic risk scoring',
            'Test impact & selection',
            'Historical change intelligence',
            'CLI with risk gating',
            'Docker & CI/CD integration',
        ],
    }
