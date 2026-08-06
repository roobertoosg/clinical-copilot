"""Cliente asíncrono para la API oficial CIE-11 (ICD-11) de la OMS.

Documentación de referencia:
- Autenticación OAuth 2.0 (client_credentials)
- Búsqueda en la linealización MMS (API v2)
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger

# FORZAR LA LECTURA DEL .ENV (ruta absoluta al backend/, independiente del CWD)
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env", override=True)

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
SEARCH_URL = "https://id.who.int/icd/release/11/2024-01/mms/search"
TOKEN_SCOPE = "icdapi_access"
API_VERSION = "v2"

# Renovar el token unos segundos antes de que expire
_TOKEN_EXPIRY_SKEW_SECONDS = 60

# Adjetivos / modificadores que suelen impedir match exacto en CIE-11
_DIAGNOSIS_NOISE_WORDS: tuple[str, ...] = (
    "aguda",
    "agudo",
    "crónica",
    "cronica",
    "crónico",
    "cronico",
    "leve",
    "moderada",
    "moderado",
    "severa",
    "severo",
    "grave",
    "inespecífica",
    "inespecifica",
    "inespecífico",
    "inespecifico",
    "sin especificación",
    "sin especificacion",
    "no especificada",
    "no especificado",
)

_NOISE_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(w) for w in sorted(_DIAGNOSIS_NOISE_WORDS, key=len, reverse=True))
    + r")\b",
    flags=re.IGNORECASE,
)


def _env_credential(name: str) -> str:
    """Lee una credencial del entorno y limpia espacios/comillas residuales."""
    raw = os.getenv(name, "") or ""
    return raw.strip().strip('"').strip("'")


class ICD11Client:
    """Cliente HTTP asíncrono para autenticación y búsqueda CIE-11 (OMS)."""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Inicializa el cliente con credenciales OAuth 2.0.

        Args:
            client_id: Client ID de la OMS. Por defecto lee ``ICD11_CLIENT_ID``.
            client_secret: Client Secret. Por defecto lee ``ICD11_CLIENT_SECRET``.
            timeout: Timeout en segundos para las peticiones HTTP.
        """
        self._client_id: str = (client_id or _env_credential("ICD11_CLIENT_ID")).strip()
        self._client_secret: str = (
            client_secret or _env_credential("ICD11_CLIENT_SECRET")
        ).strip()
        self._timeout: float = timeout

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        if self._credentials_configured():
            logger.debug(
                "ICD-11 — credenciales cargadas desde .env (client_id presente)."
            )
        else:
            logger.warning(
                "ICD-11 — no se encontraron ICD11_CLIENT_ID / ICD11_CLIENT_SECRET "
                "en {path}",
                path=_BACKEND_DIR / ".env",
            )

    def _credentials_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    @staticmethod
    def _clean_diagnosis_query(query: str) -> str:
        """Elimina adjetivos/modificadores comunes que reducen el match CIE-11.

        Ejemplos:
            ``"Rinofaringitis aguda"`` → ``"Rinofaringitis"``
            ``"Faringitis crónica leve"`` → ``"Faringitis"``
        """
        text = (query or "").strip()
        if not text:
            return ""
        text = _NOISE_PATTERN.sub(" ", text)
        text = re.sub(r"[,\s/;|-]+", " ", text)
        return text.strip(" .,-;:")

    async def _fetch_access_token(self) -> str:
        """Solicita un Bearer token vía OAuth 2.0 client_credentials.

        Returns:
            Access token (Bearer) emitido por la OMS.

        Raises:
            ValueError: Si faltan credenciales en el entorno.
            httpx.HTTPStatusError: Si la OMS responde con error HTTP.
            httpx.RequestError: Si hay fallo de red.
        """
        if not self._credentials_configured():
            raise ValueError(
                "Faltan ICD11_CLIENT_ID / ICD11_CLIENT_SECRET en el entorno."
            )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "scope": TOKEN_SCOPE,
                },
                auth=(self._client_id, self._client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()

        token = str(payload.get("access_token") or "")
        if not token:
            raise ValueError("La OMS no devolvió access_token en la respuesta.")

        expires_in = int(payload.get("expires_in") or 3600)
        self._access_token = token
        self._token_expires_at = (
            time.monotonic() + expires_in - _TOKEN_EXPIRY_SKEW_SECONDS
        )
        logger.debug(
            "ICD-11 — token OAuth obtenido (expira en ~{secs}s).",
            secs=expires_in,
        )
        return token

    async def _get_bearer_token(self) -> str:
        """Devuelve un Bearer token válido, reutilizando el cache si aplica.

        Returns:
            Access token listo para el header ``Authorization: Bearer …``.
        """
        if (
            self._access_token
            and time.monotonic() < self._token_expires_at
        ):
            return self._access_token
        return await self._fetch_access_token()

    async def _request_search(
        self,
        query: str,
        *,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Ejecuta una petición GET de búsqueda MMS y normaliza la respuesta."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                SEARCH_URL,
                params={"q": query},
                headers=headers,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        entities = data.get("destinationEntities")
        if not isinstance(entities, list):
            data["destinationEntities"] = []
        return data

    async def search_diagnosis(self, query: str) -> dict[str, Any]:
        """Busca diagnósticos en la linealización MMS del CIE-11 (API v2).

        Flujo resiliente:
        1. Petición con el query original.
        2. Si no hay ``destinationEntities``, limpia adjetivos y reintenta.
        3. Si aún falla, retorna estructura vacía / error controlado.

        Args:
            query: Texto clínico a buscar (español o inglés).

        Returns:
            Diccionario JSON de la OMS (típicamente con clave ``destinationEntities``).
            Si la petición falla o la query está vacía, retorna
            ``{"destinationEntities": [], "error": "..."}``.
        """
        original = (query or "").strip()
        if not original:
            return {
                "destinationEntities": [],
                "error": "La query de búsqueda está vacía.",
            }

        if not self._credentials_configured():
            logger.error(
                "ICD-11 — credenciales no configuradas; se omite la búsqueda."
            )
            return {
                "destinationEntities": [],
                "error": "Credenciales ICD-11 no configuradas.",
            }

        try:
            token = await self._get_bearer_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "API-Version": API_VERSION,
                "Accept": "application/json",
                "Accept-Language": "es",
            }

            # 1) Intento original
            data = await self._request_search(original, headers=headers)
            hits = data.get("destinationEntities") or []
            logger.info(
                "ICD-11 — búsqueda '{q}' → {n} resultado(s).",
                q=original[:80],
                n=len(hits),
            )
            if hits:
                return data

            # 2) Reintento con query limpia (sin adjetivos/modificadores)
            simplified = self._clean_diagnosis_query(original)
            if simplified and simplified.casefold() != original.casefold():
                logger.info(
                    "ICD-11 — sin match; reintento con query limpia '{q}'.",
                    q=simplified[:80],
                )
                data = await self._request_search(simplified, headers=headers)
                hits = data.get("destinationEntities") or []
                logger.info(
                    "ICD-11 — reintento '{q}' → {n} resultado(s).",
                    q=simplified[:80],
                    n=len(hits),
                )
                if hits:
                    data["queryUsed"] = simplified
                    data["retried"] = True
                    return data

            # 3) Fallback controlado
            return {
                "destinationEntities": [],
                "error": f"Sin resultados CIE-11 para '{original}'.",
                "queryTried": original,
                "queryCleaned": simplified or original,
            }

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.error(
                "ICD-11 — error HTTP {status} en búsqueda '{q}': {err}",
                status=status,
                q=original[:80],
                err=exc,
            )
            return {
                "destinationEntities": [],
                "error": f"Error HTTP {status} al consultar CIE-11.",
            }
        except httpx.RequestError as exc:
            logger.error(
                "ICD-11 — error de red en búsqueda '{q}': {err}",
                q=original[:80],
                err=exc,
            )
            return {
                "destinationEntities": [],
                "error": "Error de red al consultar la API CIE-11.",
            }
        except Exception as exc:
            logger.exception(
                "ICD-11 — fallo inesperado en search_diagnosis: {err}",
                err=exc,
            )
            return {
                "destinationEntities": [],
                "error": "Error inesperado al consultar CIE-11.",
            }


# ── Enriquecimiento de diagnósticos con CIE-11 ─────────────────

ICD11_FALLBACK_CODE = "[Sin Código]"

_icd11_client_singleton: ICD11Client | None = None


def get_icd11_client() -> ICD11Client:
    """Singleton del cliente CIE-11 (reutiliza el token OAuth en cache)."""
    global _icd11_client_singleton
    if _icd11_client_singleton is None:
        _icd11_client_singleton = ICD11Client()
    return _icd11_client_singleton


def _normalize_icd_title(title: Any) -> str:
    """Normaliza el título OMS (string, objeto ``@value`` o HTML)."""
    if isinstance(title, dict):
        title = title.get("@value") or title.get("value") or ""
    text = str(title or "")
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split()).strip()


