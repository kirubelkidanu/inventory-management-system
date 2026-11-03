import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    auth,
    categories,
    health,
    imports,
    inventory,
    items,
    projects,
    reconciliation,
    reports,
    transactions,
    warehouses,
)
from app.core.config import settings

logger = logging.getLogger("ims.security")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# ------------------------------------------------------------------------------
# Security Middleware: CORS Configuration
# ------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*", "X-Total-Count"],
)


# ------------------------------------------------------------------------------
# Security Error Handlers: Prevent Database Stack Trace Leaks (ADR / Security)
# ------------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches unhandled errors and returns sanitized error responses to API consumers
    without exposing raw database connection strings, schema names, or stack traces.
    Attaches CORS headers dynamically so the browser does not mask errors with 'Network Error'.
    """
    if isinstance(exc, StarletteHTTPException):
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    elif isinstance(exc, RequestValidationError):
        response = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )
    else:
        # Sanitize and log server-side only
        logger.exception(
            "Internal server error on %s %s: %s",
            request.method,
            request.url.path,
            str(exc),
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Please contact the system administrator."
            },
        )

    # Attach CORS headers if request contains an Origin header
    origin = request.headers.get("origin")
    if origin:
        allowed = settings.cors_origins_list
        if origin in allowed or origin.rstrip("/") in allowed or "*" in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"

    return response


app.include_router(health.router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["auth"])
app.include_router(categories.router, prefix=settings.API_V1_STR, tags=["categories"])
app.include_router(projects.router, prefix=settings.API_V1_STR, tags=["projects"])
app.include_router(warehouses.router, prefix=settings.API_V1_STR, tags=["warehouses"])
app.include_router(items.router, prefix=settings.API_V1_STR, tags=["items"])
app.include_router(
    inventory.router,
    prefix=f"{settings.API_V1_STR}/inventory",
    tags=["inventory"],
)
app.include_router(transactions.router, prefix=settings.API_V1_STR, tags=["transactions"])
app.include_router(imports.router, prefix=settings.API_V1_STR, tags=["imports"])
app.include_router(reports.router, prefix=settings.API_V1_STR, tags=["reports"])
app.include_router(reconciliation.router, prefix=settings.API_V1_STR, tags=["reconciliation"])


@app.get("/")
async def root():
    return {"message": "Inventory Management System API"}
