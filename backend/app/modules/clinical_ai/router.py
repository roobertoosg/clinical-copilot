import json
import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Patient
from app.db.session import get_db
from .schemas import AIClinicalOutput, ConsultationInput

load_dotenv()

router = APIRouter(prefix="/clinical-ai", tags=["Clinical AI"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")


def _build_prompt(patient: Patient, consultation: ConsultationInput) -> str:
    allergies = [
        f"- {a.allergen} ({a.severity}): {a.reaction}"
        for a in patient.allergies
    ]
    medications = [
        f"- {m.name} {m.dosage}, {m.frequency}"
        for m in patient.medications
    ]

    return f"""Eres un asistente clínico. Analiza la siguiente consulta y responde ÚNICAMENTE con un JSON válido que coincida exactamente con esta estructura:
{{
  "soape": {{"subjetivo": "...", "objetivo": "...", "analisis": "...", "plan": "...", "evaluacion": "..."}},
  "diagnosticos_sugeridos": [{{"codigo": "...", "descripcion": "...", "probabilidad": "..."}}],
  "receta_borrador": ["medicamento dosis frecuencia"],
  "resumen_paciente": "..."
}}

No incluyas texto fuera del JSON.

DATOS DEL PACIENTE:
- ID: {patient.id}
- Nombre: {patient.first_name} {patient.last_name}
- Fecha de nacimiento: {patient.date_of_birth}
- Género: {patient.gender}
- Alergias: {chr(10).join(allergies) if allergies else "Ninguna registrada"}
- Medicamentos actuales: {chr(10).join(medications) if medications else "Ninguno registrado"}

CONSULTA:
- Signos vitales: {consultation.vital_signs}
- Examen físico: {consultation.physical_exam}
- Conversación: {consultation.conversation_text}
"""


@router.post("/process-consultation", response_model=AIClinicalOutput)
def process_consultation(
    consultation: ConsultationInput,
    db: Session = Depends(get_db),
):
    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    prompt = _build_prompt(patient, consultation)
    payload = {
        "model": "llama3.1",
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = json.loads(response.json().get("response"))
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar consulta con IA: {exc}",
        ) from exc