def _extract_diagnosis_fields(dx: Any) -> tuple[str, str]:
    """Extrae (nombre, probabilidad) tolerando dicts o strings del LLM."""
    if isinstance(dx, str):
        return dx.strip(), ""
    if isinstance(dx, dict):
        name = (
            dx.get("descripcion")
            or dx.get("nombre")
            or dx.get("title")
            or dx.get("diagnosis")
            or ""
        )
        prob = dx.get("probabilidad") or dx.get("probability") or ""
        return str(name).strip(), str(prob).strip()
    return str(dx).strip(), ""


async def _enrich_one_diagnosis(
    client: ICD11Client,
    dx: Any,
) -> dict[str, str]:
    """Enriquece un diagnóstico con el primer match CIE-11 de la OMS."""
    name, probabilidad = _extract_diagnosis_fields(dx)
    if not name:
        return {
            "codigo": ICD11_FALLBACK_CODE,
            "descripcion": "",
            "probabilidad": probabilidad,
        }

    search_result = await client.search_diagnosis(name)
    entities = search_result.get("destinationEntities") or []
    if not entities:
        logger.warning(
            "ICD-11 — sin match para '{name}'; se usa fallback.",
            name=name[:80],
        )
        return {
            "codigo": ICD11_FALLBACK_CODE,
            "descripcion": name,
            "probabilidad": probabilidad,
        }

    first = entities[0] if isinstance(entities[0], dict) else {}
    code = str(first.get("theCode") or "").strip() or ICD11_FALLBACK_CODE
    official_title = _normalize_icd_title(first.get("title")) or name

    return {
        "codigo": code,
        "descripcion": official_title,
        "probabilidad": probabilidad,
    }


