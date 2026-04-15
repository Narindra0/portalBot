"""
Module de génération de lettres de motivation.
Coordonne le CV utilisateur avec l'API Hugging Face.
"""
from ..storage import recuperer_cv, cv_existe
from .huggingface_api import generer_lettre_motivation


def creer_lettre_motivation(offre_data):
    """
    Crée une lettre de motivation personnalisée pour une offre.

    Args:
        offre_data: Dictionnaire avec les données de l'offre

    Returns:
        tuple: (success: bool, result: str) - result est la lettre ou un message d'erreur
    """
    # Vérifier que le CV existe
    if not cv_existe():
        return False, "❌ CV non configuré.\n\nConfigure d'abord ton CV avec la commande `/configurer_cv` sur Telegram."

    cv = recuperer_cv()
    cv_text = cv['cv_text']

    # Extraire les données de l'offre
    titre = offre_data.get('titre', 'Poste non spécifié')
    entreprise = offre_data.get('entreprise', 'Entreprise non spécifiée')
    details = offre_data.get('details', '')

    print(f"📝 Génération LM pour: {titre} @ {entreprise}")

    # Appeler l'API Hugging Face
    lettre = generer_lettre_motivation(cv_text, titre, entreprise, details)

    if lettre:
        return True, lettre
    else:
        return False, "❌ Échec de la génération.\nVérifie ta clé HF_API_KEY dans le fichier .env"


def formater_lettre_pour_telegram(lettre):
    """
    Formate une lettre de motivation pour l'affichage Telegram.
    Découpe en plusieurs messages si trop long.
    """
    # Limiter à 4000 caractères par message (limite Telegram)
    MAX_LENGTH = 3800

    if len(lettre) <= MAX_LENGTH:
        return [lettre]

    # Découper en plusieurs parties
    parts = []
    current = ""

    for line in lettre.split('\n'):
        if len(current) + len(line) + 1 > MAX_LENGTH:
            parts.append(current)
            current = line + '\n'
        else:
            current += line + '\n'

    if current:
        parts.append(current)

    return parts


def get_info_cv():
    """Retourne les infos du CV pour vérification."""
    if not cv_existe():
        return None

    cv = recuperer_cv()
    return {
        'nom': cv['nom'],
        'email': cv['email'],
        'telephone': cv['telephone'],
        'date_mise_a_jour': cv['date_mise_a_jour'],
        'longueur_cv': len(cv['cv_text'])
    }


if __name__ == "__main__":
    # Test
    if cv_existe():
        info = get_info_cv()
        print(f"✅ CV configuré: {info['nom']}")
        print(f"   Email: {info['email']}")
        print(f"   Longueur: {info['longueur_cv']} caractères")
        print(f"   Dernière MAJ: {info['date_mise_a_jour']}")
    else:
        print("❌ Aucun CV configuré")
        print("   Utilise la commande `/configurer_cv` sur Telegram pour configurer ton CV.")
