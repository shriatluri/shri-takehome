import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.apps.kyc.routes import router as kyc_router
from app.config import Settings
from app.demo.routes import router as demo_router
from app.platform.migrations import run_migrations, run_seed
from app.platform.routes import router as platform_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    applied = run_migrations(settings)
    logger.info("migrations applied: %s", applied or "none")
    logger.info("seed loaded: %s", run_seed(settings))
    yield


app = FastAPI(title="KYC Review Queue", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(platform_router)
app.include_router(demo_router)
app.include_router(kyc_router)


@app.get("/healthz")
def healthz() -> dict:
    """Liveness only. It used to report a row count per table, but the counts
    now depend on who is asking, and this route has no caller."""
    return {"status": "ok"}
