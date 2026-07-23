"""Pipeline de ingesta masiva de PDFs (Guías Clínicas / NOMs) hacia Qdrant.

Extrae texto con PyMuPDF, hace chunking con solapamiento, vectoriza con
Ollama (nomic-embed-text) y sube a Qdrant en lotes. Idempotente: reanuda
desde processed_files.txt si se interrumpe.

Uso (desde backend/):
    ./venv/bin/python scripts/ingest_pdfs.py
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import fitz  # pymupdf
from dotenv import load_dotenv
from loguru import logger
from qdrant_client.http import models as qmodels

# Raíz del backend en sys.path para importar app.*
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app.modules.clinical_rag.embeddings import get_ollama_embedding  # noqa: E402
from app.modules.clinical_rag.retriever import (  # noqa: E402
    COLLECTION_NAME,
    ensure_collection_exists,
    get_qdrant_client,
)

GUIDELINES_DIR = BACKEND_DIR / "data" / "guidelines"
PROCESSED_LOG = GUIDELINES_DIR / "processed_files.txt"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
UPSERT_BATCH_SIZE = 50


def load_processed_files() -> set[str]:
    """Lee el registro de PDFs ya ingestados con éxito."""
    if not PROCESSED_LOG.exists():
        return set()
    names = {
        line.strip()
        for line in PROCESSED_LOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    logger.info(
        "Registro de progreso: {n} PDF(s) ya procesados.",
        n=len(names),
    )
    return names


def mark_as_processed(filename: str) -> None:
    """Añade un PDF al registro solo tras upsert completo."""
    with PROCESSED_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{filename}\n")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extrae y limpia el texto de todas las páginas del PDF."""
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            page_text = page.get_text("text") or ""
            parts.append(page_text)

    raw = "\n".join(parts)
    # Colapsa saltos de línea múltiples → espacio; limpia whitespace redundante
    cleaned = re.sub(r"\n+", " ", raw)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def chunk_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Divide el texto en bloques con solapamiento estricto.

    Ejemplo: size=1000, overlap=200 → avance de 800 caracteres por chunk.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("CHUNK_OVERLAP debe ser menor que CHUNK_SIZE")

    chunks: list[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        piece = text[start:end]
        # No hacer strip del slice: preserva el overlap exacto de `overlap` chars
        if piece.strip():
            chunks.append(piece)
        if end >= text_len:
            break
        start += step
    return chunks


def upsert_batch(client, points: list[qmodels.PointStruct]) -> None:
    """Sube un lote de puntos a Qdrant."""
    if not points:
        return
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.debug(
        "Upsert de lote: {n} punto(s) → '{col}'.",
        n=len(points),
        col=COLLECTION_NAME,
    )


def process_pdf(client, pdf_path: Path) -> int:
    """Extrae, chunkifica, embeddea y sube un PDF. Retorna chunks indexados."""
    text = extract_text_from_pdf(pdf_path)
    if not text:
        logger.warning("PDF sin texto extraíble: {name}", name=pdf_path.name)
        return 0

    chunks = chunk_text(text)
    if not chunks:
        logger.warning("PDF sin chunks válidos: {name}", name=pdf_path.name)
        return 0

    logger.info(
        "  → {n} chunk(s) generados ({chars} caracteres de texto).",
        n=len(chunks),
        chars=len(text),
    )

    batch: list[qmodels.PointStruct] = []
    indexed = 0
    skipped_embeddings = 0

    for idx, chunk in enumerate(chunks):
        vector = get_ollama_embedding(chunk)
        if not vector:
            skipped_embeddings += 1
            logger.warning(
                "  → Embedding vacío; chunk {i}/{total} omitido ({name}).",
                i=idx,
                total=len(chunks),
                name=pdf_path.name,
            )
            continue

        batch.append(
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "content": chunk,
                    "source": pdf_path.name,
                    "chunk_index": idx,
                },
            )
        )

        if len(batch) >= UPSERT_BATCH_SIZE:
            upsert_batch(client, batch)
            indexed += len(batch)
            batch = []

    if batch:
        upsert_batch(client, batch)
        indexed += len(batch)

    if skipped_embeddings:
        logger.warning(
            "  → {n} chunk(s) omitidos por embedding fallido en {name}.",
            n=skipped_embeddings,
            name=pdf_path.name,
        )

    return indexed


def main() -> None:
    if not GUIDELINES_DIR.is_dir():
        logger.error("No existe el directorio de guías: {path}", path=GUIDELINES_DIR)
        sys.exit(1)

    pdf_files = sorted(GUIDELINES_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error("No se encontraron PDFs en {path}", path=GUIDELINES_DIR)
        sys.exit(1)

    processed = load_processed_files()
    pending = [p for p in pdf_files if p.name not in processed]
    total = len(pdf_files)
    already_done = total - len(pending)

    logger.info(
        "Ingesta masiva RAG — {total} PDF(s) en disco | "
        "{done} ya procesados | {pending} pendientes.",
        total=total,
        done=already_done,
        pending=len(pending),
    )

    if not pending:
        logger.success("Nada pendiente: todos los PDFs ya están en el registro.")
        return

    ensure_collection_exists()
    client = get_qdrant_client()

    ok_count = 0
    fail_count = 0
    total_chunks = 0

    for i, pdf_path in enumerate(pending, start=1):
        # Numeración global para trazabilidad (incluye los ya saltados)
        global_index = already_done + i
        logger.info(
            "Procesando archivo {idx} de {total}: {name}",
            idx=global_index,
            total=total,
            name=pdf_path.name,
        )

        try:
            indexed = process_pdf(client, pdf_path)
            mark_as_processed(pdf_path.name)
            ok_count += 1
            total_chunks += indexed
            logger.success(
                "✓ {name} — {n} chunk(s) indexados. "
                "Progreso: {done}/{total} archivos.",
                name=pdf_path.name,
                n=indexed,
                done=already_done + i,
                total=total,
            )
        except Exception as exc:
            fail_count += 1
            logger.exception(
                "✗ Error al procesar {name}: {err}. Se continúa con el siguiente.",
                name=pdf_path.name,
                err=exc,
            )

    logger.info(
        "Ingesta finalizada — OK: {ok} | fallidos: {fail} | "
        "chunks nuevos: {chunks} | colección: '{col}'.",
        ok=ok_count,
        fail=fail_count,
        chunks=total_chunks,
        col=COLLECTION_NAME,
    )
    if fail_count:
        logger.warning(
            "Algunos PDFs fallaron; re-ejecuta el script para reintentarlos "
            "(solo se saltan los listados en processed_files.txt)."
        )
    else:
        logger.success("Pipeline de ingesta masiva completado sin errores.")


if __name__ == "__main__":
    main()