async def enrich_diagnoses_with_icd11(
    diagnoses: list[Any],
    *,
    client: ICD11Client | None = None,
) -> list[dict[str, str]]:
    """Enriquece en paralelo una lista de diagnósticos con códigos CIE-11.

    Usa ``asyncio.gather`` para consultar la OMS sin serializar las búsquedas.
    Si un diagnóstico no tiene match, conserva el nombre de la IA y
    ``codigo="[Sin Código]"``.
    """
    if not diagnoses:
        return []

    icd_client = client or get_icd11_client()
    enriched = await asyncio.gather(
        *(_enrich_one_diagnosis(icd_client, dx) for dx in diagnoses)
    )
    logger.success(
        "ICD-11 — {n} diagnóstico(s) enriquecidos.",
        n=len(enriched),
    )
    return list(enriched)


async def search_icd11_options(
    query: str,
    *,
    limit: int = 10,
    client: ICD11Client | None = None,
) -> list[dict[str, str]]:
    """Busca opciones CIE-11 para typeahead del médico (código + título)."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    icd_client = client or get_icd11_client()
    raw = await icd_client.search_diagnosis(q)
    entities = raw.get("destinationEntities") or []
    results: list[dict[str, str]] = []

    for entity in entities:
        if not isinstance(entity, dict):
            continue
        code = str(entity.get("theCode") or "").strip()
        title = _normalize_icd_title(entity.get("title"))
        if not title:
            continue
        results.append(
            {
                "codigo": code or ICD11_FALLBACK_CODE,
                "descripcion": title,
            }
        )
        if len(results) >= limit:
            break

    return results
