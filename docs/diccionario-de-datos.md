# Diccionario de datos — Aura Clinical Copilot

## 1. Información general

| Concepto | Valor identificado |
| -------- | ------------------ |
| **Nombre del sistema** | Aura Clinical Copilot (`clinical-copilot`) |
| **Motor de base de datos** | PostgreSQL 15 (servicio Docker `db` / contenedor `copilot_postgres`, puerto host `5433`) |
| **Almacén vectorial (no SQL)** | Qdrant (servicio Docker `qdrant`, puerto host `6333`) |
| **Tecnología de persistencia** | SQLAlchemy 2 ORM (`declarative_base`), sesiones vía `SessionLocal` / `get_db` |
| **Migraciones formales** | **No existen** (no hay Alembic ni scripts `.sql` de esquema versionado) |
| **Creación de esquema** | `Base.metadata.create_all()` en `backend/app/main.py` al arranque; script de desarrollo `backend/reset_db.py` (`drop_all` + `create_all` + seed de doctor) |
| **Ajuste ad hoc de esquema** | `ALTER TABLE consultations ADD COLUMN ai_accuracy_score FLOAT` si falta la columna (`backend/app/main.py`) |
| **Extensión PostgreSQL** | `pg_trgm` + índices GIN sobre `medications_catalog` (`backend/app/modules/medications/router.py` → `ensure_pg_trgm`) |
| **Ubicación de modelos ORM** | `backend/app/db/models.py` |
| **Sesión / URL DB** | `backend/app/db/session.py` (cadena de conexión hardcodeada; **no documentada aquí por seguridad**) |
| **Esquemas de API (Pydantic)** | `backend/app/modules/*/schemas.py` |
| **Convenciones de nombres** | Tablas SQL en **inglés snake_case plural** (`patients`, `clinical_notes`). Columnas ORM mayormente en inglés. **API clínica / JSON IA en español** (`soape.subjetivo`, `receta[].medicamento`). Mapeo ES↔EN en `crud.py` y `get_consultation_detail`. |
| **Zona horaria** | `America/Mexico_City` (`now_mx()` en `models.py`) |
| **Fecha de generación** | 2026-07-28 |
| **Alcance del análisis** | Código actual del repositorio: ORM, Pydantic, routers FastAPI, CRUD, servicios CIE-11/RAG/Gemini, scripts ETL, frontend React (payloads), Docker Compose. Sin inventar tablas ni columnas ausentes del código. |

---

## 2. Resumen de entidades

| Entidad o tabla | Descripción | Estado | Archivo de origen |
| --------------- | ----------- | ------ | ----------------- |
| `patients` | Pacientes (demografía básica) | Implementada | `backend/app/db/models.py` → `Patient` |
| `doctors` | Médicos (preparación para login futuro) | Parcialmente implementada | `backend/app/db/models.py` → `Doctor`; seed en `reset_db.py` |
| `allergies` | Alergias del paciente | Implementada | `backend/app/db/models.py` → `Allergy` |
| `medications` | Medicación crónica/actual del paciente (activo/suspendido) | Implementada | `backend/app/db/models.py` → `Medication` |
| `consultations` | Consulta clínica (folio, transcripción, precisión IA) | Implementada | `backend/app/db/models.py` → `Consultation` |
| `clinical_notes` | Nota SOAPE persistida | Implementada | `backend/app/db/models.py` → `ClinicalNote` |
| `prescriptions` | Líneas de receta de la consulta | Implementada | `backend/app/db/models.py` → `Prescription` |
| `clinical_alerts` | Alertas clínicas de la consulta | Implementada | `backend/app/db/models.py` → `ClinicalAlert` |
| `diagnostics` | Diagnósticos CIE-11 de la consulta | Implementada | `backend/app/db/models.py` → `Diagnostic` |
| `medications_catalog` | Catálogo institucional de farmacia (Capa 1) | Implementada | `backend/app/db/models.py` → `MedicationCatalog`; ETL `scripts/load_catalog.py` |
| Colección Qdrant `clinical_guidelines` | Chunks RAG de guías/NOM | Implementada (vector store) | `clinical_rag/retriever.py`, `ingest.py`, `scripts/ingest_pdfs.py` |
| Colección Qdrant `doctor_feedback` | Correcciones SOAPE para aprendizaje de estilo | Implementada (vector store) | `clinical_rag/doctor_feedback.py` |
| `AIClinicalOutput` / `ConsultationInput` | Contratos HTTP / salida IA | Solo definida en esquemas | `clinical_ai/schemas.py` |
| `ActivityEvent` | Evento de bitácora (derivado, no tabla) | Solo definida en esquemas | `system/schemas.py` |
| `DashboardStats` | Agregados de dashboard (no tabla) | Solo definida en esquemas | `dashboard/schemas.py` |
| Signos vitales estructurados (`ta`, `fc`, …) | UI frontend; se envían como un solo `string` | Referenciada, pero no implementada como tabla/columnas | `ConsultationForm.jsx` |
| Autenticación / sesión de médico | Comentada como futuro en `Doctor` | Referenciada, pero no implementada | `models.py` docstring; `doctor_id=1` hardcodeado en `crud.py` |

---

## 3. Diccionario de datos por entidad

### Tabla: `patients`

