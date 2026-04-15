"""
Module d'extraction de texte depuis PDF et images.
Supporte : PDF texte, PDF image (OCR), photos de CV.
"""
import os
import io
import requests
from PyPDF2 import PdfReader
from PIL import Image

# Configuration Tesseract pour Windows
try:
    import pytesseract
    # Si Tesseract n'est pas dans le PATH, essayer le chemin Windows par défaut
    if os.name == 'nt':  # Windows
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
except ImportError:
    pytesseract = None


def telecharger_fichier_telegram(file_id, token):
    """Télécharge un fichier depuis Telegram."""
    try:
        # 1. Récupérer le path du fichier
        response = requests.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id},
            timeout=30
        )

        if response.status_code != 200:
            return None

        data = response.json()
        if not data.get('ok'):
            return None

        file_path = data['result']['file_path']

        # 2. Télécharger le fichier
        response = requests.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}",
            timeout=60
        )

        if response.status_code == 200:
            return response.content
        return None

    except Exception as e:
        print(f"⚠️ Erreur téléchargement: {e}")
        return None


def extraire_texte_pdf(content):
    """Extrait le texte d'un PDF (texte natif)."""
    try:
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)

        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        if text.strip():
            return text.strip()
        return None

    except Exception as e:
        print(f"⚠️ Erreur extraction PDF: {e}")
        return None


def extraire_texte_ocr(content):
    """Extrait le texte d'une image avec OCR (Tesseract)."""
    if pytesseract is None:
        print("⚠️ pytesseract non installé")
        return None

    try:
        # Convertir en image PIL
        image = Image.open(io.BytesIO(content))

        # Convertir en RGB si nécessaire (pour les PNG avec transparence)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # OCR avec Tesseract (français + anglais)
        try:
            text = pytesseract.image_to_string(image, lang='fra+eng')
        except Exception:
            # Fallback sans langue spécifique
            text = pytesseract.image_to_string(image)

        if text.strip():
            return text.strip()
        return None

    except Exception as e:
        print(f"⚠️ Erreur OCR: {e}")
        return None


def traiter_fichier_cv(file_id, token, mime_type=None):
    """
    Traite un fichier CV (PDF ou image) et extrait le texte.

    Args:
        file_id: ID du fichier Telegram
        token: Token du bot Telegram
        mime_type: Type MIME du fichier (optionnel)

    Returns:
        tuple: (success: bool, text: str or error_message: str)
    """
    print(f"📥 Téléchargement du fichier...")

    # Télécharger le fichier
    content = telecharger_fichier_telegram(file_id, token)
    if not content:
        return False, "❌ Impossible de télécharger le fichier"

    print(f"✅ Fichier téléchargé ({len(content)} octets)")

    # Détecter le type
    is_pdf = False
    is_image = False

    if mime_type:
        is_pdf = 'pdf' in mime_type.lower()
        is_image = any(img in mime_type.lower() for img in ['image', 'jpg', 'jpeg', 'png'])
    else:
        # Détection par magic bytes
        if content[:4] == b'%PDF':
            is_pdf = True
        elif content[:2] in [b'\xff\xd8', b'\x89PNG']:
            is_image = True

    extracted_text = None

    if is_pdf:
        print("📄 Extraction texte PDF...")
        extracted_text = extraire_texte_pdf(content)

        # Si pas de texte extrait (PDF image/scanné), essayer OCR
        if not extracted_text and pytesseract is not None:
            print("🔍 PDF sans texte natif, tentative OCR...")
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(content, dpi=200)  # DPI réduit pour rapidité
                extracted_text = ""
                for i, img in enumerate(images[:3]):  # Limiter à 3 pages max
                    print(f"   OCR page {i+1}/{min(len(images), 3)}...")
                    try:
                        text = pytesseract.image_to_string(img, lang='fra+eng')
                    except:
                        text = pytesseract.image_to_string(img)  # Fallback
                    extracted_text += text + "\n"
                if len(images) > 3:
                    extracted_text += f"\n[... {len(images)-3} pages supplémentaires non lues ...]"
            except Exception as e:
                print(f"⚠️ Erreur conversion PDF->Image: {e}")
        elif not extracted_text and pytesseract is None:
            print("⚠️ OCR non disponible (pytesseract non installé)")

    elif is_image:
        print("🖼️ OCR sur l'image...")
        extracted_text = extraire_texte_ocr(content)

    else:
        return False, "❌ Format non supporté (PDF ou image uniquement)"

    if extracted_text and extracted_text.strip():
        # Nettoyer le texte
        cleaned_text = nettoyer_texte(extracted_text)
        print(f"✅ Texte extrait: {len(cleaned_text)} caractères")
        return True, cleaned_text
    else:
        return False, "❌ Aucun texte extrait du fichier\nLe PDF est peut-être une image trop complexe"


def nettoyer_texte(text):
    """Nettoie le texte extrait."""
    # Supprimer les espaces multiples
    text = ' '.join(text.split())

    # Conserver les sauts de ligne importants
    lines = text.split('. ')
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if len(line) > 3:  # Ignorer les lignes trop courtes
            cleaned_lines.append(line)

    result = '.\n'.join(cleaned_lines)
    return result[:5000]  # Limiter à 5000 caractères pour éviter les trop gros CV
