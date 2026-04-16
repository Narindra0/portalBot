"""
Module d'extraction de texte depuis PDF et images.
Refactorisé pour utiliser httpx (async) et le logger centralisé.
"""
import os
import io
import httpx
from PyPDF2 import PdfReader
from PIL import Image
from ..utils.logger import logger

# Configuration Tesseract pour Windows
try:
    import pytesseract
    if os.name == 'nt':  # Windows
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
except ImportError:
    pytesseract = None

async def telecharger_fichier_telegram_async(file_id, token):
    """Télécharge un fichier depuis Telegram de manière asynchrone."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Récupérer le path du fichier
            resp = await client.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id}
            )
            
            if resp.status_code != 200:
                logger.error(f"Erreur getFile: {resp.status_code}")
                return None
                
            data = resp.json()
            if not data.get('ok'):
                logger.error(f"Réponse Telegram non OK: {data}")
                return None
                
            file_path = data['result']['file_path']
            
            # 2. Télécharger le fichier
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            resp = await client.get(file_url)
            
            if resp.status_code == 200:
                return resp.content
            
            logger.error(f"Erreur téléchargement fichier: {resp.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Exception téléchargement Telegram: {e}")
        return None

def extraire_texte_pdf(content):
    """Extrait le texte d'un PDF (texte natif)."""
    try:
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            extr = page.extract_text()
            if extr:
                text += extr + "\n"
        return text.strip() if text.strip() else None
    except Exception as e:
        logger.error(f"Erreur PDF natif: {e}")
        return None

def extraire_texte_ocr(content):
    """Extrait le texte d'une image avec OCR (Tesseract)."""
    if not pytesseract:
        logger.warning("pytesseract non installé")
        return None
    try:
        image = Image.open(io.BytesIO(content))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        try:
            text = pytesseract.image_to_string(image, lang='fra+eng')
        except:
            text = pytesseract.image_to_string(image)
            
        return text.strip() if text.strip() else None
    except Exception as e:
        logger.error(f"Erreur OCR image: {e}")
        return None

async def traiter_fichier_cv(file_id, token, mime_type=None):
    """Traite un fichier CV et extrait le texte (Async wrapper)."""
    logger.info("📥 Début du traitement du fichier CV...")
    
    content = await telecharger_fichier_telegram_async(file_id, token)
    if not content:
        return False, "❌ Impossible de télécharger le fichier."

    is_pdf = False
    is_image = False

    if mime_type:
        is_pdf = 'pdf' in mime_type.lower()
        is_image = any(img in mime_type.lower() for img in ['image', 'jpg', 'jpeg', 'png'])
    else:
        if content[:4] == b'%PDF': is_pdf = True
        elif content[:2] in [b'\xff\xd8', b'\x89PNG']: is_image = True

    text = None
    if is_pdf:
        logger.info("📄 Analyse PDF...")
        text = extraire_texte_pdf(content)
        if not text and pytesseract:
            logger.info("🔍 Tentative OCR sur PDF...")
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(content, dpi=200)
                text = ""
                for i, img in enumerate(images[:3]):
                    logger.info(f"   OCR page {i+1}...")
                    t = pytesseract.image_to_string(img, lang='fra+eng')
                    text += t + "\n"
            except Exception as e:
                logger.error(f"Erreur PDF OCR: {e}")
    elif is_image:
        logger.info("🖼️ Analyse image OCR...")
        text = extraire_texte_ocr(content)
    else:
        return False, "❌ Format non supporté."

    if text and text.strip():
        # Nettoyage
        cleaned = ' '.join(text.split())
        logger.info(f"✅ Texte extrait: {len(cleaned)} caractères.")
        return True, cleaned[:5000]
    
    return False, "❌ Aucun texte extrait."
