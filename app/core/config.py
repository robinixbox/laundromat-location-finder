"""
Configuration de l'application
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


# Chemin racine du projet
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Configuration principale de l'application"""
    
    # Nom et version de l'application
    APP_NAME: str = "Laundromat Location Finder"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API Keys
    GOOGLE_MAPS_API_KEY: str
    GEOPORTAIL_API_KEY: Optional[str] = None
    
    # Base de données
    DATABASE_URL: str = f"sqlite:///{ROOT_DIR}/data/laundromat_finder.db"
    
    # Chemins pour les données
    DATA_DIR: Path = ROOT_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    CACHE_DIR: Path = DATA_DIR / "cache"
    
    # Configuration du cache
    CACHE_EXPIRATION: int = 86400  # 24 heures en secondes
    
    # Configuration du journal
    LOG_LEVEL: str = "INFO"
    
    # Configuration de la carte
    MAP_CENTER_LAT: float = 46.603354  # Centre de la France
    MAP_CENTER_LON: float = 1.888334
    MAP_DEFAULT_ZOOM: int = 6
    
    # Paramètres métier
    WALKING_SPEED: float = 5.0  # km/h pour les calculs de distance à pied
    MAX_WALKING_TIME: int = 10  # minutes
    COMPETITOR_SEARCH_RADIUS: int = 800  # mètres (environ 10min à pied)
    DENSITY_THRESHOLD: int = 1000  # habitants/km² pour considérer une densité élevée
    POPULATION_MIN_THRESHOLD: int = 2000  # population minimale dans la zone de marche
    
    # Poids pour le score
    WEIGHT_POPULATION: float = 0.4
    WEIGHT_COMPETITION: float = 0.4
    WEIGHT_DENSITY: float = 0.2
    
    # Mots-clés pour rechercher des concurrents
    COMPETITOR_KEYWORDS: List[str] = ["laverie", "laundromat", "pressing", "laverie automatique", "laverie libre service"]
    
    @field_validator("DATABASE_URL")
    def validate_db_url(cls, v: str) -> str:
        """Convertit le chemin de la base de données en chemin absolu si nécessaire"""
        if v.startswith("sqlite:///./"):
            return v.replace("./", str(ROOT_DIR) + "/")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Instance de configuration globale
settings = Settings()

# Assurer l'existence des dossiers de données
settings.DATA_DIR.mkdir(exist_ok=True)
settings.RAW_DATA_DIR.mkdir(exist_ok=True)
settings.PROCESSED_DATA_DIR.mkdir(exist_ok=True)
settings.CACHE_DIR.mkdir(exist_ok=True)
