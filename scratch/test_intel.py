import asyncio
import sys
import os

# Ajouter le chemin du projet
sys.path.append(os.getcwd())

from src.utils.intel import CompanyIntel

async def test_search():
    target = "BOCASAY"
    print(f"--- Test Recherche Intelligence (Playwright Headless) pour: {target} ---")
    
    try:
        # Test via CompanyIntel (Playwright)
        print("\nRecherche en cours (veuillez patienter)...")
        intel = await CompanyIntel.search_company_info(target)
        
        print("\n--- RESULTATS STRUCTURES ---")
        if intel:
            print(f"LinkedIn : {intel.get('linkedin')}")
            print(f"Facebook : {intel.get('facebook')}")
            print(f"Site Web : {intel.get('website')}")
        else:
            print("❌ Aucun résultat trouvé.")
        
    except Exception as e:
        print(f"Erreur lors du test: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
