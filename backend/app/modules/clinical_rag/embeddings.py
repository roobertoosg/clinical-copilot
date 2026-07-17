"""Cliente de embeddings locales vía Ollama (nomic-embed-text, 768 dims)."""

from __future__ import annotations

import os

import requests
from loguru import logger

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"


def _embeddings_endpoint() -> str:
    """URL del endpoint de embeddings, normalizada desde OLLAMA_URL."""
    base = OLLAMA_URL.rstrip("/")
    if base.endswith("/api/generate"):
        base = base[: -len("/api/generate")]
    if base.endswith("/api/embeddings"):
        return base
    return f"{base}/api/embeddings"


def get_ollama_embedding(text: str) -> list[float]:
    """Llama a la API local de Ollama para vectorizar texto."""
    try:
        response = requests.post(
            _embeddings_endpoint(),
            json={"model": EMBEDDING_MODEL, "prompt": text},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("embedding", [])
    except Exception as exc:
        logger.error("Error al generar embedding con Ollama: {err}", err=exc)
        return []
