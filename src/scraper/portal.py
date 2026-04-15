"""
Scraper PortalJob Madagascar - Secteur Informatique/Web.
Extrait les offres d'emploi dev et les envoie sur Telegram.
Stockage des offres dans SQLite (remplace JSON).
"""
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from ..telegram import envoyer_offre, tester_configuration
from ..storage import charger_toutes_offres, sauvegarder_offre_permanente, offre_existe, compter_offres

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "session")
# Mode headless pour exécution sur serveur (défaut: False en local, True sur CI)
HEADLESS_MODE = os.getenv('HEADLESS', 'false').lower() == 'true'

# Liste des mots-clés pour filtrer uniquement les jobs de dev
MOTS_CLES_DEV = [
    "développeur", "developpeur", "developer", "fullstack", "full-stack",
    "backend", "frontend", "front-end", "back-end", "net", "python",
    "php", "java", "javascript", "angular", "react", "odoo", "logiciel", "web", "software", "dev"
]


def charger_base():
    """Charge toutes les offres depuis SQLite."""
    return charger_toutes_offres()


def sauvegarder_offre(offre_data):
    """Sauvegarde une nouvelle offre dans SQLite."""
    return sauvegarder_offre_permanente(offre_data)


def est_une_offre_dev(titre):
    """Vérifie si le titre contient un mot-clé de développement."""
    if not titre:
        return False
    titre_clean = titre.lower()
    return any(mot in titre_clean for mot in MOTS_CLES_DEV)


def convertir_date_relative(date_texte):
    """Convertit 'Aujourd'hui' ou 'Hier' en date formatée."""
    date_texte = date_texte.strip().lower()
    aujourdhui = datetime.now()

    if date_texte == "aujourd'hui":
        return aujourdhui.strftime("%d/%m/%Y")
    elif date_texte == "hier":
        hier = aujourdhui.replace(day=aujourdhui.day - 1)
        return hier.strftime("%d/%m/%Y")
    else:
        # Essayer de parser d'autres formats
        return date_texte


def extraire_offres_du_dom(page):
    """Extrait les offres directement depuis le DOM de la page secteur."""
    offres = []

    try:
        # Chercher tous les articles (éléments contenant les offres)
        articles = page.locator('article').all()

        for article in articles:
            try:
                # Chercher le lien principal de l'offre (titre)
                lien_titre = article.locator('a h3').first
                if not lien_titre or lien_titre.count() == 0:
                    continue

                # Récupérer le parent <a> du h3
                lien_principal = article.locator('a').first
                if not lien_principal or lien_principal.count() == 0:
                    continue

                href = lien_principal.get_attribute('href')
                if not href or 'view' not in href:
                    continue

                # Titre de l'offre
                titre_el = article.locator('h3').first
                titre = titre_el.inner_text().strip() if titre_el and titre_el.count() > 0 else ""
                if not titre or len(titre) < 5:
                    continue

                # Entreprise (cherche dans le <p> avec l'icône building)
                entreprise_el = article.locator('p.font-semibold').first
                entreprise = entreprise_el.inner_text().strip() if entreprise_el and entreprise_el.count() > 0 else "Non spécifiée"

                # Date de publication (dans le 4ème span du lien)
                # Les spans sont: [0]=type contrat, [1]=ville, [2]=secteur, [3]=date
                spans = article.locator('a span').all()
                date_texte = ""
                if len(spans) >= 4:
                    date_texte = spans[3].inner_text().strip()

                # Convertir la date relative (Aujourd'hui → date, Hier → date, ou garder le format existant)
                date_pub = convertir_date_relative(date_texte) if date_texte else "Inconnue"

                # Construire URL complète
                url_offre = f"https://www.portaljob-madagascar.com{href}" if href.startswith('/') else href

                offres.append({
                    'titre': titre,
                    'entreprise': entreprise,
                    'url': url_offre,
                    'date': date_pub
                })

            except Exception as e:
                continue

    except Exception as e:
        print(f"Erreur extraction DOM: {e}")

    return offres


