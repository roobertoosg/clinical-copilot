from pydantic import BaseModel
from datetime import date, datetime

# La estructura básica que el usuario debe enviar
class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str

# Datos demográficos editables (PUT /patients/{id})
class PatientUpdate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str

# La estructura que el servidor devolverá (incluye el ID que genera la base de datos)
class PatientResponse(PatientCreate):
    id: int

    class Config:
        from_attributes = True

# Fila del listado/búsqueda de pacientes (id, nombre completo, fecha de nacimiento)
class PatientSearchItem(BaseModel):
    id: int
    nombre: str
    date_of_birth: date | None  # Permite que Pydantic lea desde SQLAlchemy

    # --- ESQUEMAS PARA ALERGIAS ---
class AllergyCreate(BaseModel):
    allergen: str
    reaction: str
    severity: str

class AllergyResponse(AllergyCreate):
    id: int
    patient_id: int

    class Config:
        from_attributes = True

# --- ESQUEMAS PARA MEDICAMENTOS ---
class MedicationCreate(BaseModel):
    name: str
    dosage: str
    frequency: str

class MedicationResponse(MedicationCreate):
    id: int
    patient_id: int
    is_active: bool

    class Config:
        from_attributes = True

# --- ESQUEMA DE PERFIL CLÍNICO (para el frontend) ---
class ClinicalProfileAllergy(BaseModel):
    allergen: str
    reaction: str
    severity: str

class ClinicalProfileMedication(BaseModel):
    id: int
    name: str
    dosage: str
    frequency: str
    is_active: bool

class PatientClinicalProfileResponse(BaseModel):
    id: int
    nombre: str
    edad: int | None
    sexo: str | None
    alergias: list[ClinicalProfileAllergy]
    medicamentos_actuales: list[ClinicalProfileMedication]

# --- ESQUEMA DE RESUMEN DE CONSULTAS (para el historial) ---
class ConsultationSummary(BaseModel):
    id: int
    date: datetime | None
    reason: str | None
    status: str | None

    class Config:
        from_attributes = True
