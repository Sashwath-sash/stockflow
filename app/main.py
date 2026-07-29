from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.catalog import admin_router as catalog_admin_router
from app.api.catalog import router as catalog_router
from app.api.health import router as health_router
from app.api.orders import admin_router as orders_admin_router
from app.api.orders import router as orders_router
from app.bootstrap import create_development_admin
from app.config import settings

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_development_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Transactional inventory and order fulfilment API.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(catalog_admin_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(orders_admin_router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
