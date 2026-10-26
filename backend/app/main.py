import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs, users
from app.config import get_settings
from app.db.session import init_db
from app.schemas import HealthOut
from app.services.transform import has_rubberband
from app.workers.queue import get_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("secuencialive")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    await init_db()
    queue = get_queue()
    await queue.start()
    logger.info(
        "SecuenciaLive listo | backend=%s gpu=%s rubberband=%s",
        settings.separation_backend,
        settings.use_gpu,
        has_rubberband(),
    )
    yield
    await queue.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "MVP para generar secuencias / multitracks para músicos en vivo. "
            "Dueño: Jhon Fuentes (Colombia)."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(jobs.router)
    app.include_router(users.router)

    @app.get("/api/health", response_model=HealthOut)
    async def health() -> HealthOut:
        s = get_settings()
        return HealthOut(
            status="ok",
            app=s.app_name,
            version=s.app_version,
            separation_backend=s.separation_backend,
            use_gpu=s.use_gpu,
            rubberband=has_rubberband(),
        )

    @app.get("/api/terminos")
    async def terminos():
        return {
            "titulo": "Términos de uso — SecuenciaLive",
            "derechos_de_autor": (
                "Solo sube material del que tengas derechos (composiciones propias, "
                "licencias o autorizaciones). SecuenciaLive no almacena canciones de "
                "forma permanente: los archivos se eliminan tras el procesamiento y "
                "los resultados expiran según la retención configurada "
                f"({get_settings().retention_hours} h)."
            ),
            "responsabilidad": (
                "El usuario es responsable del uso de las secuencias generadas en "
                "ensayos, cultos, conciertos u otros contextos."
            ),
            "membresias": (
                "Los planes Free/Pro/Studio están preparados en el sistema; "
                "los pagos se integrarán en una versión posterior."
            ),
        }

    return app


app = create_app()
