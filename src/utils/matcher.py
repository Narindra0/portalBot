"""
Matcher - Algorithme de scoring offre vs profil sans IA.
Calcule un score 0-100% et génère un résumé explicable.
"""
import re
from typing import Dict, List, Tuple, Optional
from .cv_parser import parser_cv_complet
from .logger import logger

# Configuration des scores (modifiable)
SCORE_CONFIG = {
    'competences': {'points_par_match': 10, 'max': 40},
    'poste': {'match_exact': 25, 'match_partiel': 15},
    'experience': {'adequate': 15, 'trop_junior': -10, 'trop_senior': 0},
    'contrat': {'exclusion': -30, 'bonus_cdi': 5},
    'mots_positifs': {'senior': 5, 'lead': 5, 'expert': 5, 'confirmé': 3, 'max': 10}
}

# Exclusions courantes
EXCLUSIONS_CONTRAT = ['stage', 'stagiaire', 'apprentissage', 'alternance', 'volontariat', 'volunteer']
MOTS_SENIORITE = ['senior', 'sénior', 'lead', 'leader', 'expert', 'confirmé', 'confirmé', 'expérimenté']

def extraire_experience_requise(offre_text: str) -> Optional[int]:
    """Extrait l'expérience requise dans l'offre."""
    patterns = [
        r'(\d+)\+?\s*ans?\s+d\'exp[eé]rience',
        r'exp[eé]rience\s*:?\s*(\d+)\+?\s*ans?',
        r'(\d+)\+?\s*ann[eé]es\s+d\'exp[eé]rience',
        r'(\d+)\+?\s*ans?\s+minimum',
        r'minimum\s+(\d+)\+?\s*ans?',
        r'au\s+moins\s+(\d+)\+?\s*ans?',
    ]

    for pattern in patterns:
        match = re.search(pattern, offre_text.lower())
        if match:
            return int(match.group(1))

    return None

def detecter_type_contrat(offre_text: str) -> Tuple[str, bool]:
    """Détecte le type de contrat et si c'est une exclusion."""
    text_lower = offre_text.lower()

    for exclusion in EXCLUSIONS_CONTRAT:
        if re.search(r'\b' + re.escape(exclusion) + r'\b', text_lower):
            return exclusion, True

    # Cherche le type de contrat
    if re.search(r'\b(cdi)\b', text_lower):
        return 'CDI', False
    elif re.search(r'\b(cdd)\b', text_lower):
        return 'CDD', False
    elif re.search(r'\bfreelance\b', text_lower):
        return 'Freelance', False

    return 'Non précisé', False

def compter_mots_seniorite(offre_text: str) -> int:
    """Compte les mots indiquant une position senior."""
    text_lower = offre_text.lower()
    count = 0
    for mot in MOTS_SENIORITE:
        if re.search(r'\b' + re.escape(mot) + r'\b', text_lower):
            count += 1
    return min(count, 2)  # Max 2 pour le score

def trouver_competences_dans_offre(offre_text: str, competences_cv: List[str]) -> List[str]:
    """Trouve quelles compétences du CV apparaissent dans l'offre."""
    offre_lower = offre_text.lower()
    trouvees = []

    for comp in competences_cv:
        comp_lower = comp.lower()
        # Cherche le mot entier
        pattern = r'\b' + re.escape(comp_lower) + r'\b'
        if re.search(pattern, offre_lower):
            trouvees.append(comp)

    return trouvees

def matcher_poste(titre_offre: str, postes_cv: List[str]) -> Tuple[bool, bool]:
    """Vérifie si le poste correspond à l'historique."""
    titre_lower = titre_offre.lower()

    for poste in postes_cv:
        poste_lower = poste.lower()
        # Match exact
        if re.search(r'\b' + re.escape(poste_lower) + r'\b', titre_lower):
            return True, True  # Match exact
        # Match partiel
        if poste_lower in titre_lower or any(mot in titre_lower for mot in poste_lower.split()):
            return True, False  # Match partiel

    return False, False

