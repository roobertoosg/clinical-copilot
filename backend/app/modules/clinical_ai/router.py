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


def _build_prompts(patient: Patient, consultation: ConsultationInput) -> tuple[str, str]:
    # --- 1. SYSTEM PROMPT (La personalidad y reglas) ---
    system_prompt = """Eres 'Clinical Copilot', un asistente médico inteligente de grado clínico.
    
TUS REGLAS ESTRICTAS:
1. Actúa de forma profesional, objetiva y científica.
2. DIAGNÓSTICOS: Prefiere diagnósticos sindromáticos (ej. Faringoamigdalitis aguda) y NO adivines el agente patógeno (bacterias/virus) sin pruebas de laboratorio. Usa códigos CIE-10 reales; si no estás seguro del código exacto, déjalo en blanco.
3. No inventes información, síntomas o signos vitales que no estén en el texto provisto.
4. Devuelve ÚNICAMENTE un JSON válido, sin texto antes ni después.
5. Prioriza la seguridad: SIEMPRE compara los medicamentos a recetar con las alergias del paciente.
6. BLOQUEO DE RECETA: Si detectas que el medicamento sugerido por el médico causa reacción cruzada o alergia, GENERA LA ALERTA, pero ESTÁ ESTRICTAMENTE PROHIBIDO incluir ese medicamento en la 'receta_borrador'. En su lugar, sugiere una alternativa segura o deja la receta vacía."""

    # --- 2. USER PROMPT (Los datos específicos de esta consulta) ---
    registered_allergens_str = ", ".join([a.allergen for a in patient.allergies]) if patient.allergies else "Ninguna"
    allergies = [
        f"- {a.allergen} ({a.severity}): {a.reaction}"
        for a in patient.allergies
    ]
    medications = [
        f"- {m.name} {m.dosage}, {m.frequency}"
        for m in patient.medications
    ]

    user_prompt = f"""Analiza la siguiente consulta y estructura la información.

FORMATO DE SALIDA EXACTO (JSON):
{{
  "soape": {{"subjetivo": "...", "objetivo": "...", "analisis": "...", "plan": "...", "evaluacion": "..."}},
  "diagnosticos_sugeridos": [{{"codigo": "...", "descripcion": "...", "probabilidad": "..."}}],
  "receta_borrador": ["medicamento dosis frecuencia"],
  "resumen_paciente": "...",
  "alertas": ["alerta 1"]
}}

DATOS DEL PACIENTE:
- ID: {patient.id}
- Nombre: {patient.first_name} {patient.last_name}
- Fecha de nacimiento: {patient.date_of_birth}
- Género: {patient.gender}
- ALÉRGENOS REGISTRADOS: {chr(10).join(allergies) if allergies else "Ninguna registrada"}
- Medicamentos actuales: {chr(10).join(medications) if medications else "Ninguno registrado"}

CONSULTA:
- Signos vitales: {consultation.vital_signs}
- Examen físico: {consultation.physical_exam}
- Conversación: {consultation.conversation_text}
"""
    return system_prompt, user_prompt


@router.post("/process-consultation", response_model=AIClinicalOutput)
def process_consultation(
    consultation: ConsultationInput,
    db: Session = Depends(get_db),
):
    # 1. Buscar paciente
    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # 2. Construir los dos prompts separados
    system_prompt, user_prompt = _build_prompts(patient, consultation)
    
    # 3. Armar el payload para Ollama
    payload = {
        "model": "llama3.1",
        "system": system_prompt,
        "prompt": user_prompt,
        "format": "json",
        "stream": False
    }

    # 4. Procesar y aplicar lógica híbrida (IA + Python)
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        
        # Extraer el string y convertirlo a diccionario de Python
        respuesta_texto = response.json().get("response", "{}")
        result = json.loads(respuesta_texto)
        
        # --- INICIO DE VALIDACIÓN MANUAL (PYTHON) ---
        # Asegurar que exista la lista de alertas
        if "alertas" not in result or result["alertas"] is None:
            result["alertas"] = []
            
        # Validar si faltan los signos vitales
        if not consultation.vital_signs or consultation.vital_signs.strip() == "":
            result["alertas"].append(
                "No se registraron signos vitales en el formulario. Es un requerimiento clínico indispensable."
            )
        # --- FIN DE VALIDACIÓN MANUAL ---

        return result
        
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar consulta con IA: {exc}",
        ) from exc