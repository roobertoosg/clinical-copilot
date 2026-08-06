"""Feedback Loop: aprendizaje continuo del estilo del médico vía Qdrant.

Usa embeddings locales (Ollama / nomic-embed-text, 768 dims) y la colección
``doctor_feedback`` para guardar correcciones cuando la precisión IA < 0.95
e inyectar ejemplos similares en futuros borradores.
"""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger
from qdrant_client.http import models as qmodels

from .embeddings import get_ollama_embedding
from .retriever import VECTOR_SIZE, get_qdrant_client

FEEDBACK_COLLECTION = "doctor_feedback"
FEEDBACK_ACCURACY_THRESHOLD = 0.95
FEEDBACK_TOP_K = 2
# Cosine en Qdrant: score alto = más similar. Debajo de esto se descarta (evita cruces débiles).
FEEDBACK_MIN_SCORE = 0.72


def ensure_doctor_feedback_collection() -> None:
    """Crea la colección ``doctor_feedback`` (768 dims, Cosine) si no existe."""
    client = get_qdrant_client()
    try:
        existing = {c.name for c in client.get_collections().collections}
        if FEEDBACK_COLLECTION in existing:
            logger.debug(
                "Colección Qdrant '{name}' ya existe.",
                name=FEEDBACK_COLLECTION,
            )
            return

        logger.info(
            "Creando colección Qdrant '{name}' (dim={dim}, COSINE).",
            name=FEEDBACK_COLLECTION,
            dim=VECTOR_SIZE,
        )
        client.create_collection(
            collection_name=FEEDBACK_COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.success(
            "Colección '{name}' creada en Qdrant.",
            name=FEEDBACK_COLLECTION,
        )
    except Exception as exc:
        if "already exists" in str(exc).lower() or "exist" in str(exc).lower():
            logger.debug(
                "Colección '{name}' ya existía (condición de carrera).",
                name=FEEDBACK_COLLECTION,
            )
            return
        logger.exception(
            "Error al asegurar colección '{name}': {err}",
            name=FEEDBACK_COLLECTION,
            err=exc,
        )
        raise


def _format_soape(soape: dict[str, Any] | None) -> str:
    """Serializa un SOAPE a texto legible para el feedback."""
    if not isinstance(soape, dict):
        return ""
    keys = ("subjetivo", "objetivo", "analisis", "plan", "evaluacion")
    parts: list[str] = []
    for key in keys:
        value = soape.get(key)
        text = "" if value is None else str(value).strip()
        if text:
            parts.append(f"{key.capitalize()}: {text}")
    return " | ".join(parts) if parts else "(vacío)"


def build_patient_symptoms_text(
    *,
    conversation_text: str = "",
    vital_signs: str = "",
    physical_exam: str = "",
) -> str:
    """Construye el texto de contexto clínico (síntomas) para embedding/búsqueda."""
    parts: list[str] = []
    conv = (conversation_text or "").strip()
    if conv:
        parts.append(conv)
    vitals = (vital_signs or "").strip()
    if vitals and vitals.lower() not in ("no registrados", "n/a", "na"):
        parts.append(f"Signos vitales: {vitals}")
    exam = (physical_exam or "").strip()
    if exam and exam.lower() not in ("no registrado", "n/a", "na"):
        parts.append(f"Examen físico: {exam}")
    return "\n".join(parts).strip()


def build_feedback_document(
    *,
    patient_symptoms: str,
    ai_soape: dict[str, Any] | None,
    doctor_soape: dict[str, Any] | None,
) -> str:
    """Arma el documento de aprendizaje a indexar en Qdrant."""
    return (
        f"Contexto clínico: {patient_symptoms}. "
        f"Generado por IA: {_format_soape(ai_soape)}. "
        f"Corregido por el médico: {_format_soape(doctor_soape)}."
    )


def store_doctor_feedback(
    *,
    patient_symptoms: str,
    ai_soape: dict[str, Any] | None,
    doctor_soape: dict[str, Any] | None,
    accuracy_score: float,
    patient_id: int | None = None,
    folio: str | None = None,
) -> bool:
    """Indexa una corrección del médico si la precisión es baja.

    Returns:
        True si se guardó el punto en Qdrant; False si se omitió o falló.
    """
    if accuracy_score >= FEEDBACK_ACCURACY_THRESHOLD:
        logger.debug(
            "Feedback Loop — precisión {score:.4f} >= {thr}; no se indexa.",
            score=accuracy_score,
            thr=FEEDBACK_ACCURACY_THRESHOLD,
        )
        return False

    symptoms = (patient_symptoms or "").strip()
    if not symptoms:
        logger.warning(
            "Feedback Loop — sin síntomas/contexto; no se indexa la corrección."
        )
        return False

    document = build_feedback_document(
        patient_symptoms=symptoms,
        ai_soape=ai_soape,
        doctor_soape=doctor_soape,
    )

    try:
        ensure_doctor_feedback_collection()
        vector = get_ollama_embedding(document)
        if not vector:
            logger.warning(
                "Feedback Loop — embedding vacío; corrección no indexada."
            )
            return False

        client = get_qdrant_client()
        point_id = str(uuid.uuid4())
        client.upsert(
            collection_name=FEEDBACK_COLLECTION,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "content": document,
                        "patient_symptoms": symptoms,
                        "ai_soape": ai_soape or {},
                        "doctor_soape": doctor_soape or {},
                        "accuracy_score": accuracy_score,
                        "patient_id": patient_id,
                        "folio": folio,
                    },
                )
            ],
        )
        logger.success(
            "Feedback Loop — corrección indexada en '{col}' "
            "(accuracy={score:.4f}, id={pid}).",
            col=FEEDBACK_COLLECTION,
            score=accuracy_score,
            pid=point_id,
        )
        return True
    except Exception as exc:
        logger.exception(
            "Feedback Loop — error al guardar corrección: {err}",
            err=exc,
        )
        return False


