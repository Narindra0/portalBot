# Module de génération de lettres de motivation
from .huggingface_api import generer_lettre_motivation, generer_lettre_motivation_async
from .generator import creer_lettre_motivation, formater_lettre_pour_telegram

__all__ = [
    'generer_lettre_motivation',
    'generer_lettre_motivation_async',
    'creer_lettre_motivation',
    'formater_lettre_pour_telegram',
]
