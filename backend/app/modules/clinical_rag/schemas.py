"""Esquemas Pydantic del módulo RAG (Capa 2 — Qdrant)."""

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Fragmento de documento clínico recuperado del vector store."""

    id: str
    content: str
    metadata: dict = Field(default_factory=dict)


class RetrieveRequest(BaseModel):
    """Petición de recuperación semántica."""

    query: str = Field(min_length=1, description="Texto de búsqueda clínica")
    top_k: int = Field(default=3, ge=1, le=20)


class RetrieveResponse(BaseModel):
    """Respuesta con chunks relevantes."""

    chunks: list[DocumentChunk]


class IngestTextRequest(BaseModel):
    """Petición de ingestión de texto plano (guías, NOM, protocolos)."""

    text: str = Field(min_length=1)
    source_metadata: dict = Field(default_factory=dict)


class IngestTextResponse(BaseModel):
    """Resultado de la ingestión."""

    status: str
    chunks_created: int
    message: str
