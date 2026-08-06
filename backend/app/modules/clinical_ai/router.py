import json
import os
import tempfile
from datetime import date
from difflib import SequenceMatcher

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
from app.modules.clinical_rag.doctor_feedback import (
    build_doctor_style_prompt_block,
    build_patient_symptoms_text,
    retrieve_doctor_style_examples,
    store_doctor_feedback,
)
from app.services.icd11_service import enrich_diagnoses_with_icd11, search_icd11_options
from . import crud
from .gemini_pipeline import run_gemini_clinical_pipeline
from .patient_summary import parse_patient_summary
from .pdf_generator import generate_clinical_note_pdf, generate_prescription_pdf
from .schemas import (
    AIClinicalOutput,
    ConsultationInput,
    ConsultationListItem,
    ConsultationDetail,
    FinalizeConsultationRequest,
    FinalizeConsultationResponse,
    Icd11SearchResponse,
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


def _build_prompts(
    patient: Patient,
    consultation: ConsultationInput,
    *,
    doctor_style_guide: str = "",
) -> tuple[str, str]:
    # --- 1. SYSTEM PROMPT (La personalidad y reglas) ---
    system_prompt = """Eres 'Aura Clinical Copilot', un asistente médico inteligente y estricto de grado clínico.

TUS REGLAS CRÍTICAS DE COMPORTAMIENTO:
1. ANTI-BUCLES Y CONCISIÓN: ESTÁ ESTRICTAMENTE PROHIBIDO repetir la misma oración, frase o palabra de forma consecutiva. Sé clínico, directo y telegráfico.
2. CERO ALUCINACIONES: No inventes información, síntomas, medicamentos, ni signos vitales que no estén explícitamente en el texto provisto. Utiliza EXACTAMENTE la edad proporcionada en los datos del paciente. NUNCA intentes calcularla ni modificarla.
3. FORMATO ESTRICTO: Devuelve ÚNICAMENTE un JSON válido. NINGÚN texto antes, NINGÚN texto después, ni bloques de código markdown (```json).
4. SEGURIDAD DEL PACIENTE (PRIORIDAD MÁXIMA): Compara SIEMPRE los medicamentos a recetar con las alergias registradas del paciente. Si hay riesgo de reacción cruzada o alergia, GENERA UNA ALERTA DE SEVERIDAD 'Alta' y OMITE ese medicamento de la receta. Sugiere una alternativa en el 'Plan'.
5. AISLAMIENTO DE CONTEXTO (OBLIGATORIO): Si recibes ejemplos de estilo del médico, guías clínicas u otros documentos de referencia, úsalos SOLO como plantilla de formato, tono y estructura. Los diagnósticos, enfermedades, códigos CIE-11, hallazgos y planes terapéuticos deben extraerse EXCLUSIVAMENTE de la conversación, signos vitales y examen físico de LA CONSULTA ACTUAL. Está ESTRICTAMENTE PROHIBIDO arrastrar, copiar o inferir patologías de documentos de otras consultas o del historial de estilo.

REGLAS DE RAZONAMIENTO CLÍNICO (SOAPE Y DIAGNÓSTICOS):
- SUBJETIVO: Extrae el malestar principal, evolución y síntomas referidos por el paciente en la conversación.
- OBJETIVO: Basa esto en los 'Signos vitales' y 'Examen físico'. Si van vacíos o no se mencionan en la charla, usa estrictamente la frase: "Pendiente de exploración física completa". NUNCA lo dejes en blanco.
- ANÁLISIS: Justifica brevemente por qué sugieres los diagnósticos basados en el Subjetivo y Objetivo de ESTA consulta (no de ejemplos previos).
- PLAN: Define los pasos a seguir (laboratorios, tratamiento, reposo). Si no hay datos, infiere el siguiente paso lógico (ej. "Realizar exploración física y prescribir tratamiento sintomático").
- DIAGNÓSTICOS: Devuelve SOLO nombres clínicos en texto plano. NUNCA inventes ni adivines códigos
  CIE-10/CIE-11. El campo "codigo" debe ir SIEMPRE como cadena vacía ""; el backend lo
  enriquecerá después con la API oficial de la OMS.
  Cada diagnóstico DEBE estar soportado por síntomas/hallazgos de la consulta actual.
  Si un diagnóstico aparece solo en documentos de referencia/estilo y NO en la consulta actual, DESCÁRTALO.
  IMPORTANTE para CIE-11: Extrae diagnósticos utilizando EXCLUSIVAMENTE términos médicos atómicos
  y estandarizados. NUNCA uses términos compuestos (ej. usa 'Faringitis' y 'Amigdalitis' por
  separado, NUNCA 'Faringoamigdalitis'). Omite modificadores temporales o de severidad en el
  nombre principal (ej. extrae 'Rinofaringitis' en lugar de 'Rinofaringitis aguda') para
  maximizar la coincidencia exacta en bases de datos.

RECETA (NORMATIVA MEXICANA — DENOMINACIÓN GENÉRICA PRIMERO):
Cada elemento de "receta" DEBE incluir:
- sustancia_activa: denominación genérica del fármaco (ej. "Paracetamol", "Amoxicilina").
  OBLIGATORIO. Es el dato que la normativa exige mostrar primero en la receta impresa.
- medicamento: nombre comercial/presentación exacta del catálogo institucional (complementario).
NUNCA dejes sustancia_activa vacío si prescribes un medicamento.

RESUMEN PARA EL PACIENTE (OBLIGATORIO — lenguaje sencillo, NO técnico):
El objeto "resumen_paciente" va en la receta que el paciente lleva a casa/farmacia.
Usa oraciones cortas, usted/tú natural en español de México, sin jerga clínica
(prohibido: eritema, crepitación, faringe hiperémica, códigos CIE, abreviaturas como IRA/TA).
NO copies el SOAPE. NO repitas la tabla completa de la receta.
Estructura FIJA de 4 campos (todos string):
- diagnostico_simple: qué tiene, en palabras claras (1–2 oraciones). OBLIGATORIO si hay diagnóstico.
- instrucciones_medicinas: refuerzo breve de cómo tomar/completar el tratamiento (NO copies la tabla de la receta). Si hay al menos un medicamento en 'receta', este campo es OBLIGATORIO y NO puede ir vacío (ej. completar antibiótico, con/sin alimentos, qué hacer si olvida una dosis).
- cuidados_casa: cuidados prácticos en casa (2–4 ideas). OBLIGATORIO en consultas ambulatorias.
- senales_alarma: cuándo regresar o ir a urgencias (criterios concretos). OBLIGATORIO.

ESTRUCTURA JSON OBLIGATORIA (Todas las claves deben existir):
{
  "soape": {"subjetivo": "...", "objetivo": "...", "analisis": "...", "plan": "...", "evaluacion": "..."},
  "diagnosticos_sugeridos": [{"codigo": "", "descripcion": "Nombre del diagnóstico en texto plano", "probabilidad": "Alta|Media|Baja"}],
  "receta": [{"sustancia_activa": "Denominación genérica (ej. Paracetamol)", "medicamento": "Nombre comercial exacto del catálogo", "dosis": "...", "frecuencia": "...", "duracion": "...", "indicaciones": "..."}],
  "resumen_paciente": {
    "diagnostico_simple": "...",
    "instrucciones_medicinas": "...",
    "cuidados_casa": "...",
    "senales_alarma": "..."
  },
  "alertas": [{"tipo": "alergia|interaccion|clinica", "descripcion": "...", "severidad": "Alta|Media|Baja"}]
}
*Nota: 'receta' y 'alertas' son siempre listas de objetos. Si no hay datos, devuelve una lista vacía [].*"""

    style_block = (doctor_style_guide or "").strip()
    if style_block:
        system_prompt = f"{system_prompt.strip()}\n\n{style_block}"

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


def _soape_to_comparable_text(soape: dict | None) -> str:
    """Aplana el SOAPE a un texto comparable (orden de claves estable)."""
    if not isinstance(soape, dict):
        return ""
    keys = ("subjetivo", "objetivo", "analisis", "plan", "evaluacion")
    parts: list[str] = []
    for key in keys:
        value = soape.get(key)
        text = "" if value is None else str(value).strip()
        parts.append(f"{key}:{text}")
    return "\n".join(parts)


def calculate_soape_similarity(
    ai_soape: dict | None,
    doctor_soape: dict | None,
) -> float:
    """Calcula similitud (0.0–1.0) entre SOAPE de la IA y del médico.

    Usa ``difflib.SequenceMatcher.ratio()`` sobre el texto aplanado del SOAPE.
    """
    original = _soape_to_comparable_text(ai_soape)
    final = _soape_to_comparable_text(doctor_soape)
    if not original and not final:
        return 1.0
    return float(SequenceMatcher(None, original, final).ratio())


async def _generate_clinical_draft(
    patient: Patient,
    consultation: ConsultationInput,
) -> AIClinicalOutput:
    """Ejecuta el pipeline IA + CIE-11 y retorna el borrador sin persistir."""
    # Feedback Loop: recupera estilo del médico desde Qdrant (embeddings locales)
    symptoms_text = build_patient_symptoms_text(
        conversation_text=consultation.conversation_text,
        vital_signs=consultation.vital_signs,
        physical_exam=consultation.physical_exam,
    )
    style_examples = retrieve_doctor_style_examples(symptoms_text, top_k=2)
    style_guide = build_doctor_style_prompt_block(style_examples)
    if style_guide:
        logger.info(
            "Feedback Loop — inyectando {n} ejemplo(s) de estilo en el System Prompt.",
            n=len(style_examples),
        )

    system_prompt, user_prompt = _build_prompts(
        patient,
        consultation,
        doctor_style_guide=style_guide,
    )
    provider = (consultation.ai_provider or "gemini").strip().lower()

    if provider == "gemini":
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

    if "alertas" not in result or result["alertas"] is None:
        result["alertas"] = []

    if not consultation.vital_signs or consultation.vital_signs.strip() == "":
        result["alertas"].append(
            {
                "tipo": "clinica",
                "descripcion": (
                    "No se registraron signos vitales en el formulario. "
                    "Es un requerimiento clínico indispensable."
                ),
                "severidad": "Alta",
            }
        )

    result.setdefault("soape", {})
    result.setdefault("diagnosticos_sugeridos", [])
    result.setdefault("receta", [])
    result.setdefault(
        "resumen_paciente",
        {
            "diagnostico_simple": "",
            "instrucciones_medicinas": "",
            "cuidados_casa": "",
            "senales_alarma": "",
        },
    )

    logger.info(
        "Enriqueciendo {n} diagnóstico(s) con la API CIE-11 de la OMS.",
        n=len(result.get("diagnosticos_sugeridos") or []),
    )
    result["diagnosticos_sugeridos"] = await enrich_diagnoses_with_icd11(
        result.get("diagnosticos_sugeridos") or []
    )

    try:
        return AIClinicalOutput(**result)
    except Exception as validation_exc:
        logger.error(
            "Error al mapear la respuesta de {provider} a AIClinicalOutput: {err}",
            provider=provider,
            err=validation_exc,
        )
        logger.debug("Payload recibido para validación: {payload}", payload=result)
        raise HTTPException(
            status_code=500,
            detail=(
                "La respuesta de la IA no cumple el esquema esperado: "
                f"{validation_exc}"
            ),
        ) from validation_exc


@router.get("/icd11/search", response_model=Icd11SearchResponse)
async def search_icd11(q: str = "", limit: int = 10):
    """Typeahead CIE-11 para que el médico añada/corrija diagnósticos."""
    query = (q or "").strip()
    if len(query) < 2:
        return Icd11SearchResponse(results=[])

    capped = max(1, min(int(limit or 10), 20))
    results = await search_icd11_options(query, limit=capped)
    return Icd11SearchResponse(results=results)


@router.post("/generate-draft", response_model=AIClinicalOutput)
async def generate_draft(
    consultation: ConsultationInput,
    db: Session = Depends(get_db),
):
    """Genera el borrador clínico (IA + CIE-11) sin guardar ni emitir PDF.

    Human-in-the-Loop — Paso 1: el médico revisa/edita este JSON en el frontend.
    """
    logger.info(
        "Generando borrador clínico para paciente ID: {id}",
        id=consultation.patient_id,
    )

    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    try:
        draft = await _generate_clinical_draft(patient, consultation)
        logger.success(
            "Borrador clínico listo para revisión humana (paciente ID: {id}).",
            id=patient.id,
        )
        return draft
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al generar borrador clínico: {err}", err=exc)
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar borrador clínico: {exc}",
        ) from exc


