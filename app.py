import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import db
import prices as px

# Load .env from the same folder as this file (local dev)
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

st.set_page_config(page_title="Inventory Split", page_icon="🎸", layout="wide")
st.title("🎸 Inventario")

# Mobile-friendly: stack columns vertically on small screens
st.markdown("""
<style>
@media (max-width: 768px) {
    /* Stack all Streamlit columns vertically */
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    /* Give number inputs more breathing room */
    [data-testid="stNumberInput"] { margin-bottom: 0.5rem; }
    /* Make metric boxes full-width */
    [data-testid="metric-container"] { width: 100% !important; }
}
</style>
""", unsafe_allow_html=True)

# Simple password gate
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        with st.sidebar:
            st.caption("Acceso")
            pwd = st.text_input("Contraseña", type="password")
        if pwd != APP_PASSWORD:
            if pwd:
                st.warning("Contraseña incorrecta.")
            else:
                st.info("Ingresá la contraseña para continuar.")
            st.stop()
        else:
            st.session_state["authenticated"] = True
            st.rerun()



def check_connection() -> bool:
    try:
        db.ping()
        return True
    except db.ConnectionError as e:
        st.error(f"⚠️ Sin conexión con la base de datos: {e}")
        return False
    except Exception as e:
        st.error(f"⚠️ Error inesperado al conectar: {e}")
        return False


if not check_connection():
    st.stop()


def calc_avg_value(row) -> float:
    a = float(row.get("price_a") or 0)
    b = float(row.get("price_b") or 0)
    q = float(row.get("quantity") or 1)
    return q * (a + b) / 2.0


def auto_assign_all(df_all: pd.DataFrame) -> None:
    """Greedy: asigna los items sin asignar balanceando por avg_value."""
    unassigned = df_all[df_all["assigned_to"].isna()].copy()
    if unassigned.empty:
        return

    assigned_a = df_all[df_all["assigned_to"] == "Redo"].copy()
    assigned_b = df_all[df_all["assigned_to"] == "Emi"].copy()
    running_a = float(assigned_a["avg_value"].sum()) if not assigned_a.empty else 0.0
    running_b = float(assigned_b["avg_value"].sum()) if not assigned_b.empty else 0.0

    unassigned = unassigned.sort_values("avg_value", ascending=False)
    for _, r in unassigned.iterrows():
        if running_a <= running_b:
            db.set_assignment(r["id"], "Redo")
            running_a += float(r["avg_value"] or 0)
        else:
            db.set_assignment(r["id"], "Emi")
            running_b += float(r["avg_value"] or 0)


def load_items_df() -> pd.DataFrame:
    items = db.list_items()
    if not items:
        return pd.DataFrame(columns=["id", "name", "description", "price_a", "price_b", "assigned_to"])
    df = pd.DataFrame(items)
    df["avg_value"] = df.apply(calc_avg_value, axis=1)
    return df


def rerun():
    st.rerun()


# -------------------------
# Agregar instrumento
# -------------------------
with st.expander("➕ Agregar instrumento", expanded=False):
    c1, c2 = st.columns([2, 3])
    with c1:
        name = st.text_input("Nombre")
    with c2:
        description = st.text_input("Descripción (opcional)")
    c3, c4, c5 = st.columns([1, 1, 2])
    with c3:
        price_a = st.number_input("Precio estimado (Redo) - USD", min_value=0.0, step=10.0, value=0.0)
    with c4:
        price_b = st.number_input("Precio estimado (Emi) - USD", min_value=0.0, step=10.0, value=0.0)
    with c5:
        st.write("")
        st.write("")
        if st.button("Agregar", type="primary"):
            try:
                db.add_item(name, description, price_a, price_b)
                st.success("Instrumento agregado.")
                rerun()
            except Exception as e:
                st.error(str(e))

st.divider()

# -------------------------
# Tabla editable
# -------------------------
df = load_items_df()

if df.empty:
    st.info("Todavía no hay instrumentos cargados.")
