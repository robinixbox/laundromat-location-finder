"""
Routes pour l'API FastAPI
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Body
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_api_key, get_db_session
from app.core.config import settings
from app.core.models import SearchParameters, Location, Coordinates
from app.core.schemas import (
    LocationRequest, LocationResponse, SearchResultsResponse, 
    LocationDetailResponse, ReportRequest, ErrorResponse
)
from app.db import crud
from app.services.google_maps_service import google_maps_service
from app.services.smappen_service import smappen_service
from app.services.geoportail_service import geoportail_service
from app.services.scoring_service import scoring_service
from app.services.report_service import report_service

logger = logging.getLogger(__name__)

# Création du routeur
router = APIRouter(prefix="/api/v1", tags=["Laveries"])


@router.get("/", response_class=HTMLResponse)
async def root():
    """Page d'accueil de l'API"""
    return """
    <html>
        <head>
            <title>Laundromat Location Finder API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #2c3e50; }
                code { background: #f8f9fa; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>Laundromat Location Finder API</h1>
            <p>Bienvenue sur l'API de recherche d'emplacements optimaux pour les laveries automatiques.</p>
            <h2>Endpoints disponibles:</h2>
            <ul>
                <li><code>GET /api/v1/locations/search</code> - Recherche d'emplacements par ville ou code postal</li>
                <li><code>GET /api/v1/locations/{location_id}</code> - Détails d'un emplacement spécifique</li>
                <li><code>GET /api/v1/searches</code> - Liste des recherches précédentes</li>
                <li><code>GET /api/v1/searches/{search_id}</code> - Résultats d'une recherche spécifique</li>
                <li><code>GET /api/v1/reports/{search_id}</code> - Génération de rapports PDF</li>
            </ul>
            <p>Pour plus d'informations, consultez la documentation complète.</p>
        </body>
    </html>
    """


@router.get("/health")
async def health_check():
    """Vérifie l'état de santé de l'API"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": settings.APP_VERSION
    }


@router.get(
    "/locations/search",
    response_model=SearchResultsResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def search_locations(
    city_or_postal_code: str = Query(..., description="Ville ou code postal"),
    radius_km: float = Query(10.0, description="Rayon de recherche en km"),
    walking_time_min: int = Query(10, description="Temps de marche en minutes"),
    db: Session = Depends(get_db_session),
    api_key: str = Depends(get_api_key)
):
    """
    Recherche des emplacements optimaux pour une laverie automatique dans une ville ou un code postal.
    
    Args:
        city_or_postal_code: Ville ou code postal à analyser
        radius_km: Rayon de recherche en kilomètres
        walking_time_min: Temps de marche en minutes pour calculer la population accessible
        db: Session de base de données
        api_key: Clé API
        
    Returns:
        Liste des emplacements optimaux avec leurs scores et caractéristiques
    """
    try:
        # Convertir les paramètres
        search_params = SearchParameters(
            city_or_postal_code=city_or_postal_code,
            radius=int(radius_km * 1000),  # Convertir en mètres
            walking_time=walking_time_min,
            competitor_keywords=settings.COMPETITOR_KEYWORDS
        )
        
        # Effectuer la recherche
        results = scoring_service.search_optimal_locations(db, search_params)
        
        # Sauvegarder les résultats
        search_id = scoring_service.save_search_results(db, results)
        
        # Préparer la réponse
        locations_response = [
            LocationResponse.from_location(location)
            for location in results.locations
        ]
        
        return SearchResultsResponse(
            query=city_or_postal_code,
            timestamp=results.timestamp,
            total_results=results.total_count,
            locations=locations_response
        )
    
    except Exception as e:
        logger.exception("Erreur lors de la recherche d'emplacements")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche d'emplacements: {str(e)}"
        )


