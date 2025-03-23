"""
Service simulé pour l'intégration avec Smappen.
Comme l'API Smappen n'est pas directement disponible, ce service
simule les données de population accessible à pied autour d'une adresse.
"""
import logging
import random
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Coordinates
from app.db.cache import cache_response
from app.services.google_maps_service import google_maps_service

logger = logging.getLogger(__name__)


class SmappenService:
    """Service simulé pour Smappen (estimation de population accessible)"""
    
    def __init__(self):
        """Initialisation du service"""
        # Densités de population moyennes par type de zone (habitants/km²)
        self.densities = {
            "urban_center": (10000, 25000),  # Centre-ville dense
            "urban": (5000, 10000),          # Zone urbaine
            "suburban": (1000, 5000),        # Banlieue
            "town": (500, 2000),             # Petite ville
            "rural": (50, 500)               # Zone rurale
        }
    
    def _detect_area_type(self, coordinates: Coordinates) -> str:
        """
        Détermine le type de zone en fonction des coordonnées.
        Cette fonction utilise des données fictives et un générateur de nombres
        aléatoires déterministe basé sur les coordonnées.
        
        Args:
            coordinates: Coordonnées géographiques
            
        Returns:
            Type de zone ("urban_center", "urban", "suburban", "town", "rural")
        """
        # Utiliser les coordonnées comme graine pour avoir des résultats cohérents
        seed = int((coordinates.latitude * 1000) + (coordinates.longitude * 10000)) % 10000
        rng = random.Random(seed)
        
        # Pour la France, coordonnées approximatives des grandes villes
        major_cities = [
            (48.8566, 2.3522),    # Paris
            (43.2965, 5.3698),    # Marseille
            (45.7578, 4.8320),    # Lyon
            (43.6043, 1.4437),    # Toulouse
            (47.2173, -1.5534),   # Nantes
            (43.7102, 7.2620),    # Nice
            (48.5734, 7.7521),    # Strasbourg
            (50.6333, 3.0667),    # Lille
            (44.8378, -0.5792),   # Bordeaux
            (47.3900, 0.6889)     # Tours
        ]
        
        # Calculer la distance minimale aux grandes villes
        min_distance = float('inf')
        for city_lat, city_lon in major_cities:
            city_coord = Coordinates(latitude=city_lat, longitude=city_lon)
            distance = google_maps_service.calculate_distance(coordinates, city_coord)
            min_distance = min(min_distance, distance)
        
        # Déterminer le type de zone en fonction de la distance
        if min_distance < 2000:  # Moins de 2km d'un centre-ville majeur
            return "urban_center"
        elif min_distance < 10000:  # Moins de 10km d'un centre-ville majeur
            return "urban"
        elif min_distance < 30000:  # Moins de 30km d'un centre-ville majeur
            return "suburban"
        elif min_distance < 100000:  # Moins de 100km d'un centre-ville majeur
            # 70% de chance d'être une petite ville, 30% d'être rural
            return "town" if rng.random() < 0.7 else "rural"
        else:
            # 30% de chance d'être une petite ville, 70% d'être rural
            return "rural" if rng.random() < 0.7 else "town"
    
    def _calculate_density(self, area_type: str, coordinates: Coordinates) -> float:
        """
        Calcule la densité de population pour un type de zone donné.
        
        Args:
            area_type: Type de zone
            coordinates: Coordonnées pour générer une variation aléatoire cohérente
            
        Returns:
            Densité de population estimée (habitants/km²)
        """
        min_density, max_density = self.densities.get(area_type, (50, 500))
        
        # Utiliser les coordonnées comme graine pour avoir des résultats cohérents
        seed = int((coordinates.latitude * 1000) + (coordinates.longitude * 10000)) % 10000
        rng = random.Random(seed)
        
        # Générer une valeur aléatoire entre min et max
        base_density = min_density + rng.random() * (max_density - min_density)
        
        # Ajouter une variation gaussienne
        variation = rng.gauss(0, 0.2)  # 20% de variation standard
        density = base_density * (1 + variation)
        
        return max(min_density * 0.5, density)  # Éviter les valeurs trop basses
    
    @cache_response(service="smappen", expiration=86400 * 30)  # 30 jours
    def get_population_within_walking_distance(
        self,
        db: Session,
        coordinates: Coordinates,
        walking_time_minutes: int = 10
    ) -> int:
        """
        Estime la population accessible à pied dans un temps donné.
        
        Args:
            db: Session de base de données (pour le cache)
            coordinates: Coordonnées du point central
            walking_time_minutes: Temps de marche en minutes
            
        Returns:
            Estimation de la population accessible
        """
        # Détecter le type de zone
        area_type = self._detect_area_type(coordinates)
        
        # Calculer la densité de population
        density = self._calculate_density(area_type, coordinates)
        
        # Calculer la surface accessible (cercle)
        # Vitesse moyenne de marche : 5 km/h = 83.33 m/min
        walking_speed_meters_per_minute = settings.WALKING_SPEED * 1000 / 60
        radius_meters = walking_speed_meters_per_minute * walking_time_minutes
        
        # Surface en km²
        area_km2 = np.pi * (radius_meters / 1000) ** 2
        
        # Population = densité * surface
        population = int(density * area_km2)
        
        logger.info(f"Population estimée dans un rayon de {walking_time_minutes} min "
                   f"({radius_meters:.0f}m) : {population} habitants (densité: {density:.0f} hab/km²)")
        
        return population
    
    @cache_response(service="smappen", expiration=86400 * 30)  # 30 jours
    def get_density_index(self, db: Session, coordinates: Coordinates) -> float:
        """
        Calcule un indice de densité pour les coordonnées données.
        
        Args:
            db: Session de base de données (pour le cache)
            coordinates: Coordonnées du point
            
        Returns:
            Indice de densité (habitants/km²)
        """
        area_type = self._detect_area_type(coordinates)
        return self._calculate_density(area_type, coordinates)
    
    def generate_population_heatmap(
        self, 
        db: Session,
        center: Coordinates, 
        radius_km: float = 5.0,
        resolution: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Génère une carte de chaleur de la population dans une zone.
        
        Args:
            db: Session de base de données (pour le cache)
            center: Coordonnées du centre de la zone
            radius_km: Rayon de la zone en kilomètres
            resolution: Nombre de points sur chaque axe
            
        Returns:
            Liste de points avec leurs coordonnées et densité de population
        """
        # Conversion approximative degrés -> km à la latitude de la France
        lat_km = 111.0  # 1 degré de latitude = environ 111 km
        lon_km = 111.0 * np.cos(np.radians(center.latitude))  # Ajustement selon la latitude
        
        # Dimensions de la grille en degrés
        lat_range = radius_km / lat_km
        lon_range = radius_km / lon_km
        
        # Générer la grille
        points = []
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
                    # Calculer la densité
                    density = self.get_density_index(db, point_coord)
                    
                    points.append({
                        "coordinates": {"latitude": lat, "longitude": lon},
                        "density": density,
                        "distance": distance
                    })
        
        return points


# Instance globale du service
smappen_service = SmappenService()
