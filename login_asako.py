import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    print("🚀 Lancement de l'outil de connexion pour Asako.mg...")
    print("⚠️  Veuillez vous connecter manuellement à votre compte Asako.")
    print("⚠️  Une fois connecté, fermez simplement la fenêtre du navigateur.")
    print("-" * 50)

    # Récupération du chemin absolu pour le dossier session
    base_dir = os.path.dirname(os.path.abspath(__file__))
    session_dir = os.path.join(base_dir, 'session_asako')

    # Création du dossier session s'il n'existe pas
    os.makedirs(session_dir, exist_ok=True)

    async with async_playwright() as p:
        # Lancement de Chromium en mode non-headless pour que l'utilisateur puisse interagir
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=False,
            # On simule un user_agent classique pour éviter certains blocages
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        # Navigation vers la page de connexion
        await page.goto("https://www.asako.mg/connexion")
        
        print("\n✅ Navigateur ouvert sur la page de connexion.")
        print("Prenez tout le temps nécessaire pour vous connecter.")
        print("⚠️  Ne fermez pas le navigateur ! ⚠️")
        
        try:
            # On attend que l'utilisateur appuie sur Entrée dans le terminal
            await asyncio.get_event_loop().run_in_executor(None, input, "\n👉 APPUYEZ SUR ENTRÉE ICI UNE FOIS CONNECTÉ SUR LE NAVIGATEUR : ")
        except Exception as e:
            print(f"Erreur : {e}")
        finally:
            # Avant de fermer, on exporte l'état de la session (cookies + localstorage)
            export_path = os.path.join(base_dir, 'asako_session.json')
            await browser.storage_state(path=export_path)
            
            await browser.close()
            print("\n🔒 Navigateur fermé et session enregistrée !")
            print(f"✅ EXPORT RÉUSSI : Le fichier '{export_path}' a été créé.")
            print("Tu pourras utiliser le contenu de ce fichier asako_session.json dans GitHub Actions (via un SECRET) pour le déploiement sur le cloud.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt manuel.")
