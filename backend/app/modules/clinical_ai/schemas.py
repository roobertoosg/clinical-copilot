from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator


class ConsultationInput(BaseModel):
    patient_id: int
    conversation_text: str
    vital_signs: str = "No registrados"
    physical_exam: str = "No registrado"
    # Proveedor de IA a utilizar: "gemini" (nube) u "ollama" (local)
    ai_provider: str = "gemini"


class PrescriptionItem(BaseModel):
    """Un medicamento de la receta, estructurado por campo."""

    medicamento: str
    dosis: str = ""
    frecuencia: str = ""
    duracion: str = ""
    indicaciones: str = ""

    @field_validator("medicamento", "dosis", "frecuencia", "duracion", "indicaciones", mode="before")
    @classmethod
    def _none_to_empty(cls, value):
        return "" if value is None else value


class AlertItem(BaseModel):
    """Una alerta clínica, estructurada por campo."""

    tipo: str = "clinica"        # ej: 'interaccion', 'alergia', 'clinica'
    descripcion: str
    severidad: str = "Media"     # ej: 'Alta', 'Media', 'Baja'

    @field_validator("tipo", "descripcion", "severidad", mode="before")
    @classmethod
    def _none_to_empty(cls, value):
        return "" if value is None else value


class AIClinicalOutput(BaseModel):
    soape: Dict
    diagnosticos_sugeridos: List[Dict]
    receta: List[PrescriptionItem]
    resumen_paciente: str
    alertas: List[AlertItem] = []
    # Folio de la consulta ya persistida (lo rellena el router tras guardar);
    # permite al frontend exportar el PDF inmediatamente desde el Workspace.
    folio: Optional[str] = None

    @field_validator("receta", mode="before")
    @classmethod
    def _coerce_prescriptions(cls, value):
        """Tolera que el LLM devuelva strings sueltos en vez de objetos."""
        if not value:
            return []
        coerced = []
        for item in value:
            if isinstance(item, str):
                coerced.append({"medicamento": item})
            else:
                coerced.append(item)
        return coerced

    @field_validator("alertas", mode="before")
    @classmethod
    def _coerce_alerts(cls, value):
        """Tolera que el LLM (o la validación manual) devuelva strings."""
        if not value:
            return []
        coerced = []
        for item in value:
            if isinstance(item, str):
                coerced.append({"descripcion": item})
            else:
                coerced.append(item)
        return coerced


# ── Esquemas estrictos para Gemini (sin defaults) ──────────────
# El SDK de google.generativeai falla al traducir esquemas Pydantic que
# contienen valores por defecto ("Unknown field for Schema: default").
# Estos modelos son exclusivos para response_schema en generate_content.


class GeminiSoape(BaseModel):
    subjetivo: str
    objetivo: str
    analisis: str
    plan: str
    evaluacion: str


class GeminiDiagnosticItem(BaseModel):
    codigo: str
    descripcion: str
    probabilidad: str


class GeminiPrescriptionItem(BaseModel):
    medicamento: str
    dosis: str
    frecuencia: str
    duracion: str
    indicaciones: str


class GeminiAlertItem(BaseModel):
    tipo: str
    descripcion: str
    severidad: str


class GeminiClinicalOutput(BaseModel):
    """Copia estricta de AIClinicalOutput para el motor de Gemini (sin defaults)."""

    soape: GeminiSoape
    diagnosticos_sugeridos: List[GeminiDiagnosticItem]
    receta: List[GeminiPrescriptionItem]
    resumen_paciente: str
    alertas: List[GeminiAlertItem]


# ── Esquemas de consulta (expediente) ──────────────────────────

class ConsultationListItem(BaseModel):
    """Fila del listado de consultas (vista /consultas)."""

    id: int
    folio: Optional[str]
    date: Optional[datetime]
    status: Optional[str]
    patient_id: int
    patient_name: str


class ConsultationDetail(BaseModel):
    """Detalle completo de una consulta (SOAPE + receta + alertas)."""

    id: int
    folio: Optional[str]
    date: Optional[datetime]
    status: Optional[str]
    patient_id: int
    patient_name: str
    resumen_paciente: Optional[str]
    soape: Dict
    diagnosticos_sugeridos: List[Dict]
    receta: List[PrescriptionItem]
    alertas: List[AlertItem]