**Descripción funcional:**  
Registro demográfico del paciente. Base para perfil clínico, alergias, medicación crónica y consultas.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Patient` (`__tablename__ = "patients"`).

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador interno | `Integer` | No determinado | Sí | No | — | No | Sí (PK) | Autogenerado | Índice | `1` | Interno |
| `first_name` | Nombre(s) | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Requerido en `PatientCreate` | `María` | Dato personal |
| `last_name` | Apellido(s) | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Requerido en `PatientCreate` | `García` | Dato personal |
| `date_of_birth` | Fecha de nacimiento | `Date` | Fecha | No | No | — | Sí* | No | — | Requerido en API create/update | `1990-05-12` | Dato personal |
| `gender` | Sexo / género | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Requerido en API | `Femenino` | Dato personal |
| `created_at` | Alta del registro | `DateTime(timezone=True)` | timestamp TZ | No | No | — | No | No | `now_mx` | — | `2026-07-28T10:00:00-06:00` | Auditoría |

\*En el modelo ORM las columnas demográficas no declaran `nullable=False`; la obligatoriedad se impone en Pydantic (`PatientCreate` / `PatientUpdate`).

#### Reglas de negocio identificadas

- Alta/edición vía `POST /patients/`, `PUT /patients/{patient_id}`.
- Búsqueda por nombre, apellido o ID (`GET /patients/?search=`).
- Edad (`edad`) se **calcula** en `get_patient_clinical_profile`; no se almacena.
- Nombre completo expuesto como `nombre` en listados/perfil (campo derivado, no columna).

#### Relaciones

- Uno a muchos → `allergies`, `medications`, `consultations`.
- Eliminación de paciente: FKs hijas con `ondelete="CASCADE"` en alergias, medicamentos y consultas.

#### Uso dentro del sistema

- Endpoints: `backend/app/modules/patients/router.py`.
- Pantallas: `PatientsPage.jsx`, `PatientProfile.jsx`, `ConsultationForm.jsx` (selección), `ClinicalWorkspace.jsx`.
- Prompt IA: edad, sexo, alergias y medicamentos se inyectan en `_build_user_prompt` (`clinical_ai/router.py`).

---

### Tabla: `doctors`

**Descripción funcional:**  
Médico responsable de consultas. Preparado para un futuro módulo de login; hoy se usa un doctor de prueba.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Doctor`. Seed: `backend/reset_db.py` → `seed_data()`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `full_name` | Nombre completo | `String` | Sin longitud explícita | No | No | — | No | No | — | `nullable=False` | `Dr. Ricardo Mendoza` | Dato personal |
| `specialty` | Especialidad | `String` | Sin longitud explícita | No | No | — | Sí | No | — | — | `Medicina Interna` | Interno |
| `license_number` | Cédula profesional | `String` | Sin longitud explícita | No | No | — | Sí | No | — | — | `12345678` | Dato personal sensible |

#### Reglas de negocio identificadas

- `save_consultation_results` asigna siempre `doctor_id=1` (comentario: temporal hasta login).
- PDF lee datos del doctor por `consultation.doctor_id` (`export_consultation_pdf`).
- Frontend muestra nombre hardcodeado `DOCTOR_NAME` en `DashboardPage.jsx` (no lee la tabla).

#### Relaciones

- Uno a muchos → `consultations` (`doctor_id`, `ondelete="SET NULL"`).

#### Uso dentro del sistema

- Persistencia al finalizar consulta; PDF; seed de desarrollo.
- No hay endpoints CRUD públicos de médicos en el código analizado.

---

### Tabla: `allergies`

**Descripción funcional:**  
Alergias del paciente usadas para seguridad clínica (prompt + perfil).

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Allergy`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `patient_id` | Paciente dueño | `Integer` | — | No | Sí | `patients.id` | No | No | — | Índice; CASCADE | `1` | Interno |
| `allergen` | Alérgeno | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Requerido en `AllergyCreate` | `Penicilina` | Dato clínico sensible |
| `reaction` | Reacción | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Requerido en API | `Erupción cutánea` | Dato clínico sensible |
| `severity` | Severidad | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Texto libre (Leve/Moderada/Severa en comentarios) | `Severa` | Dato clínico sensible |

#### Reglas de negocio identificadas

- Alta: `POST /patients/{patient_id}/allergies`.
- El system prompt exige omitir medicamentos incompatibles y generar alerta `Alta`.
- No hay endpoint de borrado/edición de alergias en el código revisado.

#### Relaciones

- Muchos a uno → `patients`.

#### Uso dentro del sistema

- `PatientProfile.jsx`, perfil clínico, prompt Gemini/Ollama.

---

### Tabla: `medications`

**Descripción funcional:**  
Medicamentos actuales del paciente (historial farmacoterapéutico), distintos del catálogo institucional y de la receta de consulta.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Medication`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `patient_id` | Paciente | `Integer` | — | No | Sí | `patients.id` | No | No | — | CASCADE | `1` | Interno |
| `name` | Nombre del medicamento | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | Requerido en `MedicationCreate` | `Paracetamol` | Dato clínico sensible |
| `dosage` | Dosis | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | API | `500mg` | Dato clínico sensible |
| `frequency` | Frecuencia | `String` | Sin longitud explícita | No | No | — | Sí* | No | — | API | `Cada 8 horas` | Dato clínico sensible |
| `is_active` | Activo vs suspendido | `Boolean` | — | No | No | — | No | No | `True` | Toggle vía PATCH | `true` | Interno |
| `created_at` | Creación | `DateTime(timezone=True)` | timestamp TZ | No | No | — | No | No | `now_mx` | — | — | Auditoría |
| `updated_at` | Última actualización | `DateTime(timezone=True)` | timestamp TZ | No | No | — | No | No | `now_mx` / `onupdate` | Usado en activity-log de suspendidos | — | Auditoría |