@router.post("/finalize-consultation", response_model=FinalizeConsultationResponse)
def finalize_consultation(
    payload: FinalizeConsultationRequest,
    db: Session = Depends(get_db),
):
    """Persiste la versión final del médico, calcula precisión IA y habilita PDF.

    Human-in-the-Loop — Paso 2: compara SOAPE original vs. editado, guarda en
    PostgreSQL y deja listo el folio para exportar nota clínica y receta.
    """
    logger.info(
        "Finalizando consulta Human-in-the-Loop para paciente ID: {id}",
        id=payload.patient_id,
    )

    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    accuracy = calculate_soape_similarity(
        payload.ai_original_data.soape,
        payload.doctor_final_data.soape,
    )
    logger.info(
        "Precisión IA (similitud SOAPE): {score:.4f}",
        score=accuracy,
    )

    input_data = ConsultationInput(
        patient_id=payload.patient_id,
        conversation_text=payload.conversation_text,
        vital_signs=payload.vital_signs,
        physical_exam=payload.physical_exam,
    )

    try:
        saved = crud.save_consultation_results(
            db=db,
            patient_id=patient.id,
            input_data=input_data,
            ai_output=payload.doctor_final_data,
            ai_accuracy_score=accuracy,
        )
    except Exception as db_exc:
        logger.error(
            "Error al guardar la consulta finalizada: {err}",
            err=db_exc,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar la consulta en la base de datos: {db_exc}",
        ) from db_exc

    # Feedback Loop: si accuracy < 0.95, indexar corrección con embeddings locales
    if accuracy < 0.95:
        symptoms_text = build_patient_symptoms_text(
            conversation_text=payload.conversation_text,
            vital_signs=payload.vital_signs,
            physical_exam=payload.physical_exam,
        )
        store_doctor_feedback(
            patient_symptoms=symptoms_text,
            ai_soape=payload.ai_original_data.soape,
            doctor_soape=payload.doctor_final_data.soape,
            accuracy_score=accuracy,
            patient_id=payload.patient_id,
            folio=saved.folio,
        )

    final_output = payload.doctor_final_data.model_copy(deep=True)
    final_output.folio = saved.folio
    final_output.ai_accuracy_score = accuracy

    logger.success(
        "Consulta {folio} finalizada. ai_accuracy_score={score:.4f}",
        folio=saved.folio,
        score=accuracy,
    )

    return FinalizeConsultationResponse(
        folio=saved.folio or "",
        ai_accuracy_score=accuracy,
        consultation=final_output,
    )


