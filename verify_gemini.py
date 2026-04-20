import asyncio
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.llm.gemini_api import generer_lettre_motivation_gemini_async, generer_resume_entreprise_gemini_async
from src.config import GEMINI_API_KEY

async def test_integration_gemini():
    print("Verification de l'integration Gemini...")
    
    if not GEMINI_API_KEY:
        print("INFO : GEMINI_API_KEY est vide dans .env. C'est attendu si vous ne l'avez pas encore ajoutee.")
        print("SVP ajoutez votre cle dans config/.env puis relancez ce script.")
        return

    # Test Lettre
    print("\n1. Test de generation de lettre...")
    lettre = await generer_lettre_motivation_gemini_async(
        "Developpeur Python", "Dev Python", "Google", "Scraping Expert"
    )
    if lettre:
        print("Succes ! La lettre commence par :", lettre[:100], "...")
    else:
        print("Echec de la generation de lettre.")

    # Test Resume
    print("\n2. Test de generation de resume d'entreprise...")
    resume = await generer_resume_entreprise_gemini_async("Bocasay", "Entreprise informatique Madagascar")
    if resume:
        print("Succes ! Resume :", resume)
    else:
        print("Echec du resume.")

if __name__ == "__main__":
    asyncio.run(test_integration_gemini())