#### Reglas de negocio identificadas

- Alta: `POST /patients/{patient_id}/medications`.
- Suspender/reactivar: `PATCH .../medications/{medication_id}/toggle-status`.
- Bitácora del día lista medicamentos con `is_active=False` actualizados hoy (`/system/activity-log`).

#### Relaciones

- Muchos a uno → `patients`.

#### Uso dentro del sistema

- `PatientProfile.jsx`, prompt clínico, historial de actividad.

---

### Tabla: `consultations`

**Descripción funcional:**  
Cabecera de la consulta clínica finalizada (o procesada). Contiene folio, vínculo paciente/médico, transcripción, estado y score de precisión IA.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Consultation`. Columna `ai_accuracy_score` también asegurada en `main.py`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `10` | Interno |
| `folio` | Folio legible | `String` | Sin longitud explícita | No | No | — | Sí | Sí (unique + index) | Generado `CON-YYYYMMDD-NNNN` | `_generate_folio` | `CON-20260728-0001` | Interno |
| `patient_id` | Paciente | `Integer` | — | No | Sí | `patients.id` | No | No | — | CASCADE | `1` | Interno |
| `doctor_id` | Médico | `Integer` | — | No | Sí | `doctors.id` | Sí | No | Hardcode `1` al guardar | `SET NULL` al borrar doctor | `1` | Interno |
| `date` | Fecha/hora consulta | `DateTime(timezone=True)` | timestamp TZ | No | No | — | No | No | `now_mx` | Filtros dashboard/hoy | — | Auditoría |
| `reason` | Motivo / resumen | `Text` | — | No | No | — | Sí | No | Se guarda `resumen_paciente` de la IA/médico | — | Texto resumen | Dato clínico sensible / Generado por IA* |
| `transcription` | Conversación / texto capturado | `Text` | — | No | No | — | Sí | No | `conversation_text` del input | — | Diálogo clínico | Dato clínico sensible |
| `status` | Estado | `String` | Sin longitud explícita | No | No | — | No | No | `"completed"` | Siempre `completed` al persistir actual | `completed` | Interno |
| `ai_accuracy_score` | Similitud SOAPE IA vs médico (0.0–1.0) | `Float` | float | No | No | — | Sí | No | — | `difflib.SequenceMatcher` en finalize | `0.983` | Generado por IA / Auditoría |

\*El contenido de `reason` suele originarse en `resumen_paciente` (IA o editado por médico).

#### Reglas de negocio identificadas

- Persistencia solo en finalize / process-consultation legado (`crud.save_consultation_statement` → `save_consultation_results`).
- `generate-draft` **no** inserta fila en `consultations`.
- Dashboard promedia `ai_accuracy_score` del mes (`func.avg` × 100).
- PDF y detalle se buscan por `folio`.

#### Relaciones

- Muchos a uno → `patients`, `doctors`.
- Uno a uno → `clinical_notes` (`uselist=False`).
- Uno a muchos → `prescriptions`, `clinical_alerts`, `diagnostics`.
- Cascada de borrado hacia notas/recetas/alertas/diagnósticos.

#### Uso dentro del sistema

- `POST /clinical-ai/finalize-consultation`, `process-consultation`.
- `GET /clinical-ai/consultations`, `/{folio}`, `/{folio}/export-pdf`.
- Dashboard, Consultas, Historial, perfil del paciente (`/patients/{id}/consultations`).

---

### Tabla: `clinical_notes`

**Descripción funcional:**  
Nota clínica SOAPE persistida (una por consulta).

**Fuente de definición:**  
`backend/app/db/models.py` — clase `ClinicalNote`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `consultation_id` | Consulta | `Integer` | — | No | Sí | `consultations.id` | No | No | — | CASCADE | `10` | Interno |
| `subjective` | Subjetivo (S) | `Text` | — | No | No | — | Sí | No | Mapeo desde `soape.subjetivo` | — | Texto clínico | Dato clínico sensible / Generado por IA* |
| `objective` | Objetivo (O) | `Text` | — | No | No | — | Sí | No | `soape.objetivo` | — | — | Dato clínico sensible / Generado por IA* |
| `analysis` | Análisis (A) | `Text` | — | No | No | — | Sí | No | `soape.analisis` | — | — | Dato clínico sensible / Generado por IA* |
| `plan` | Plan (P) | `Text` | — | No | No | — | Sí | No | `soape.plan` | — | — | Dato clínico sensible / Generado por IA* |
| `evaluation` | Evaluación (E) | `Text` | — | No | No | — | Sí | No | `soape.evaluacion` | — | — | Dato clínico sensible / Generado por IA* |

\*Tras HITL se persiste la versión `doctor_final_data` (puede haber sido editada).

#### Reglas de negocio identificadas

- Mapeo ES→EN en `crud.py`; EN→ES al leer detalle.
- Precisión IA compara SOAPE original vs final **antes** de persistir; solo se guarda el final.

#### Relaciones

- Uno a uno (lógico) con `consultations`.

#### Uso dentro del sistema

- Persistencia finalize; detalle de consulta; PDF (`pdf_generator.py`).

---

### Tabla: `prescriptions`

**Descripción funcional:**  
Líneas de receta asociadas a una consulta.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Prescription`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `consultation_id` | Consulta | `Integer` | — | No | Sí | `consultations.id` | No | No | — | CASCADE | `10` | Interno |
| `medication` | Nombre del medicamento | `String` | Sin longitud explícita | No | No | — | No | No | Desde `receta[].medicamento` | Se omiten vacíos | `Amoxil 12 cápsulas 500mg` | Dato clínico sensible |
| `dose` | Dosis | `String` | Sin longitud explícita | No | No | — | Sí | No | `dosis` | — | `500 mg` | Dato clínico sensible |
| `frequency` | Frecuencia | `String` | Sin longitud explícita | No | No | — | Sí | No | `frecuencia` | — | `Cada 8 horas` | Dato clínico sensible |
| `duration` | Duración | `String` | Sin longitud explícita | No | No | — | Sí | No | `duracion` | — | `7 días` | Dato clínico sensible |
| `indications` | Indicaciones | `Text` | — | No | No | — | Sí | No | `indicaciones` | — | `Con alimentos` | Dato clínico sensible |

