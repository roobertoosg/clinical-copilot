from pydantic import BaseModel
from datetime import date

# La estructura básica que el usuario debe enviar
class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str

# La estructura que el servidor devolverá (incluye el ID que genera la base de datos)
class PatientResponse(PatientCreate):
    id: int

    class Config:
        from_attributes = True  # Permite que Pydantic lea desde SQLAlchemy

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

    class Config:
        from_attributes = True
