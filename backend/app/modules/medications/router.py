"""Búsqueda difusa del catálogo farmacéutico (Capa 1 — PostgreSQL + pg_trgm)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.db.models import MedicationCatalog
from app.db.session import get_db

from .schemas import MedicationCatalogItem, MedicationSearchResponse

router = APIRouter(prefix="/api/v1/medications", tags=["Medications Catalog"])


def ensure_pg_trgm(engine) -> None:
    """Habilita pg_trgm e índices GIN para búsqueda difusa rápida."""
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        """
        CREATE INDEX IF NOT EXISTS idx_med_catalog_producto_trgm
        ON medications_catalog
        USING gin (producto gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_med_catalog_sustancia_trgm
        ON medications_catalog
        USING gin (sustancia_activa gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_med_catalog_marca_trgm
        ON medications_catalog
        USING gin (marca gin_trgm_ops)
        """,
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.success(
        "pg_trgm habilitado e índices GIN verificados en medications_catalog."
    )


def _format_label(row: MedicationCatalog) -> str:
    """Etiqueta legible para el typeahead / campo medicamento de la receta."""
    producto = (row.producto or "").strip()
    marca = (row.marca or "").strip()
    sustancia = (row.sustancia_activa or "").strip()

    if producto and marca and marca.lower() not in producto.lower():
        return f"{producto} ({marca})"
    if producto:
        return producto
    if sustancia and marca:
        return f"{sustancia} ({marca})"
    return sustancia or marca or "Medicamento sin nombre"


@router.get("/search", response_model=MedicationSearchResponse)
def search_medications(
    q: str = Query(..., min_length=1, description="Texto a buscar (typos tolerados)"),
    limit: int = Query(10, ge=1, le=50, description="Máximo de resultados"),
    db: Session = Depends(get_db),
) -> MedicationSearchResponse:
    """Búsqueda difusa sobre ``medications_catalog`` con ``pg_trgm``.

    Combina ``similarity()`` (ranking + tolerancia a typos) con ``ILIKE``
    (prefijos cortos) para el typeahead de receta.
    """
    term = (q or "").strip()
    if len(term) < 2:
        return MedicationSearchResponse(results=[], query=term, count=0)

    # Más tolerante a errores tipográficos del médico (default PG = 0.3)
    db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.2"))

    score_expr = func.greatest(
        func.similarity(MedicationCatalog.producto, term),
        func.similarity(MedicationCatalog.sustancia_activa, term),
        func.coalesce(func.similarity(MedicationCatalog.marca, term), 0.0),
    ).label("score")

    like = f"%{term}%"

    rows = (
        db.query(MedicationCatalog, score_expr)
        .filter(MedicationCatalog.estatus == "ACTIVO")
        .filter(
            or_(
                MedicationCatalog.producto.op("%")(term),
                MedicationCatalog.sustancia_activa.op("%")(term),
                MedicationCatalog.marca.op("%")(term),
                MedicationCatalog.producto.ilike(like),
                MedicationCatalog.sustancia_activa.ilike(like),
                MedicationCatalog.marca.ilike(like),
            )
        )
        .order_by(score_expr.desc(), MedicationCatalog.producto.asc())
        .limit(limit)
        .all()
    )

    results = [
        MedicationCatalogItem(
            id=row.id,
            producto=row.producto,
            marca=row.marca,
            sustancia_activa=row.sustancia_activa,
            categoria=row.categoria,
            ean=row.ean,
            laboratorio=row.laboratorio,
            estatus=row.estatus,
            medicamento=_format_label(row),
            score=round(float(score or 0.0), 4),
        )
        for row, score in rows
    ]

    return MedicationSearchResponse(
        results=results,
        query=term,
        count=len(results),
    )
