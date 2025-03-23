"""
Dépendances pour les routes API
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.config import settings


async def get_api_key(api_key: str = None):
    """
    Vérifie si la clé API fournie est valide.
    Simple implémentation pour démonstration.
    
    Args:
        api_key: Clé API facultative
        
    Returns:
        La clé API si elle est valide
        
    Raises:
        HTTPException: Si la clé API est invalide
    """
    # Si on est en mode debug, ne pas vérifier la clé API
    if settings.DEBUG:
        return api_key or "debug_key"
    
    # Vérifier si une clé API est fournie
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Vérifier si la clé API est valide (à implémenter)
    # Pour l'instant, accepter n'importe quelle clé pour la démonstration
    return api_key


def get_db_session():
    """Dépendance pour obtenir une session de base de données"""
    return next(get_db())
