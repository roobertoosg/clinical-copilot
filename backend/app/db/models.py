from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from .session import Base

# Zona horaria del sistema: hora central de México
MEXICO_TZ = ZoneInfo("America/Mexico_City")


def now_mx() -> datetime:
    """Fecha/hora actual en la zona horaria de México (America/Mexico_City)."""
    return datetime.now(MEXICO_TZ)

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    date_of_birth = Column(Date)
    gender = Column(String)
    created_at = Column(DateTime(timezone=True), default=now_mx, nullable=False)
    
    # Relaciones (Un paciente puede tener muchas alergias y medicamentos)
    allergies = relationship("Allergy", back_populates="patient")
    medications = relationship("Medication", back_populates="patient")
    consultations = relationship("Consultation", back_populates="patient")


class Doctor(Base):
    """Médico responsable de las consultas (preparación para el futuro Login)."""

    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)      # Ej: Dr. Ricardo Mendoza
    specialty = Column(String, nullable=True)       # Ej: Medicina Interna
    license_number = Column(String, nullable=True)  # Cédula profesional

    consultations = relationship("Consultation", back_populates="doctor")

class Allergy(Base):
    __tablename__ = "allergies"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allergen = Column(String) # Ej: Penicilina
    reaction = Column(String) # Ej: Erupción cutánea
    severity = Column(String) # Ej: Leve, Moderada, Severa
    
    patient = relationship("Patient", back_populates="allergies")

class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String) # Ej: Paracetamol
    dosage = Column(String) # Ej: 500mg
    frequency = Column(String) # Ej: Cada 8 horas
    is_active = Column(Boolean, default=True, nullable=False)  # Activo vs suspendido
    created_at = Column(DateTime(timezone=True), default=now_mx, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=now_mx, onupdate=now_mx, nullable=False
    )
    
    patient = relationship("Patient", back_populates="medications")


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, index=True)
    folio = Column(String, unique=True, index=True, nullable=True)  # Ej: CON-20260711-0001
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # El médico NO es un registro dependiente de la consulta: si se elimina un
    # doctor, la consulta debe conservarse (por eso SET NULL y no CASCADE).
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    date = Column(DateTime(timezone=True), default=now_mx, nullable=False)
    reason = Column(Text, nullable=True)          # Motivo de la consulta / resumen
    transcription = Column(Text, nullable=True)   # Transcripción de la conversación
    status = Column(String, default="completed", nullable=False)
    # Similitud SOAPE IA vs. versión final del médico (0.0–1.0), Human-in-the-Loop
    ai_accuracy_score = Column(Float, nullable=True)

    patient = relationship("Patient", back_populates="consultations")
    doctor = relationship("Doctor", back_populates="consultations")
    # Al eliminar una consulta se eliminan sus registros clínicos asociados
    # (passive_deletes delega el borrado en cascada a PostgreSQL vía ondelete)
    clinical_note = relationship(
        "ClinicalNote",
        back_populates="consultation",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    prescriptions = relationship(
        "Prescription",
        back_populates="consultation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    alerts = relationship(
        "ClinicalAlert",
        back_populates="consultation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    diagnostics = relationship(
        "Diagnostic",
        back_populates="consultation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ClinicalNote(Base):
    """Nota clínica estructurada en formato SOAPE."""

    __tablename__ = "clinical_notes"

    id = Column(Integer, primary_key=True, index=True)
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subjective = Column(Text, nullable=True)
    objective = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    plan = Column(Text, nullable=True)
    evaluation = Column(Text, nullable=True)

    consultation = relationship("Consultation", back_populates="clinical_note")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medication = Column(String, nullable=False)
    dose = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    indications = Column(Text, nullable=True)

    consultation = relationship("Consultation", back_populates="prescriptions")


class ClinicalAlert(Base):
    __tablename__ = "clinical_alerts"

    id = Column(Integer, primary_key=True, index=True)
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_type = Column(String, nullable=True)   # Ej: alergia, interacción, dato faltante
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=True)     # Ej: baja, media, alta

    consultation = relationship("Consultation", back_populates="alerts")


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id = Column(Integer, primary_key=True, index=True)
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo = Column(String, nullable=True)        # Código CIE-11 OMS (ej. BA00) o "[Sin Código]"
    description = Column(String, nullable=False)  # Descripción del diagnóstico
    probabilidad = Column(String, nullable=True)  # Ej: Alta, Media, Baja

    consultation = relationship("Consultation", back_populates="diagnostics")


class MedicationCatalog(Base):
    """Catálogo institucional de medicamentos disponibles (Capa 1 — SQL estructurado)."""

    __tablename__ = "medications_catalog"

    id = Column(Integer, primary_key=True, index=True)
    producto = Column(String, nullable=False)
    marca = Column(String, nullable=True)
    sustancia_activa = Column(String, nullable=False, index=True)
    categoria = Column(String, nullable=True, index=True)
    ean = Column(String, nullable=True, index=True)
    laboratorio = Column(String, nullable=True)
    estatus = Column(String, default="ACTIVO", nullable=False, index=True)