@router.post("/process-consultation", response_model=AIClinicalOutput)
async def process_consultation(
    consultation: ConsultationInput,
    db: Session = Depends(get_db),
):
    """Compatibilidad: genera borrador + persiste en un solo paso.

    Preferir el flujo Human-in-the-Loop:
    ``/generate-draft`` → revisión médica → ``/finalize-consultation``.
    """
    logger.info(
        "Iniciando procesamiento de consulta (legacy) para paciente ID: {id}",
        id=consultation.patient_id,
    )

    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    if patient is None:
        logger.error(
            "Paciente no encontrado (ID: {id}); se aborta el procesamiento.",
            id=consultation.patient_id,
        )
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    try:
        ai_output = await _generate_clinical_draft(patient, consultation)
        logger.success(
            "La IA devolvió una respuesta estructurada válida para el paciente ID: {id}.",
            id=patient.id,
        )

        try:
            saved = crud.save_consultation_results(
                db=db,
                patient_id=patient.id,
                input_data=consultation,
                ai_output=ai_output,
                ai_accuracy_score=None,
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

        ai_output.folio = saved.folio
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
            "sustancia_activa": p.active_ingredient or "",
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
        resumen_paciente=parse_patient_summary(consultation.reason),
        soape=soape,
        diagnosticos_sugeridos=diagnosticos,
        receta=receta,
        alertas=alertas,
    )


