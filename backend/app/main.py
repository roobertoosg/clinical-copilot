from fastapi import FastAPI
from app.db.session import engine
from app.db import models
from app.modules.patients import router as patients_router # <-- NUEVA IMPORTACIÓN
from app.modules.clinical_ai import router as ai_router

# Crea las tablas
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Clinical Copilot API",
    description="API para el asistente clínico inteligente",
    version="0.1.0"
)

# <-- CONECTAMOS LAS NUEVAS VENTANILLAS AQUÍ
app.include_router(patients_router.router)
app.include_router(ai_router.router)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "message": "Clinical Copilot backend is running",
        "version": "0.1.0"
    }
