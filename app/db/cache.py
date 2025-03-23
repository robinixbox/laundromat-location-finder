"""
Système de cache pour les appels API
"""
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union, TypeVar, cast

from sqlalchemy.orm import Session

from app.core.models import CacheKey
from app.db.crud import create_cache_entry, get_cache_entry, clean_expired_cache
from app.core.config import settings

# Type générique pour le retour de la fonction
T = TypeVar('T')


def get_or_create_cache(
    db: Session,
    service: str,
    query: str,
    params: Dict[str, Any] = None,
    creator_func: Callable[[], T] = None,
    expiration: int = None
) -> Optional[T]:
    """
    Récupère une valeur depuis le cache ou la crée si elle n'existe pas
    
    Args:
        db: Session de base de données
        service: Nom du service (par exemple 'google_maps')
        query: Requête ou identifiant
        params: Paramètres supplémentaires
        creator_func: Fonction de création si la valeur n'est pas en cache
        expiration: Durée de validité en secondes (utilise la valeur par défaut si None)
        
    Returns:
        La valeur mise en cache ou None si elle n'existe pas et qu'aucune fonction
        de création n'a été fournie
    """
    if params is None:
        params = {}
    
    cache_key = CacheKey(service=service, query=query, params=params)
    key = cache_key.get_key()
    
    # Nettoyer les entrées expirées occasionnellement (1% de chance)
    import random
    if random.random() < 0.01:
        clean_expired_cache(db)
    
    # Vérifier si l'entrée existe dans le cache
    cache_entry = get_cache_entry(db, key)
    if cache_entry:
        return cast(T, cache_entry.get_value())
    
    # Si la valeur n'existe pas et qu'une fonction de création est fournie
    if creator_func:
        value = creator_func()
        expiration_time = expiration or settings.CACHE_EXPIRATION
        create_cache_entry(db, key, value, expiration_time)
        return value
    
    return None


def cache_response(
    service: str, 
    expiration: int = None,
    key_func: Callable = None
):
    """
    Décorateur pour mettre en cache les réponses des fonctions
    
    Args:
        service: Nom du service
        expiration: Durée de validité en secondes
        key_func: Fonction optionnelle pour générer la clé de cache
        
    Returns:
        Décorateur
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extraire la session de base de données
            db = next((arg for arg in args if isinstance(arg, Session)), None)
            if not db:
                # Chercher dans les kwargs
                db = kwargs.get('db')
            
            if not db:
                # Si aucune session n'est trouvée, exécuter la fonction sans cache
                return func(*args, **kwargs)
            
            # Générer la clé de cache
            if key_func:
                query, params = key_func(*args, **kwargs)
            else:
                # Utiliser les arguments comme clé par défaut
                func_args = {f"arg_{i}": arg for i, arg in enumerate(args) if not isinstance(arg, Session)}
                query = f"{func.__name__}"
                params = {**func_args, **kwargs}
            
            # Utiliser le système de cache
            return get_or_create_cache(
                db=db,
                service=service,
                query=query,
                params=params,
                creator_func=lambda: func(*args, **kwargs),
                expiration=expiration
            )
        
        return wrapper
    
    return decorator
