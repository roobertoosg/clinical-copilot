from typing import Dict, List

from pydantic import BaseModel, field_validator


class ConsultationInput(BaseModel):
    patient_id: int
    conversation_text: str
    vital_signs: str = "No registrados"
    physical_exam: str = "No registrado"


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