#### Reglas de negocio identificadas

- No hay FK a `medications_catalog`; el vínculo con catálogo es por nombre (texto) vía typeahead / tool Gemini.
- Frontend normaliza `dosis`/`duracion` (minúsculas) y `frecuencia`/`indicaciones` (sentence case) en `onBlur` (`ClinicalReviewEditor.jsx`).

#### Relaciones

- Muchos a uno → `consultations`.
- Sin relación formal con `medications` ni `medications_catalog`.

#### Uso dentro del sistema

- Finalize/CRUD; PDF; detalle consulta; edición HITL.

---

### Tabla: `clinical_alerts`

**Descripción funcional:**  
Alertas de seguridad o datos faltantes asociadas a la consulta.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `ClinicalAlert`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `consultation_id` | Consulta | `Integer` | — | No | Sí | `consultations.id` | No | No | — | CASCADE | `10` | Interno |
| `alert_type` | Tipo | `String` | Sin longitud explícita | No | No | — | Sí | No | API: `tipo` (default esquema `clinica`) | — | `alergia` | Dato clínico sensible / Generado por IA* |
| `description` | Descripción | `Text` | — | No | No | — | No | No | `descripcion` | Omitidas si vacías | Texto alerta | Dato clínico sensible / Generado por IA* |
| `severity` | Severidad | `String` | Sin longitud explícita | No | No | — | Sí | No | `severidad` | Dashboard filtra `lower(severity)=='alta'` | `Alta` | Dato clínico sensible |

#### Reglas de negocio identificadas

- Dashboard `/dashboard/critical-alerts` lista severidad Alta.
- Backend puede inyectar alerta de signos vitales faltantes antes de devolver borrador.

#### Relaciones

- Muchos a uno → `consultations`.

#### Uso dentro del sistema

- Persistencia finalize; UI revisión/cards; dashboard.

---

### Tabla: `diagnostics`

**Descripción funcional:**  
Diagnósticos sugeridos/confirmados de la consulta, con código CIE-11 cuando la OMS responde.

**Fuente de definición:**  
`backend/app/db/models.py` — clase `Diagnostic`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `consultation_id` | Consulta | `Integer` | — | No | Sí | `consultations.id` | No | No | — | CASCADE | `10` | Interno |
| `codigo` | Código CIE-11 o marcador | `String` | Sin longitud explícita | No | No | — | Sí | No | Enriquecido por WHO; puede ser `"[Sin Código]"` | LLM no debe inventar códigos | `BA00` | Dato clínico sensible |
| `description` | Descripción diagnóstica | `String` | Sin longitud explícita | No | No | — | No | No | `descripcion` del JSON | Obligatoria para insertar | `Asma` | Dato clínico sensible / Generado por IA* |
| `probabilidad` | Probabilidad textual | `String` | Sin longitud explícita | No | No | — | Sí | No | `Alta`/`Media`/`Baja` (convención prompt) | — | `Alta` | Generado por IA |

#### Reglas de negocio identificadas

- Códigos se asignan en backend (`enrich_diagnoses_with_icd11`), no inventados por el LLM.
- En revisión HITL los diagnósticos se muestran; la edición principal documentada está en SOAPE/receta (diagnósticos se persisten desde `doctor_final_data`).

#### Relaciones

- Muchos a uno → `consultations`.

#### Uso dentro del sistema

- Generate-draft (enriquecimiento); finalize; PDF; UI.

---

### Tabla: `medications_catalog`

**Descripción funcional:**  
Catálogo institucional de productos de farmacia (Capa 1 de verdad para prescripción).

**Fuente de definición:**  
`backend/app/db/models.py` — clase `MedicationCatalog`. Carga: `backend/scripts/load_catalog.py` desde `backend/data/catalogo_2000_productos.csv`.

