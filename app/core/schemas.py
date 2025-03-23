"""
Schémas Pydantic pour les requêtes et réponses API
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.models import Coordinates, Location, Competitor


class LocationRequest(BaseModel):
    """Requête pour la recherche d'emplacements"""
    city_or_postal_code: str
    radius_km: float = 10.0
    walking_time_min: int = 10


class LocationResponse(BaseModel):
    """Réponse pour un emplacement potentiel"""
    id: str
    address: str
    coordinates: Coordinates
    population_within_walking_distance: int
    nearest_competitor_distance_meters: float
    nearest_competitor_name: Optional[str] = None
    density_index: float
    score: float
    
    @classmethod
    def from_location(cls, location: Location) -> "LocationResponse":
        """Crée une réponse à partir d'un modèle Location"""
        return cls(
            id=location.id,
            address=location.address,
            coordinates=location.coordinates,
            population_within_walking_distance=location.population_10min,
            nearest_competitor_distance_meters=location.nearest_competitor_distance,
            nearest_competitor_name=location.nearest_competitor.name if location.nearest_competitor else None,
            density_index=location.density_index,
            score=location.total_score
        )


class SearchResultsResponse(BaseModel):
    """Réponse pour une recherche d'emplacements"""
    query: str
    timestamp: datetime = Field(default_factory=datetime.now)
    total_results: int
    locations: List[LocationResponse]


class CompetitorResponse(BaseModel):
    """Réponse pour un concurrent"""
    name: str
    address: str
    coordinates: Coordinates
    distance_meters: float
    
    @classmethod
    def from_competitor(cls, competitor: Competitor) -> "CompetitorResponse":
        """Crée une réponse à partir d'un modèle Competitor"""
        return cls(
            name=competitor.name,
            address=competitor.address,
            coordinates=competitor.coordinates,
            distance_meters=competitor.distance
        )


class LocationDetailResponse(LocationResponse):
    """Réponse détaillée pour un emplacement"""
    competitors_within_radius: List[CompetitorResponse] = []
    details: Dict[str, Any] = {}
    
    @classmethod
    def from_location(cls, location: Location) -> "LocationDetailResponse":
        """Crée une réponse détaillée à partir d'un modèle Location"""
        base = LocationResponse.from_location(location)
        
        return cls(
            **base.dict(),
            competitors_within_radius=[
                CompetitorResponse.from_competitor(comp) 
                for comp in location.competitors_within_radius
            ],
            details=location.details
        )


class ReportRequest(BaseModel):
    """Requête pour la génération d'un rapport"""
    search_id: str
    title: Optional[str] = None
    max_locations: int = 10
    include_map: bool = True
    include_details: bool = True


class ErrorResponse(BaseModel):
    """Réponse d'erreur"""
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.now)
