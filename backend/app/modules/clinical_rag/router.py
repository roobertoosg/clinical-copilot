"""Endpoints internos del módulo RAG (no expuestos al UI del frontend)."""

from fastapi import APIRouter
from loguru import logger

from .ingest import ingest_text_request
from .retriever import ensure_collection_exists, get_qdrant_client, retrieve_chunks
from .schemas import IngestTextRequest, IngestTextResponse, RetrieveRequest, RetrieveResponse

router = APIRouter(prefix="/clinical-rag", tags=["Clinical RAG (interno)"])


@router.get("/health")
def rag_health():
    """Verifica que el módulo RAG y Qdrant respondan."""
    logger.debug("Health check del módulo clinical_rag.")
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        names = [c.name for c in collections]
        return {
            "status": "ok",
            "module": "clinical_rag",
            "qdrant_collections": names,
        }
    except Exception as exc:
        logger.exception("RAG health check falló: {err}", err=exc)
        return {"status": "degraded", "module": "clinical_rag", "error": str(exc)}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest):
    """Recupera chunks clínicos relevantes desde Qdrant (uso interno / dev)."""
    return retrieve_chunks(request)


@router.post("/ingest", response_model=IngestTextResponse)
def ingest(request: IngestTextRequest):
    """Ingesta texto plano (guías, NOM) hacia Qdrant (uso interno / dev)."""
    ensure_collection_exists()
    return ingest_text_request(request)
