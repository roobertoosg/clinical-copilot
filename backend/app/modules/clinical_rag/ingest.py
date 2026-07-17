"""Ingestión de documentos clínicos hacia Qdrant (Capa 2 — RAG)."""

from __future__ import annotations

import uuid

from loguru import logger
from qdrant_client.http import models as qmodels

from .embeddings import get_ollama_embedding
from .retriever import COLLECTION_NAME, ensure_collection_exists, get_qdrant_client
from .schemas import IngestTextRequest, IngestTextResponse

MIN_CHUNK_CHARS = 50


def _chunk_by_paragraphs(text: str) -> list[str]:
    """Chunking rudimentario por párrafos (\\n\\n), descartando fragmentos cortos."""
    paragraphs = [p.strip() for p in text.split("\n\n")]
    return [p for p in paragraphs if len(p) >= MIN_CHUNK_CHARS]


def ingest_text(text: str, source_metadata: dict | None = None) -> int:
    """Ingesta texto plano: chunking → embedding → upsert en Qdrant.

    Returns:
        Número de chunks indexados.
    """
    source_metadata = source_metadata or {}
    chunks = _chunk_by_paragraphs(text)

    if not chunks:
        logger.warning(
            "RAG ingest_text — sin párrafos válidos (>= {n} chars).",
            n=MIN_CHUNK_CHARS,
        )
        return 0

    logger.info(
        "RAG ingest_text — {n} chunk(s) a indexar. metadata={meta}",
        n=len(chunks),
        meta=source_metadata,
    )

    ensure_collection_exists()
    client = get_qdrant_client()
    points: list[qmodels.PointStruct] = []
    inserted_ids: list[str] = []

    for chunk in chunks:
        vector = get_ollama_embedding(chunk)
        if not vector:
            logger.warning(
                "RAG ingest_text — embedding fallido; chunk omitido ({n} chars).",
                n=len(chunk),
            )
            continue

        chunk_id = str(uuid.uuid4())
        payload = {"content": chunk, **source_metadata}
        points.append(
            qmodels.PointStruct(
                id=chunk_id,
                vector=vector,
                payload=payload,
            )
        )
        inserted_ids.append(chunk_id)
        logger.debug(
            "RAG ingest_text — chunk preparado con id={point_id}.",
            point_id=chunk_id,
        )

    if not points:
        logger.warning("RAG ingest_text — ningún chunk indexado (embeddings fallidos).")
        return 0

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.success(
        "RAG ingest_text — {n} chunk(s) únicos insertados en '{col}' "
        "(ids generados: {ids}).",
        n=len(inserted_ids),
        col=COLLECTION_NAME,
        ids=inserted_ids,
    )
    return len(inserted_ids)


def ingest_text_request(request: IngestTextRequest) -> IngestTextResponse:
    """Wrapper para el endpoint HTTP de ingestión."""
    try:
        count = ingest_text(request.text, request.source_metadata)
        return IngestTextResponse(
            status="ok",
            chunks_created=count,
            message=f"{count} chunk(s) indexados en {COLLECTION_NAME}.",
        )
    except Exception as exc:
        logger.exception("RAG ingest_text_request falló: {err}", err=exc)
        return IngestTextResponse(
            status="error",
            chunks_created=0,
            message=str(exc),
        )
