from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import diagnosis, dispatch, events, intervention, invoices, promises
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Recoup API",
    description="Root-Cause Revenue Recovery Agent API for B2B and Consumer Payment Failures",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware configuration for React / Vite dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check and database connectivity verification",
)
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint that executes SELECT 1 to verify database availability."""
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="connected")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(exc)}",
        )


# Mount routers
app.include_router(events.router)
app.include_router(invoices.router)
app.include_router(diagnosis.router)
app.include_router(intervention.router)
app.include_router(promises.router)
app.include_router(dispatch.router)