def retrieve_doctor_style_examples(
    patient_symptoms: str,
    *,
    top_k: int = FEEDBACK_TOP_K,
) -> list[str]:
    """Recupera Top-K correcciones similares del historial del médico.

    Toda la vectorización es local (Ollama). Si Qdrant/embeddings fallan,
    retorna lista vacía sin romper el pipeline.
    """
    query = (patient_symptoms or "").strip()
    if not query:
        return []

    try:
        ensure_doctor_feedback_collection()
        query_vector = get_ollama_embedding(query)
        if not query_vector:
            logger.warning(
                "Feedback Loop — embedding de síntomas vacío; sin guía de estilo."
            )
            return []

        client = get_qdrant_client()
        # Pedimos más hits y filtramos por score para no arrastrar cruces débiles
        hits = client.search(
            collection_name=FEEDBACK_COLLECTION,
            query_vector=query_vector,
            limit=max(top_k * 3, 6),
            score_threshold=FEEDBACK_MIN_SCORE,
        )

        examples: list[str] = []
        for hit in hits:
            if len(examples) >= top_k:
                break
            score = float(getattr(hit, "score", 0.0) or 0.0)
            payload = hit.payload or {}
            # Preferir solo la redacción del médico (menos "Generado por IA" ruidoso)
            doctor_soape = payload.get("doctor_soape")
            if isinstance(doctor_soape, dict) and doctor_soape:
                content = (
                    "Redacción de referencia (OTRA consulta — ignorar enfermedades): "
                    + _format_soape(doctor_soape)
                )
            else:
                content = (payload.get("content") or "").strip()
                if content:
                    content = (
                        "Redacción de referencia (OTRA consulta — ignorar enfermedades): "
                        + content
                    )

            if content:
                examples.append(content)
                logger.debug(
                    "Feedback Loop — ejemplo aceptado score={score:.3f}",
                    score=score,
                )

        logger.info(
            "Feedback Loop — {n} ejemplo(s) de estilo recuperados "
            "(filtro score>={min}).",
            n=len(examples),
            min=FEEDBACK_MIN_SCORE,
        )
        return examples
    except Exception as exc:
        logger.exception(
            "Feedback Loop — error al recuperar estilo del médico: {err}",
            err=exc,
        )
        return []


def build_doctor_style_prompt_block(examples: list[str]) -> str:
    """Formatea el bloque a inyectar en el System Prompt.

    Los ejemplos son SOLO plantilla de tono/estructura. Nunca fuente de diagnósticos.
    """
    if not examples:
        return ""
    joined = "\n\n".join(f"- {ex}" for ex in examples)
    return (
        "### GUÍA DE ESTILO DEL MÉDICO (SOLO FORMA — NO CONTENIDO CLÍNICO):\n"
        "Los ejemplos siguientes pertenecen a OTRAS consultas distintas.\n"
        "Úsalos ÚNICAMENTE para imitar tono, concisión, orden y estilo redaccional.\n"
        "PROHIBIDO ABSOLUTO: copiar, arrastrar o reutilizar diagnósticos, enfermedades, "
        "códigos CIE, signos, planes terapéuticos o cualquier hallazgo clínico de estos "
        "ejemplos. El razonamiento clínico (SOAPE, diagnósticos, receta) debe basarse "
        "EXCLUSIVAMENTE en la conversación, signos vitales y examen físico del paciente "
        "ACTUAL.\n\n"
        f"{joined}"
    )
