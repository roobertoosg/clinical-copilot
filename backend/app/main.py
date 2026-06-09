from fastapi import FastAPI

app = FastAPI(
    title="Clinical Copilot API",
    description="API para el asistente clínico inteligente",
    version="0.1.0"
)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "message": "Clinical Copilot backend is running",
        "version": "0.1.0"
    }
