# Module de génération de lettres de motivation
from .huggingface_api import generer_lettre_motivation, tester_connexion
from .generator import creer_lettre_motivation, formater_lettre_pour_telegram, get_info_cv

__all__ = [
    'generer_lettre_motivation',
    'tester_connexion',
    'creer_lettre_motivation',
    'formater_lettre_pour_telegram',
    'get_info_cv',
]
