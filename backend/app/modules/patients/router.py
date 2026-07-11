from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Patient, Allergy, Medication
from .schemas import (
    PatientCreate,
    PatientResponse,
    AllergyCreate,
    AllergyResponse,
    MedicationCreate,
    MedicationResponse,
    PatientClinicalProfileResponse,
)

# Creamos un router específico para todo lo relacionado a pacientes
router = APIRouter(prefix="/patients", tags=["Patients"])


def _calculate_age(date_of_birth: date | None) -> int | None:
    """Calcula la edad en años a partir de la fecha de nacimiento."""
    if not date_of_birth:
        return None
    today = date.today()
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )

# Ventanilla 1: CREAR PACIENTE (POST)
@router.post("/", response_model=PatientResponse)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    # Convertimos los datos validados a un modelo de base de datos
    db_patient = Patient(
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender
    )
    db.add(db_patient)   # Preparamos para guardar
    db.commit()          # Guardamos en PostgreSQL
    db.refresh(db_patient) # Refrescamos para obtener el ID generado
    return db_patient

# Ventanilla 2: BUSCAR PACIENTE (GET)
@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    # Buscamos en la base de datos por ID
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if db_patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return db_patient

# Ventanilla 2.5: PERFIL CLÍNICO COMPLETO (GET)
@router.get("/{patient_id}/clinical-profile", response_model=PatientClinicalProfileResponse)
def get_patient_clinical_profile(patient_id: int, db: Session = Depends(get_db)):
    # Traemos al paciente junto con sus relaciones (allergies, medications)
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Transformamos los datos de la BD al esquema esperado por el frontend
    return PatientClinicalProfileResponse(
        id=patient.id,
        nombre=f"{patient.first_name} {patient.last_name}".strip(),
        edad=_calculate_age(patient.date_of_birth),
        sexo=patient.gender,
        alergias=[
            {
                "allergen": a.allergen,
                "reaction": a.reaction,
                "severity": a.severity,
            }
            for a in patient.allergies
        ],
        medicamentos_actuales=[
            {
                "name": m.name,
                "dosage": m.dosage,
                "frequency": m.frequency,
            }
            for m in patient.medications
        ],
    )


# Ventanilla 3: REGISTRAR ALERGIA (POST)
@router.post("/{patient_id}/allergies", response_model=AllergyResponse)
def create_allergy(patient_id: int, allergy: AllergyCreate, db: Session = Depends(get_db)):
    # Verificamos que el paciente exista
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    db_allergy = Allergy(**allergy.model_dump(), patient_id=patient_id)
    db.add(db_allergy)
    db.commit()
    db.refresh(db_allergy)
    return db_allergy

# Ventanilla 4: REGISTRAR MEDICAMENTO (POST)
@router.post("/{patient_id}/medications", response_model=MedicationResponse)
def create_medication(patient_id: int, medication: MedicationCreate, db: Session = Depends(get_db)):
    # Verificamos que el paciente exista
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    db_medication = Medication(**medication.model_dump(), patient_id=patient_id)
    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    return db_medication