else:
    edit_df = df[["id", "name", "description", "price_a", "price_b", "avg_value", "assigned_to"]].copy()
    edit_df["description"] = edit_df["description"].fillna("")
    edit_df["Eliminar"] = False

    edited = st.data_editor(
        edit_df,
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("Nombre", required=True),
            "description": st.column_config.TextColumn("Descripción"),
            "price_a": st.column_config.NumberColumn("Precio Redo (USD)", min_value=0.0, step=10.0, format="$%.2f"),
            "price_b": st.column_config.NumberColumn("Precio Emi (USD)", min_value=0.0, step=10.0, format="$%.2f"),
            "avg_value": st.column_config.NumberColumn("Promedio (USD)", disabled=True, format="$%.2f"),
            "assigned_to": st.column_config.SelectboxColumn("Asignado a", options=["Redo", "Emi"], required=False),
            "Eliminar": st.column_config.CheckboxColumn("Eliminar"),
        },
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
    )

    st.caption("Editá celdas directamente · marcá 'Eliminar' para borrar · el promedio se actualiza al guardar.")

    if st.button("Guardar cambios", type="primary"):
        try:
            for _, row in edited[edited["Eliminar"]].iterrows():
                db.delete_item(row["id"])

            for _, new in edited[~edited["Eliminar"]].iterrows():
                orig_rows = df[df["id"] == new["id"]]
                if orig_rows.empty:
                    continue
                orig = orig_rows.iloc[0]

                if (new["name"] != orig["name"] or
                        new["description"] != (orig.get("description") or "") or
                        float(new["price_a"]) != float(orig.get("price_a") or 0) or
                        float(new["price_b"]) != float(orig.get("price_b") or 0)):
                    db.update_item(new["id"], new["name"], new["description"] or "",
                                   float(new["price_a"]), float(new["price_b"]))

                new_assigned = new["assigned_to"] if new["assigned_to"] in ("Redo", "Emi") else None
                if new_assigned != orig.get("assigned_to"):
                    db.set_assignment(new["id"], new_assigned)

        except Exception as e:
            st.error(str(e))
        else:
            st.success("Cambios guardados.")
            rerun()

# -------------------------
# Caja
# -------------------------
st.divider()
st.markdown("### Caja")

usd_prices = px.get_prices()

# Precios en tiempo real
col_btc, col_eth, col_ada, col_ars = st.columns(4)
col_btc.metric("Precio BTC", f"${usd_prices.get('BTC', 0):,.0f}" if usd_prices.get('BTC') else "—")
col_eth.metric("Precio ETH", f"${usd_prices.get('ETH', 0):,.0f}" if usd_prices.get('ETH') else "—")
col_ada.metric("Precio ADA", f"${usd_prices.get('ADA', 0):,.4f}" if usd_prices.get('ADA') else "—")
ars_rate = 1 / usd_prices["ARS"] if usd_prices.get("ARS") else 0
col_ars.metric("Precio USD Blue", f"${ars_rate:,.0f} ARS" if ars_rate else "—")

with st.expander("➕ Agregar ítem de caja", expanded=False):
    cc1, cc2, cc3 = st.columns([1, 1, 1])
    with cc1:
        new_currency = st.selectbox("Moneda", px.CURRENCIES, key="new_cash_currency")
    with cc2:
        new_amount = st.number_input("Monto", min_value=0.0, value=0.0, format="%.8g", key="new_cash_amount")
    with cc3:
        st.write("")
        st.write("")
        if st.button("Agregar", type="primary", key="add_cash_btn"):
            try:
                db.add_cash(new_currency, new_currency, new_amount)
                st.success("Ítem agregado.")
                rerun()
            except Exception as e:
                st.error(str(e))

cash_items = db.list_cash()
cash_df = pd.DataFrame(cash_items) if cash_items else pd.DataFrame(
    columns=["id", "label", "currency", "amount", "assigned_to"]
)

if not cash_df.empty:
    cash_df["amount_usd"] = cash_df.apply(
        lambda r: px.to_usd(float(r["amount"] or 0), r["currency"], usd_prices), axis=1
    )
else:
    cash_df["amount_usd"] = []

cash_edit_df = cash_df[["id", "currency", "amount", "amount_usd", "assigned_to"]].copy() \
    if not cash_df.empty else \
    pd.DataFrame(columns=["id", "currency", "amount", "amount_usd", "assigned_to"])
