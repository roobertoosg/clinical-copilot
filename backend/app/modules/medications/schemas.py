"""Schemas del catálogo institucional de medicamentos."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MedicationCatalogItem(BaseModel):
    """Ítem del catálogo listo para el typeahead de receta."""

    id: int
    producto: str
    marca: str | None = None
    sustancia_activa: str
    categoria: str | None = None
    ean: str | None = None
    laboratorio: str | None = None
    estatus: str = "ACTIVO"
    # Etiqueta lista para inyectar en doctorFinalData.receta[].medicamento
    medicamento: str
    score: float = Field(0.0, description="Similitud pg_trgm (0–1)")


class MedicationSearchResponse(BaseModel):
    results: list[MedicationCatalogItem]
    query: str
    count: int
