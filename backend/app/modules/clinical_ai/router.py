import json
import os
import tempfile

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
from . import crud
from .pdf_generator import generate_consultation_pdf
from .schemas import (
    AIClinicalOutput,
    GeminiClinicalOutput,
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
            # --- Proveedor en la nube: Gemini ---
            logger.info(
                "Procesando con Gemini API (modelo: {model})",
                model=GEMINI_MODEL_NAME,
            )
            try:
                model = genai.GenerativeModel(
                    model_name=GEMINI_MODEL_NAME,
                    system_instruction=system_prompt,
                )
                logger.debug(
                    "Enviando prompt a Gemini con esquema estricto GeminiClinicalOutput"
                )
                response = model.generate_content(
                    user_prompt,
                    generation_config=genai.types.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=GeminiClinicalOutput,
                        temperature=0.0,
                    ),
                )

                if not response.text:
                    logger.error("Gemini devolvió una respuesta vacía.")
                    raise HTTPException(
                        status_code=500,
                        detail="Gemini devolvió una respuesta vacía.",
                    )

                logger.debug(
                    "Texto crudo de Gemini recibido ({n} caracteres).",
                    n=len(response.text),
                )
                try:
                    result = json.loads(response.text)
                except json.JSONDecodeError as json_exc:
                    logger.error(
                        "Error al parsear JSON de Gemini: {err}. Fragmento: {text}",
                        err=json_exc,
                        text=response.text[:500],
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"La respuesta de Gemini no es un JSON válido: {json_exc}",
                    ) from json_exc

                logger.success(
                    "Respuesta estructurada de Gemini recibida. Claves: {keys}",
                    keys=list(result.keys()),
                )

            except HTTPException:
                raise
            except Exception as gemini_exc:
                logger.exception("Error durante la llamada a Gemini API")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al procesar consulta con Gemini: {gemini_exc}",
                ) from gemini_exc

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