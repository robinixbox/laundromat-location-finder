"""
Service pour l'intégration avec l'API Google Maps
"""
import logging
from typing import Dict, List, Optional, Tuple, Any

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Coordinates, Competitor
from app.db.cache import cache_response

logger = logging.getLogger(__name__)


class GoogleMapsService:
    """Service pour interagir avec l'API Google Maps"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Effectue une requête à l'API Google Maps
        
        Args:
            endpoint: Point de terminaison de l'API
            params: Paramètres de la requête
            
        Returns:
            Réponse de l'API sous forme de dictionnaire
            
        Raises:
            Exception: En cas d'erreur lors de la requête
        """
        url = f"{self.base_url}/{endpoint}"
        
        # Ajouter la clé API
        params["key"] = self.api_key
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la requête à l'API Google Maps: {e}")
            raise Exception(f"Erreur Google Maps: {str(e)}")
    
    @cache_response(service="google_maps", expiration=86400 * 7)  # 7 jours
    def geocode_address(self, db: Session, address: str) -> Optional[Coordinates]:
        """
        Convertit une adresse en coordonnées géographiques
        
        Args:
            db: Session de base de données (pour le cache)
            address: Adresse à géocoder
            
        Returns:
            Coordonnées géographiques ou None en cas d'erreur
        """
        params = {
            "address": address,
            "language": "fr"
        }
        
        try:
            response = self._make_request("geocode/json", params)
            
            if response.get("status") == "OK" and response.get("results"):
                location = response["results"][0]["geometry"]["location"]
                return Coordinates(
                    latitude=location["lat"],
                    longitude=location["lng"]
                )
            
            logger.warning(f"Aucun résultat trouvé pour l'adresse: {address}")
            return None
        
        except Exception as e:
            logger.error(f"Erreur lors du géocodage de l'adresse '{address}': {e}")
            return None
    
    @cache_response(service="google_maps")
    def reverse_geocode(self, db: Session, coordinates: Coordinates) -> Optional[str]:
        """
        Convertit des coordonnées géographiques en adresse
        
        Args:
            db: Session de base de données (pour le cache)
            coordinates: Coordonnées à convertir
            
        Returns:
            Adresse ou None en cas d'erreur
        """
        params = {
            "latlng": f"{coordinates.latitude},{coordinates.longitude}",
            "language": "fr"
        }
        
        try:
            response = self._make_request("geocode/json", params)
            
            if response.get("status") == "OK" and response.get("results"):
                return response["results"][0]["formatted_address"]
            
            logger.warning(f"Aucun résultat trouvé pour les coordonnées: {coordinates}")
            return None
        
        except Exception as e:
            logger.error(f"Erreur lors du géocodage inverse: {e}")
            return None
    
    @cache_response(service="google_maps")
    def find_nearby_laundromats(
        self, 
        db: Session,
        coordinates: Coordinates, 
        radius: int = 800,
        keywords: List[str] = None
    ) -> List[Competitor]:
        """
        Trouve les laveries à proximité d'un point donné
        
        Args:
            db: Session de base de données (pour le cache)
            coordinates: Coordonnées du point central
            radius: Rayon de recherche en mètres
            keywords: Mots-clés pour filtrer les résultats
            
        Returns:
            Liste des laveries trouvées
        """
        if keywords is None:
            keywords = settings.COMPETITOR_KEYWORDS
        
        keyword_str = "|".join(keywords)
        
        params = {
            "location": f"{coordinates.latitude},{coordinates.longitude}",
            "radius": radius,
            "keyword": keyword_str,
            "type": "establishment",
            "language": "fr"
        }
        
        try:
            response = self._make_request("place/nearbysearch/json", params)
            
            if response.get("status") == "OK" and response.get("results"):
                competitors = []
                
                for place in response["results"]:
                    # Calculer la distance (approximation euclidienne)
                    place_loc = place["geometry"]["location"]
                    place_coords = Coordinates(
                        latitude=place_loc["lat"],
                        longitude=place_loc["lng"]
                    )
                    
                    # Calcul approximatif de la distance (à vol d'oiseau)
                    distance = self.calculate_distance(coordinates, place_coords)
                    
                    competitor = Competitor(
                        name=place["name"],
                        address=place.get("vicinity", "Adresse inconnue"),
                        coordinates=place_coords,
                        distance=distance,
                        place_id=place["place_id"]
                    )
                    
                    competitors.append(competitor)
                
                # Trier par distance
                competitors.sort(key=lambda x: x.distance)
                
                return competitors
            
            if response.get("status") == "ZERO_RESULTS":
                logger.info(f"Aucune laverie trouvée dans un rayon de {radius}m")
                return []
            
            logger.warning(f"Erreur API Google Maps: {response.get('status')}")
            return []
        
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de laveries: {e}")
            return []
    
    @staticmethod
    def calculate_distance(coord1: Coordinates, coord2: Coordinates) -> float:
        """
        Calcule la distance approximative entre deux points (formule de Haversine)
        
        Args:
            coord1: Premier point
            coord2: Deuxième point
            
        Returns:
            Distance en mètres
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # Rayon de la Terre en mètres
        R = 6371000
        
        # Convertir en radians
        lat1 = radians(coord1.latitude)
        lon1 = radians(coord1.longitude)
        lat2 = radians(coord2.latitude)
        lon2 = radians(coord2.longitude)
        
        # Différence de latitude et longitude
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Formule de Haversine
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    
    @cache_response(service="google_maps")
    def get_place_details(self, db: Session, place_id: str) -> Dict[str, Any]:
        """
        Récupère les détails d'un lieu à partir de son ID
        
        Args:
            db: Session de base de données (pour le cache)
            place_id: ID du lieu
            
        Returns:
            Détails du lieu ou dictionnaire vide en cas d'erreur
        """
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,geometry,opening_hours,website,formatted_phone_number",
            "language": "fr"
        }
        
        try:
            response = self._make_request("place/details/json", params)
            
            if response.get("status") == "OK" and response.get("result"):
                return response["result"]
            
            logger.warning(f"Aucun détail trouvé pour le lieu: {place_id}")
            return {}
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des détails du lieu '{place_id}': {e}")
            return {}
    
    @cache_response(service="google_maps", expiration=86400 * 30)  # 30 jours
    def get_city_coordinates(self, db: Session, city: str) -> Optional[Coordinates]:
        """
        Récupère les coordonnées d'une ville
        
        Args:
            db: Session de base de données (pour le cache)
            city: Nom de la ville ou code postal
            
        Returns:
            Coordonnées de la ville ou None en cas d'erreur
        """
        # Supposons qu'il s'agit d'un code postal français si c'est un nombre à 5 chiffres
        if city.isdigit() and len(city) == 5:
            query = f"{city}, France"
        else:
            query = f"{city}, France"
        
        return self.geocode_address(db, query)
    
    @cache_response(service="google_maps")
    def get_city_boundary(self, db: Session, city: str) -> List[Coordinates]:
        """
        Récupère les limites administratives d'une ville (approximation)
        
        Args:
            db: Session de base de données (pour le cache)
            city: Nom de la ville ou code postal
            
        Returns:
            Liste de coordonnées représentant le contour de la ville
        """
        # Cette fonctionnalité nécessiterait des données supplémentaires ou une autre API
        # Pour l'instant, créons un carré autour du centre de la ville
        center = self.get_city_coordinates(db, city)
        if not center:
            return []
        
        # Créer un carré de 5km x 5km
        # Environ 0.045 degrés de latitude = 5km
        # Environ 0.06 degrés de longitude = 5km à la latitude de la France
        delta_lat = 0.045
        delta_lon = 0.06
        
        boundary = [
            Coordinates(latitude=center.latitude - delta_lat, longitude=center.longitude - delta_lon),
            Coordinates(latitude=center.latitude - delta_lat, longitude=center.longitude + delta_lon),
            Coordinates(latitude=center.latitude + delta_lat, longitude=center.longitude + delta_lon),
            Coordinates(latitude=center.latitude + delta_lat, longitude=center.longitude - delta_lon),
            Coordinates(latitude=center.latitude - delta_lat, longitude=center.longitude - delta_lon),  # Fermer le polygone
        ]
        
        return boundary


# Instance globale du service
google_maps_service = GoogleMapsService()
