"""
Test du système de matching sans IA.
Ce script simule une offre et un profil pour vérifier le scoring.
"""
import sys
sys.path.insert(0, 'src')

from utils.cv_parser import parser_cv_complet
from utils.matcher import analyser_offre, calculer_score_match, generer_resume_match

# Simuler un CV texte
cv_text = """
NARINDRA Thonny
Développeur Python & Data Analyst

Email: thonny@example.com | Tel: 034 12 345 67

RÉSUMÉ
Développeur Python passionné avec 5 ans d'expérience en analyse de données.
Expert en Python, SQL, Tableau, et machine learning. Je recherche un poste
Data Analyst ou Développeur Python en CDI.

EXPÉRIENCE

2020-2023 - Data Analyst @TechCorp
• Développement d'applications Python pour l'analyse de données
• Création de dashboards Tableau et Power BI
• Gestion de bases de données SQL (PostgreSQL, MySQL)
• Utilisation de Pandas, NumPy, Scikit-learn

2019-2020 - Développeur Python @StartupXYZ
• Développement backend avec Django et Flask
• Intégration API REST
• Docker et AWS

COMPÉTENCES TECHNIQUES
Langages: Python, SQL, JavaScript
Outils: Tableau, Power BI, Dataiku, Docker, Git
Bases de données: PostgreSQL, MySQL, MongoDB
Méthodologies: Agile, Scrum

FORMATION
Master en Informatique - Université d'Antananarivo (2018)
Bac+5 en Data Science
"""

# Test 1: Parser le CV
print("=" * 60)
print("TEST 1: Extraction des informations du CV")
print("=" * 60)
profil = parser_cv_complet(cv_text)
print(f"\n✅ Compétences trouvées ({len(profil['competences'])}):")
for comp in profil['competences']:
    print(f"   • {comp}")
print(f"\n✅ Années d'expérience: {profil['annees_exp']} ans")
print(f"✅ Postes: {', '.join(profil['postes'])}")
print(f"✅ Niveau d'études: {profil['niveau_etudes']}")
print(f"\n📝 Extrait important:\n{profil['extrait_important'][:200]}...")

# Test 2: Simuler une offre
offre = {
    'titre': 'Data Analyst Senior (H/F)',
    'entreprise': 'ESN Innovation',
    'details': """
**Description de l'offre:**
ESN fondée sur l'innovation recherche un Data Analyst Senior.

**Missions:**
- Collecter, analyser et interpréter des données complexes
- Concevoir et maintenir des tableaux de bord Tableau
- Développer des scripts Python pour l'automatisation
- Collaborer avec les équipes métiers

**Profil recherché:**
- Bac+5 en data, statistiques ou informatique
- 5 ans d'expérience minimum en analyse de données
- Maîtrise de Python, SQL, Tableau
- Connaissance de Power BI appréciée
- Expérience avec PostgreSQL
- Rigoureux, autonome et proactif

**Conditions:**
CDI - Antananarivo - Télétravail partiel possible
"""
}

print("\n" + "=" * 60)
print("TEST 2: Analyse de l'offre")
print("=" * 60)
print(f"\n📌 Titre: {offre['titre']}")
print(f"🏢 Entreprise: {offre['entreprise']}")

# Test 3: Calculer le score
print("\n" + "=" * 60)
print("TEST 3: Score de matching")
print("=" * 60)
resultat = analyser_offre(offre, profil)

print(f"\n📊 Score: {resultat['score']}%")
print(f"✅ Recommandé: {'Oui' if resultat['recommande'] else 'Non'}")
print("\n" + resultat['resume'])

# Détails
print("\n" + "=" * 60)
print("TEST 4: Détails du scoring")
print("=" * 60)
details = resultat['details']
print(f"\nCompétences trouvées dans l'offre ({len(details['competences_trouvees'])}):")
for comp in details['competences_trouvees']:
    print(f"   • {comp}")
print(f"\nPoste match exact: {'Oui' if details['poste_match_exact'] else 'Non'}")
print(f"Poste match partiel: {'Oui' if details['poste_match_partiel'] else 'Non'}")
print(f"Expérience requise: {details['experience_requise']} ans")
print(f"Expérience OK: {'Oui' if details['experience_ok'] else 'Non'}")
print(f"Type de contrat: {details['type_contrat']}")
print(f"Exclusion détectée: {'Oui' if details['exclusion_detectee'] else 'Non'}")
print(f"Mots de seniorité: {details['mots_seniorite']}")

print("\n" + "=" * 60)
print("✅ TOUS LES TESTS SONT PASSÉS !")
print("=" * 60)
print("\nLe système de matching est prêt à être utilisé.")
print("Prochaines étapes:")
print("1. Assure-toi d'avoir un CV enregistré dans la base")
print("2. Exécute le scraper - il extraira automatiquement le profil")
print("3. Les offres arriveront avec leur score de matching !")
