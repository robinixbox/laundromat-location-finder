"""
Configuration de la base de données SQLite avec SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Création du moteur SQLAlchemy avec l'URL de la base de données
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # Nécessaire pour SQLite
)

# Création d'une classe SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Création d'une classe de base pour les modèles déclaratifs
Base = declarative_base()


def get_db():
    """
    Fonction pour obtenir une session de base de données.
    À utiliser comme dépendance dans FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
