# Module de stockage et cache
from .cache_db import (
    # Cache temporaire (pour Telegram)
    ajouter_offre_async,
    recuperer_offre_async,
    nettoyer_vieilles_offres_async,
    vider_cache,
    # CV
    sauvegarder_cv_async,
    recuperer_cv_async,
    init_db_async,
    # Profil matching
    sauvegarder_profil_matching_async,
    recuperer_profil_matching_async,
    # Stockage permanent des offres
    sauvegarder_offre_permanente_async,
    offre_existe_async,
    compter_offres_async,
    # Wrappers synchros (pour compatibilité si besoin)
    ajouter_offre,
    recuperer_offre,
    sauvegarder_cv,
    recuperer_cv,
    sauvegarder_profil_matching,
    recuperer_profil_matching,
    offre_existe,
    sauvegarder_offre_permanente,
    compter_offres,
)
from .pdf_extractor import traiter_fichier_cv

__all__ = [
    'ajouter_offre_async',
    'recuperer_offre_async',
    'nettoyer_vieilles_offres_async',
    'vider_cache',
    'sauvegarder_cv_async',
    'recuperer_cv_async',
    'sauvegarder_profil_matching_async',
    'recuperer_profil_matching_async',
    'init_db_async',
    'sauvegarder_offre_permanente_async',
    'offre_existe_async',
    'compter_offres_async',
    'ajouter_offre',
    'recuperer_offre',
    'sauvegarder_cv',
    'recuperer_cv',
    'sauvegarder_profil_matching',
    'recuperer_profil_matching',
    'offre_existe',
    'sauvegarder_offre_permanente',
    'compter_offres',
    'traiter_fichier_cv',
]
