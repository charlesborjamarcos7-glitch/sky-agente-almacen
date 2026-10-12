"""Puente aislado por sesión para el agente existente (estado global protegido)."""
import threading
from pathlib import Path
from config import REPORTES
_LOCK = threading.RLock()

def responder(pregunta, contexto):
    """Devuelve texto, historial actualizado y PDFs creados en el turno."""
    import agente_inventario as ia
    with _LOCK:
        ia.historial = list(contexto)
        ia.pendiente = None
        anteriores = {f.name for f in REPORTES.glob('*.pdf')}
        try:
            respuesta = ia.conversar(pregunta)
            nuevo_historial = list(ia.historial)
        finally:
            ia.pendiente = None
            ia.historial = []
        archivos = [p for p in REPORTES.glob('*.pdf') if p.name not in anteriores]
        return respuesta, nuevo_historial, archivos
