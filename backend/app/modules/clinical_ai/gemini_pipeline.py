"""Pipeline de Gemini con Function Calling para el catálogo farmacéutico."""

from __future__ import annotations

import json

import google.generativeai as genai
from fastapi import HTTPException
from loguru import logger

from app.modules.clinical_rag.retriever import retrieve_context

from .tools import consultar_inventario_farmacia

# Instrucción adicional exclusiva de Gemini (Capa 1 — catálogo SQL)
GEMINI_CATALOG_INSTRUCTION = """
REGLA DE CATÁLOGO FARMACÉUTICO (OBLIGATORIO — CAPA 1):
Antes de incluir CUALQUIER medicamento en la sección "receta" del JSON final, DEBES invocar
la herramienta `consultar_inventario_farmacia` para cada sustancia activa que vayas a prescribir.
Usa EXCLUSIVAMENTE los productos, marcas, laboratorios y códigos EAN devueltos por la herramienta.
Si la herramienta no devuelve resultados para una sustancia, NO incluyas ese medicamento en la receta;
genera una alerta clínica explicando que no hay producto disponible en el catálogo institucional.
"""


def _append_catalog_instruction(system_prompt: str) -> str:
    return f"{system_prompt.strip()}\n\n{GEMINI_CATALOG_INSTRUCTION.strip()}"


def _clean_json_text(raw_text: str) -> str:
    """Elimina fences markdown residuales antes de parsear el JSON."""
    texto_json = raw_text.strip()
    if texto_json.startswith("```json"):
        texto_json = texto_json[7:]
    if texto_json.startswith("```"):
        texto_json = texto_json[3:]
    if texto_json.endswith("```"):
        texto_json = texto_json[:-3]
    return texto_json.strip()


# Configuración explícita de la Fase 2 (JSON clínico final)
GEMINI_PHASE2_CONFIG = genai.types.GenerationConfig(
    response_mime_type="application/json",
    temperature=0.2,
    max_output_tokens=8192,
)


def _build_rag_enriched_prompt(
    user_prompt: str,
    *,
    conversation_text: str | None = None,
    physical_exam: str | None = None,
) -> str:
    """Recupera contexto clínico de Qdrant y lo antepone al prompt del usuario."""
    query_parts: list[str] = []
    if conversation_text and conversation_text.strip():
        query_parts.append(conversation_text.strip())
    if physical_exam and physical_exam.strip():
        exam = physical_exam.strip()
        if exam.lower() not in ("no registrado", "n/a", "na"):
            query_parts.append(exam)

    if not query_parts:
        return user_prompt

    rag_query = "\n".join(query_parts)
    context_chunks = retrieve_context(rag_query, top_k=3)

    if not context_chunks:
        logger.debug("RAG — sin chunks recuperados; prompt sin enriquecer.")
        return user_prompt

    rag_block = (
        "=== CONTEXTO CLÍNICO DE REFERENCIA (GUÍAS/NOM) ===\n"
        + "\n\n".join(context_chunks)
        + "\n(Nota para el LLM: Utiliza este contexto como apoyo informativo, "
        "pero la prioridad es la seguridad clínica).\n\n"
    )
    logger.info(
        "RAG — {n} chunk(s) inyectados al prompt de Fase 1.",
        n=len(context_chunks),
    )
    return rag_block + user_prompt


def run_gemini_clinical_pipeline(
    *,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    conversation_text: str | None = None,
    physical_exam: str | None = None,
) -> dict:
    """Ejecuta Gemini en dos fases: tools (inventario) → JSON clínico final.

    Fase 1: chat con function calling automático (sin response_schema).
    Fase 2: mismo chat pide el JSON final con response_mime_type=application/json.
    """
    user_prompt = _build_rag_enriched_prompt(
        user_prompt,
        conversation_text=conversation_text,
        physical_exam=physical_exam,
    )

    enriched_system = _append_catalog_instruction(system_prompt)

    logger.debug(
        "Inicializando GenerativeModel ({model}) con tool consultar_inventario_farmacia",
        model=model_name,
    )
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=enriched_system,
        tools=[consultar_inventario_farmacia],
    )

    chat = model.start_chat(enable_automatic_function_calling=True)

    tool_phase_prompt = (
        f"{user_prompt}\n\n"
        "PASO PREVIO OBLIGATORIO: Identifica las sustancias activas que necesitas recetar "
        "e invoca la herramienta consultar_inventario_farmacia para cada una. "
        "Resume brevemente qué productos del catálogo encontraste (producto, marca, EAN, laboratorio)."
    )

    json_response = None
    try:
        logger.info("Gemini Fase 1 — consulta de inventario farmacéutico (function calling)")
        tool_response = chat.send_message(tool_phase_prompt)
        tool_summary = (tool_response.text or "").strip()
        logger.debug(
            "Gemini Fase 1 completada ({n} caracteres en respuesta).",
            n=len(tool_summary),
        )

        logger.info("Gemini Fase 2 — generación del JSON clínico estructurado")
        json_response = chat.send_message(
            "Con base en el análisis clínico y los productos verificados en el catálogo, "
            "genera AHORA ÚNICAMENTE el JSON clínico final con la estructura obligatoria "
            "(soape, diagnosticos_sugeridos, receta, resumen_paciente, alertas). "
            "En 'receta', usa los nombres comerciales exactos del inventario consultado. "
            "NO incluyas markdown ni texto fuera del JSON.",
            generation_config=GEMINI_PHASE2_CONFIG,
        )

        if not json_response.text:
            logger.error("Gemini Fase 2 devolvió una respuesta vacía.")
            raise HTTPException(
                status_code=500,
                detail="Gemini devolvió una respuesta JSON vacía.",
            )

        texto_json = _clean_json_text(json_response.text)
        logger.debug(
            "Texto JSON de Gemini recibido ({n} caracteres tras limpieza).",
            n=len(texto_json),
        )
        result = json.loads(texto_json)
        logger.success(
            "Pipeline Gemini completado. Claves en JSON: {keys}",
            keys=list(result.keys()),
        )
        return result

    except HTTPException:
        raise
    except json.JSONDecodeError as json_exc:
        raw = _clean_json_text(json_response.text) if json_response and json_response.text else ""
        logger.error(
            "Error al parsear JSON de Gemini Fase 2: {err}. Fragmento: {text}",
            err=json_exc,
            text=raw[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"La respuesta de Gemini no es un JSON válido: {json_exc}",
        ) from json_exc
    except Exception as exc:
        logger.exception("Error en pipeline Gemini con function calling")
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar consulta con Gemini: {exc}",
        ) from exc
