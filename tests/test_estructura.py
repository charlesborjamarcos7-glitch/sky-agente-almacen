from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_archivos():
    assert (ROOT/'app.py').exists()
    assert (ROOT/'agente.py').exists()
    assert (ROOT/'herramientas_inventario.py').exists()
    assert (ROOT/'.gitignore').exists()
def test_no_secretos():
    assert not (ROOT/'.env').exists()
    assert not (ROOT/'credentials.json').exists()
    assert not (ROOT/'token.json').exists()
