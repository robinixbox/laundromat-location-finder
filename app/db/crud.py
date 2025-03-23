"""
Opérations CRUD (Create, Read, Update, Delete) pour les modèles de base de données
"""
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union

from sqlalchemy.orm import Session

from app.core.models import Location, Competitor, SearchParameters, SearchResults
from app.db import models


def create_search_query(db: Session, query: str, params: Dict[str, Any]) -> models.SearchQuery:
    """
    Crée une nouvelle entrée de recherche dans la base de données
    
    Args:
        db: Session de base de données
        query: Chaîne de recherche (ville ou code postal)
        params: Paramètres de recherche
        
    Returns:
        L'objet SearchQuery créé
    """
    db_query = models.SearchQuery(
        query=query,
        params=json.dumps(params)
    )
    db.add(db_query)
    db.commit()
    db.refresh(db_query)
    return db_query


def get_search_query(db: Session, search_id: int) -> Optional[models.SearchQuery]:
    """
    Récupère une recherche par son ID
    
    Args:
        db: Session de base de données
        search_id: ID de la recherche
        
    Returns:
        L'objet SearchQuery ou None si non trouvé
    """
    return db.query(models.SearchQuery).filter(models.SearchQuery.id == search_id).first()


def get_search_queries(db: Session, skip: int = 0, limit: int = 100) -> List[models.SearchQuery]:
    """
    Récupère la liste des recherches effectuées
    
    Args:
        db: Session de base de données
        skip: Nombre d'entrées à ignorer (pour la pagination)
        limit: Nombre maximum d'entrées à retourner
        
    Returns:
        Liste des objets SearchQuery
    """
    return db.query(models.SearchQuery).order_by(
        models.SearchQuery.created_at.desc()
    ).offset(skip).limit(limit).all()


def create_location(
    db: Session, 
    location: Location, 
    search_id: int
) -> models.LocationDB:
    """
    Crée une nouvelle entrée d'emplacement dans la base de données
    
    Args:
        db: Session de base de données
        location: Objet Location à enregistrer
        search_id: ID de la recherche associée
        
    Returns:
        L'objet LocationDB créé
    """
    db_location = models.LocationDB(
        id=location.id,
        search_id=search_id,
        address=location.address,
        latitude=location.coordinates.latitude,
        longitude=location.coordinates.longitude,
        population_10min=location.population_10min,
        nearest_competitor_distance=location.nearest_competitor_distance,
        density_index=location.density_index,
        total_score=location.total_score,
        details=json.dumps(location.details)
    )
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    
    # Créer les entrées pour les concurrents
    for competitor in location.competitors_within_radius:
        create_competitor(db, competitor, db_location.id)
    
    return db_location


def get_location(db: Session, location_id: str) -> Optional[models.LocationDB]:
    """
    Récupère un emplacement par son ID
    
    Args:
        db: Session de base de données
        location_id: ID de l'emplacement
        
    Returns:
        L'objet LocationDB ou None si non trouvé
    """
    return db.query(models.LocationDB).filter(models.LocationDB.id == location_id).first()


def get_locations_by_search(db: Session, search_id: int) -> List[models.LocationDB]:
    """
    Récupère tous les emplacements pour une recherche donnée
    
    Args:
        db: Session de base de données
        search_id: ID de la recherche
        
    Returns:
        Liste des objets LocationDB
    """
    return db.query(models.LocationDB).filter(
        models.LocationDB.search_id == search_id
    ).order_by(models.LocationDB.total_score.desc()).all()


def create_competitor(
    db: Session, 
    competitor: Competitor, 
    location_id: str
) -> models.CompetitorDB:
    """
    Crée une nouvelle entrée de concurrent dans la base de données
    
    Args:
        db: Session de base de données
        competitor: Objet Competitor à enregistrer
        location_id: ID de l'emplacement associé
        
    Returns:
        L'objet CompetitorDB créé
    """
    db_competitor = models.CompetitorDB(
        location_id=location_id,
        name=competitor.name,
        address=competitor.address,
        latitude=competitor.coordinates.latitude,
        longitude=competitor.coordinates.longitude,
        distance=competitor.distance,
        place_id=competitor.place_id
    )
    db.add(db_competitor)
    db.commit()
    db.refresh(db_competitor)
    return db_competitor


def get_competitors_by_location(db: Session, location_id: str) -> List[models.CompetitorDB]:
    """
    Récupère tous les concurrents pour un emplacement donné
    
    Args:
        db: Session de base de données
        location_id: ID de l'emplacement
        
    Returns:
        Liste des objets CompetitorDB
    """
    return db.query(models.CompetitorDB).filter(
        models.CompetitorDB.location_id == location_id
    ).order_by(models.CompetitorDB.distance).all()


