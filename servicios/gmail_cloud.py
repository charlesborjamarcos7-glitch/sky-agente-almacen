"""Gmail OAuth para Streamlit Cloud, sin token.json en GitHub."""
import base64
import os
import re
from email.message import EmailMessage
from pathlib import Path

SCOPE = 'https://www.googleapis.com/auth/gmail.send'
EMAIL = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')


def configurado():
    return all(os.getenv(k) for k in ('GMAIL_CLIENT_ID','GMAIL_CLIENT_SECRET','GMAIL_REFRESH_TOKEN','GMAIL_ALLOWED_RECIPIENTS'))


def autorizados():
    return {x.strip().casefold() for x in os.getenv('GMAIL_ALLOWED_RECIPIENTS','').split(',') if x.strip()}


def validar_destinatario(destinatario):
    if not isinstance(destinatario,str) or len(destinatario)>254 or not EMAIL.fullmatch(destinatario):
        raise ValueError('Dirección de correo inválida.')
    if destinatario.casefold() not in autorizados():
        raise ValueError('Destinatario no autorizado. Agrégalo a GMAIL_ALLOWED_RECIPIENTS en Secrets.')


def enviar_pdf(destinatario, ruta):
    """Solo llamar después de una confirmación explícita en la interfaz."""
    if not configurado():
        raise RuntimeError('Faltan secretos de Gmail.')
    validar_destinatario(destinatario)
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from config import REPORTES
    path=Path(ruta).resolve()
    if path.parent!=REPORTES.resolve() or path.suffix.lower()!='.pdf' or not path.is_file():
        raise ValueError('Solo se pueden enviar PDF generados dentro de la carpeta reportes.')
    if path.stat().st_size>10*1024*1024 or not path.read_bytes().startswith(b'%PDF-'):
        raise ValueError('Adjunto inválido o mayor a 10 MB.')
    cred=Credentials(token=None,refresh_token=os.environ['GMAIL_REFRESH_TOKEN'],
       token_uri='https://oauth2.googleapis.com/token',client_id=os.environ['GMAIL_CLIENT_ID'],
       client_secret=os.environ['GMAIL_CLIENT_SECRET'],scopes=[SCOPE])
    cred.refresh(Request())
    mensaje=EmailMessage()
    mensaje['To']=destinatario
    mensaje['Subject']='Sky | Reporte de almacén - '+path.stem.replace('_',' ')[:75]
    mensaje.set_content('Adjunto se encuentra el reporte de inventario solicitado.\n\nSky — Agente de IA para Almacén.')
    mensaje.add_attachment(path.read_bytes(),maintype='application',subtype='pdf',filename=path.name)
    raw=base64.urlsafe_b64encode(mensaje.as_bytes()).decode('ascii')
    servicio=build('gmail','v1',credentials=cred,cache_discovery=False)
    resultado=servicio.users().messages().send(userId='me',body={'raw':raw}).execute()
    if not resultado.get('id'):
        raise RuntimeError('Gmail no devolvió un ID de mensaje. No reintentar automáticamente.')
    return {'id':resultado['id'],'destinatario':destinatario,'archivo':path.name}
