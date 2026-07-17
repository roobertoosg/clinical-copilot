"""Herramientas (Function Calling) expuestas a Gemini para consultas clínicas."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import MedicationCatalog
from app.db.session import SessionLocal


def consultar_inventario_farmacia(sustancia_activa: str, categoria: str = "") -> list[dict]:
    """Consulta el catálogo institucional de medicamentos disponibles en la farmacia.

    DEBES invocar esta herramienta SIEMPRE antes de incluir cualquier medicamento
    en la sección "receta" del JSON clínico. Busca por sustancia activa (nombre
    genérico) y devuelve los productos comerciales reales con marca, laboratorio
    y código EAN registrados en el inventario.

    Usa los resultados para rellenar el campo "medicamento" de la receta con el
    nombre comercial exacto (producto + marca) tal como aparece en el catálogo.
    NUNCA inventes nombres comerciales, marcas, laboratorios ni códigos EAN.

    Args:
        sustancia_activa: Nombre genérico del fármaco a buscar (ej. "CELECOXIB",
            "PARACETAMOL", "AMOXICILINA"). Búsqueda parcial insensible a mayúsculas.
        categoria: Categoría terapéutica opcional para acotar resultados
            (ej. "REUMATOLOGÍA", "SISTEMA RESPIRATORIO"). Dejar vacío "" si no aplica.

    Returns:
        Lista de hasta 10 medicamentos activos, cada uno como dict con:
        producto, marca, sustancia_activa, categoria, ean, laboratorio, estatus.
        Lista vacía si no hay coincidencias o ocurre un error.
    """
    term = (sustancia_activa or "").strip()
    if not term:
        logger.warning("consultar_inventario_farmacia: sustancia_activa vacía.")
        return []

    logger.info(
        "Tool consultar_inventario_farmacia — sustancia='{sustancia}', categoria='{cat}'",
        sustancia=term,
        cat=categoria or "(todas)",
    )

    db: Session = SessionLocal()
    try:
        query = db.query(MedicationCatalog).filter(
            MedicationCatalog.estatus == "ACTIVO",
            MedicationCatalog.sustancia_activa.ilike(f"%{term}%"),
        )
        cat = (categoria or "").strip()
        if cat:
            query = query.filter(MedicationCatalog.categoria.ilike(f"%{cat}%"))

        rows = query.limit(10).all()
        results = [
            {
                "producto": r.producto,
                "marca": r.marca or "",
                "sustancia_activa": r.sustancia_activa,
                "categoria": r.categoria or "",
                "ean": r.ean or "",
                "laboratorio": r.laboratorio or "",
                "estatus": r.estatus,
            }
            for r in rows
        ]
        logger.success(
            "Tool consultar_inventario_farmacia — {n} resultado(s) para '{sustancia}'.",
            n=len(results),
            sustancia=term,
        )
        return results

    except Exception as exc:
        logger.exception(
            "Error en consultar_inventario_farmacia para sustancia '{sustancia}': {err}",
            sustancia=term,
            err=exc,
        )
        return []
    finally:
        db.close()
