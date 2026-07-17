"""Conexión y recuperación de contexto clínico desde Qdrant (Capa 2 — RAG)."""

from __future__ import annotations

import os

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from .embeddings import get_ollama_embedding
from .schemas import DocumentChunk, RetrieveRequest, RetrieveResponse

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "clinical_guidelines"
VECTOR_SIZE = 768

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Cliente singleton apuntando al contenedor Qdrant de docker-compose."""
    global _client
    if _client is None:
        logger.info(
            "Conectando a Qdrant en {host}:{port}",
            host=QDRANT_HOST,
            port=QDRANT_PORT,
        )
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.success("Cliente Qdrant inicializado.")
    return _client


def ensure_collection_exists() -> None:
    """Crea la colección clinical_guidelines (768 dims, Cosine) si no existe."""
    client = get_qdrant_client()
    try:
        existing = {c.name for c in client.get_collections().collections}
        if COLLECTION_NAME in existing:
            logger.debug(
                "Colección Qdrant '{name}' ya existe.", name=COLLECTION_NAME
            )
            return

        logger.info(
            "Creando colección Qdrant '{name}' (dim={dim}, COSINE).",
            name=COLLECTION_NAME,
            dim=VECTOR_SIZE,
        )
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.success("Colección '{name}' creada en Qdrant.", name=COLLECTION_NAME)

    except Exception as exc:
        # Si otro proceso la creó en paralelo, continuar sin fallar
        if "already exists" in str(exc).lower() or "exist" in str(exc).lower():
            logger.debug(
                "Colección '{name}' ya existía (condición de carrera).",
                name=COLLECTION_NAME,
            )
            return
        logger.exception(
            "Error al asegurar colección Qdrant '{name}': {err}",
            name=COLLECTION_NAME,
            err=exc,
        )
        raise


def retrieve_context(query: str, top_k: int = 3) -> list[str]:
    """Recupera los textos de los chunks más relevantes para enriquecer el prompt.

    Returns:
        Lista de strings con el contenido de cada chunk. Lista vacía si no hay
        resultados o si Qdrant/embeddings fallan (no interrumpe el pipeline).
    """
    query = (query or "").strip()
    if not query:
        logger.debug("RAG retrieve_context — query vacía, se omite búsqueda.")
        return []

    logger.info(
        "RAG retrieve_context — query='{q}' top_k={k}",
        q=query[:120],
        k=top_k,
    )

    try:
        query_vector = get_ollama_embedding(query)
        if not query_vector:
            logger.warning(
                "RAG retrieve_context — embedding vacío; se omite búsqueda."
            )
            return []

        ensure_collection_exists()
        client = get_qdrant_client()

        hits = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
        )

        contents: list[str] = []
        for hit in hits:
            payload = hit.payload or {}
            content = (payload.get("content") or "").strip()
            if content:
                contents.append(content)

        logger.success(
            "RAG retrieve_context — {n} chunk(s) recuperados.",
            n=len(contents),
        )
        return contents

    except Exception as exc:
        logger.exception(
            "RAG retrieve_context falló (Qdrant o embedding): {err}", err=exc
        )
        return []


def retrieve_chunks(request: RetrieveRequest) -> RetrieveResponse:
    """Recupera chunks estructurados (endpoint interno / dev)."""
    try:
        query_vector = get_ollama_embedding(request.query)
        if not query_vector:
            logger.warning(
                "RAG retrieve_chunks — embedding vacío; respuesta sin chunks."
            )
            return RetrieveResponse(chunks=[])

        ensure_collection_exists()
        client = get_qdrant_client()
        hits = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=request.top_k,
        )

        chunks: list[DocumentChunk] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            content = (payload.pop("content", None) or "").strip()
            if not content:
                continue
            chunks.append(
                DocumentChunk(
                    id=str(hit.id),
                    content=content,
                    metadata=payload,
                )
            )

        logger.debug(
            "RAG retrieve_chunks — {n} chunk(s) para API.", n=len(chunks)
        )
        return RetrieveResponse(chunks=chunks)

    except Exception as exc:
        logger.exception("RAG retrieve_chunks falló: {err}", err=exc)
        return RetrieveResponse(chunks=[])
