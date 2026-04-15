# Module de stockage et cache
from .cache_db import (
    # Cache temporaire (pour Telegram)
    ajouter_offre,
    recuperer_offre,
    nettoyer_vieilles_offres,
    vider_cache,
    # CV
    sauvegarder_cv,
    recuperer_cv,
    cv_existe,
    init_db,
    init_cv_table,
    # Stockage permanent des offres (remplace JSON)
    sauvegarder_offre_permanente,
    charger_toutes_offres,
    offre_existe,
    compter_offres,
    exporter_vers_json,
    importer_depuis_json,
)
from .pdf_extractor import traiter_fichier_cv

__all__ = [
    # Cache temporaire
    'ajouter_offre',
    'recuperer_offre',
    'nettoyer_vieilles_offres',
    'vider_cache',
    # CV
    'sauvegarder_cv',
    'recuperer_cv',
    'cv_existe',
    'init_db',
    'init_cv_table',
    # Stockage permanent
    'sauvegarder_offre_permanente',
    'charger_toutes_offres',
    'offre_existe',
    'compter_offres',
    'exporter_vers_json',
    'importer_depuis_json',
    # PDF
    'traiter_fichier_cv',
]
