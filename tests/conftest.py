"""Configuración compartida de pytest."""
import sys
import pytest


@pytest.fixture(autouse=True)
def clean_db_module():
    """
    Elimina 'db' del cache de módulos antes de cada test para que cada test
    importe la versión real de db.py (no el stub de test_logic.py).
    """
    sys.modules.pop("db", None)
    yield
    sys.modules.pop("db", None)