| Campo | Descripción | Tipo de dato | Longitud o precisión | PK | FK | Referencia | Nulo | Único | Valor predeterminado | Validaciones | Ejemplo | Clasificación |
| ----- | ----------- | ------------ | -------------------- | :-: | :-: | ---------- | :--: | :---: | -------------------- | ------------ | ------- | ------------- |
| `id` | Identificador | `Integer` | No determinado | Sí | No | — | No | Sí | Autogenerado | — | `1` | Interno |
| `producto` | Nombre / presentación | `String` | Sin longitud explícita | No | No | — | No | No | — | ETL omite filas sin producto ni sustancia | `Xeletec 200mg capsula 20` | Interno |
| `marca` | Marca comercial | `String` | Sin longitud explícita | No | No | — | Sí | No | — | — | `XELETEC` | Interno |
| `sustancia_activa` | Principio activo | `String` | Sin longitud explícita | No | No | — | No | No | — | Índice; tool Gemini busca por ILIKE | `CELECOXIB` | Interno |
| `categoria` | Categoría terapéutica | `String` | Sin longitud explícita | No | No | — | Sí | No | — | Índice | `REUMATOLOGÍA` | Interno |
| `ean` | Código EAN | `String` | Sin longitud explícita | No | No | — | Sí | No | — | Índice | `7502226295503` | Interno |
| `laboratorio` | Laboratorio | `String` | Sin longitud explícita | No | No | — | Sí | No | — | — | `ALPHARMA` | Interno |
| `estatus` | Estado del producto | `String` | Sin longitud explícita | No | No | — | No | No | `"ACTIVO"` | Filtro búsqueda/`ACTIVO` | `ACTIVO` | Interno |

#### Reglas de negocio identificadas

- Búsqueda difusa: `GET /api/v1/medications/search` (`pg_trgm` + ILIKE).
- Tool Gemini `consultar_inventario_farmacia` consulta por `sustancia_activa`.
- ETL idempotente; `--force` trunca y recarga.
- Campo API calculado `medicamento` (etiqueta) **no** es columna SQL.

#### Relaciones

- Sin FK hacia otras tablas (catálogo independiente).

#### Uso dentro del sistema

- Typeahead receta (`ClinicalReviewEditor.jsx`); function calling Gemini; scripts ETL.

---

### Almacén vectorial: colección Qdrant `clinical_guidelines`

**Descripción funcional:**  
Fragmentos de guías clínicas / NOM para RAG (Capa 2). No es tabla PostgreSQL.

**Fuente de definición:**  
`backend/app/modules/clinical_rag/retriever.py` (`COLLECTION_NAME = "clinical_guidelines"`, `VECTOR_SIZE = 768`, Cosine).

| Campo / payload | Descripción | Tipo | Persistencia | Clasificación |
| --------------- | ----------- | ---- | ------------ | ------------- |
| `id` (point) | UUID del punto | string/uuid | Qdrant | Interno |
| `vector` | Embedding 768-d | float[] | Qdrant | Interno |
| `content` | Texto del chunk | string | payload | Interno / clínico de referencia |
| `source_metadata` (claves variables) | Metadatos de ingestión | dict | payload | No determinado |

#### Uso

- `retrieve_context` en pipeline Gemini; endpoints `/clinical-rag/*`; `scripts/ingest_pdfs.py`.

---

### Almacén vectorial: colección Qdrant `doctor_feedback`

**Descripción funcional:**  
Correcciones SOAPE del médico cuando `ai_accuracy_score < 0.95`, para inyectar estilo en futuros borradores.

**Fuente de definición:**  
`backend/app/modules/clinical_rag/doctor_feedback.py` (`FEEDBACK_COLLECTION = "doctor_feedback"`).

| Campo payload | Descripción | Clasificación |
| ------------- | ----------- | ------------- |
| `content` | Documento combinado síntomas + SOAPE IA + SOAPE médico | Dato clínico sensible / Generado por IA |
| `patient_symptoms` | Contexto clínico | Dato clínico sensible |
| `ai_soape` | SOAPE original IA (dict) | Generado por IA |
| `doctor_soape` | SOAPE corregido | Dato clínico sensible |
| `accuracy_score` | Float 0–1 | Auditoría |
| `patient_id` | ID paciente (opcional) | Interno / Dato personal (identificador) |
| `folio` | Folio consulta (opcional) | Interno |

#### Uso

- Escrito en `finalize_consultation`; leído en `_generate_clinical_draft`.

---

## 4. Relaciones generales

| Entidad origen | Relación | Entidad destino | Campo de relación | Cardinalidad | Evidencia |
| -------------- | -------- | --------------- | ----------------- | ------------ | --------- |
| `patients` | tiene | `allergies` | `allergies.patient_id` | Uno a muchos | `models.py` FK + `relationship` |
| `patients` | tiene | `medications` | `medications.patient_id` | Uno a muchos | `models.py` |
| `patients` | recibe | `consultations` | `consultations.patient_id` | Uno a muchos | `models.py` |
| `doctors` | atiende | `consultations` | `consultations.doctor_id` | Uno a muchos | `models.py` (`SET NULL`) |
| `consultations` | genera | `clinical_notes` | `clinical_notes.consultation_id` | Uno a uno (uso) | `relationship(..., uselist=False)` |
| `consultations` | incluye | `prescriptions` | `prescriptions.consultation_id` | Uno a muchos | `models.py` |
| `consultations` | dispara | `clinical_alerts` | `clinical_alerts.consultation_id` | Uno a muchos | `models.py` |
| `consultations` | sugiere | `diagnostics` | `diagnostics.consultation_id` | Uno a muchos | `models.py` |
| `medications_catalog` | — | (ninguna FK) | — | Sin relación formal | Modelo sin `ForeignKey` |
| Consulta finalizada | indexa (condicional) | Qdrant `doctor_feedback` | payload `folio` / `patient_id` | Lógica aplicación | `doctor_feedback.store_doctor_feedback` |
| Prompt / tool | consulta | `medications_catalog` | sustancia/producto | Lógica aplicación | `tools.py`, `medications/router.py` |

