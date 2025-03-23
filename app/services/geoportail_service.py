"""
Service simulé pour l'intégration avec Géoportail.
Comme l'API Géoportail complète n'est pas directement accessible,
ce service simule les données de densité de population et les zones résidentielles.
"""
import logging
import random
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Coordinates
from app.db.cache import cache_response
from app.services.smappen_service import smappen_service

logger = logging.getLogger(__name__)


class GeoportailService:
    """Service simulé pour Géoportail (données de densité résidentielle)"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEOPORTAIL_API_KEY
        
        # Types de zones résidentielles
        self.residential_types = {
            "high_density": (0.8, 1.0),  # Grands immeubles
            "medium_density": (0.5, 0.8),  # Petits immeubles
            "low_density": (0.2, 0.5),    # Maisons mitoyennes
            "very_low_density": (0.0, 0.2)  # Maisons individuelles
        }
    
    def _estimate_residential_type(self, density: float) -> str:
        """
        Estime le type de zone résidentielle en fonction de la densité.
        
        Args:
            density: Densité de population (hab/km²)
            
        Returns:
            Type de zone résidentielle
        """
        if density > 5000:
            return "high_density"
        elif density > 2000:
            return "medium_density"
        elif density > 500:
            return "low_density"
        else:
            return "very_low_density"
    
    def _calculate_residential_index(self, 
                                     residential_type: str, 
                                     coordinates: Coordinates) -> float:
        """
        Calcule un indice de résidentialité (proportion de logements).
        
        Args:
            residential_type: Type de zone résidentielle
            coordinates: Coordonnées pour générer une variation aléatoire cohérente
            
        Returns:
            Indice de résidentialité (0-1)
        """
        min_index, max_index = self.residential_types.get(
            residential_type, (0.0, 0.2))
        
        # Utiliser les coordonnées comme graine pour avoir des résultats cohérents
        seed = int((coordinates.latitude * 100) + (coordinates.longitude * 1000)) % 10000
        rng = random.Random(seed)
        
        # Générer une valeur aléatoire entre min et max
        base_index = min_index + rng.random() * (max_index - min_index)
        
        # Ajouter une variation gaussienne
        variation = rng.gauss(0, 0.1)  # 10% de variation standard
        index = base_index * (1 + variation)
        
        # Limiter entre 0 et 1
        return max(0.0, min(1.0, index))
    
    @cache_response(service="geoportail", expiration=86400 * 30)  # 30 jours
    def get_residential_density_index(
        self, 
        db: Session,
        coordinates: Coordinates
    ) -> float:
        """
        Calcule un indice de densité résidentielle.
        
        Args:
            db: Session de base de données (pour le cache)
            coordinates: Coordonnées du point
            
        Returns:
            Indice de densité résidentielle (0-1)
        """
        # Utiliser la densité de population de Smappen comme base
        population_density = smappen_service.get_density_index(db, coordinates)
        
        # Déterminer le type de zone résidentielle
        residential_type = self._estimate_residential_type(population_density)
        
        # Calculer l'indice de résidentialité
        residential_index = self._calculate_residential_index(residential_type, coordinates)
        
        # Calculer l'indice final en combinant densité et résidentialité
        # Normaliser la densité de population (10000 hab/km² = 1.0)
        normalized_density = min(1.0, population_density / 10000)
        
        # L'indice final est une moyenne pondérée
        final_index = 0.7 * normalized_density + 0.3 * residential_index
        
        logger.info(f"Indice de densité résidentielle calculé: {final_index:.2f} "
                   f"(densité: {population_density:.0f} hab/km², type: {residential_type})")
        
        return final_index
    
    @cache_response(service="geoportail", expiration=86400 * 30)  # 30 jours
    def find_residential_areas(
        self,
        db: Session, 
        center: Coordinates,
        radius_km: float = 5.0,
        min_density_index: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Trouve les zones à forte densité résidentielle dans un rayon donné.
        
        Args:
            db: Session de base de données (pour le cache)
            center: Coordonnées du centre de la zone
            radius_km: Rayon de la zone en kilomètres
            min_density_index: Indice de densité minimal pour considérer une zone
            
        Returns:
            Liste de zones résidentielles avec leurs coordonnées et indices
        """
        # Générer une grille de points
        grid_resolution = 10  # 10x10 points
        
        # Conversion approximative degrés -> km à la latitude de la France
        lat_km = 111.0  # 1 degré de latitude = environ 111 km
        lon_km = 111.0 * np.cos(np.radians(center.latitude))
        
        # Dimensions de la grille en degrés
        lat_range = radius_km / lat_km
        lon_range = radius_km / lon_km
        
        residential_areas = []
        
        # Générer la grille et évaluer chaque point
        for i in range(grid_resolution):
            for j in range(grid_resolution):
                # Coordonnées du point
                lat = center.latitude + (2 * i / (grid_resolution - 1) - 1) * lat_range
                lon = center.longitude + (2 * j / (grid_resolution - 1) - 1) * lon_range
                
                # Distance au centre (pour créer un cercle)
                point_coord = Coordinates(latitude=lat, longitude=lon)
                
                # Ne considérer que les points dans le rayon
                from app.services.google_maps_service import google_maps_service
                distance = google_maps_service.calculate_distance(center, point_coord)
                
                if distance <= radius_km * 1000:
                    # Calculer l'indice de densité résidentielle
                    density_index = self.get_residential_density_index(db, point_coord)
                    
                    # Ne garder que les zones à forte densité
                    if density_index >= min_density_index:
                        residential_areas.append({
                            "coordinates": {"latitude": lat, "longitude": lon},
                            "density_index": density_index,
                            "distance": distance
                        })
        
        # Trier par indice de densité (du plus élevé au plus faible)
        residential_areas.sort(key=lambda x: x["density_index"], reverse=True)
        
        return residential_areas
    
    @cache_response(service="geoportail", expiration=86400 * 30)  # 30 jours
    def generate_grid_points(
        self, 
        db: Session,
        city_name: str,
        radius_km: float = 5.0,
        resolution: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Génère une grille de points autour d'une ville pour l'analyse.
        
        Args:
            db: Session de base de données (pour le cache)
            city_name: Nom de la ville ou code postal
            radius_km: Rayon autour du centre-ville en kilomètres
            resolution: Résolution de la grille (nombre de points par axe)
            
        Returns:
            Liste de points avec leurs coordonnées
        """
        # Obtenir les coordonnées du centre de la ville
        from app.services.google_maps_service import google_maps_service
        center = google_maps_service.get_city_coordinates(db, city_name)
        
        if not center:
            logger.error(f"Impossible de trouver les coordonnées de la ville: {city_name}")
            return []
        
        # Conversion approximative degrés -> km à la latitude de la France
        lat_km = 111.0
        lon_km = 111.0 * np.cos(np.radians(center.latitude))
        
        # Dimensions de la grille en degrés
        lat_range = radius_km / lat_km
        lon_range = radius_km / lon_km
        
        # Générer la grille
        grid_points = []
        for i in range(resolution):
            for j in range(resolution):
                # Coordonnées du point
                lat = center.latitude + (2 * i / (resolution - 1) - 1) * lat_range
                lon = center.longitude + (2 * j / (resolution - 1) - 1) * lon_range
                
                # Distance au centre (pour créer un cercle)
                point_coord = Coordinates(latitude=lat, longitude=lon)
                distance = google_maps_service.calculate_distance(center, point_coord)
                
                # Ne garder que les points dans le rayon
                if distance <= radius_km * 1000:
                    grid_points.append({
                        "coordinates": point_coord,
                        "distance": distance
                    })
        
        return grid_points


# Instance globale du service
geoportail_service = GeoportailService()