def _load_consultation_export_context(db: Session, folio: str):
    """Carga consulta + relaciones necesarias para exportar PDFs."""
    consultation = (
        db.query(Consultation).filter(Consultation.folio == folio).first()
    )
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    patient = consultation.patient
    doctor = (
        db.query(Doctor).filter(Doctor.id == consultation.doctor_id).first()
        if consultation.doctor_id
        else None
    )
    allergies = list(patient.allergies) if patient is not None else []
    return {
        "consultation": consultation,
        "patient": patient,
        "doctor": doctor,
        "note": consultation.clinical_note,
        "prescriptions": list(consultation.prescriptions),
        "diagnostics": list(consultation.diagnostics),
        "allergies": allergies,
        "patient_summary": parse_patient_summary(consultation.reason),
    }


def _pdf_response(buffer, filename: str) -> StreamingResponse:
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/consultations/{folio}/export-pdf/nota-clinica")
def export_clinical_note_pdf(folio: str, db: Session = Depends(get_db)):
    """PDF interno: SOAPE + CIE-11 (sin receta ni resumen al paciente)."""
    ctx = _load_consultation_export_context(db, folio)
    pdf_buffer = generate_clinical_note_pdf(
        consultation=ctx["consultation"],
        patient=ctx["patient"],
        doctor=ctx["doctor"],
        note=ctx["note"],
        diagnostics=ctx["diagnostics"],
    )
    filename = f"nota_clinica_{ctx['consultation'].folio or ctx['consultation'].id}.pdf"
    return _pdf_response(pdf_buffer, filename)


@router.get("/consultations/{folio}/export-pdf/receta")
def export_prescription_pdf(folio: str, db: Session = Depends(get_db)):
    """PDF para paciente/farmacia: receta + resumen amigable (sin SOAPE)."""
    ctx = _load_consultation_export_context(db, folio)
    pdf_buffer = generate_prescription_pdf(
        consultation=ctx["consultation"],
        patient=ctx["patient"],
        doctor=ctx["doctor"],
        prescriptions=ctx["prescriptions"],
        allergies=ctx["allergies"],
        patient_summary=ctx["patient_summary"],
    )
    filename = f"receta_{ctx['consultation'].folio or ctx['consultation'].id}.pdf"
    return _pdf_response(pdf_buffer, filename)


@router.get("/consultations/{folio}/export-pdf")
def export_consultation_pdf_legacy(folio: str, db: Session = Depends(get_db)):
    """Compatibilidad: redirige al PDF de receta (documento para el paciente)."""
    return export_prescription_pdf(folio, db)