def create_cache_entry(
    db: Session, 
    key: str, 
    value: Any, 
    expiration: int = 86400
) -> models.CacheEntryDB:
    """
    Crée ou met à jour une entrée dans le cache
    
    Args:
        db: Session de base de données
        key: Clé unique pour l'entrée
        value: Valeur à mettre en cache
        expiration: Durée de validité en secondes (par défaut 24h)
        
    Returns:
        L'objet CacheEntryDB créé ou mis à jour
    """
    # Vérifier si la clé existe déjà
    db_cache = db.query(models.CacheEntryDB).filter(models.CacheEntryDB.key == key).first()
    
    # Calculer la date d'expiration
    expires_at = datetime.now() + timedelta(seconds=expiration)
    
    if db_cache:
        # Mettre à jour l'entrée existante
        db_cache.value = json.dumps(value)
        db_cache.created_at = datetime.now()
        db_cache.expires_at = expires_at
    else:
        # Créer une nouvelle entrée
        db_cache = models.CacheEntryDB(
            key=key,
            value=json.dumps(value),
            expires_at=expires_at
        )
        db.add(db_cache)
    
    db.commit()
    db.refresh(db_cache)
    return db_cache


def get_cache_entry(db: Session, key: str) -> Optional[models.CacheEntryDB]:
    """
    Récupère une entrée du cache par sa clé
    
    Args:
        db: Session de base de données
        key: Clé unique de l'entrée
        
    Returns:
        L'objet CacheEntryDB ou None si non trouvé ou expiré
    """
    db_cache = db.query(models.CacheEntryDB).filter(models.CacheEntryDB.key == key).first()
    
    if db_cache and not db_cache.is_expired():
        return db_cache
    
    # Supprimer l'entrée si elle est expirée
    if db_cache and db_cache.is_expired():
        db.delete(db_cache)
        db.commit()
    
    return None


def clean_expired_cache(db: Session) -> int:
    """
    Supprime toutes les entrées de cache expirées
    
    Args:
        db: Session de base de données
        
    Returns:
        Nombre d'entrées supprimées
    """
    now = datetime.now()
    expired = db.query(models.CacheEntryDB).filter(models.CacheEntryDB.expires_at < now).all()
    count = len(expired)
    
    for entry in expired:
        db.delete(entry)
    
    db.commit()
    return count


def convert_db_location_to_model(
    db_location: models.LocationDB, 
    db_competitors: List[models.CompetitorDB] = None
) -> Location:
    """
    Convertit un objet LocationDB en objet Location du modèle de domaine
    
    Args:
        db_location: Objet LocationDB à convertir
        db_competitors: Liste optionnelle des concurrents (évite une requête supplémentaire)
        
    Returns:
        Objet Location
    """
    from app.core.models import Coordinates
    
    if db_competitors is None:
        # Récupérer les concurrents depuis la base de données
        db_competitors = []  # À remplacer par une requête
    
    # Convertir les concurrents
    competitors = []
    nearest = None
    for db_comp in db_competitors:
        comp = Competitor(
            name=db_comp.name,
            address=db_comp.address,
            coordinates=Coordinates(
                latitude=db_comp.latitude,
                longitude=db_comp.longitude
            ),
            distance=db_comp.distance,
            place_id=db_comp.place_id
        )
        competitors.append(comp)
        
        # Trouver le concurrent le plus proche
        if nearest is None or comp.distance < nearest.distance:
            nearest = comp
    
    # Créer et retourner l'objet Location
    location = Location(
        id=db_location.id,
        address=db_location.address,
        coordinates=Coordinates(
            latitude=db_location.latitude,
            longitude=db_location.longitude
        ),
        population_10min=db_location.population_10min,
        nearest_competitor_distance=db_location.nearest_competitor_distance,
        nearest_competitor=nearest,
        density_index=db_location.density_index,
        total_score=db_location.total_score,
        details=json.loads(db_location.details),
        competitors_within_radius=competitors
    )
    
    return location


def convert_search_query_to_parameters(db_query: models.SearchQuery) -> SearchParameters:
    """
    Convertit un objet SearchQuery en objet SearchParameters
    
    Args:
        db_query: Objet SearchQuery à convertir
        
    Returns:
        Objet SearchParameters
    """
    params = json.loads(db_query.params)
    return SearchParameters(
        city_or_postal_code=db_query.query,
        radius=params.get("radius", 10000),
        walking_time=params.get("walking_time", 10),
        competitor_keywords=params.get("competitor_keywords", ["laverie", "laundromat", "pressing"])
    )


def load_search_results(db: Session, search_id: int) -> Optional[SearchResults]:
    """
    Charge les résultats d'une recherche complète
    
    Args:
        db: Session de base de données
        search_id: ID de la recherche
        
    Returns:
        Objet SearchResults ou None si la recherche n'existe pas
    """
    # Récupérer la recherche
    db_query = get_search_query(db, search_id)
    if not db_query:
        return None
    
    # Convertir en paramètres de recherche
    search_params = convert_search_query_to_parameters(db_query)
    
    # Récupérer les emplacements
    db_locations = get_locations_by_search(db, search_id)
    
    # Convertir chaque emplacement
    locations = []
    for db_location in db_locations:
        db_competitors = get_competitors_by_location(db, db_location.id)
        location = convert_db_location_to_model(db_location, db_competitors)
        locations.append(location)
    
    # Créer et retourner les résultats de recherche
    return SearchResults(
        search_params=search_params,
        locations=locations,
        timestamp=db_query.created_at,
        total_count=len(locations)
    )