---

## 5. Datos no persistidos

| Dato | Origen | Uso | ¿Se persiste? | Destino identificado | Observaciones |
| ---- | ------ | --- | :-----------: | -------------------- | ------------- |
| `vital_signs` (string) | Frontend `ConsultationForm` → API `ConsultationInput` / finalize | Prompt IA; feedback síntomas | **No** como columna | Solo entra al texto de síntomas Qdrant si accuracy &lt; 0.95 | UI tiene TA/FC/FR/Temp/SatO2; se serializa a un string |
| `physical_exam` | Formulario / API | Prompt + RAG query + feedback | **No** como columna | Idem feedback Qdrant | No hay tabla ni campo SQL |
| `ai_provider` | Formulario (`gemini`/`ollama`) | Selección de motor | No | — | Solo request |
| `ai_original_data` | Estado React + body finalize | Cálculo accuracy + feedback | **No** en PostgreSQL | Qdrant `ai_soape` si accuracy &lt; 0.95 | Borrador crudo no se guarda en SQL |
| Borrador `generate-draft` completo | Respuesta API | Edición HITL en memoria frontend | No (hasta finalize) | Estado React | Folio suele ser `null` en borrador |
| `soape` keys ES en JSON | IA / frontend | Intercambio API | Parcial | Columnas EN en `clinical_notes` | Mapeo en `crud.py` |
| `receta[].medicamento` etc. (ES) | IA / UI | Receta | Parcial | Columnas EN en `prescriptions` | — |
| `alertas[].tipo/descripcion/severidad` | IA / UI | Alertas | Parcial | `alert_type`/`description`/`severity` | — |
| `diagnosticos_sugeridos[].descripcion` | IA + WHO | Dx | Parcial | `diagnostics.description` | — |
| `folio`, `ai_accuracy_score` en `AIClinicalOutput` | Backend tras finalize | UI/PDF | `folio` y score sí en `consultations` | — | En borrador pueden ir vacíos |
| `edad`, `nombre`, `sexo` (perfil) | Calculados/derivados | UI perfil | No columnas | — | `sexo` ← `gender` |
| `MedicationCatalogItem.medicamento`, `score` | Búsqueda catálogo | Typeahead | No columnas | Calculados en endpoint | — |
| `DashboardStats.*` | Agregaciones SQL | Tarjetas dashboard | No | — | Incluye `current_ai_accuracy` |
| `ActivityEvent` | Derivado de patients/consultations/medications | Historial | No tabla propia | — | `/system/activity-log` |
| Audio de grabación | Micrófono → Whisper | Transcripción | No | Texto en `conversation_text` / luego `transcription` | Archivo multipart temporal en request |
| PDF generado | ReportLab | Descarga | No en DB | Stream HTTP | Se regenera on-demand |
| Chunks RAG guías | PDFs / ingest | Prompt | Qdrant, no PG | `clinical_guidelines` | — |
| Prompt system/user completo | `router.py` | Gemini/Ollama | No | Proveedor IA externo/local | Contiene PII/clínico |
| Respuesta cruda Gemini (texto) | Fase 2 | Parseo JSON | No (salvo resultado mapeado al finalizar) | — | Sanitizado con `_clean_json_text` |

---

## 6. Información generada por inteligencia artificial

### Entrada al modelo (resumen)

- Demografía: edad calculada, sexo.
- Alergias y medicamentos actuales del paciente (PostgreSQL).
- `conversation_text`, `vital_signs`, `physical_exam`.
- Ejemplos de estilo desde Qdrant `doctor_feedback` (si existen).
- Chunks de guías desde Qdrant `clinical_guidelines` (pipeline Gemini).
- Resultados de `consultar_inventario_farmacia` (Fase 1 Gemini).

### Salida del modelo

Estructura `AIClinicalOutput` / `GeminiClinicalOutput`:

- `soape` (`subjetivo`, `objetivo`, `analisis`, `plan`, `evaluacion`)
- `diagnosticos_sugeridos` (`codigo` vacío o placeholder → enriquecido por WHO)
- `receta[]` (`medicamento`, `dosis`, `frecuencia`, `duracion`, `indicaciones`)
- `resumen_paciente`
- `alertas[]` (`tipo`, `descripcion`, `severidad`)

### ¿Se guarda?

| Momento | ¿Se persiste en PostgreSQL? | Destino |
| ------- | --------------------------- | ------- |
| Tras `generate-draft` | **No** | Solo frontend |
| Tras `finalize-consultation` | **Sí** (versión `doctor_final_data`) | `consultations` + hijas |
| Si accuracy &lt; 0.95 | Adicional en Qdrant | `doctor_feedback` (incluye SOAPE IA y médico) |
| `process-consultation` (legado) | Sí, en un paso | Igual que finalize sin comparación formal de edición previa |

### Aprobación médica (HITL)

