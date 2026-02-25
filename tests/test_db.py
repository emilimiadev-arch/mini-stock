"""Tests para db.py — mockean el cliente Supabase, no requieren conexión real."""

import os
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supabase_mock(data=None):
    """Retorna un mock de create_client que responde .data con `data`."""
    result = MagicMock()
    result.data = data or []

    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.eq.return_value = table
    table.neq.return_value = table
    table.execute.return_value = result

    sb = MagicMock()
    sb.table.return_value = table
    return sb


def _env():
    return {"SUPABASE_URL": "https://fake.supabase.co", "SUPABASE_ANON_KEY": "fake-key"}


# ---------------------------------------------------------------------------
# db.client()
# ---------------------------------------------------------------------------

class TestClient:
    def test_raises_connection_error_when_env_missing(self):
        import db
        with patch.dict(os.environ, {}, clear=True):
            # Remove keys if present
            os.environ.pop("SUPABASE_URL", None)
            os.environ.pop("SUPABASE_ANON_KEY", None)
            with pytest.raises(db.ConnectionError, match="SUPABASE_URL"):
                db.client()

    def test_creates_client_with_valid_env(self):
        import db
        with patch.dict(os.environ, _env()):
            with patch("db.create_client") as mock_create:
                mock_create.return_value = MagicMock()
                result = db.client()
                mock_create.assert_called_once_with(
                    "https://fake.supabase.co", "fake-key"
                )


# ---------------------------------------------------------------------------
# db.ping()
# ---------------------------------------------------------------------------

class TestPing:
    def test_returns_row_count(self):
        import db
        sb = _make_supabase_mock(data=[{"id": "1"}])
        with patch.dict(os.environ, _env()):
            with patch("db.create_client", return_value=sb):
                assert db.ping() == 1

    def test_empty_table_returns_zero(self):
        import db
        sb = _make_supabase_mock(data=[])
        with patch.dict(os.environ, _env()):
            with patch("db.create_client", return_value=sb):
                assert db.ping() == 0


# ---------------------------------------------------------------------------
# db.list_items() — mapeo A/B → Redo/Emi
# ---------------------------------------------------------------------------

class TestListItems:
    def _run(self, raw_data):
        import db
        sb = _make_supabase_mock(data=raw_data)
        with patch.dict(os.environ, _env()):
            with patch("db.create_client", return_value=sb):
                return db.list_items()

    def test_maps_A_to_Redo(self):
        result = self._run([{"id": "1", "assigned_to": "A", "created_at": "2024-01-01"}])
        assert result[0]["assigned_to"] == "Redo"

    def test_maps_B_to_Emi(self):
        result = self._run([{"id": "2", "assigned_to": "B", "created_at": "2024-01-01"}])
        assert result[0]["assigned_to"] == "Emi"

    def test_maps_None_to_None(self):
        result = self._run([{"id": "3", "assigned_to": None, "created_at": "2024-01-01"}])
        assert result[0]["assigned_to"] is None

    def test_maps_unknown_code_to_None(self):
        result = self._run([{"id": "4", "assigned_to": "X", "created_at": "2024-01-01"}])
        assert result[0]["assigned_to"] is None

    def test_empty_returns_empty_list(self):
        result = self._run([])
        assert result == []


# ---------------------------------------------------------------------------
# db.add_item() — validación
# ---------------------------------------------------------------------------

class TestAddItem:
    def test_raises_value_error_on_empty_name(self):
        import db
        with pytest.raises(ValueError, match="obligatorio"):
            db.add_item("", "", 0, 0)

    def test_raises_value_error_on_whitespace_name(self):
        import db
        with pytest.raises(ValueError):
            db.add_item("   ", "", 0, 0)

    def test_calls_insert_with_correct_payload(self):
        import db
        sb = _make_supabase_mock()
        with patch.dict(os.environ, _env()):
            with patch("db.create_client", return_value=sb):
                db.add_item("Guitarra", "Fender", 500.0, 450.0)
        table = sb.table.return_value
        table.insert.assert_called_once()
        payload = table.insert.call_args[0][0]
        assert payload["name"] == "Guitarra"
        assert payload["price_a"] == 500.0
        assert payload["price_b"] == 450.0
        assert payload["assigned_to"] is None


# ---------------------------------------------------------------------------
# db.set_assignment() — mapeo Redo/Emi → A/B
# ---------------------------------------------------------------------------

class TestSetAssignment:
    def _run(self, assigned_to):
        import db
        sb = _make_supabase_mock()
        with patch.dict(os.environ, _env()):
            with patch("db.create_client", return_value=sb):
                db.set_assignment("item-1", assigned_to)
        table = sb.table.return_value
        return table.update.call_args[0][0]

    def test_redo_maps_to_A(self):
        payload = self._run("Redo")
        assert payload["assigned_to"] == "A"

    def test_emi_maps_to_B(self):
        payload = self._run("Emi")
        assert payload["assigned_to"] == "B"

    def test_none_maps_to_None(self):
        payload = self._run(None)
        assert payload["assigned_to"] is None

    def test_invalid_value_raises(self):
        import db
        with pytest.raises(ValueError):
            db.set_assignment("item-1", "Otro")


# ---------------------------------------------------------------------------
# db._wrap() — detección de errores de red
# ---------------------------------------------------------------------------

class TestWrap:
    def test_reraises_connection_error_as_is(self):
        import db
        with pytest.raises(db.ConnectionError):
            db._wrap(lambda: (_ for _ in ()).throw(db.ConnectionError("ya es ConnectionError")))

    def test_wraps_timeout_in_connection_error(self):
        import db
        def _raise():
            raise Exception("connection timeout")
        with pytest.raises(db.ConnectionError, match="Supabase"):
            db._wrap(_raise)

    def test_passes_through_unrelated_exceptions(self):
        import db
        def _raise():
            raise ValueError("algo raro")
        with pytest.raises(ValueError, match="algo raro"):
            db._wrap(_raise)