@router.get(
    "/locations/{location_id}",
    response_model=LocationDetailResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def get_location_details(
    location_id: str,
    db: Session = Depends(get_db_session),
    api_key: str = Depends(get_api_key)
):
    """
    Récupère les détails d'un emplacement spécifique
    
    Args:
        location_id: ID de l'emplacement
        db: Session de base de données
        api_key: Clé API
        
    Returns:
        Détails de l'emplacement
    """
    try:
        # Récupérer l'emplacement depuis la base de données
        db_location = crud.get_location(db, location_id)
        if not db_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emplacement non trouvé: {location_id}"
            )
        
        # Récupérer les concurrents
        db_competitors = crud.get_competitors_by_location(db, location_id)
        
        # Convertir en modèle de domaine
        location = crud.convert_db_location_to_model(db_location, db_competitors)
        
        # Retourner la réponse détaillée
        return LocationDetailResponse.from_location(location)
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des détails de l'emplacement {location_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur: {str(e)}"
        )


@router.get(
    "/searches",
    responses={
        500: {"model": ErrorResponse}
    }
)
async def get_searches(
    skip: int = Query(0, ge=0, description="Nombre d'entrées à ignorer"),
    limit: int = Query(10, ge=1, le=100, description="Nombre d'entrées à retourner"),
    db: Session = Depends(get_db_session),
    api_key: str = Depends(get_api_key)
):
    """
    Récupère la liste des recherches précédentes
    
    Args:
        skip: Nombre d'entrées à ignorer (pagination)
        limit: Nombre d'entrées à retourner (pagination)
        db: Session de base de données
        api_key: Clé API
        
    Returns:
        Liste des recherches
    """
    try:
        # Récupérer les recherches
        searches = crud.get_search_queries(db, skip, limit)
        
        # Convertir en dictionnaires
        return {
            "total": len(searches),
            "searches": [search.to_dict() for search in searches]
        }
    
    except Exception as e:
        logger.exception("Erreur lors de la récupération des recherches")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur: {str(e)}"
        )


@router.get(
    "/searches/{search_id}",
    response_model=SearchResultsResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def get_search_results(
    search_id: int,
    db: Session = Depends(get_db_session),
    api_key: str = Depends(get_api_key)
):
    """
    Récupère les résultats d'une recherche spécifique
    
    Args:
        search_id: ID de la recherche
        db: Session de base de données
        api_key: Clé API
        
    Returns:
        Résultats de la recherche
    """
    try:
        # Récupérer la recherche
        results = crud.load_search_results(db, search_id)
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recherche non trouvée: {search_id}"
            )
        
        # Préparer la réponse
        locations_response = [
            LocationResponse.from_location(location)
            for location in results.locations
        ]
        
        return SearchResultsResponse(
            query=results.search_params.city_or_postal_code,
            timestamp=results.timestamp,
            total_results=results.total_count,
            locations=locations_response
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des résultats de la recherche {search_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur: {str(e)}"
        )


@router.post(
    "/reports/{search_id}",
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def generate_report(
    search_id: int,
    report_config: ReportRequest = Body(...),
    db: Session = Depends(get_db_session),
    api_key: str = Depends(get_api_key)
):
    """
    Génère un rapport PDF pour une recherche spécifique
    
    Args:
        search_id: ID de la recherche
        report_config: Configuration du rapport
        db: Session de base de données
        api_key: Clé API
        
    Returns:
        Rapport PDF
    """
    try:
        # Vérifier si la recherche existe
        db_query = crud.get_search_query(db, search_id)
        if not db_query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recherche non trouvée: {search_id}"
            )
        
        # Générer le rapport
        from app.core.models import ReportConfig as ModelReportConfig
        config = ModelReportConfig(
            title=report_config.title or f"Rapport d'analyse - {db_query.query}",
            include_map=report_config.include_map,
            max_locations=report_config.max_locations,
            include_details=report_config.include_details
        )
        
        pdf_buffer = report_service.generate_pdf_report(db, search_id, config)
        
        # Retourner le PDF
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=rapport_{search_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
            }
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Erreur lors de la génération du rapport pour la recherche {search_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur: {str(e)}"
        )
