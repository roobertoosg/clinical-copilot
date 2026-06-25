from typing import Dict, List

from pydantic import BaseModel


class ConsultationInput(BaseModel):
    patient_id: int
    conversation_text: str
    vital_signs: str = "No registrados"
    physical_exam: str = "No registrado"


class AIClinicalOutput(BaseModel):
    soape: Dict
    diagnosticos_sugeridos: List[Dict]
    receta_borrador: List[str]
    resumen_paciente: str
