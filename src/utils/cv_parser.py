"""
CV Parser - Extraction automatique des mots-clés du CV pour matching.
Sans IA, utilisant des règles et patterns.
"""
import re
import json
from typing import Dict, List, Set

def extraire_competences(cv_text: str) -> List[str]:
    """Extrait les compétences techniques du CV."""
    # Liste des compétences tech courantes à rechercher
    competences_courantes = {
        'python', 'sql', 'javascript', 'java', 'php', 'c#', 'c++', 'go', 'rust',
        'html', 'css', 'react', 'angular', 'vue', 'node', 'django', 'flask',
        'tableau', 'powerbi', 'looker', 'dataiku', 'power bi',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git',
        'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy',
        'mongodb', 'postgresql', 'mysql', 'oracle', 'sqlite', 'redis',
        'spark', 'hadoop', 'kafka', 'airflow',
        'excel', 'word', 'powerpoint', 'access',
        'linux', 'windows', 'macos', 'unix',
        'agile', 'scrum', 'kanban', 'jira', 'confluence'
    }

    cv_lower = cv_text.lower()
    competences_trouvees = []

    for comp in competences_courantes:
        # Cherche le mot entier
        pattern = r'\b' + re.escape(comp) + r'\b'
        if re.search(pattern, cv_lower):
            competences_trouvees.append(comp.title() if len(comp) > 3 else comp.upper())

    # Cherche aussi les mots en majuscules (souvent des technologies/acronymes)
    mots_majuscules = re.findall(r'\b[A-Z]{2,}\b', cv_text)
    for mot in mots_majuscules:
        if len(mot) >= 2 and mot not in ['CV', 'PDF', 'HTML']:
            if mot not in competences_trouvees:
                competences_trouvees.append(mot)

    return list(set(competences_trouvees))

def extraire_annees_experience(cv_text: str) -> int:
    """Extrait les années d'expérience du CV."""
    patterns = [
        r'(\d+)\+?\s*ans?\s+d\'exp[eé]rience',
        r'exp[eé]rience\s*:?\s*(\d+)\+?\s*ans?',
        r'(\d+)\+?\s*ann[eé]es\s+d\'exp[eé]rience',
        r'(\d+)\+?\s*ans?\s+en\s',
    ]

    for pattern in patterns:
        match = re.search(pattern, cv_text.lower())
        if match:
            return int(match.group(1))

    # Cherche des patterns comme "5 ans" ou "10+ ans" près de mots comme "expérience", "professionnelle"
    matches = re.findall(r'(\d+)\+?\s*ans?', cv_text.lower())
    if matches:
        # Prend le plus grand nombre trouvé (souvent l'expérience totale)
        return max(int(m) for m in matches)

    return 0

def extraire_postes(cv_text: str) -> List[str]:
    """Extrait les postes précédemment occupés."""
    postes_indicateurs = [
        'data analyst', 'data scientist', 'développeur', 'developpeur', 'developer',
        'ingénieur', 'ingenieur', 'engineer', 'consultant', 'administrateur',
        'manager', 'chef de projet', 'lead', 'architecte', 'analyste',
        'technicien', 'stagiaire', 'étudiant', 'étudiante', 'freelance'
    ]

    cv_lower = cv_text.lower()
    postes_trouves = []

    for poste in postes_indicateurs:
        pattern = r'\b' + re.escape(poste) + r'\b'
        if re.search(pattern, cv_lower):
            postes_trouves.append(poste.title())

    return list(set(postes_trouves))

def extraire_niveau_etudes(cv_text: str) -> str:
    """Extrait le niveau d'études."""
    patterns = [
        (r'bac\s*\+\s*(\d+)', 'Bac+{}'),
        (r'licence\s*(\d+)?', 'Licence'),
        (r'master\s*(\d+)?', 'Master'),
        (r'doctorat\s*|phd\s*|doctor', 'Doctorat'),
        (r'ingénieur\s*|engineer', 'Ingénieur'),
        (r'bts\s*|btec', 'BTS'),
        (r'dut\s*', 'DUT'),
    ]

    for pattern, label in patterns:
        match = re.search(pattern, cv_text.lower())
        if match:
            if '{}' in label and match.groups() and match.group(1):
                return label.format(match.group(1))
            return label

    return "Non détecté"

def extraire_extraits_important(cv_text: str, max_phrases: int = 4) -> str:
    """Extrait les phrases clés du CV (résumé professionnel, objectif)."""
    # Cherche des sections importantes
    sections_cibles = [
        r'résumé\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|$)',
        r'resumé\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|$)',
        r'objectif\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|$)',
        r'profil\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|$)',
    ]

    extraits = []
    for pattern in sections_cibles:
        match = re.search(pattern, cv_text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1).strip()
            # Limite la longueur
            if len(text) > 50 and len(text) < 500:
                extraits.append(text)

    if extraits:
        return ' '.join(extraits[:max_phrases])[:800]

    # Fallback: prend les 3 premières phrases du CV
    phrases = re.split(r'[.!?]+', cv_text)
    phrases_propres = [p.strip() for p in phrases if len(p.strip()) > 30 and len(p.strip()) < 300]
    if phrases_propres:
        return '. '.join(phrases_propres[:max_phrases]) + '.'

    return cv_text[:500] if cv_text else ""

def parser_cv_complet(cv_text: str) -> Dict:
    """Parse complet du CV et retourne un dictionnaire structuré."""
    if not cv_text:
        return {
            'competences': [],
            'annees_exp': 0,
            'postes': [],
            'niveau_etudes': "Non détecté",
            'extrait_important': ""
        }

    return {
        'competences': extraire_competences(cv_text),
        'annees_exp': extraire_annees_experience(cv_text),
        'postes': extraire_postes(cv_text),
        'niveau_etudes': extraire_niveau_etudes(cv_text),
        'extrait_important': extraire_extraits_important(cv_text)
    }
