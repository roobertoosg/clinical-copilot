from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey
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

class Allergy(Base):
    __tablename__ = "allergies"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    allergen = Column(String) # Ej: Penicilina
    reaction = Column(String) # Ej: Erupción cutánea
    severity = Column(String) # Ej: Leve, Moderada, Severa
    
    patient = relationship("Patient", back_populates="allergies")

class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    name = Column(String) # Ej: Paracetamol
    dosage = Column(String) # Ej: 500mg
    frequency = Column(String) # Ej: Cada 8 horas
    
    patient = relationship("Patient", back_populates="medications")
