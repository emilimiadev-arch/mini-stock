"""Tests para la lógica de negocio de app.py (calc_avg_value, auto_assign_all)."""

import pytest
import pandas as pd

# Importamos directamente las funciones sin levantar Streamlit
# Usamos importlib para evitar ejecutar el módulo completo
import importlib, sys, types


def _load_logic():
    """
    Extrae calc_avg_value y auto_assign_all de app.py sin ejecutar Streamlit.
    Devuelve un namespace con ambas funciones.
    """
    # Stub de streamlit para que el import de app no falle
    st_stub = types.ModuleType("streamlit")
    for attr in ["set_page_config", "title", "markdown", "sidebar", "stop",
                 "warning", "error", "success", "info", "subheader", "divider",
                 "caption", "write", "dataframe", "download_button", "metric",
                 "expander", "container", "columns", "text_input", "number_input",
                 "button", "selectbox", "rerun"]:
        setattr(st_stub, attr, lambda *a, **kw: None)

    # sidebar necesita atributos extra
    sidebar = types.SimpleNamespace(
        radio=lambda *a, **kw: "Instrumentos",
        caption=lambda *a, **kw: None,
        text_input=lambda *a, **kw: "",
    )
    st_stub.sidebar = sidebar

    sys.modules.setdefault("streamlit", st_stub)
    sys.modules.setdefault("db", types.ModuleType("db"))
    sys.modules.setdefault("pandas", pd)

    # Leer y compilar solo las funciones que nos interesan
    import ast, pathlib
    src = pathlib.Path(__file__).parent.parent / "app.py"
    tree = ast.parse(src.read_text())

    target_funcs = {"calc_avg_value", "auto_assign_all"}
    ns: dict = {"pd": pd, "__builtins__": __builtins__}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_funcs:
            mod = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(mod)
            exec(compile(mod, str(src), "exec"), ns)  # noqa: S102

    return ns


_ns = _load_logic()
calc_avg_value = _ns["calc_avg_value"]
auto_assign_all = _ns.get("auto_assign_all")  # puede no estar si el nombre cambió


# ---------------------------------------------------------------------------
# calc_avg_value
# ---------------------------------------------------------------------------

class TestCalcAvgValue:
    def _row(self, price_a, price_b, quantity=1):
        return {"price_a": price_a, "price_b": price_b, "quantity": quantity}

    def test_basic_average(self):
        assert calc_avg_value(self._row(100, 200)) == pytest.approx(150.0)

    def test_with_quantity(self):
        # quantity=2, avg_price=150 → 300
        assert calc_avg_value(self._row(100, 200, quantity=2)) == pytest.approx(300.0)

    def test_zero_prices(self):
        assert calc_avg_value(self._row(0, 0)) == pytest.approx(0.0)

    def test_none_price_a_treated_as_zero(self):
        assert calc_avg_value(self._row(None, 200)) == pytest.approx(100.0)

    def test_none_price_b_treated_as_zero(self):
        assert calc_avg_value(self._row(100, None)) == pytest.approx(50.0)

    def test_none_quantity_defaults_to_one(self):
        assert calc_avg_value({"price_a": 100, "price_b": 200, "quantity": None}) == pytest.approx(150.0)

    def test_equal_prices(self):
        assert calc_avg_value(self._row(500, 500)) == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# auto_assign_all (greedy algorithm)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(auto_assign_all is None, reason="auto_assign_all not found in app.py")
class TestAutoAssignAll:
    """
    Testea el algoritmo greedy de asignación directamente, mockeando db.set_assignment.
    auto_assign_all fue extraída via AST, así que 'db' no está en su __globals__.
    Lo inyectamos con un stub antes de cada test.
    """

    def _make_df(self, items):
        """items: list of (id, avg_value, assigned_to)"""
        return pd.DataFrame([
            {"id": i, "avg_value": v, "assigned_to": a}
            for i, v, a in items
        ])

    def _run(self, df, calls_store):
        """Ejecuta auto_assign_all con un stub de db inyectado en su namespace."""
        import types
        db_stub = types.ModuleType("db")
        db_stub.set_assignment = lambda iid, who: calls_store.append((iid, who))
        _ns["db"] = db_stub
        try:
            auto_assign_all(df)
        finally:
            _ns.pop("db", None)

    def test_assigns_all_unassigned(self):
        calls = []
        df = self._make_df([("a", 100, None), ("b", 80, None), ("c", 60, None)])
        self._run(df, calls)
        assert {c[0] for c in calls} == {"a", "b", "c"}

    def test_balanced_distribution(self):
        calls = []
        df = self._make_df([("a", 200, None), ("b", 100, None), ("c", 100, None)])
        self._run(df, calls)
        by_id = {iid: who for iid, who in calls}
        items = {"a": 200, "b": 100, "c": 100}
        total_redo = sum(v for i, v in items.items() if by_id.get(i) == "Redo")
        total_emi = sum(v for i, v in items.items() if by_id.get(i) == "Emi")
        assert abs(total_redo - total_emi) <= 200

    def test_skips_already_assigned(self):
        calls = []
        df = self._make_df([("a", 100, "Redo"), ("b", 80, None)])
        self._run(df, calls)
        assert [c[0] for c in calls] == ["b"]

    def test_no_unassigned_makes_no_calls(self):
        calls = []
        df = self._make_df([("a", 100, "Redo"), ("b", 80, "Emi")])
        self._run(df, calls)
        assert calls == []
