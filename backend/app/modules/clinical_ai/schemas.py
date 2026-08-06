from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator

from .patient_summary import coerce_patient_summary


class ConsultationInput(BaseModel):
    patient_id: int
    conversation_text: str
    vital_signs: str = "No registrados"
    physical_exam: str = "No registrado"
    # Proveedor de IA a utilizar: "gemini" (nube) u "ollama" (local)
    ai_provider: str = "gemini"


class PrescriptionItem(BaseModel):
    """Un medicamento de la receta, estructurado por campo."""

    # Denominación genérica (obligatoria por normativa; va primero en la receta)
    sustancia_activa: str = ""
    medicamento: str = ""
    dosis: str = ""
    frecuencia: str = ""
    duracion: str = ""
    indicaciones: str = ""

    @field_validator(
        "sustancia_activa",
        "medicamento",
        "dosis",
        "frecuencia",
        "duracion",
        "indicaciones",
        mode="before",
    )
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


class PatientSummary(BaseModel):
    """Instrucciones claras para el paciente (va en la receta PDF)."""

    diagnostico_simple: str = ""
    instrucciones_medicinas: str = ""
    cuidados_casa: str = ""
    senales_alarma: str = ""

    @field_validator(
        "diagnostico_simple",
        "instrucciones_medicinas",
        "cuidados_casa",
        "senales_alarma",
        mode="before",
    )
    @classmethod
    def _none_to_empty(cls, value):
        return "" if value is None else value


class AIClinicalOutput(BaseModel):
    soape: Dict
    diagnosticos_sugeridos: List[Dict]
    receta: List[PrescriptionItem]
    resumen_paciente: PatientSummary
    alertas: List[AlertItem] = []
    # Folio de la consulta ya persistida (lo rellena el router tras guardar);
    # permite al frontend exportar el PDF inmediatamente desde el Workspace.
    folio: Optional[str] = None
    # Similitud SOAPE IA vs. médico (0.0–1.0); se rellena en finalize-consultation
    ai_accuracy_score: Optional[float] = None

    @field_validator("resumen_paciente", mode="before")
    @classmethod
    def _coerce_patient_summary(cls, value):
        """Tolera string legado o dict parcial del LLM."""
        return coerce_patient_summary(value)

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


class FinalizeConsultationRequest(BaseModel):
    """Payload Human-in-the-Loop: borrador IA + versión editada por el médico."""

    patient_id: int
    conversation_text: str = ""
    vital_signs: str = "No registrados"
    physical_exam: str = "No registrado"
    ai_original_data: AIClinicalOutput
    doctor_final_data: AIClinicalOutput


class FinalizeConsultationResponse(BaseModel):
    """Respuesta tras persistir la consulta final del médico."""

    folio: str
    ai_accuracy_score: float
    consultation: AIClinicalOutput


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
    sustancia_activa: str
    medicamento: str
    dosis: str
    frecuencia: str
    duracion: str
    indicaciones: str


class GeminiAlertItem(BaseModel):
    tipo: str
    descripcion: str
    severidad: str


class GeminiPatientSummary(BaseModel):
    diagnostico_simple: str
    instrucciones_medicinas: str
    cuidados_casa: str
    senales_alarma: str


class GeminiClinicalOutput(BaseModel):
    """Copia estricta de AIClinicalOutput para el motor de Gemini (sin defaults)."""

    soape: GeminiSoape
    diagnosticos_sugeridos: List[GeminiDiagnosticItem]
    receta: List[GeminiPrescriptionItem]
    resumen_paciente: GeminiPatientSummary
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
    resumen_paciente: Optional[PatientSummary] = None
    soape: Dict
    diagnosticos_sugeridos: List[Dict]
    receta: List[PrescriptionItem]
    alertas: List[AlertItem]


class Icd11SearchItem(BaseModel):
    """Resultado de búsqueda CIE-11 para typeahead del médico."""

    codigo: str
    descripcion: str


class Icd11SearchResponse(BaseModel):
    results: List[Icd11SearchItem]
