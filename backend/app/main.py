from contextlib import asynccontextmanager
from app.api.v1.organization import (
    department_router,
    designation_router,
)
from app.api.v1.comms import router as comms_router
from app.api.v1.dashboards import router as dashboards_router
from app.api.v1.attendance import router as attendance_router
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.employees import router as employees_router
from app.api.v1.auth import router as auth_router
from app.api.v1.setup import router as setup_router
from app.core.config import settings
from app.api.v1.ai_assistant import router as ai_assistant_router
from app.core.database import (
    close_mongo_connection,
    connect_to_mongo,
    get_database,
)

from app.api.v1.audit import router as audit_router
from app.api.v1.leave import router as leave_router
from app.api.v1.payroll import router as payroll_router
from app.api.v1.face import router as face_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime_configuration()
    await connect_to_mongo()

    try:
        yield
    finally:
        await close_mongo_connection()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    setup_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    employees_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    department_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    designation_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    attendance_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(leave_router, prefix=settings.api_v1_prefix)

app.include_router(
    payroll_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(dashboards_router, prefix=settings.api_v1_prefix)

app.include_router(comms_router, prefix=settings.api_v1_prefix)

app.include_router(
    ai_assistant_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(face_router, prefix=settings.api_v1_prefix)

app.include_router(audit_router, prefix=settings.api_v1_prefix)

@app.get("/")
async def root():
    return {
        "message": "HCM Lite API is running.",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    try:
        await get_database().command("ping")
        return {
            "status": "ready",
            "database": "connected",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable.",
        ) from exc