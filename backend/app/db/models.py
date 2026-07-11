from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .session import Base

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    date_of_birth = Column(Date)
    gender = Column(String)
    
    # Relaciones (Un paciente puede tener muchas alergias y medicamentos)
    allergies = relationship("Allergy", back_populates="patient")
    medications = relationship("Medication", back_populates="patient")
    consultations = relationship("Consultation", back_populates="patient")

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
    
    patient = relationship("Patient", back_populates="medications")


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    reason = Column(Text, nullable=True)          # Motivo de la consulta / resumen
    transcription = Column(Text, nullable=True)   # Transcripción de la conversación
    status = Column(String, default="completed", nullable=False)

    patient = relationship("Patient", back_populates="consultations")
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
