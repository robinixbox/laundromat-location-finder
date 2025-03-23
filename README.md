# Laundromat Location Finder

Application intelligente pour identifier des emplacements optimaux pour l'implantation de laveries automatiques.

## 🎯 Objectif

Ce logiciel identifie et classe les adresses idéales pour l'implantation de laveries automatiques en fonction de critères spécifiques :

1. **Population accessible** : Densité de population dans un rayon de 10 minutes à pied
2. **Absence de concurrence** : Aucune laverie existante dans ce même rayon
3. **Densité résidentielle** : Priorité aux zones à forte présence d'immeubles et de logements collectifs

## 🛠️ Fonctionnalités

- Recherche par ville ou code postal
- Analyse multicritère des emplacements potentiels
- Visualisation cartographique des résultats
- Génération de rapports détaillés
- Système de cache pour optimiser les appels API

## 🧰 Technologies utilisées

- **FastAPI** : API backend rapide et moderne
- **Streamlit** : Interface utilisateur interactive
- **SQLite** : Stockage local des données
- **Folium** : Visualisation cartographique
- **Google Maps API** : Identification des concurrents
- **Smappen API** (simulée) : Données de population accessible
- **Géoportail/INSEE** : Données de densité résidentielle

## 🚀 Installation

```bash
# Cloner le dépôt
git clone https://github.com/robinixbox/laundromat-location-finder.git
cd laundromat-location-finder

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer le fichier .env avec vos clés API

# Lancer l'application Streamlit
cd app/ui
streamlit run streamlit_app.py
```

## 🔧 Configuration

Créez un fichier `.env` à la racine du projet avec les configurations suivantes :

```
# API Keys
GOOGLE_MAPS_API_KEY=votre_clé_api_google_maps
GEOPORTAIL_API_KEY=votre_clé_api_geoportail

# Configuration de base de données
DATABASE_URL=sqlite:///./data/laundromat_finder.db

# Autres configurations
DEBUG=True
```

## 📊 Utilisation

1. Lancez l'application Streamlit
2. Entrez une ville ou un code postal dans le champ de recherche
3. Consultez les résultats classés par score d'intérêt
4. Explorez la visualisation cartographique
5. Générez un rapport PDF des meilleurs emplacements

## 📝 License

MIT
