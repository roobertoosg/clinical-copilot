"""Utilidades para el resumen estructurado al paciente (4 campos)."""

from __future__ import annotations

import json
from typing import Any


SUMMARY_KEYS = (
    "diagnostico_simple",
    "instrucciones_medicinas",
    "cuidados_casa",
    "senales_alarma",
)

EMPTY_SUMMARY = {key: "" for key in SUMMARY_KEYS}


def coerce_patient_summary(value: Any) -> dict[str, str]:
    """Normaliza string legado / dict / None a los 4 campos."""
    if value is None:
        return dict(EMPTY_SUMMARY)

    if isinstance(value, str):
        text = value.strip()
        out = dict(EMPTY_SUMMARY)
        if text:
            # Texto plano antiguo: va a "qué tiene" para no perderlo
            out["diagnostico_simple"] = text
        return out

    if isinstance(value, dict):
        return {
            key: ("" if value.get(key) is None else str(value.get(key))).strip()
            for key in SUMMARY_KEYS
        }

    # Objeto Pydantic u otro con atributos
    if hasattr(value, "model_dump"):
        return coerce_patient_summary(value.model_dump())
    if hasattr(value, "dict"):
        return coerce_patient_summary(value.dict())

    return dict(EMPTY_SUMMARY)


def serialize_patient_summary(value: Any) -> str:
    """Serializa a JSON para guardar en consultations.reason."""
    return json.dumps(coerce_patient_summary(value), ensure_ascii=False)


def parse_patient_summary(raw: str | None) -> dict[str, str]:
    """Lee consultations.reason (JSON nuevo o texto legado)."""
    if raw is None:
        return dict(EMPTY_SUMMARY)
    text = str(raw).strip()
    if not text:
        return dict(EMPTY_SUMMARY)
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return coerce_patient_summary(data)
        except json.JSONDecodeError:
            pass
    return coerce_patient_summary(text)


def summary_has_content(value: Any) -> bool:
    data = coerce_patient_summary(value)
    return any(data[key] for key in SUMMARY_KEYS)
