"""
Modèles de données principaux
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """Coordonnées géographiques"""
    latitude: float
    longitude: float


class SearchParameters(BaseModel):
    """Paramètres de recherche d'emplacements"""
    city_or_postal_code: str
    radius: int = 10000  # Rayon de recherche en mètres
    walking_time: int = 10  # Temps de marche en minutes
    competitor_keywords: List[str] = ["laverie", "laundromat", "pressing"]


class Competitor(BaseModel):
    """Information sur un concurrent (laverie existante)"""
    name: str
    address: str
    coordinates: Coordinates
    distance: float  # Distance en mètres