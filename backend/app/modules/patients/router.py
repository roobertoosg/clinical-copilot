from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Patient, Allergy, Medication
from .schemas import PatientCreate, PatientResponse, AllergyCreate, AllergyResponse, MedicationCreate, MedicationResponse

# Creamos un router específico para todo lo relacionado a pacientes
router = APIRouter(prefix="/patients", tags=["Patients"])

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