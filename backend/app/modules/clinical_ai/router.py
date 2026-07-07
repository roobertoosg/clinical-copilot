import json
import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Patient
from app.db.session import get_db
from . import crud
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
6. BLOQUEO DE RECETA: Si detectas que el medicamento sugerido por el médico causa reacción cruzada o alergia, GENERA LA ALERTA, pero ESTÁ ESTRICTAMENTE PROHIBIDO incluir ese medicamento en la 'receta'. En su lugar, sugiere una alternativa segura o deja la receta vacía.
7. ANCLAJE DE ATENCIÓN (FRAME): Al analizar la 'Conversación', busca activamente y dale máxima prioridad a las respuestas del paciente ante preguntas clave del médico como '¿Cuál es su malestar?', '¿Qué siente?', '¿Desde cuándo?' o '¿A qué es alérgico?'. Usa estas respuestas como tu fuente principal de verdad para estructurar la sección 'Subjetivo' del SOAPE.

ESQUEMA DE SALIDA (OBLIGATORIO):
Devuelve EXACTAMENTE esta estructura JSON. 'receta' y 'alertas' son SIEMPRE listas de objetos (nunca listas de texto plano).

{
  "soape": {"subjetivo": "...", "objetivo": "...", "analisis": "...", "plan": "...", "evaluacion": "..."},
  "diagnosticos_sugeridos": [{"codigo": "...", "descripcion": "...", "probabilidad": "..."}],
  "receta": [
    {"medicamento": "...", "dosis": "...", "frecuencia": "...", "duracion": "...", "indicaciones": "..."}
  ],
  "resumen_paciente": "...",
  "alertas": [
    {"tipo": "...", "descripcion": "...", "severidad": "..."}
  ]
}

REGLAS DE 'receta' (cada elemento es UN objeto por medicamento, todos los valores son string):
- 'medicamento': nombre del fármaco (ej. "Amoxicilina").
- 'dosis': cantidad por toma (ej. "500 mg").
- 'frecuencia': cada cuánto (ej. "cada 8 horas").
- 'duracion': por cuánto tiempo (ej. "7 días").
- 'indicaciones': notas de administración (ej. "tomar con alimentos").
- Si un dato no aplica o se desconoce, usa string vacío "". Si no hay receta, devuelve [].

REGLAS DE 'alertas' (cada elemento es UN objeto por alerta, todos los valores son string):
- 'tipo': categoría de la alerta. Usa 'alergia', 'interaccion' o 'clinica'.
- 'descripcion': explicación clara del riesgo.
- 'severidad': impacto clínico. Usa 'Alta', 'Media' o 'Baja'.
- Si no hay alertas, devuelve [].

EJEMPLO de 'receta':
[{"medicamento": "Amoxicilina", "dosis": "500 mg", "frecuencia": "cada 8 horas", "duracion": "7 días", "indicaciones": "tomar con alimentos"}]

EJEMPLO de 'alertas':
[{"tipo": "alergia", "descripcion": "El paciente es alérgico a la penicilina; se evitó la amoxicilina.", "severidad": "Alta"}]"""

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
  "receta": [{{"medicamento": "...", "dosis": "...", "frecuencia": "...", "duracion": "...", "indicaciones": "..."}}],
  "resumen_paciente": "...",
  "alertas": [{{"tipo": "alergia|interaccion|clinica", "descripcion": "...", "severidad": "Alta|Media|Baja"}}]
}}

Recuerda: 'receta' y 'alertas' son listas de OBJETOS (no de texto). Si no hay datos, usa []. Rellena con "" los campos que no apliquen.

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
        "stream": False,
        "options": {"temperature": 0.0}
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
                {
                    "tipo": "clinica",
                    "descripcion": "No se registraron signos vitales en el formulario. Es un requerimiento clínico indispensable.",
                    "severidad": "Alta",
                }
            )

        # Asegurar que existan las claves requeridas por el esquema de salida
        result.setdefault("soape", {})
        result.setdefault("diagnosticos_sugeridos", [])
        result.setdefault("receta", [])
        result.setdefault("resumen_paciente", "")
        # --- FIN DE VALIDACIÓN MANUAL ---

        # Validar la salida de la IA contra el esquema Pydantic
        ai_output = AIClinicalOutput(**result)

        # 5. Persistir los resultados en PostgreSQL (transacción segura)
        try:
            crud.save_consultation_results(
                db=db,
                patient_id=patient.id,
                input_data=consultation,
                ai_output=ai_output,
            )
        except Exception as db_exc:
            raise HTTPException(
                status_code=500,
                detail=f"Error al guardar la consulta en la base de datos: {db_exc}",
            ) from db_exc

        # 6. Devolver el mismo JSON al frontend, ya persistido
        return ai_output

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar consulta con IA: {exc}",
        ) from exc