# Aura Clinical Copilot

Asistente clínico inteligente con **Human-in-the-Loop**: genera un borrador SOAPE + diagnósticos CIE-11 + receta a partir de la consulta, el médico lo revisa/edita y luego se finaliza, se guarda y se exporta a PDF.

Pensado para consulta ambulatoria en español (México).

---

## ¿Qué hace este proyecto?

1. El médico captura paciente, conversación, signos vitales y examen físico (opcional: audio → texto).
2. La IA genera un **borrador clínico** (Gemini por defecto, u Ollama local).
3. El médico **revisa y corrige** SOAPE y receta.
4. Al finalizar se guarda la consulta, se calcula precisión respecto al borrador IA y se descarga el PDF.

### Capas de apoyo a la IA

| Capa | Qué aporta |
|------|------------|
| Catálogo farmacéutico (PostgreSQL) | Gemini consulta inventario real antes de recetar |
| RAG de guías clínicas (Qdrant) | Contexto de NOMs / guías clínicas |
| CIE-11 (API OMS) | Códigos oficiales; el LLM no inventa códigos |
| Feedback del médico (Qdrant) | Aprende del estilo cuando el médico corrige el borrador |

---

## Arquitectura (vista rápida)

```
React (Vite)  →  FastAPI  →  PostgreSQL
                    ↓              ↓
                 Gemini / Ollama   medications_catalog
                    ↓
                 Qdrant (guías + feedback médico)
                    ↓
                 WHO ICD-11 API
```

| Pieza | Tecnología |
|-------|------------|
| Frontend | React 19 + Vite + React Router |
| Backend | FastAPI + SQLAlchemy + Uvicorn |
| Base de datos | PostgreSQL 15 (Docker, puerto **5433**) |
| Vectores | Qdrant (Docker, puerto **6333**) |
| IA nube | Google Gemini (`gemini-3.5-flash`) |
| IA / embeddings locales | Ollama (`llama3.1`, `nomic-embed-text`) |
| PDF | ReportLab |
| STT | faster-whisper |

---

## Requisitos previos

Instala en tu máquina:

| Requisito | Versión sugerida | Notas |
|-----------|------------------|--------|
| Git | cualquiera reciente | Clonar el repo |
| Docker + Docker Compose | v2+ | Postgres y Qdrant |
| Python | **3.10+** (recomendado 3.11/3.12) | Backend |
| Node.js | **18+** (recomendado 20 LTS) | Frontend |
| Ollama | opcional pero recomendado | Embeddings RAG + proveedor local |
| API Key de Gemini | recomendado | Flujo principal de IA |
| Credenciales ICD-11 OMS | recomendado | Códigos CIE-11 reales |

> **Puertos usados:** `5433` (Postgres), `6333`/`6334` (Qdrant), `8000` (API), `5173` (Vite), `11434` (Ollama).

---

## Instalación (paso a paso)

### 1. Clonar el repositorio

```bash
git clone https://github.com/roobertoosg/clinical-copilot.git
cd clinical-copilot
```

### 2. Levantar infraestructura (Postgres + Qdrant)

Desde la raíz del proyecto:

```bash
docker compose up -d
```

Verifica que los contenedores estén arriba:

```bash
docker compose ps
```

Deberías ver `copilot_postgres` y `copilot_qdrant`.

### 3. Configurar el backend

```bash
cd backend

# Entorno virtual
python3 -m venv venv

# Activar (Linux / macOS)
source venv/bin/activate

# En Windows (PowerShell):
# .\venv\Scripts\Activate.ps1

# Dependencias
pip install -r requirements.txt

# Variables de entorno
cp .env.example .env
```

Edita `backend/.env` con tus claves reales:

```env
GEMINI_API_KEY="tu_api_key_de_google_ai"
OLLAMA_URL="http://localhost:11434"
ICD11_CLIENT_ID="tu_client_id_oms"
ICD11_CLIENT_SECRET="tu_client_secret_oms"
```

**Dónde obtener las claves**