- Sí: el flujo principal exige revisión en `ClinicalReviewEditor` antes de finalizar.
- Distinción borrador vs validado:
  - **Borrador:** respuesta de `generate-draft`, sin `folio` persistido / sin fila consulta.
  - **Validado:** fila en `consultations` con `status="completed"`, `folio`, `ai_accuracy_score`, y datos clínicos hijos desde `doctor_final_data`.
- No hay columna booleana tipo `reviewed_by_doctor`; la evidencia de revisión es la existencia de la consulta finalizada + score.

### Riesgos de almacenar contenido generado automáticamente

- Alucinaciones residuales si el médico no corrige y finaliza.
- Mezcla de contenido IA y humano en las mismas columnas (sin marca por campo).
- `doctor_feedback` y prompts pueden retener texto clínico + `patient_id`.
- `reason`/`transcription`/`clinical_notes` almacenan texto libre sensible sin cifrado en reposo identificado en aplicación.

---

## 7. Seguridad y privacidad

| Entidad o campo | Tipo de información | Riesgo | Protección actual identificada | Recomendación |
| --------------- | ------------------- | ------ | ------------------------------ | ------------- |
| `patients.first_name/last_name/date_of_birth` | Dato personal | Identificación del paciente | Ninguna de cifrado/enmascaramiento en app; CORS `allow_origins=["*"]` | Control de acceso, TLS, minimizar exposición en logs |
| `doctors.license_number` | Dato personal sensible | Uso indebido de cédula | Sin auth; seed en claro | Autenticación real; restringir lectura |
| `allergies.*`, `medications.*` | Expediente / clínico | Discriminación, daño si filtrado | Sin RBAC | Autorización por rol; auditoría de acceso |
| `consultations.transcription` | Clínico + posible PII | Alto | Persistencia en texto plano | Cifrado en reposo DB; retención definida |
| `clinical_notes.*` | Expediente SOAPE | Alto | HITL antes de guardar (flujo principal) | Marcar campos editados; no reenviar a terceros sin base legal |
| `prescriptions.*` | Receta | Alto | Typeahead catálogo reduce invención | Validar contra catálogo en backend al finalizar |
| `diagnostics.*` | Diagnóstico | Alto | CIE-11 vía OMS | Evitar logs con diagnósticos completos |
| `clinical_alerts.*` | Seguridad clínica | Medio-Alto | Visibles en dashboard | Restringir dashboard |
| `ai_accuracy_score` | Métrica calidad | Bajo-Medio | Cálculo servidor | No exponer fuera del entorno clínico |
| Qdrant `doctor_feedback` | Clínico + IA + `patient_id` | Alto | Local/embeddings Ollama | TTL, anonimización, no subir a cloud sin acuerdo |
| Audio STT | Biometría/voz potencial | Alto | No se persiste el audio (solo texto) | Confirmar borrado de temporales; política Whisper |
| PDF export | Expediente completo | Alto | Generación on-demand | Auth en descarga; watermark; no cache público |
| API keys Gemini / ICD-11 | Secretos | Crítico | Archivo `.env` (gitignored); `.env.example` sin secretos reales | Secret manager; rotación |
| Cadena PostgreSQL en `session.py` | Credencial infra | Alto | Hardcodeada en código fuente | Mover a variables de entorno; no commitear secretos |

**Nota:** En el código analizado **no** se identificó cifrado a nivel de campo, autenticación de usuarios, ni enmascaramiento de PII en respuestas API.

---

## 8. Hallazgos e inconsistencias

| ID | Hallazgo | Evidencia | Impacto | Recomendación |
| -- | -------- | --------- | ------- | ------------- |
| H1 | Signos vitales y examen físico **no tienen columnas** SQL | `ConsultationInput.vital_signs/physical_exam` vs `Consultation` model | Pérdida de trazabilidad estructurada de vitales | `Recomendación, no implementada actualmente`: tabla o columnas JSON/normalizadas |
| H2 | Nombres ES (API) vs EN (DB) para SOAPE/receta/alertas | `schemas.py` vs `models.py` + mapeo `crud.py` | Riesgo de desalineación en nuevos campos | Documentar mapeo canónico; tests de round-trip |
| H3 | `ai_original_data` no se guarda en PostgreSQL | `finalize_consultation` solo persiste `doctor_final_data` | No auditable el borrador IA en SQL | Persistir borrador o versionado si se requiere auditoría clínica |
| H4 | `doctor_id` fijo a `1` | `crud.py` comentario temporal | Trazabilidad médica incorrecta multi-usuario | Implementar auth y asignar médico real |
| H5 | Modelo `Doctor` sin endpoints ni login | docstring `Doctor`; frontend `DOCTOR_NAME` hardcode | Parcialidad del dominio “médico” | Completar módulo de autenticación |
| H6 | Sin migraciones versionadas (Alembic) | Ausencia de carpetas/migrations; `create_all` + ALTER ad hoc | Drift de esquema entre entornos | Introducir migraciones formales |
| H7 | `String` sin longitud máxima | `models.py` columnas `String` | Validación débil / límites impredecibles | Definir longitudes o usar `Text` conscientemente |
| H8 | Demografía ORM nullable vs Pydantic required | `Patient` vs `PatientCreate` | Inconsistencia de obligatoriedad | Alinear `nullable=False` en ORM |
| H9 | Receta sin FK a `medications_catalog` | `Prescription.medication` texto libre | Pueden persistirse medicamentos fuera de catálogo | Validar EAN/producto al finalize |
| H10 | Cascadas `ON DELETE CASCADE` en expediente | FKs en `models.py` | Borrado de paciente elimina historial clínico | Preferir borrado lógico / retención legal |
| H11 | No hay `updated_at`/`created_by` en la mayoría de tablas clínicas | Modelos `consultations`, `clinical_notes`, etc. | Auditoría incompleta | Campos de auditoría y usuario responsable |
| H12 | No hay flag explícito “revisado por médico” por campo | Solo existencia de consulta + `ai_accuracy_score` | Difícil distinguir IA vs edición humana a nivel campo | Versionado o metadatos de revisión |
| H13 | Dashboard `consultations_month` sigue con fallback estático en frontend | `DashboardPage.jsx` usa `stats?.consultations_month ?? 18` y el backend no lo envía | Métrica engañosa | Calcular en `/dashboard/stats` o quitar tarjeta estática |
| H14 | CORS abierto | `main.py` `allow_origins=["*"]` | Exposición en despliegues no locales | Restringir orígenes |
| H15 | Credenciales DB en código | `session.py` | Riesgo de fuga en repositorio | Externalizar a entorno |

