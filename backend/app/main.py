from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.db.session import engine
from app.db import models
from app.modules.patients import router as patients_router # <-- NUEVA IMPORTACIÓN
from app.modules.clinical_ai import router as ai_router
from app.modules.system import router as system_router
from app.modules.dashboard import router as dashboard_router
from app.modules.clinical_rag import router as clinical_rag_router

# Crea las tablas (y verifica la conexión con PostgreSQL)
try:
    models.Base.metadata.create_all(bind=engine)
    # Asegura columna Human-in-the-Loop en DBs ya existentes (create_all no altera)
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if inspector.has_table("consultations"):
        existing_cols = {c["name"] for c in inspector.get_columns("consultations")}
        if "ai_accuracy_score" not in existing_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE consultations "
                        "ADD COLUMN ai_accuracy_score FLOAT"
                    )
                )
            logger.info("Columna consultations.ai_accuracy_score añadida.")
    logger.success("Conexión con PostgreSQL establecida y tablas verificadas.")
except Exception as exc:
    logger.error(f"No se pudo conectar con PostgreSQL: {exc}")
    raise

app = FastAPI(
    title="Clinical Copilot API",
    description="API para el asistente clínico inteligente",
    version="0.1.0"
)
logger.info("Aplicación FastAPI 'Clinical Copilot API' inicializada.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# <-- CONECTAMOS LAS NUEVAS VENTANILLAS AQUÍ
app.include_router(patients_router.router)
app.include_router(ai_router.router)
app.include_router(system_router.router)
app.include_router(dashboard_router.router)
app.include_router(clinical_rag_router.router)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "message": "Clinical Copilot backend is running",
        "version": "0.1.0"
    }
