from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_nested_delimiter="__")

    app_name: str = "SecuenciaLive"
    app_version: str = "0.1.0"
    debug: bool = True

    # Persistencia temporal (no permanente de canciones)
    data_dir: Path = Path("/workspace/data")
    upload_dir: Path = Path("/workspace/data/uploads")
    jobs_dir: Path = Path("/workspace/data/jobs")
    exports_dir: Path = Path("/workspace/data/exports")
    db_url: str = "sqlite+aiosqlite:////workspace/data/secuencialive.db"

    # Retención: borrar audio procesado tras N horas (términos de uso)
    retention_hours: int = 24

    # Separación: demucs | mock (mock para CI / pruebas rápidas)
    # Env: SEPARATION_BACKEND, DEMUCS_MODEL, USE_GPU
    separation_backend: str = "demucs"
    demucs_model: str = "htdemucs"
    # htdemucs = 4 stems; htdemucs_6s = 6 stems (voz, batería, bajo, guitarra, piano, otros)
    demucs_two_stems: str | None = None
    use_gpu: bool = False

    # Límites de membresía (prep; sin pagos)
    free_songs_per_month: int = 3
    pro_songs_per_month: int = 50
    max_upload_mb: int = 80
    max_duration_seconds: int = 600

    cors_origins: list[str] = [
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3847",
        "http://127.0.0.1:3847",
    ]

    sample_rate: int = 44100


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    s.jobs_dir.mkdir(parents=True, exist_ok=True)
    s.exports_dir.mkdir(parents=True, exist_ok=True)
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