---

## 9. Elementos pendientes de implementar

| Elemento | Evidencia de mención/uso | Persistencia actual | Nota |
| -------- | ------------------------ | ------------------- | ---- |
| Login / autenticación de médico | Docstring `Doctor` (“futuro Login”); `doctor_id=1` temporal | Tabla `doctors` existe; **no hay auth** | Parcial |
| Signos vitales estructurados (TA, FC, FR, Temp, SatO₂) | `ConsultationForm.jsx` | Solo string efímero en request | No persistidos |
| Examen físico como campo de expediente | API + formulario | No columna SQL | No persistido |
| Borrador IA (`ai_original_data`) en PostgreSQL | Body de finalize | Solo Qdrant parcial si accuracy baja | No en SQL |
| Relación formal receta ↔ catálogo | Typeahead + tool | Texto en `prescriptions.medication` | Sin FK |
| Bitácora de auditoría dedicada | `/system/activity-log` derivado | No tabla `activity_log` | Solo lectura agregada del día |
| `consultations_month` en API stats | UI Dashboard | No implementado en `DashboardStats` | Frontend usa default `18` |
| Control de acceso / roles | Ausencia en routers | — | `Recomendación, no implementada actualmente` |
| Cifrado de campos clínicos | Ausencia en código | Texto plano | `Recomendación, no implementada actualmente` |

---

## 10. Archivos analizados

### Persistencia y configuración

- `backend/app/db/models.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/reset_db.py`
- `backend/.env.example`
- `docker-compose.yml`
- `backend/scripts/load_catalog.py`
- `backend/scripts/ingest_pdfs.py`
- `backend/data/catalogo_2000_productos.csv` (estructura de columnas; no secretos)

### Módulos backend

- `backend/app/modules/clinical_ai/schemas.py`
- `backend/app/modules/clinical_ai/router.py`
- `backend/app/modules/clinical_ai/crud.py`
- `backend/app/modules/clinical_ai/gemini_pipeline.py`
- `backend/app/modules/clinical_ai/tools.py`
- `backend/app/modules/clinical_ai/pdf_generator.py`
- `backend/app/modules/patients/schemas.py`
- `backend/app/modules/patients/router.py`
- `backend/app/modules/dashboard/schemas.py`
- `backend/app/modules/dashboard/router.py`
- `backend/app/modules/medications/schemas.py`
- `backend/app/modules/medications/router.py`
- `backend/app/modules/system/schemas.py`
- `backend/app/modules/system/router.py`
- `backend/app/modules/clinical_rag/schemas.py`
- `backend/app/modules/clinical_rag/retriever.py`
- `backend/app/modules/clinical_rag/ingest.py`
- `backend/app/modules/clinical_rag/doctor_feedback.py`
- `backend/app/modules/clinical_rag/embeddings.py`
- `backend/app/services/icd11_service.py` (uso de enriquecimiento; sin secretos en este documento)

### Frontend (intercambio de datos)

- `frontend/src/pages/ClinicalWorkspace.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/PatientsPage.jsx`
- `frontend/src/pages/ConsultationsPage.jsx`
- `frontend/src/pages/HistoryPage.jsx`
- `frontend/src/components/ConsultationForm.jsx`
- `frontend/src/components/ClinicalReviewEditor.jsx`
- `frontend/src/components/PatientProfile.jsx`
- `frontend/src/components/AIResults.jsx`
- `frontend/src/components/ClinicalCards.jsx`
- `frontend/src/utils/exportPdf.js`

### No encontrados en el repositorio

- Migraciones Alembic / carpetas `alembic/`
- Scripts `.sql` de esquema versionado
- Capa Repository genérica aparte de routers + `crud.py`

---

## Verificación final (checklist del analista)

1. Cada tabla SQL documentada tiene evidencia en `models.py` / uso en código.
2. Nombres técnicos coinciden con `__tablename__` y columnas ORM.
3. Modelos Pydantic y colecciones Qdrant se marcan como no-tablas o “solo esquemas”.
4. Recomendaciones aparecen explícitamente como no implementadas.
5. No se incluyen secretos, passwords ni connection strings completas.
6. Rutas de archivo incluidas para trazabilidad.
7. Documento guardado únicamente en `docs/diccionario-de-datos.md`.
