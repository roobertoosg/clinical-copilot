from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# URL de conexión a tu base de datos PostgreSQL en Docker
SQLALCHEMY_DATABASE_URL = "postgresql://copilot_user:copilot_password@localhost:5433/copilot_db"

# Motor de conexión
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Fábrica de sesiones (cada vez que un usuario hace una petición, se abre una sesión)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base de la que heredarán todos nuestros modelos
Base = declarative_base()

# Dependencia para inyectar la base de datos en los endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
