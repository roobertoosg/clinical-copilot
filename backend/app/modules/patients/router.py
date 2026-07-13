from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Patient, Allergy, Medication, Consultation
from .schemas import (
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    PatientSearchItem,
    AllergyCreate,
    AllergyResponse,
    MedicationCreate,
    MedicationResponse,
    PatientClinicalProfileResponse,
    ConsultationSummary,
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

def _full_name(patient: Patient) -> str:
    """Nombre completo del paciente para listados/búsqueda."""
    return f"{patient.first_name or ''} {patient.last_name or ''}".strip()


# Ventanilla 1: CREAR PACIENTE (POST)
@router.post("/", response_model=PatientResponse)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    # Convertimos los datos validados a un modelo de base de datos.
    # Normalizamos la capitalización de los nombres con .title().
    db_patient = Patient(
        first_name=patient.first_name.strip().title(),
        last_name=patient.last_name.strip().title(),
        date_of_birth=patient.date_of_birth,
        gender=patient.gender
    )
    db.add(db_patient)   # Preparamos para guardar
    db.commit()          # Guardamos en PostgreSQL
    db.refresh(db_patient) # Refrescamos para obtener el ID generado
    return db_patient


# Ventanilla 1.5: LISTAR / BUSCAR PACIENTES (GET)
@router.get("/", response_model=list[PatientSearchItem])
def search_patients(search: str | None = None, db: Session = Depends(get_db)):
    """Lista pacientes; con ?search={texto} filtra por nombre, apellido o ID."""
    query = db.query(Patient)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                # Permite buscar también por ID escribiendo un número
                cast(Patient.id, String).ilike(term),
            )
        )

    patients = query.order_by(Patient.first_name, Patient.last_name).all()
    return [
        PatientSearchItem(
            id=p.id,
            nombre=_full_name(p),
            date_of_birth=p.date_of_birth,
        )
        for p in patients
    ]

# Ventanilla 2: BUSCAR PACIENTE (GET)
@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    # Buscamos en la base de datos por ID
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if db_patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return db_patient


# Ventanilla 2.1: ACTUALIZAR DATOS DEMOGRÁFICOS (PUT)
@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int, patient: PatientUpdate, db: Session = Depends(get_db)
):
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if db_patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Normalizamos la capitalización igual que en la creación
    db_patient.first_name = patient.first_name.strip().title()
    db_patient.last_name = patient.last_name.strip().title()
    db_patient.date_of_birth = patient.date_of_birth
    db_patient.gender = patient.gender

    db.commit()
    db.refresh(db_patient)
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
                "id": m.id,
                "name": m.name,
                "dosage": m.dosage,
                "frequency": m.frequency,
                "is_active": m.is_active,
            }
            for m in patient.medications
        ],
    )


# Perfil: HISTORIAL DE CONSULTAS (GET)
@router.get("/{patient_id}/consultations", response_model=list[ConsultationSummary])
def get_patient_consultations(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Consultas del paciente ordenadas de la más reciente a la más antigua
    consultations = (
        db.query(Consultation)
        .filter(Consultation.patient_id == patient_id)
        .order_by(Consultation.date.desc())
        .all()
    )
    return consultations


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


# Ventanilla 5: ACTIVAR / SUSPENDER MEDICAMENTO (PATCH)
@router.patch(
    "/{patient_id}/medications/{medication_id}/toggle-status",
    response_model=MedicationResponse,
)
def toggle_medication_status(
    patient_id: int, medication_id: int, db: Session = Depends(get_db)
):
    medication = (
        db.query(Medication)
        .filter(
            Medication.id == medication_id,
            Medication.patient_id == patient_id,
        )
        .first()
    )
    if medication is None:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")

    # Invertimos el estado activo/suspendido
    medication.is_active = not medication.is_active
    db.commit()
    db.refresh(medication)
    return medication