- **Gemini:** [Google AI Studio](https://aistudio.google.com/apikey)
- **CIE-11 OMS:** regístrate en [icd.who.int/icdapi](https://icd.who.int/icdapi) → *View API access key(s)* → Client ID / Client Secret

> La URL de PostgreSQL ya está definida en el código (`localhost:5433`, usuario/password del `docker-compose.yml`). No hace falta ponerla en `.env`.

### 4. (Recomendado) Instalar Ollama y modelos

Necesario para **embeddings RAG** y para usar el proveedor local:

```bash
# Instalar Ollama: https://ollama.com/download
# Luego:
ollama pull nomic-embed-text
ollama pull llama3.1
```

Sin Ollama el flujo Gemini puede funcionar, pero el RAG / embeddings fallarán o quedarán vacíos.

### 5. Cargar el catálogo de medicamentos

Con Postgres arriba y el venv activo, desde `backend/`:

```bash
python scripts/load_catalog.py
```

Carga `data/catalogo_2000_productos.csv` en la tabla `medications_catalog` (idempotente: si ya hay datos, no vuelve a insertar).

Para forzar una recarga limpia:

```bash
python scripts/load_catalog.py --force
```

Al arrancar la API se habilita automáticamente la extensión **`pg_trgm`** (búsqueda difusa del typeahead):

`GET /api/v1/medications/search?q=paracet&limit=10`

### 6. (Opcional) Ingestar guías clínicas en Qdrant

Los PDFs viven en `backend/data/guidelines/`. Con Ollama y Qdrant corriendo:

```bash
python scripts/ingest_pdfs.py
```

Puede tardar bastante la primera vez (muchos PDFs). El script es reanudable.

### 7. Arrancar el backend

Desde `backend/` con el venv activo:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Prueba: [http://localhost:8000/health](http://localhost:8000/health)  
Docs Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)

### 8. Arrancar el frontend

En **otra terminal**:

```bash
cd frontend
npm install
npm run dev
```

Abre: [http://localhost:5173](http://localhost:5173)

El frontend llama a la API en `http://localhost:8000`.

---

## Checklist rápido de arranque

```bash
# Terminal 1 — infra
docker compose up -d

# Terminal 2 — API
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3 — UI
cd frontend && npm run dev
```

---

## Uso básico

1. Entra a **Nueva Consulta** (`/`).
2. Busca o registra un paciente; agrega alergias/medicamentos si aplica.
3. Completa conversación / vitales / examen; opcionalmente graba audio para transcribir.
4. Elige proveedor (**Gemini** o **Ollama**) y genera el borrador.
5. En la pantalla de revisión, edita SOAPE y receta.
6. **Finalizar consulta** → se guarda y descarga el PDF.

---

## Estructura del repositorio

```
clinical-copilot/
├── docker-compose.yml          # Postgres + Qdrant
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── db/                 # modelos y sesión SQLAlchemy
│   │   ├── services/           # cliente CIE-11 OMS
│   │   └── modules/
│   │       ├── clinical_ai/    # draft, finalize, PDF, Gemini, tools
│   │       ├── clinical_rag/   # embeddings, retriever, feedback
│   │       ├── patients/
│   │       ├── dashboard/
│   │       └── system/
│   ├── data/
│   │   ├── catalogo_2000_productos.csv
│   │   └── guidelines/         # PDFs para RAG
│   └── scripts/
│       ├── load_catalog.py
│       └── ingest_pdfs.py
└── frontend/
    └── src/
        ├── pages/              # Workspace, Dashboard, Pacientes…
        └── components/         # Formulario, ReviewEditor, Sidebar…
```

---

## Variables de entorno

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | Para Gemini | Clave de Google Generative AI |
| `OLLAMA_URL` | No (default local) | Base de Ollama, ej. `http://localhost:11434` |
| `ICD11_CLIENT_ID` | Para CIE-11 | Client ID de la OMS |
| `ICD11_CLIENT_SECRET` | Para CIE-11 | Client Secret de la OMS |
| `QDRANT_HOST` | No | Default `localhost` |
| `QDRANT_PORT` | No | Default `6333` |

**No subas tu `.env` a Git** (ya está en `.gitignore`).

---

## Solución de problemas

| Problema | Qué revisar |
|----------|-------------|
| Backend no arranca / error de Postgres | `docker compose ps` y que el puerto **5433** esté libre |
| `Connection refused` a Qdrant | Contenedor `copilot_qdrant` arriba; puerto **6333** |
| Gemini falla | `GEMINI_API_KEY` en `backend/.env` y reinicio de Uvicorn |
| Diagnósticos sin código CIE-11 | Credenciales OMS en `.env`; registro en [icd.who.int/icdapi](https://icd.who.int/icdapi) |
| RAG vacío / error de embeddings | Ollama corriendo + `ollama pull nomic-embed-text` + ingest de PDFs |
| Receta inventada / sin catálogo | Ejecutar `python scripts/load_catalog.py` |
| Frontend no habla con la API | API en `:8000`; CORS ya permite orígenes |
| Clone muy pesado | La carpeta `guidelines/` incluye muchos PDFs (~cientos de MB) |

---

## Notas importantes

- El modelo Gemini del proyecto es **`gemini-3.5-flash`**.
- Las tablas de Postgres se crean solas al iniciar FastAPI (`create_all`).
- Este software es un **asistente de apoyo**: no sustituye el criterio clínico del médico.
- Credenciales y datos de pacientes son sensibles; úsalo solo en entornos controlados.

---

## Licencia / contribución

Proyecto académico / prototipo. Si haces fork, configura tus propias claves en `.env` y no compartas secretos en commits ni issues.
