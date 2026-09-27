import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform.db import get_session
from app.platform.migrations import run_migrations, run_seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLES = ("employees", "customers", "sanctions_list", "policy_rules", "cases", "audit_log")


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


@app.get("/healthz")
def healthz(session: Session = Depends(get_session)) -> dict:
    """Liveness plus a row count per table, which is how the frontend shell and
    `docker compose up` confirm the database came up seeded."""
    counts = {
        table: session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        for table in TABLES
    }
    return {"status": "ok", "counts": counts}
