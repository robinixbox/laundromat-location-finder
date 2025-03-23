"""
Point d'entrée principal pour l'application FastAPI
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router as api_router
from app.core.config import settings
from app.db.database import engine, Base

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Contexte de vie de l'application
    Initialise la base de données et effectue les opérations de démarrage
    """
    # Créer les tables dans la base de données si elles n'existent pas
    logger.info("Initialisation de la base de données...")
    Base.metadata.create_all(bind=engine)
    
    # Vérifier la connexion à la base de données
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Connexion à la base de données établie avec succès")
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {e}")
    finally:
        db.close()
    
    # Log de démarrage
    logger.info(f"Démarrage de l'application {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    # Opérations de nettoyage au shutdown
    logger.info("Arrêt de l'application...")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="API pour identifier les emplacements optimaux pour l'implantation de laveries automatiques",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Configuration des CORS pour permettre les requêtes cross-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autoriser toutes les origines pour le développement
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Gestionnaire d'erreurs global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'exceptions global"""
    logger.exception("Exception non gérée")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Erreur interne du serveur: {str(exc)}",
            "status_code": 500,
            "timestamp": str
        }
    )


# Inclure les routes de l'API
app.include_router(api_router)


@app.get("/")
async def root():
    """Redirection vers l'API"""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "message": "Bienvenue sur l'API de recherche d'emplacements pour laveries",
        "docs_url": "/docs",
        "api_url": "/api/v1"
    }


if __name__ == "__main__":
    # Lancement direct pour le développement
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
