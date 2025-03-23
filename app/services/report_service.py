"""
Service pour la génération de rapports PDF et exportations
"""
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Any, BinaryIO

import matplotlib.pyplot as plt
import folium
from folium.plugins import MarkerCluster
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Location, SearchParameters, SearchResults, ReportConfig
from app.db import crud

logger = logging.getLogger(__name__)


class ReportService:
    """Service pour la génération de rapports et d'exportations"""
    
    def __init__(self):
        """Initialisation du service"""
        pass
    
    def generate_map_html(self, results: SearchResults) -> str:
        """
        Génère une carte HTML avec les emplacements et les concurrents
        
        Args:
            results: Résultats de recherche
            
        Returns:
            HTML de la carte Folium
        """
        # Déterminer le centre de la carte (premier emplacement ou centre de la ville)
        if results.locations:
            # Utiliser le meilleur emplacement comme centre
            center_location = results.locations[0].coordinates
            center = [center_location.latitude, center_location.longitude]
            zoom = 13
        else:
            # Coordonnées par défaut (France)
            center = [settings.MAP_CENTER_LAT, settings.MAP_CENTER_LON]
            zoom = settings.MAP_DEFAULT_ZOOM
        
        # Créer la carte
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles="OpenStreetMap"
        )
        
        # Ajouter les marqueurs pour les emplacements potentiels
        locations_group = MarkerCluster(name="Emplacements potentiels")
        
        for i, location in enumerate(results.locations):
            # Créer le popup avec les informations clés
            popup_text = f"""
            <div style="width: 250px;">
                <h4>Emplacement #{i+1}</h4>
                <p><b>Adresse:</b> {location.address}</p>
                <p><b>Score:</b> {location.total_score:.2f}</p>
                <p><b>Population à 10min:</b> {location.population_10min}</p>
                <p><b>Distance au concurrent le plus proche:</b> {location.nearest_competitor_distance:.0f}m</p>
                <p><b>Indice de densité:</b> {location.density_index:.0f}</p>
            </div>
            """
            
            # Déterminer la couleur en fonction du score
            if location.total_score >= 0.8:
                color = "green"
            elif location.total_score >= 0.6:
                color = "blue"
            elif location.total_score >= 0.4:
                color = "orange"
            else:
                color = "red"
            
            # Ajouter le marqueur
            folium.Marker(
                [location.coordinates.latitude, location.coordinates.longitude],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"Emplacement #{i+1} (Score: {location.total_score:.2f})",
                icon=folium.Icon(color=color, icon="home", prefix="fa")
            ).add_to(locations_group)
            
            # Ajouter les concurrents pour cet emplacement
            for j, competitor in enumerate(location.competitors_within_radius):
                popup_comp = f"""
                <div style="width: 200px;">
                    <h5>{competitor.name}</h5>
                    <p><b>Adresse:</b> {competitor.address}</p>
                    <p><b>Distance:</b> {competitor.distance:.0f}m</p>
                </div>
                """
                
                # Ajouter le marqueur du concurrent
                folium.Marker(
                    [competitor.coordinates.latitude, competitor.coordinates.longitude],
                    popup=folium.Popup(popup_comp, max_width=250),
                    tooltip=f"{competitor.name}",
                    icon=folium.Icon(color="red", icon="tint", prefix="fa")
                ).add_to(m)
        
        # Ajouter le groupe de marqueurs à la carte
        locations_group.add_to(m)
        
        # Ajouter une légende
        legend_html = """
        <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
            <h4>Légende</h4>
            <div><i class="fa fa-home" style="color: green;"></i> Excellent (>0.8)</div>
            <div><i class="fa fa-home" style="color: blue;"></i> Bon (>0.6)</div>
            <div><i class="fa fa-home" style="color: orange;"></i> Moyen (>0.4)</div>
            <div><i class="fa fa-home" style="color: red;"></i> Faible (<0.4)</div>
            <div><i class="fa fa-tint" style="color: red;"></i> Concurrent</div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Ajouter le contrôle de couches
        folium.LayerControl().add_to(m)
        
        # Retourner le HTML
        map_html = m._repr_html_()
        return map_html
    
    def generate_chart_image(self, locations: List[Location], title: str) -> BytesIO:
        """
        Génère une image de graphique comparant les scores des emplacements
        
        Args:
            locations: Liste des emplacements
            title: Titre du graphique
            
        Returns:
            Image du graphique au format PNG (BytesIO)
        """
        # Limiter à 10 emplacements pour la lisibilité
        top_locations = locations[:10]
        
        # Créer la figure
        plt.figure(figsize=(10, 6))
        
        # Données pour le graphique
        labels = [f"#{i+1}" for i in range(len(top_locations))]
        population_scores = [min(1.0, loc.population_10min / 10000) for loc in top_locations]
        competition_scores = [min(1.0, loc.nearest_competitor_distance / 1000) if loc.nearest_competitor_distance != float('inf') else 1.0 for loc in top_locations]
        density_scores = [min(1.0, loc.density_index / 5000) for loc in top_locations]
        total_scores = [loc.total_score for loc in top_locations]
        
        # Créer le graphique en barres empilées
        width = 0.6
        plt.bar(labels, population_scores, width, label='Population', color='#3274A1')
        plt.bar(labels, competition_scores, width, bottom=population_scores, label='Absence concurrence', color='#E1812C')
        
        # Calculer la somme des deux premières barres pour positionner la troisième
        sum_heights = [p + c for p, c in zip(population_scores, competition_scores)]
        plt.bar(labels, density_scores, width, bottom=sum_heights, label='Densité résidentielle', color='#3A923A')
        
        # Ajouter une ligne pour le score total
        plt.plot(labels, total_scores, 'ro-', linewidth=2, label='Score total')
        
        # Ajouter les titres et légendes
        plt.title(title)
        plt.xlabel('Emplacements')
        plt.ylabel('Score (0-1)')
        plt.ylim(0, 2.0)  # Maximum est 3.0 car les 3 composantes sont empilées
        plt.legend(loc='upper right')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Enregistrer l'image dans un buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
    
    def generate_pdf_report(
        self, 
        db: Session,
        search_id: int,
        config: ReportConfig = None
    ) -> BytesIO:
        """
        Génère un rapport PDF pour les résultats d'une recherche
        
        Args:
            db: Session de base de données
            search_id: ID de la recherche
            config: Configuration du rapport (optionnelle)
            
        Returns:
            Rapport PDF (BytesIO)
        """
        # Charger les résultats de la recherche
        results = crud.load_search_results(db, search_id)
        if not results:
            logger.error(f"Recherche non trouvée: {search_id}")
            return BytesIO()
        
        # Configuration par défaut si non fournie
        if config is None:
            config = ReportConfig(
                title=f"Analyse des emplacements pour laveries - {results.search_params.city_or_postal_code}",
                include_map=True,
                max_locations=10,
                include_details=True
            )
        
        # Limiter le nombre d'emplacements
        locations = results.locations[:config.max_locations]
        
        # Créer le document PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Contenu du document
        content = []
        
        # Titre et introduction
        content.append(Paragraph(config.title, title_style))
        content.append(Spacer(1, 0.5*cm))
        
        intro_text = f"""
        Ce rapport présente les résultats de l'analyse des emplacements potentiels pour l'implantation
        d'une laverie automatique à {results.search_params.city_or_postal_code}. L'analyse a été réalisée le
        {results.timestamp.strftime('%d/%m/%Y à %H:%M')} et a identifié {len(results.locations)} emplacements
        potentiels.
        """
        content.append(Paragraph(intro_text, normal_style))
        content.append(Spacer(1, 0.5*cm))
        
        # Méthodologie
        content.append(Paragraph("Méthodologie", heading_style))
        methodology_text = """
        L'analyse a été réalisée en utilisant les critères suivants :
        <ul>
            <li><b>Population accessible</b> : Nombre d'habitants à 10 minutes à pied</li>
            <li><b>Absence de concurrence</b> : Distance à la laverie la plus proche</li>
            <li><b>Densité résidentielle</b> : Indice de densité de logements dans la zone</li>
        </ul>
        Chaque emplacement a reçu un score global pondéré sur ces trois critères.
        """
        content.append(Paragraph(methodology_text, normal_style))
        content.append(Spacer(1, 0.5*cm))
        
        # Graphique de comparaison
        content.append(Paragraph("Comparaison des emplacements", heading_style))
        
        if locations:
            chart_buffer = self.generate_chart_image(
                locations, 
                f"Comparaison des {len(locations)} meilleurs emplacements"
            )
            img = Image(chart_buffer, width=450, height=250)
            content.append(img)
        else:
            content.append(Paragraph("Aucun emplacement trouvé pour générer le graphique.", normal_style))
        
        content.append(Spacer(1, 0.5*cm))
        
        # Tableau récapitulatif
        content.append(Paragraph("Résumé des meilleurs emplacements", heading_style))
        
        if locations:
            # Entêtes du tableau
            table_data = [
                ["#", "Adresse", "Population\n(10min)", "Distance\nconcurrent (m)", "Densité", "Score"]
            ]
            
            # Données
            for i, location in enumerate(locations):
                dist_text = f"{location.nearest_competitor_distance:.0f}" if location.nearest_competitor_distance != float('inf') else ">1000"
                
                table_data.append([
                    str(i+1),
                    location.address[:50] + "..." if len(location.address) > 50 else location.address,
                    str(location.population_10min),
                    dist_text,
                    f"{location.density_index:.0f}",
                    f"{location.total_score:.2f}"
                ])
            
            # Créer le tableau
            table = Table(table_data, colWidths=[1*cm, 7*cm, 2.5*cm, 2.5*cm, 2*cm, 2*cm])
            
            # Style du tableau
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ])
            
            # Ajouter des couleurs conditionnelles
            for i, location in enumerate(locations):
                if location.total_score >= 0.8:
                    table_style.add('BACKGROUND', (5, i+1), (5, i+1), colors.lightgreen)
                elif location.total_score >= 0.6:
                    table_style.add('BACKGROUND', (5, i+1), (5, i+1), colors.lightblue)
                elif location.total_score >= 0.4:
                    table_style.add('BACKGROUND', (5, i+1), (5, i+1), colors.orange)
                else:
                    table_style.add('BACKGROUND', (5, i+1), (5, i+1), colors.salmon)
            
            table.setStyle(table_style)
            content.append(table)
        else:
            content.append(Paragraph("Aucun emplacement trouvé pour générer le tableau récapitulatif.", normal_style))
        
        content.append(Spacer(1, 0.5*cm))
        
        # Détails des emplacements
        if config.include_details and locations:
            content.append(Paragraph("Détails des meilleurs emplacements", heading_style))
            
            for i, location in enumerate(locations):
                if i > 0:
                    content.append(Spacer(1, 0.5*cm))
                
                detail_title = f"Emplacement #{i+1} - Score: {location.total_score:.2f}"
                content.append(Paragraph(detail_title, styles['Heading3']))
                
                details_text = f"""
                <b>Adresse :</b> {location.address}<br/>
                <b>Coordonnées :</b> {location.coordinates.latitude:.6f}, {location.coordinates.longitude:.6f}<br/>
                <b>Population à 10min :</b> {location.population_10min} habitants<br/>
                """
                
                if location.nearest_competitor:
                    details_text += f"""
                    <b>Concurrent le plus proche :</b> {location.nearest_competitor.name}<br/>
                    <b>Adresse du concurrent :</b> {location.nearest_competitor.address}<br/>
                    <b>Distance au concurrent :</b> {location.nearest_competitor_distance:.0f} mètres<br/>
                    <b>Nombre de concurrents dans un rayon de {settings.COMPETITOR_SEARCH_RADIUS}m :</b> {len(location.competitors_within_radius)}<br/>
                    """
                else:
                    details_text += f"""
                    <b>Aucun concurrent</b> trouvé dans un rayon de {settings.COMPETITOR_SEARCH_RADIUS} mètres.<br/>
                    """
                
                details_text += f"""
                <b>Indice de densité résidentielle :</b> {location.density_index:.0f}<br/>
                <b>Score de population :</b> {min(1.0, location.population_10min / 10000):.2f}<br/>
                <b>Score de concurrence :</b> {min(1.0, location.nearest_competitor_distance / 1000) if location.nearest_competitor_distance != float('inf') else 1.0:.2f}<br/>
                <b>Score de densité :</b> {min(1.0, location.density_index / 5000):.2f}<br/>
                """
                
                content.append(Paragraph(details_text, normal_style))
                
                # Ajouter une ligne de séparation
                if i < len(locations) - 1:
                    content.append(Spacer(1, 0.2*cm))
                    content.append(Paragraph("_" * 80, normal_style))
        
        # Conclusion
        content.append(Spacer(1, 1*cm))
        content.append(Paragraph("Conclusion", heading_style))
        
        if locations:
            conclusion_text = f"""
            L'analyse a identifié {len(results.locations)} emplacements potentiels pour l'implantation d'une
            laverie automatique à {results.search_params.city_or_postal_code}. Les trois meilleurs emplacements
            présentent des scores supérieurs à {locations[2].total_score:.2f if len(locations) > 2 else 0},
            ce qui indique une bonne adéquation avec les critères recherchés.
            
            Le meilleur emplacement identifié se situe à l'adresse "{locations[0].address if locations else ''}"
            avec un score de {locations[0].total_score:.2f if locations else 0}. Cet emplacement offre un bon
            compromis entre la population accessible, l'absence de concurrence directe et la densité résidentielle.
            """
        else:
            conclusion_text = f"""
            L'analyse n'a pas identifié d'emplacements satisfaisant les critères minimaux pour l'implantation
            d'une laverie automatique à {results.search_params.city_or_postal_code}. Il est recommandé d'élargir
            la zone de recherche ou de reconsidérer les critères d'évaluation.
            """
        
        content.append(Paragraph(conclusion_text, normal_style))
        
        # Pied de page
        footer_text = f"""
        Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        par Laundromat Location Finder v{settings.APP_VERSION}
        """
        content.append(Spacer(1, 1*cm))
        content.append(Paragraph(footer_text, styles['Italic']))
        
        # Générer le PDF
        doc.build(content)
        buffer.seek(0)
        
        return buffer
    
    def export_locations_to_csv(self, results: SearchResults) -> str:
        """
        Exporte les emplacements au format CSV
        
        Args:
            results: Résultats de recherche
            
        Returns:
            Contenu du fichier CSV
        """
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Entêtes
        writer.writerow([
            "ID", "Adresse", "Latitude", "Longitude", 
            "Population (10min)", "Distance concurrent (m)", 
            "Concurrent le plus proche", "Densité", "Score"
        ])
        
        # Données
        for location in results.locations:
            writer.writerow([
                location.id,
                location.address,
                location.coordinates.latitude,
                location.coordinates.longitude,
                location.population_10min,
                f"{location.nearest_competitor_distance:.0f}" if location.nearest_competitor_distance != float('inf') else ">1000",
                location.nearest_competitor.name if location.nearest_competitor else "Aucun",
                f"{location.density_index:.0f}",
                f"{location.total_score:.2f}"
            ])
        
        return output.getvalue()


# Instance globale du service
report_service = ReportService()
