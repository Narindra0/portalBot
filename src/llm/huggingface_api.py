"""
Module de connexion à l'API Hugging Face pour génération de lettres de motivation.
Modèle utilisé : Qwen 2.5 7B Instruct
"""
import os
import time
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# Charger les variables d'environnement
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', '.env'))

HF_API_KEY = os.getenv('HF_API_KEY')
HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def generer_lettre_motivation(cv_text, offre_titre, offre_entreprise, offre_details):
    """
    Génère une lettre de motivation en utilisant l'API Inference de Hugging Face.
    """
    if not HF_API_KEY:
        print("⚠️ HF_API_KEY manquante dans le fichier .env")
        return None

    client = InferenceClient(model=HF_MODEL, token=HF_API_KEY)

    # Renforcement du System Prompt pour forcer le Français et le professionnalisme
    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un expert en recrutement français. "
                "Tu dois impérativement rédiger TOUTE la lettre en FRANÇAIS uniquement. "
                "N'utilise jamais de caractères chinois. "
                "Produis une lettre de motivation formelle, structurée et convaincante."
            )
        },
        {
            "role": "user",
            "content": f"""Rédige une lettre de motivation professionnelle en FRANÇAIS pour le poste suivant :
            
            POSTE : {offre_titre}
            ENTREPRISE : {offre_entreprise}
            DÉTAILS DE L'OFFRE : {offre_details}

            MON CV (Expériences à utiliser) :
            {cv_text}

            CONSIGNES STRICTES :
            1. RÉDIGE EXCLUSIVEMENT EN FRANÇAIS.
            2. Adopte un ton professionnel et enthousiaste.
            3. Structure : En-tête (Candidat/Entreprise), Objet, Corps de texte (Vous/Moi/Nous), Formule de politesse.
            4. Ne pas inventer de compétences non citées dans le CV.
            5. Ne pas ajouter de commentaires avant ou après la lettre.
            """
        }
    ]

    try:
        print(f"🤖 Appel API Hugging Face ({HF_MODEL})...")
        
        response = client.chat_completion(
            messages=messages,
            max_tokens=1500,  # Augmenté pour une lettre complète
            temperature=0.7
        )

        lettre = response.choices[0].message.content
        
        # Sécurité supplémentaire au cas où le modèle ignorerait encore la consigne
        if any(ord(char) > 10000 for char in lettre[:100]):
            print("⚠️ Attention : Le modèle semble avoir encore généré du texte non-latin.")
            
        print(f"✅ Lettre générée avec succès ({len(lettre)} caractères)")
        return lettre.strip()

    except Exception as e:
        print(f"❌ Erreur lors de la génération avec {HF_MODEL}: {e}")
        return None


def tester_connexion():
    """Vérifie si le modèle est disponible et le token valide."""
    if not HF_API_KEY:
        print("❌ Token HF_API_KEY manquant.")
        return False
        
    client = InferenceClient(model=HF_MODEL, token=HF_API_KEY)
    try:
        client.chat_completion(messages=[{"role": "user", "content": "Réponds 'OK' en français."}], max_tokens=5)
        print(f"✅ Modèle {HF_MODEL} prêt et accessible.")
        return True
    except Exception as e:
        print(f"❌ Impossible d'accéder au modèle {HF_MODEL} : {e}")
        return False


if __name__ == "__main__":
    if tester_connexion():
        # Test avec les mêmes données que précédemment
        res = generer_lettre_motivation(
            "Développeur Python, 3 ans d'XP en Django et API REST.", 
            "Développeur Backend", 
            "Tech Solutions", 
            "Maîtrise de Django et des API REST demandée."
        )
        if res:
            print("\n--- APERÇU (FRANÇAIS) ---\n")
            print(res)
