import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    redis_url: str
    data_dir: Path
    model_config: Path
    upload_dir: Path
    cors_origins: list[str]
    jwt_secret: str
    jwt_algorithm: str
    municipal_demo_email: str
    municipal_demo_password: str


@lru_cache
def get_settings() -> Settings:
    origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002",
    )
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv(
            "DATABASE_URL", "postgresql+psycopg://flood:flood@localhost:5432/flood_risk"
        ).replace("postgresql+psycopg://", "postgresql://"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        data_dir=Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))),
        model_config=Path(
            os.getenv(
                "MODEL_CONFIG", str(PROJECT_ROOT / "models" / "risk_engine" / "v1" / "risk_weights.yaml")
            )
        ),
        upload_dir=Path(os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads"))),
        cors_origins=[value.strip() for value in origins.split(",") if value.strip()],
        jwt_secret=os.getenv("JWT_SECRET", "development-only-change-before-deployment"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        municipal_demo_email=os.getenv("MUNICIPAL_DEMO_EMAIL", "staff@pune.gov.in"),
        municipal_demo_password=os.getenv("MUNICIPAL_DEMO_PASSWORD", "change-before-deployment"),
    )
