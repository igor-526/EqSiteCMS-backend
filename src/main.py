from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from uvicorn import run

from api import (
    auth_router,
    breed_groups_router,
    breeds_router,
    callback_request_router,
    coat_color_router,
    emails_router,
    horse_owner_router,
    horse_service_relations_router,
    horse_service_router,
    horses_router,
    news_router,
    notification_settings_router,
    photos_router,
    prices_router,
    service_users_router,
    site_settings_router,
    user_management_router,
    users_router,
)
from containers import container
from core.exceptions.auth import ForbiddenError, InvalidCredentials, InvalidServiceKey
from core.exceptions.base import ClientError, ConflictError, NotFoundError
from core.exceptions.tenant import TenantNotFound
from core.middleware.cors import SplitCORSMiddleware
from settings import settings
from utils.configure_logger import configure_logger
from utils.seeding.init_registry import init_registry

from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator

configure_logger(logger_root_name=__name__, logger_prefix_output="EqSiteCMS Backend")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_registry()

    nats_client = container.nats_client()

    await nats_client.connect()
    await nats_client.setup()

    try:
        yield
    finally:
        await nats_client.close()


app = FastAPI(
    title=settings.swagger_title,
    debug=settings.debug,
    lifespan=lifespan,
)

Instrumentator().instrument(app)

start_http_server(
    port=9000,
    addr="0.0.0.0",
)

router = APIRouter(prefix="/api")
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(breeds_router)
router.include_router(breed_groups_router)
router.include_router(coat_color_router)
router.include_router(emails_router)
router.include_router(horse_owner_router)
router.include_router(horse_service_router)
router.include_router(horse_service_relations_router)
router.include_router(horses_router, prefix="/horses", tags=["Horses"])
router.include_router(news_router)
router.include_router(notification_settings_router)
router.include_router(photos_router)
router.include_router(prices_router)
router.include_router(site_settings_router)
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(
    callback_request_router, prefix="/callback_requests", tags=["Callback Requests"]
)
app.include_router(router)

# Service router for microservice endpoints
service_router = APIRouter(prefix="/api/service")
service_router.include_router(
    service_users_router, prefix="/users", tags=["Service Users"]
)
app.include_router(service_router)
app.include_router(user_management_router)


@app.get("/health", tags=["Healthcheck"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


app.add_middleware(
    SplitCORSMiddleware,
    cms_origins=settings.cms_cors_origins,
)


@app.exception_handler(ForbiddenError)
def forbidden_error_handler(_: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=403)


@app.exception_handler(NotFoundError)
def not_found_error_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(ConflictError)
def conflict_error_handler(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(ClientError)
def client_error_handler(_: Request, exc: ClientError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(TenantNotFound)
def tenant_not_found_handler(_: Request, exc: TenantNotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(InvalidCredentials)
def invalid_token_error_handler(_: Request, exc: InvalidCredentials) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=401)


@app.exception_handler(InvalidServiceKey)
def invalid_service_key_handler(_: Request, exc: InvalidServiceKey) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=401)


@app.exception_handler(RequestValidationError)
def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Преобразует ошибки валидации FastAPI в ClientError."""
    errors = exc.errors()
    status_code = (
        422
        if any(
            error.get("loc", [None])[0] == "path"
            or (
                request.url.path.startswith("/api/horses/breed-groups")
                and error.get("loc", [None])[0] == "body"
            )
            or error.get("type") == "extra_forbidden"
            or error.get("loc", [None, None])[:2] == ("query", "sort")
            or error.get("loc", [None, None])[:2] == ("query", "services")
            for error in errors
        )
        else 400
    )
    if errors:
        # Берем первую ошибку для сообщения
        error = errors[0]
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Ошибка валидации")
        detail = f"{field}: {message}" if field else message
    else:
        detail = "Ошибка валидации данных"
    return JSONResponse({"detail": detail}, status_code=status_code)


@app.exception_handler(ValidationError)
def pydantic_validation_error_handler(_: Request, exc: ValidationError) -> JSONResponse:
    """Преобразует ошибки валидации Pydantic в ClientError."""
    errors = exc.errors()
    if errors:
        error = errors[0]
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Ошибка валидации")
        detail = f"{field}: {message}" if field else message
    else:
        detail = "Ошибка валидации данных"
    return JSONResponse({"detail": detail}, status_code=400)


if __name__ == "__main__":
    run(
        "main:app",
        host="0.0.0.0",
        reload=settings.debug,
        workers=settings.workers,
    )
