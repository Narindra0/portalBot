"""
Module d'envoi d'emails pour le fallback de candidature.
Utilise SMTP via Gmail (mot de passe d'application requis).
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from ..config import SMTP_EMAIL, SMTP_PASSWORD
from ..utils.logger import logger


async def envoyer_candidature_email(
    destinataire: str,
    offre_titre: str,
    offre_entreprise: str,
    lettre_motivation: str,
    cv_pdf_path: str = None
) -> tuple[bool, str]:
    """
    Envoie une candidature par email en fallback.
    Retourne (succès: bool, message: str)
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False, "SMTP non configuré. Vérifie SMTP_EMAIL et SMTP_PASSWORD dans ton .env"

    if not destinataire or '@' not in destinataire:
        return False, "Adresse email du destinataire invalide."

    try:
        # Préparer le message
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = destinataire
        msg['Subject'] = f"Candidature au poste de {offre_titre} – {offre_entreprise}"

        # Corps de l'email (lettre de motivation)
        msg.attach(MIMEText(lettre_motivation, 'plain', 'utf-8'))

        # Pièce jointe PDF si disponible
        if cv_pdf_path and os.path.exists(cv_pdf_path):
            with open(cv_pdf_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(cv_pdf_path)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)
            logger.info(f"📎 CV joint : {filename}")

        # Envoi via Gmail SMTP
        import asyncio
        await asyncio.to_thread(_envoyer_smtp, msg, destinataire)

        logger.info(f"✅ Email envoyé à {destinataire}")
        return True, f"📧 Candidature envoyée par email à **{destinataire}** !"

    except Exception as e:
        logger.error(f"❌ Erreur envoi email : {e}")
        return False, f"Échec de l'envoi email : {e}"


def _envoyer_smtp(msg: MIMEMultipart, destinataire: str):
    """Envoi SMTP synchrone (appelé dans un thread)."""
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, destinataire, msg.as_string())


def extraire_email_depuis_texte(texte: str) -> str | None:
    """Extrait la première adresse email trouvée dans un texte."""
    import re
    pattern = r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(pattern, texte or '')
    # Filtrer les faux positifs commonaux (images, etc.)
    exclusions = ['example.com', 'email.com', 'domaine.com', '.png', '.jpg']
    for match in matches:
        if not any(exc in match.lower() for exc in exclusions):
            return match
    return None
