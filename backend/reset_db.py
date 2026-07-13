"""Script de reinicio de la base de datos (SOLO para desarrollo).

Elimina TODAS las tablas y las vuelve a crear a partir de los modelos
actuales de SQLAlchemy, de modo que se apliquen los ajustes recientes
(ondelete="CASCADE", nullable=False, índices, etc.).

ADVERTENCIA: esto BORRA todos los datos existentes. No usar en producción.

Uso:
    python reset_db.py
"""

from app.db.session import Base, SessionLocal, engine

# Importar los modelos registra todas las tablas en Base.metadata
from app.db import models  # noqa: F401
from app.db.models import Doctor


def seed_data() -> None:
    """Inserta datos base de desarrollo (un doctor de prueba)."""
    db = SessionLocal()
    try:
        doctor = Doctor(
            full_name="Dr. Ricardo Mendoza",
            specialty="Medicina Interna",
            license_number="12345678",
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
        print(
            f"👨‍⚕️  Doctor de prueba creado: {doctor.full_name} "
            f"(ID {doctor.id}, cédula {doctor.license_number})."
        )
    finally:
        db.close()


def reset_database() -> None:
    print("⚠️  Eliminando todas las tablas...")
    Base.metadata.drop_all(bind=engine)
    print("✅ Tablas eliminadas.")

    print("🛠️  Recreando tablas desde los modelos...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas recreadas correctamente.")

    print("🌱 Insertando datos base (seed)...")
    seed_data()

    tablas = ", ".join(sorted(Base.metadata.tables.keys()))
    print(f"📋 Esquema actual: {tablas}")


if __name__ == "__main__":
    reset_database()
