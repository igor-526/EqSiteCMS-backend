from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from uvicorn import run

from api import (
    auth_router,
    breeds_router,
    coat_color_router,
    horse_owner_router,
    horse_service_router,
    horses_router,
    photos_router,
    prices_router,
    site_settings_router,
)
from core.exceptions.auth import InvalidCredentials
from core.exceptions.base import ClientError
from settings import settings
from utils.configure_logger import configure_logger
from utils.seeding.init_registry import init_registry

configure_logger(
    logger_root_name=__name__, logger_prefix_output="EqSiteCMS Backend"
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_registry()
    yield


app = FastAPI(
    title=settings.swagger_title,
    debug=settings.debug,
    lifespan=lifespan,
)

router = APIRouter(prefix="/api")
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(horses_router, prefix="/horses", tags=["Horses"])
router.include_router(breeds_router)
router.include_router(coat_color_router)
router.include_router(horse_owner_router)
router.include_router(horse_service_router)
router.include_router(photos_router)
router.include_router(prices_router)
router.include_router(site_settings_router)
app.include_router(router)


@app.get("/health", tags=["Healthcheck"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


if settings.debug:
    media_dir = Path(__file__).parent / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        f"http://{settings.cms_panel_domain}",
        f"http://{settings.cms_backend_domain}",
        f"http://{settings.main_site_domain}",
        f"https://{settings.cms_panel_domain}",
        f"https://{settings.cms_backend_domain}",
        f"https://{settings.main_site_domain}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ClientError)
def client_error_handler(_: Request, exc: ClientError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(InvalidCredentials)
def invalid_token_error_handler(_: Request, exc: InvalidCredentials) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=401)


@app.exception_handler(RequestValidationError)
def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Преобразует ошибки валидации FastAPI в ClientError."""
    errors = exc.errors()
    if errors:
        # Берем первую ошибку для сообщения
        error = errors[0]
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Ошибка валидации")
        detail = f"{field}: {message}" if field else message
    else:
        detail = "Ошибка валидации данных"
    return JSONResponse({"detail": detail}, status_code=400)


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