def calculer_score_match(profil: Dict, offre: Dict) -> Tuple[int, Dict]:
    """
    Calcule le score de matching entre le profil et l'offre.
    Retourne: (score 0-100, details dict)
    """
    score = 0
    details = {
        'competences_trouvees': [],
        'nb_competences_cv': 0,
        'poste_match_exact': False,
        'poste_match_partiel': False,
        'experience_requise': None,
        'experience_ok': False,
        'type_contrat': 'Non précisé',
        'exclusion_detectee': False,
        'mots_seniorite': 0,
        'details_score': []
    }

    # Texte complet de l'offre pour analyse
    offre_text = f"{offre.get('titre', '')} {offre.get('details', '')}"
    if not offre_text.strip():
        return 0, details

    # 1. Compétences (max 40 points)
    competences_cv = profil.get('competences', [])
    details['nb_competences_cv'] = len(competences_cv)

    if competences_cv:
        competences_trouvees = trouver_competences_dans_offre(offre_text, competences_cv)
        details['competences_trouvees'] = competences_trouvees

        nb_match = len(competences_trouvees)
        points_comp = min(nb_match * SCORE_CONFIG['competences']['points_par_match'],
                         SCORE_CONFIG['competences']['max'])
        score += points_comp
        details['details_score'].append(f"Compétences: {nb_match}/{len(competences_cv)} trouvées = +{points_comp}pts")

    # 2. Poste (25 points pour match exact, 15 pour partiel)
    postes_cv = profil.get('postes', [])
    if postes_cv:
        match_poste, match_exact = matcher_poste(offre.get('titre', ''), postes_cv)
        details['poste_match_exact'] = match_exact
        details['poste_match_partiel'] = match_poste and not match_exact

        if match_exact:
            score += SCORE_CONFIG['poste']['match_exact']
            details['details_score'].append(f"Poste match exact = +{SCORE_CONFIG['poste']['match_exact']}pts")
        elif match_poste:
            score += SCORE_CONFIG['poste']['match_partiel']
            details['details_score'].append(f"Poste match partiel = +{SCORE_CONFIG['poste']['match_partiel']}pts")

    # 3. Expérience (15 points si OK)
    exp_requise = extraire_experience_requise(offre_text)
    details['experience_requise'] = exp_requise
    exp_cv = profil.get('annees_exp', 0)

    if exp_requise and exp_cv:
        if exp_cv >= exp_requise:
            score += SCORE_CONFIG['experience']['adequate']
            details['experience_ok'] = True
            details['details_score'].append(f"Expérience OK ({exp_cv}ans ≥ {exp_requise}ans requis) = +{SCORE_CONFIG['experience']['adequate']}pts")
        elif exp_cv >= exp_requise - 1:  # Tolérance d'1 an
            score += 10
            details['experience_ok'] = True
            details['details_score'].append(f"Expérience presque OK ({exp_cv}ans vs {exp_requise}ans) = +10pts")
        else:
            details['details_score'].append(f"Expérience insuffisante ({exp_cv}ans < {exp_requise}ans)")

    # 4. Type de contrat (bonus/malus)
    type_contrat, is_exclusion = detecter_type_contrat(offre_text)
    details['type_contrat'] = type_contrat
    details['exclusion_detectee'] = is_exclusion

    if is_exclusion:
        score += SCORE_CONFIG['contrat']['exclusion']
        details['details_score'].append(f"Exclusion contrat ({type_contrat}) = {SCORE_CONFIG['contrat']['exclusion']}pts")
    elif type_contrat == 'CDI':
        score += SCORE_CONFIG['contrat']['bonus_cdi']
        details['details_score'].append(f"CDI = +{SCORE_CONFIG['contrat']['bonus_cdi']}pts")

    # 5. Mots seniorité (max 10 points)
    nb_senior = compter_mots_seniorite(offre_text)
    details['mots_seniorite'] = nb_senior
    points_senior = min(nb_senior * 5, SCORE_CONFIG['mots_positifs']['max'])
    if points_senior > 0:
        score += points_senior
        details['details_score'].append(f"Mots seniorité ({nb_senior}) = +{points_senior}pts")

    # Normaliser le score sur 100
    score_final = max(0, min(100, score))

    return score_final, details

def generer_resume_match(score: int, details: Dict, profil: Dict, offre: Dict) -> str:
    """Génère un résumé textuel du matching (sans IA)."""
    lignes = []

    # Emoji selon le score
    if score >= 80:
        emoji = "🔥"
        appreciation = "Excellent match"
    elif score >= 60:
        emoji = "✅"
        appreciation = "Bon match"
    elif score >= 40:
        emoji = "⚠️"
        appreciation = "Match moyen"
    else:
        emoji = "❌"
        appreciation = "Match faible"

    lignes.append(f"📊 Match: {score}% {emoji} {appreciation}")
    lignes.append("")

    # Compétences
    comp_trouvees = details['competences_trouvees']
    comp_total = details['nb_competences_cv']
    if comp_total > 0:
        if comp_trouvees:
            comp_str = ", ".join(comp_trouvees[:6])  # Max 6 compétences
            if len(comp_trouvees) > 6:
                comp_str += f" +{len(comp_trouvees)-6} autres"
            lignes.append(f"✓ {len(comp_trouvees)}/{comp_total} compétences: {comp_str}")
        else:
            lignes.append(f"⚠️ Aucune compétence du CV trouvée")
        lignes.append("")

    # Poste
    if details['poste_match_exact']:
        lignes.append(f"✓ Poste correspondant à ton profil")
    elif details['poste_match_partiel']:
        lignes.append(f"~ Poste partiellement correspondant")
    else:
        lignes.append(f"⚠️ Poste différent de ton historique")
    lignes.append("")

    # Expérience
    if details['experience_requise']:
        exp_cv = profil.get('annees_exp', 0)
        if details['experience_ok']:
            lignes.append(f"✓ Expérience: {exp_cv}ans (offre demande {details['experience_requise']}ans)")
        else:
            lignes.append(f"⚠️ Expérience: {exp_cv}ans vs {details['experience_requise']}ans requis")
        lignes.append("")

    # Contrat
    if details['exclusion_detectee']:
        lignes.append(f"❌ Exclusion: Contrat en {details['type_contrat']}")
    elif details['type_contrat'] == 'CDI':
        lignes.append(f"✓ Contrat: CDI")

    # Points forts si bon match
    if score >= 60:
        lignes.append("")
        lignes.append(f"💡 Points forts:")

        points_forts = []
        if len(comp_trouvees) >= 3:
            points_forts.append("• Bonne adéquation technique")
        if details['poste_match_exact']:
            points_forts.append("• Poste dans ta continuité")
        if details['experience_ok'] and details['experience_requise']:
            points_forts.append("• Niveau d'expérience adapté")
        if details['type_contrat'] == 'CDI':
            points_forts.append("• CDI stable")

        lignes.extend(points_forts[:3])

    return "\n".join(lignes)

def analyser_offre(offre: Dict, profil: Dict) -> Dict:
    """
    Analyse complète d'une offre vs le profil.
    Retourne un dict avec score, résumé et détails.
    """
    score, details = calculer_score_match(profil, offre)
    resume = generer_resume_match(score, details, profil, offre)

    return {
        'score': score,
        'resume': resume,
        'details': details,
        'recommande': score >= 50  # Seuil pour recommander
    }
