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
    place_id: Optional[str] = None


class Location(BaseModel):
    """Emplacement potentiel pour une laverie"""
    id: str = Field(default_factory=lambda: f"loc_{int(datetime.now().timestamp())}")
    address: str
    coordinates: Coordinates
    population_10min: int = 0
    nearest_competitor_distance: float = float('inf')
    nearest_competitor: Optional[Competitor] = None
    density_index: float = 0.0
    total_score: float = 0.0
    details: Dict[str, Any] = {}
    competitors_within_radius: List[Competitor] = []
    
    def calculate_score(self, 
                        weight_population: float = 0.4, 
                        weight_competition: float = 0.4, 
                        weight_density: float = 0.2) -> float:
        """Calcule un score global pour cet emplacement"""
        # Score population (normalisé pour 10k personnes = 1.0)
        population_score = min(1.0, self.population_10min / 10000)
        
        # Score concurrence (1.0 si > 1km, 0.0 si 0m)
        if self.nearest_competitor_distance == float('inf'):
            competition_score = 1.0
        else:
            competition_score = min(1.0, self.nearest_competitor_distance / 1000)
        
        # Score densité (normalisé pour densité de 5000 hab/km² = 1.0)
        density_score = min(1.0, self.density_index / 5000)
        
        # Score total
        self.total_score = (
            weight_population * population_score +
            weight_competition * competition_score +
            weight_density * density_score
        )
        
        return self.total_score


class SearchResults(BaseModel):
    """Résultats de recherche d'emplacements"""
    search_params: SearchParameters
    locations: List[Location] = []
    timestamp: datetime = Field(default_factory=datetime.now)
    total_count: int = 0
    
    def sort_by_score(self) -> None:
        """Trie les emplacements par score (du plus élevé au plus faible)"""
        self.locations.sort(key=lambda loc: loc.total_score, reverse=True)


class ReportConfig(BaseModel):
    """Configuration pour la génération de rapports"""
    title: str
    include_map: bool = True
    max_locations: int = 10
    include_details: bool = True


class CacheKey(BaseModel):
    """Clé de cache pour les requêtes API"""
    service: str
    query: str
    params: Dict[str, Any] = {}
    
    def get_key(self) -> str:
        """Génère une clé unique pour cette requête"""
        import hashlib
        import json
        
        # Création d'une représentation en chaîne de caractères de la clé
        key_dict = {
            "service": self.service,
            "query": self.query,
            "params": self.params
        }
        
        # Conversion en JSON et hachage pour obtenir une clé unique
        key_str = json.dumps(key_dict, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