def extraire_details(page, url):
    """Extrait les détails structurés d'une offre depuis sa page détail."""
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        details = {}

        # Structure attendue:
        # - div avec h2 "Activité de l'entreprise"
        # - div avec h2 "Missions"
        # - div avec h2 "Profil recherché"

        sections = [
            ("Activité de l'entreprise", "entreprise"),
            ("Missions", "missions"),
            ("Profil recherché", "profil")
        ]

        for titre_section, key in sections:
            try:
                # Chercher le h2 avec le titre de section
                section_heading = page.locator(f'h2:has-text("{titre_section}")').first
                if section_heading and section_heading.count() > 0:
                    # Le contenu est dans le div sibling suivant
                    parent = section_heading.locator('xpath=..').first
                    if parent and parent.count() > 0:
                        # Chercher le div avec le contenu textuel
                        content_div = parent.locator('div.text-\\[16px\\]').first
                        if content_div and content_div.count() > 0:
                            text = content_div.inner_text().strip()
                            if text:
                                details[key] = text
            except:
                continue

        # Si on n'a pas trouvé les sections, essayer le container principal
        if not details:
            try:
                main_container = page.locator('.max-w-none.space-y-8').first
                if main_container and main_container.count() > 0:
                    full_text = main_container.inner_text().strip()
                    if full_text:
                        details["description_complete"] = full_text[:1000]
            except:
                pass

        # Fallback: tout le body si vraiment rien
        if not details:
            body_text = page.locator('body').inner_text()
            lines = [l.strip() for l in body_text.split('\n') if l.strip() and len(l.strip()) > 30]
            if lines:
                desc = '\n'.join(lines[:10])
                details["description"] = desc[:800]

        # Formater le résultat
        result_parts = []
        if "entreprise" in details:
            result_parts.append(f"**Activité entreprise:**\n{details['entreprise'][:300]}")
        if "missions" in details:
            result_parts.append(f"**Missions:**\n{details['missions'][:300]}")
        if "profil" in details:
            result_parts.append(f"**Profil recherché:**\n{details['profil'][:300]}")
        if "description_complete" in details:
            result_parts.append(details["description_complete"])
        if "description" in details:
            result_parts.append(details["description"])

        return '\n\n'.join(result_parts) if result_parts else "Détails non disponibles."

    except Exception as e:
        return f"Détails non disponibles ({str(e)[:50]})."


def surveiller_portal():
    url_secteur = "https://www.portaljob-madagascar.com/emploi/liste/secteur/informatique-web"
    nouvelles_offres = []
    total_offres_avant = compter_offres()

    # Test initial de Telegram
    print("📱 Vérification du bot Telegram...")
    telegram_ok = tester_configuration()
    if not telegram_ok:
        print("   (Tu peux continuer sans Telegram ou corriger le fichier config/.env)")

    print(f"📊 {total_offres_avant} offres déjà en base SQLite")

    # S'assurer que le dossier session existe
    os.makedirs(SESSION_DIR, exist_ok=True)

    with sync_playwright() as p:
        # Sur le cloud (GitHub Actions, etc), on utilise headless=True
        # En local, on peut utiliser headless=False pour voir le navigateur
        if HEADLESS_MODE:
            print("🖥️  Mode headless activé (cloud)")
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            page = browser.new_page()
        else:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = browser.pages[0]

        try:
            print("🔍 Chargement de PortalJob (secteur Informatique/Web)...")
            page.goto(url_secteur, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            # Extraire les offres du DOM
            print("📥 Extraction des offres...")
            offres_dom = extraire_offres_du_dom(page)

            print(f"\n📊 {len(offres_dom)} offres trouvées dans le DOM")

            for offre in offres_dom:
                try:
                    titre = offre['titre']
                    url_offre = offre['url']

                    # Vérifier si déjà dans la base SQLite
                    if offre_existe(url_offre):
                        continue

                    # Vérifier si offre de dev
                    if not est_une_offre_dev(titre):
                        continue

                    # Récupérer la date déjà extraite
                    date_pub = offre.get('date', 'Inconnue')

                    print(f"🎯 {titre[:60]} ({date_pub})")

                    # Récupérer les détails
                    details = extraire_details(page, url_offre)

                    offre_data = {
                        "titre": titre,
                        "entreprise": offre['entreprise'],
                        "date_publication": date_pub,
                        "url": url_offre,
                        "details": details,
                        "date_decouverte": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    # Sauvegarder immédiatement dans SQLite
                    if sauvegarder_offre(offre_data):
                        nouvelles_offres.append(offre_data)
                        # Envoyer sur Telegram
                        envoyer_offre(offre_data)
                    else:
                        print(f"  ⚠️ Échec sauvegarde de l'offre")

                except Exception as e:
                    print(f"  ⚠️ Erreur sur offre: {e}")
                    continue

            if nouvelles_offres:
                total_apres = compter_offres()
                print(f"\n✅ {len(nouvelles_offres)} nouvelles offres enregistrées!")
                print(f"📊 Total en base: {total_apres} offres")
            else:
                print("\n😴 Aucune nouvelle offre.")

        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()

        # Fermer le browser proprement
        try:
            if HEADLESS_MODE:
                browser.close()
            else:
                browser.close()
        except:
            pass


if __name__ == "__main__":
    surveiller_portal()
