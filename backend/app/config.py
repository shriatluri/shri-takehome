import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = Path(os.environ.get("MIGRATIONS_DIR", REPO_ROOT / "db" / "migrations"))
SEED_DIR = Path(os.environ.get("SEED_DIR", REPO_ROOT / "db" / "seed"))


@dataclass(frozen=True)
class Settings:
    """Connection settings for both database roles.

    The owner role runs migrations and seeding; the app role serves requests and
    is subject to row-level security.
    """

    host: str
    port: int
    database: str
    owner_user: str
    owner_password: str
    app_user: str
    app_password: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "kyc"),
            owner_user=os.environ.get("DB_OWNER_USER", "kyc_owner"),
            owner_password=os.environ.get("DB_OWNER_PASSWORD", "kyc_owner_pw"),
            app_user=os.environ.get("DB_APP_USER", "kyc_app"),
            app_password=os.environ.get("DB_APP_PASSWORD", "kyc_app_pw"),
        )

    def url(self, user: str, password: str, driver: str = "") -> str:
        scheme = f"postgresql+{driver}" if driver else "postgresql"
        return f"{scheme}://{user}:{password}@{self.host}:{self.port}/{self.database}"

    @property
    def owner_url(self) -> str:
        return self.url(self.owner_user, self.owner_password)

    @property
    def app_url(self) -> str:
        return self.url(self.app_user, self.app_password, driver="psycopg")
