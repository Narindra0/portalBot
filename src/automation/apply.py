import os
import re
from playwright.async_api import async_playwright
from ..utils.logger import logger
from ..config import HEADLESS

async def postuler_offre_portal(url_offre, lettre_motivation):
    """
    Tente de postuler automatiquement à une offre sur PortalJob.
    Nécessite qu'une session soit déjà enregistrée dans le dossier `session/`.
    Retourne (succès: bool, message: str)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    session_json = os.path.join(base_dir, 'portal_session.json')
    session_dir = os.path.join(base_dir, 'session')

    if not os.path.exists(session_json) and not os.path.exists(session_dir):
        return False, "Aucune session trouvée. Veuillez vous connecter une fois avec login_portal.py."

    logger.info(f"🚀 Lancement de l'auto-apply sur : {url_offre}")
    
    async with async_playwright() as p:
        browser = None
        context = None
        try:
            if os.path.exists(session_json):
                logger.info("Utilisation du fichier d'état (portal_session.json)")
                browser = await p.chromium.launch(
                    headless=HEADLESS,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = await browser.new_context(
                    storage_state=session_json,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = await context.new_page()
            else:
                logger.info("Utilisation du contexte persistant (session/)")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=session_dir,
                    headless=HEADLESS,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    no_viewport=False,
                    viewport={"width": 1280, "height": 800},
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                page = context.pages[0] if context.pages else await context.new_page()
            
            # 1. Navigation vers l'offre
            logger.info("Navigation vers l'offre...")
            await page.goto(url_offre, wait_until="networkidle", timeout=60000)
            
            # Vérifier si on est bien connecté par la présence d'un bouton Postuler
            # Si le site demande de se connecter, le bouton Postuler renvoie vers /connexion
            bouton_postuler = page.locator("a, button").filter(has_text=re.compile(r"^Postuler$", re.IGNORECASE)).first
            
            if await bouton_postuler.count() == 0:
                # S'il trouve pas "Postuler", on cherche "Envoyer ma candidature" ou similaire
                bouton_postuler = page.locator("a, button").filter(has_text=re.compile(r"candidature|postuler", re.IGNORECASE)).first
                
            if await bouton_postuler.count() == 0:
                if browser: await browser.close()
                elif context: await context.close()
                return False, "Impossible de trouver le bouton 'Postuler' sur cette page. (L'offre est peut-être expirée ou externe)"

            # 2. Clic sur Postuler
            logger.info("Clic sur le bouton Postuler...")
            await bouton_postuler.click()
            
            # On attend un peu que le formulaire apparaisse
            await page.wait_for_timeout(3000)
            
            # Vérification si on n'a pas été redirigé vers la connexion
            if "connexion" in page.url.lower():
                if browser: await browser.close()
                elif context: await context.close()
                return False, "La session est expirée ou invalide. Veuillez relancer `login_portal.py`."

            # 3. Remplissage du formulaire de la lettre de motivation
            # On cherche de manière agnostique la présence d'un textarea
            logger.info("Recherche du champ texte pour la lettre...")
            text_area = page.locator("textarea").first
            
            if await text_area.count() > 0:
                await text_area.fill(lettre_motivation)
                logger.info("Lettre de motivation insérée avec succès.")
            else:
                logger.warning("Aucun champ `textarea` trouvé. S'agit-il d'un simple clic d'envoi ?")
                # Certains sites n'ont pas de textarea mais un simple bouton de confirmation.

            # 4. Soumettre la candidature
            # Chercher le bouton final qui contient "Envoyer", "Valider", "Confirmer"
            bouton_validation = page.locator("button").filter(has_text=re.compile(r"envoyer|valider|confirmer", re.IGNORECASE)).first
            
            if await bouton_validation.count() > 0:
                logger.info("Clic sur le bouton de soumission finale...")
                if not HEADLESS:
                    await page.wait_for_timeout(2000) # Laisse le temps de voir l'action si on debug
                await bouton_validation.click(force=True)
                await page.wait_for_timeout(5000) # Attente que la page confirme
            else:
                if browser: await browser.close()
                elif context: await context.close()
                return False, "Formulaire de candidature trouvé mais impossible de localiser le bouton de validation finale."

            # 5. Vérifier la réussite (Message de confirmation)
            logger.info("✅ Candidature envoyée !")
            if browser: await browser.close()
            elif context: await context.close()
            return True, "Candidature envoyée avec succès !"
            
        except Exception as e:
            if browser: await browser.close()
            elif context: await context.close()
            logger.error(f"Erreur d'automatisation Playwright : {e}")
            return False, f"Erreur technique lors de la candidature : {e}"
