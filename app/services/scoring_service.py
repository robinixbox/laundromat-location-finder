"""
Service pour l'évaluation et le classement des emplacements potentiels
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Location, Coordinates, SearchParameters, SearchResults, Competitor
from app.db import crud
from app.services.google_maps_service import google_maps_service
from app.services.smappen_service import smappen_service
from app.services.geoportail_service import geoportail_service

logger = logging.getLogger(__name__)


class ScoringService:
    """Service d'évaluation des emplacements"""
    
    def __init__(self):
        """Initialisation du service"""
        self.weight_population = settings.WEIGHT_POPULATION
        self.weight_competition = settings.WEIGHT_COMPETITION
        self.weight_density = settings.WEIGHT_DENSITY
    
    def evaluate_location(
        self, 
        db: Session,
        coordinates: Coordinates, 
        address: str = None
    ) -> Location:
        """
        Évalue un emplacement potentiel en fonction des critères définis
        
        Args:
            db: Session de base de données
            coordinates: Coordonnées de l'emplacement
            address: Adresse (optionnelle, sera géocodée si non fournie)
            
        Returns:
            Objet Location avec les évaluations
        """
        # Si l'adresse n'est pas fournie, effectuer un géocodage inverse
        if not address:
            address = google_maps_service.reverse_geocode(db, coordinates)
            if not address:
                address = f"Adresse inconnue ({coordinates.latitude}, {coordinates.longitude})"
        
        # Créer l'objet Location
        location = Location(
            address=address,
            coordinates=coordinates,
            details={}
        )
        
        # 1. Évaluer la population accessible à pied
        population = smappen_service.get_population_within_walking_distance(
            db, coordinates, settings.MAX_WALKING_TIME)
        location.population_10min = population
        location.details["population_data"] = {
            "walking_time_minutes": settings.MAX_WALKING_TIME,
            "population_within_walking_distance": population,
            "minimum_threshold": settings.POPULATION_MIN_THRESHOLD,
            "sufficiency": "sufficient" if population >= settings.POPULATION_MIN_THRESHOLD else "insufficient"
        }
        
        # 2. Rechercher les concurrents à proximité
        competitors = google_maps_service.find_nearby_laundromats(
            db, coordinates, settings.COMPETITOR_SEARCH_RADIUS, settings.COMPETITOR_KEYWORDS)
        
        if competitors:
            # Trouver le concurrent le plus proche
            nearest = min(competitors, key=lambda x: x.distance)
            location.nearest_competitor = nearest
            location.nearest_competitor_distance = nearest.distance
            
            # Ajouter tous les concurrents
            location.competitors_within_radius = competitors
            
            location.details["competition_data"] = {
                "nearest_competitor": {
                    "name": nearest.name,
                    "address": nearest.address,
                    "distance_meters": nearest.distance
                },
                "competitors_count": len(competitors),
                "search_radius_meters": settings.COMPETITOR_SEARCH_RADIUS
            }
        else:
            location.details["competition_data"] = {
                "nearest_competitor": None,
                "competitors_count": 0,
                "search_radius_meters": settings.COMPETITOR_SEARCH_RADIUS
            }
        
        # 3. Évaluer la densité résidentielle
        density_index = geoportail_service.get_residential_density_index(db, coordinates)
        location.density_index = density_index * 10000  # Convertir l'indice 0-1 en 0-10000
        location.details["density_data"] = {
            "residential_density_index": density_index,
            "density_value": location.density_index,
            "threshold": settings.DENSITY_THRESHOLD,
            "sufficiency": "high" if density_index > 0.7 else "medium" if density_index > 0.4 else "low"
        }
        
        # 4. Calculer le score global
        location.calculate_score(
            weight_population=self.weight_population,
            weight_competition=self.weight_competition,
            weight_density=self.weight_density
        )
        
        # 5. Ajouter des informations supplémentaires
        location.details["score_details"] = {
            "total_score": location.total_score,
            "population_score": min(1.0, location.population_10min / 10000),
            "competition_score": min(1.0, location.nearest_competitor_distance / 1000) if location.nearest_competitor_distance != float('inf') else 1.0,
            "density_score": min(1.0, location.density_index / 5000),
            "weights": {
                "population": self.weight_population,
                "competition": self.weight_competition,
                "density": self.weight_density
            }
        }
        
        return location
    
    def search_optimal_locations(
        self, 
        db: Session,
        params: SearchParameters
    ) -> SearchResults:
        """
        Recherche les emplacements optimaux pour une ville ou un code postal
        
        Args:
            db: Session de base de données
            params: Paramètres de recherche
            
        Returns:
            Résultats de la recherche
        """
        # 1. Obtenir les coordonnées de la ville ou du code postal
        center = google_maps_service.get_city_coordinates(db, params.city_or_postal_code)
        if not center:
            logger.error(f"Impossible de géocoder: {params.city_or_postal_code}")
            return SearchResults(search_params=params)
        
        # 2. Générer une grille de points potentiels
        grid_points = geoportail_service.generate_grid_points(
            db, params.city_or_postal_code, params.radius / 1000, 15)
        
        # 3. Trouver les zones à forte densité résidentielle
        residential_areas = geoportail_service.find_residential_areas(
            db, center, params.radius / 1000, 0.5)
        
        # 4. Combiner les points de la grille avec les zones résidentielles
        candidate_points = []
        
        # Ajouter les points de la grille
        for point in grid_points:
            candidate_points.append(point["coordinates"])
        
        # Ajouter les zones résidentielles (prioritaires)
        for area in residential_areas:
            coords = Coordinates(
                latitude=area["coordinates"]["latitude"],
                longitude=area["coordinates"]["longitude"]
            )
            if coords not in candidate_points:
                candidate_points.append(coords)
        
        # 5. Évaluer chaque point
        locations = []
        for coords in candidate_points:
            location = self.evaluate_location(db, coords)
            
            # Ne garder que les emplacements avec un score minimal
            if (location.population_10min >= settings.POPULATION_MIN_THRESHOLD and
                location.total_score > 0.4):
                locations.append(location)
        
        # 6. Créer et retourner les résultats
        results = SearchResults(
            search_params=params,
            locations=locations,
            total_count=len(locations)
        )
        
        # 7. Trier par score
        results.sort_by_score()
        
        return results
    
    def save_search_results(
        self, 
        db: Session,
        results: SearchResults
    ) -> int:
        """
        Sauvegarde les résultats d'une recherche dans la base de données
        
        Args:
            db: Session de base de données
            results: Résultats de la recherche
            
        Returns:
            ID de la recherche sauvegardée
        """
        # 1. Créer l'entrée de recherche
        params_dict = results.search_params.dict()
        db_query = crud.create_search_query(
            db, results.search_params.city_or_postal_code, params_dict)
        
        # 2. Sauvegarder chaque emplacement
        for location in results.locations:
            crud.create_location(db, location, db_query.id)
        
        return db_query.id


# Instance globale du service
scoring_service = ScoringService()