cash_edit_df["🗑️"] = False

cash_edited = st.data_editor(
    cash_edit_df,
    column_config={
        "id": None,
        "currency": st.column_config.SelectboxColumn("Moneda", options=px.CURRENCIES, required=True),
        "amount": st.column_config.NumberColumn("Monto", min_value=0.0, format="%.8g"),
        "amount_usd": st.column_config.NumberColumn("Valor USD", disabled=True, format="$%.2f"),
        "assigned_to": st.column_config.SelectboxColumn("Asignado a", options=["Redo", "Emi"], required=False),
        "Eliminar": st.column_config.CheckboxColumn("Eliminar"),
    },
    num_rows="fixed",
    hide_index=True,
    use_container_width=True,
)

st.caption("Editá celdas directamente · marcá 'Eliminar' para borrar · el valor USD se actualiza al guardar.")

if st.button("Guardar caja", type="primary"):
    try:
        for _, row in cash_edited[cash_edited["Eliminar"]].iterrows():
            db.delete_cash(row["id"])

        for _, new in cash_edited[~cash_edited["Eliminar"]].iterrows():
            orig_rows = cash_df[cash_df["id"] == new["id"]] if not cash_df.empty else pd.DataFrame()
            if orig_rows.empty:
                currency = new.get("currency") or "USD"
                if currency:
                    db.add_cash(currency, currency, float(new.get("amount") or 0))
                continue
            orig = orig_rows.iloc[0]

            if (new["currency"] != orig["currency"] or
                    float(new["amount"]) != float(orig["amount"] or 0)):
                db.update_cash(new["id"], new["currency"], new["currency"], float(new["amount"]))

            new_assigned = new["assigned_to"] if new["assigned_to"] in ("Redo", "Emi") else None
            if new_assigned != orig.get("assigned_to"):
                db.set_cash_assignment(new["id"], new_assigned)

    except Exception as e:
        st.error(str(e))
    else:
        st.success("Caja guardada.")
        rerun()

# -------------------------
# Resumen del reparto
# -------------------------
st.divider()
st.markdown("### Resumen del reparto")

# Totales instrumentos
inst_a = float(df[df["assigned_to"] == "Redo"]["avg_value"].sum()) if not df.empty else 0.0
inst_b = float(df[df["assigned_to"] == "Emi"]["avg_value"].sum()) if not df.empty else 0.0
inst_u = int(df["assigned_to"].isna().sum()) if not df.empty else 0

# Totales caja
cash_a = sum(px.to_usd(float(r["amount"] or 0), r["currency"], usd_prices)
             for r in cash_items if r.get("assigned_to") == "Redo")
cash_b = sum(px.to_usd(float(r["amount"] or 0), r["currency"], usd_prices)
             for r in cash_items if r.get("assigned_to") == "Emi")
cash_u = sum(1 for r in cash_items if not r.get("assigned_to"))

total_a = inst_a + cash_a
total_b = inst_b + cash_b
diff = total_a - total_b

c1, c2, c3 = st.columns(3)
c1.metric("Total Redo", f"${total_a:,.2f}")
c2.metric("Total Emi", f"${total_b:,.2f}")
c3.metric("Diferencia Redo−Emi", f"${diff:,.2f}")

col_btn, col_status = st.columns([1, 3])
with col_btn:
    if not df.empty and st.button("Sugerir reparto automático"):
        try:
            auto_assign_all(df)
            st.success("Asignación completada.")
            rerun()
        except Exception as e:
            st.error(str(e))
    if st.button("Resetear asignaciones"):
        try:
            db.clear_assignments()
            st.success("Asignaciones reseteadas.")
            rerun()
        except Exception as e:
            st.error(str(e))
with col_status:
    unassigned_total = inst_u + cash_u
    if unassigned_total > 0:
        st.warning(f"{unassigned_total} ítem(s) sin asignar.")
    elif diff > 0:
        st.info(f"Redo lleva ${diff:,.2f} más que Emi.")
    elif diff < 0:
        st.info(f"Emi lleva ${abs(diff):,.2f} más que Redo.")
    else:
        st.success("Reparto equilibrado.")
