import json
import os
import tempfile
from datetime import date

import google.generativeai as genai
import requests
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import Patient, Consultation, ClinicalNote, Doctor
from app.db.session import get_db
from app.services.icd11_service import enrich_diagnoses_with_icd11
from . import crud
from .gemini_pipeline import run_gemini_clinical_pipeline
from .pdf_generator import generate_consultation_pdf
from .schemas import (
    AIClinicalOutput,
    ConsultationInput,
    ConsultationListItem,
    ConsultationDetail,
)

load_dotenv()

router = APIRouter(prefix="/clinical-ai", tags=["Clinical AI"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# Configuración de Gemini (la llave se toma del entorno; se asume ya presente)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL_NAME = "gemini-3.5-flash"

# Modelo Whisper cacheado a nivel de módulo: se carga una sola vez (la primera
# petición) y se reutiliza en las siguientes para no recargarlo en cada request.
_whisper_model: WhisperModel | None = None


def _get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        # "base" ofrece un buen equilibrio velocidad/calidad en desarrollo (CPU).
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


def _calculate_age(date_of_birth: date | None) -> int | None:
    """Calcula la edad en años a partir de la fecha de nacimiento."""
    if not date_of_birth:
        return None
    today = date.today()
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )


def _build_prompts(patient: Patient, consultation: ConsultationInput) -> tuple[str, str]:
    # --- 1. SYSTEM PROMPT (La personalidad y reglas) ---
    system_prompt = """Eres 'Aura Clinical Copilot', un asistente médico inteligente y estricto de grado clínico.

TUS REGLAS CRÍTICAS DE COMPORTAMIENTO:
1. ANTI-BUCLES Y CONCISIÓN: ESTÁ ESTRICTAMENTE PROHIBIDO repetir la misma oración, frase o palabra de forma consecutiva. Sé clínico, directo y telegráfico.
2. CERO ALUCINACIONES: No inventes información, síntomas, medicamentos, ni signos vitales que no estén explícitamente en el texto provisto. Utiliza EXACTAMENTE la edad proporcionada en los datos del paciente. NUNCA intentes calcularla ni modificarla.
3. FORMATO ESTRICTO: Devuelve ÚNICAMENTE un JSON válido. NINGÚN texto antes, NINGÚN texto después, ni bloques de código markdown (```json).
4. SEGURIDAD DEL PACIENTE (PRIORIDAD MÁXIMA): Compara SIEMPRE los medicamentos a recetar con las alergias registradas del paciente. Si hay riesgo de reacción cruzada o alergia, GENERA UNA ALERTA DE SEVERIDAD 'Alta' y OMITE ese medicamento de la receta. Sugiere una alternativa en el 'Plan'.

REGLAS DE RAZONAMIENTO CLÍNICO (SOAPE Y DIAGNÓSTICOS):
- SUBJETIVO: Extrae el malestar principal, evolución y síntomas referidos por el paciente en la conversación.
- OBJETIVO: Basa esto en los 'Signos vitales' y 'Examen físico'. Si están vacíos o no se mencionan en la charla, usa estrictamente la frase: "Pendiente de exploración física completa". NUNCA lo dejes en blanco.
- ANÁLISIS: Justifica brevemente por qué sugieres los diagnósticos basados en el Subjetivo y Objetivo.
- PLAN: Define los pasos a seguir (laboratorios, tratamiento, reposo). Si no hay datos, infiere el siguiente paso lógico (ej. "Realizar exploración física y prescribir tratamiento sintomático").
- DIAGNÓSTICOS: Devuelve SOLO nombres clínicos en texto plano (ej. "Hipertensión esencial",
  "Diabetes mellitus tipo 2", "Faringoamigdalitis aguda"). NUNCA inventes ni adivines códigos
  CIE-10/CIE-11. El campo "codigo" debe ir SIEMPRE como cadena vacía ""; el backend lo
  enriquecerá después con la API oficial de la OMS.

ESTRUCTURA JSON OBLIGATORIA (Todas las claves deben existir):
{
  "soape": {"subjetivo": "...", "objetivo": "...", "analisis": "...", "plan": "...", "evaluacion": "..."},
  "diagnosticos_sugeridos": [{"codigo": "", "descripcion": "Nombre del diagnóstico en texto plano", "probabilidad": "Alta|Media|Baja"}],
  "receta": [{"medicamento": "...", "dosis": "...", "frecuencia": "...", "duracion": "...", "indicaciones": "..."}],
  "resumen_paciente": "...",
  "alertas": [{"tipo": "alergia|interaccion|clinica", "descripcion": "...", "severidad": "Alta|Media|Baja"}]
}
*Nota: 'receta' y 'alertas' son siempre listas de objetos. Si no hay datos, devuelve una lista vacía [].*"""

    # --- 2. USER PROMPT (Los datos específicos de esta consulta) ---
    allergies = [
        f"- {a.allergen} ({a.severity}): {a.reaction}"
        for a in patient.allergies
    ]
    medications = [
        f"- {m.name} {m.dosage}, {m.frequency}"
        for m in patient.medications
    ]
    lista_alergias_str = (
        chr(10).join(allergies) if allergies else "Ninguna registrada"
    )
    lista_medicamentos_str = (
        chr(10).join(medications) if medications else "Ninguno registrado"
    )

    age = _calculate_age(patient.date_of_birth)
    age_str = f"{age} años" if age is not None else "No registrada"

    user_prompt = f"""Analiza la siguiente consulta y extrae la información clínica requerida en el formato JSON establecido.

=== DATOS DEL PACIENTE ===
- ID: {patient.id}
- Nombre: {patient.first_name} {patient.last_name}
- Edad: {age_str}
- Género: {patient.gender}
- ALÉRGENOS REGISTRADOS: {lista_alergias_str}
- MEDICAMENTOS ACTUALES: {lista_medicamentos_str}

=== DATOS DE LA CONSULTA ===
- Signos vitales: {consultation.vital_signs}
- Examen físico: {consultation.physical_exam}
- Conversación:
{consultation.conversation_text}

Procesa la información ahora:"""
    return system_prompt, user_prompt


@router.post("/process-consultation", response_model=AIClinicalOutput)
async def process_consultation(
    consultation: ConsultationInput,
    db: Session = Depends(get_db),
):
    logger.info(
        "Iniciando procesamiento de consulta para paciente ID: {id}",
        id=consultation.patient_id,
    )

    # 1. Buscar paciente
    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    if patient is None:
        logger.error(
            "Paciente no encontrado (ID: {id}); se aborta el procesamiento.",
            id=consultation.patient_id,
        )
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # 2. Construir los prompts (compartidos por ambos proveedores)
    system_prompt, user_prompt = _build_prompts(patient, consultation)

    provider = (consultation.ai_provider or "gemini").strip().lower()

    # 3-4. Obtener la respuesta de la IA según el proveedor seleccionado
    try:
        if provider == "gemini":
            # --- Proveedor en la nube: Gemini + Function Calling (catálogo SQL) ---
            logger.info(
                "Procesando con Gemini API (modelo: {model})",
                model=GEMINI_MODEL_NAME,
            )
            result = run_gemini_clinical_pipeline(
                model_name=GEMINI_MODEL_NAME,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_text=consultation.conversation_text,
                physical_exam=consultation.physical_exam,
            )

        elif provider == "ollama":
            # --- Proveedor local: Ollama ---
            logger.info("Procesando con modelo local Ollama")
            payload = {
                "model": "llama3.1",
                "system": system_prompt,
                "prompt": user_prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.0},
            }
            logger.debug(
                "Enviando prompts al modelo local de Ollama ({model}) en {url}.",
                model=payload["model"],
                url=OLLAMA_URL,
            )
            response = requests.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            respuesta_texto = response.json().get("response", "{}")
            result = json.loads(respuesta_texto)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Proveedor de IA no soportado: {consultation.ai_provider}",
            )

        # --- INICIO DE VALIDACIÓN MANUAL (PYTHON), común a ambos proveedores ---
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

        # 4b. Enriquecer diagnósticos con CIE-11 oficial (OMS) en paralelo
        logger.info(
            "Enriqueciendo {n} diagnóstico(s) con la API CIE-11 de la OMS.",
            n=len(result.get("diagnosticos_sugeridos") or []),
        )
        result["diagnosticos_sugeridos"] = await enrich_diagnoses_with_icd11(
            result.get("diagnosticos_sugeridos") or []
        )

        # Validar la salida de la IA contra el esquema Pydantic original
        try:
            ai_output = AIClinicalOutput(**result)
        except Exception as validation_exc:
            logger.error(
                "Error al mapear la respuesta de {provider} a AIClinicalOutput: {err}",
                provider=provider,
                err=validation_exc,
            )
            logger.debug("Payload recibido para validación: {payload}", payload=result)
            raise HTTPException(
                status_code=500,
                detail=f"La respuesta de la IA no cumple el esquema esperado: {validation_exc}",
            ) from validation_exc

        logger.success(
            "La IA devolvió una respuesta estructurada válida para el paciente ID: {id} (proveedor: {provider}).",
            id=patient.id,
            provider=provider,
        )

        # 5. Persistir los resultados en PostgreSQL (transacción segura)
        try:
            saved = crud.save_consultation_results(
                db=db,
                patient_id=patient.id,
                input_data=consultation,
                ai_output=ai_output,
            )
        except Exception as db_exc:
            logger.error(
                "Error al guardar la consulta en la base de datos: {err}",
                err=db_exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Error al guardar la consulta en la base de datos: {db_exc}",
            ) from db_exc

        # 6. Adjuntar el folio recién generado para que el frontend pueda
        #    exportar el PDF directamente desde el Workspace.
        ai_output.folio = saved.folio

        # 7. Devolver el mismo JSON al frontend, ya persistido
        return ai_output

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al procesar la consulta con IA: {err}", err=exc)
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar consulta con IA: {exc}",
        ) from exc


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe un archivo de audio a texto usando faster-whisper (Whisper 'base')."""
    logger.info("Recibiendo archivo de audio para transcripción...")

    temp_path: str | None = None
    try:
        # 1. Guardar el audio subido en un archivo temporal
        suffix = os.path.splitext(file.filename or "")[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name

        # 2. Cargar el modelo y transcribir
        logger.debug("Cargando modelo Whisper y procesando audio...")
        model = _get_whisper_model()
        segments, _info = model.transcribe(temp_path)

        # 3. Concatenar los segmentos de texto resultantes
        texto_completo = "".join(segment.text for segment in segments).strip()

        logger.success(
            "Audio transcrito correctamente. Longitud: {n} caracteres.",
            n=len(texto_completo),
        )
        return {"transcription": texto_completo}

    except Exception as exc:
        logger.exception("Error durante la transcripción")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la transcripción: {exc}",
        ) from exc

    finally:
        # 4. Eliminar el archivo temporal siempre (haya o no error)
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _patient_name(patient: Patient | None) -> str:
    if patient is None:
        return "Paciente desconocido"
    return f"{patient.first_name} {patient.last_name}".strip()


@router.get("/consultations", response_model=list[ConsultationListItem])
def list_consultations(db: Session = Depends(get_db)):
    """Lista todas las consultas con folio, paciente y fecha (más recientes primero)."""
    consultations = (
        db.query(Consultation).order_by(Consultation.date.desc()).all()
    )
    return [
        ConsultationListItem(
            id=c.id,
            folio=c.folio,
            date=c.date,
            status=c.status,
            patient_id=c.patient_id,
            patient_name=_patient_name(c.patient),
        )
        for c in consultations
    ]


@router.get("/consultations/{folio}", response_model=ConsultationDetail)
def get_consultation_detail(folio: str, db: Session = Depends(get_db)):
    """Devuelve el detalle completo (SOAPE, receta y alertas) de una consulta."""
    consultation = (
        db.query(Consultation).filter(Consultation.folio == folio).first()
    )
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    note: ClinicalNote | None = consultation.clinical_note
    soape = {
        "subjetivo": note.subjective if note else "",
        "objetivo": note.objective if note else "",
        "analisis": note.analysis if note else "",
        "plan": note.plan if note else "",
        "evaluacion": note.evaluation if note else "",
    }

    receta = [
        {
            "medicamento": p.medication or "",
            "dosis": p.dose or "",
            "frecuencia": p.frequency or "",
            "duracion": p.duration or "",
            "indicaciones": p.indications or "",
        }
        for p in consultation.prescriptions
    ]

    alertas = [
        {
            "tipo": a.alert_type or "clinica",
            "descripcion": a.description or "",
            "severidad": a.severity or "Media",
        }
        for a in consultation.alerts
    ]

    diagnosticos = [
        {
            "codigo": d.codigo or "",
            "descripcion": d.description or "",
            "probabilidad": d.probabilidad or "",
        }
        for d in consultation.diagnostics
    ]

    return ConsultationDetail(
        id=consultation.id,
        folio=consultation.folio,
        date=consultation.date,
        status=consultation.status,
        patient_id=consultation.patient_id,
        patient_name=_patient_name(consultation.patient),
        resumen_paciente=consultation.reason,
        soape=soape,
        diagnosticos_sugeridos=diagnosticos,
        receta=receta,
        alertas=alertas,
    )


@router.get("/consultations/{folio}/export-pdf")
def export_consultation_pdf(folio: str, db: Session = Depends(get_db)):
    """Genera y descarga el PDF de una consulta (reportlab.platypus)."""
    consultation = (
        db.query(Consultation).filter(Consultation.folio == folio).first()
    )
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    # Recabar todos los datos necesarios (incluyendo al doctor asociado)
    patient = consultation.patient
    doctor = (
        db.query(Doctor).filter(Doctor.id == consultation.doctor_id).first()
        if consultation.doctor_id
        else None
    )
    note = consultation.clinical_note
    prescriptions = list(consultation.prescriptions)
    diagnostics = list(consultation.diagnostics)

    pdf_buffer = generate_consultation_pdf(
        consultation=consultation,
        patient=patient,
        doctor=doctor,
        note=note,
        prescriptions=prescriptions,
        diagnostics=diagnostics,
    )

    filename = f"consulta_{consultation.folio or consultation.id}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )