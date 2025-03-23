"""
Modèles SQLAlchemy pour la persistance des données
"""
from datetime import datetime
from typing import Dict, Any, List, Optional

import json
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from app.db.database import Base


class SearchQuery(Base):
    """
    Modèle pour stocker les recherches effectuées
    """
    __tablename__ = "search_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True, nullable=False)
    params = Column(Text, nullable=False)  # Stocké en JSON
    created_at = Column(DateTime, default=datetime.now)
    
    # Relations
    locations = relationship("LocationDB", back_populates="search_query", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'instance en dictionnaire"""
        return {
            "id": self.id,
            "query": self.query,
            "params": json.loads(self.params),
            "created_at": self.created_at.isoformat(),
            "location_count": len(self.locations)
        }


class LocationDB(Base):
    """
    Modèle pour stocker les emplacements potentiels
    """
    __tablename__ = "locations"
    
    id = Column(String, primary_key=True)
    search_id = Column(Integer, ForeignKey("search_queries.id"), nullable=False)
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    population_10min = Column(Integer, default=0)
    nearest_competitor_distance = Column(Float, default=float('inf'))
    density_index = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    details = Column(Text, default="{}")  # Stocké en JSON
    created_at = Column(DateTime, default=datetime.now)
    
    # Relations
    search_query = relationship("SearchQuery", back_populates="locations")
    competitors = relationship("CompetitorDB", back_populates="location", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'instance en dictionnaire"""
        return {
            "id": self.id,
            "address": self.address,
            "coordinates": {
                "latitude": self.latitude,
                "longitude": self.longitude
            },
            "population_10min": self.population_10min,
            "nearest_competitor_distance": self.nearest_competitor_distance,
            "density_index": self.density_index,
            "total_score": self.total_score,
            "details": json.loads(self.details),
            "created_at": self.created_at.isoformat(),
            "search_id": self.search_id
        }


class CompetitorDB(Base):
    """
    Modèle pour stocker les concurrents (laveries existantes)
    """
    __tablename__ = "competitors"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    distance = Column(Float, nullable=False)  # Distance en mètres
    place_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relations
    location = relationship("LocationDB", back_populates="competitors")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'instance en dictionnaire"""
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "coordinates": {
                "latitude": self.latitude,
                "longitude": self.longitude
            },
            "distance": self.distance,
            "place_id": self.place_id,
            "created_at": self.created_at.isoformat(),
            "location_id": self.location_id
        }


class CacheEntryDB(Base):
    """
    Modèle pour stocker le cache des requêtes API
    """
    __tablename__ = "cache_entries"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)  # Stocké en JSON
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    
    def is_expired(self) -> bool:
        """Vérifie si l'entrée du cache a expiré"""
        return datetime.now() > self.expires_at
    
    def get_value(self) -> Any:
        """Récupère la valeur mise en cache"""
        return json.loads(self.value)
