import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import db

# Load .env from the same folder as this file (local dev)
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

st.set_page_config(page_title="Inventory Split", page_icon="🎸", layout="wide")
st.title("🎸 Inventario")

# Simple password gate (for now)
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
if APP_PASSWORD:
    with st.sidebar:
        st.caption("Access")
        pwd = st.text_input("Password", type="password")
    if pwd != APP_PASSWORD:
        st.warning("Enter password to continue.")
        st.stop()

page = st.sidebar.radio("Navigate", ["Instrumentos", "Repartija", "Resumen"], index=0)


def calc_avg_value(row) -> float:
    a = float(row.get("price_a") or 0)
    b = float(row.get("price_b") or 0)
    q = float(row.get("quantity") or 1)
    return q * (a + b) / 2.0


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
# Instrumentos (CRUD)
# -------------------------
if page == "Instrumentos":
    st.subheader("Instrumentos")

    with st.expander("➕ Agregar instrumento", expanded=True):
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
    st.markdown("### Lista de instrumentos")

    df = load_items_df()
    if df.empty:
        st.info("Todavía no hay instrumentos cargados.")
    else:
        # Display table
        view = df.copy()
        view = view.rename(columns={
            "name": "Instrumento",
            "description": "Descripción",
            "price_a": "Precio Redo (USD)",
            "price_b": "Precio Emi (USD)",
            "avg_value": "Promedio (USD)",
            "assigned_to": "Asignado a",
        })
        view["Asignado a"] = view["Asignado a"].fillna("—")
        st.dataframe(view[["Instrumento", "Descripción", "Precio Redo (USD)", "Precio Emi (USD)", "Promedio (USD)", "Asignado a"]], width="stretch")

        st.caption("Tip: abajo podés editar y eliminar instrumentos individualmente.")

        for _, row in df.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([2, 3])
                with col1:
                    new_name = st.text_input("Nombre", value=row["name"], key=f"name_{row['id']}")
                with col2:
                    new_desc = st.text_input("Descripción", value=row.get("description") or "", key=f"desc_{row['id']}")

                col3, col4, col5, col6 = st.columns([1, 1, 1, 1])
                with col3:
                    new_a = st.number_input("Precio Redo (USD)", min_value=0.0, step=10.0, value=float(row.get("price_a") or 0), key=f"a_{row['id']}")
                with col4:
                    new_b = st.number_input("Precio Emi (USD)", min_value=0.0, step=10.0, value=float(row.get("price_b") or 0), key=f"b_{row['id']}")
                with col5:
                    st.metric("Promedio", f"${(new_a + new_b)/2:,.2f}")
                with col6:
                    st.write("")
                    if st.button("Guardar cambios", key=f"save_{row['id']}", type="primary"):
                        try:
                            db.update_item(row["id"], new_name, new_desc, new_a, new_b)
                            st.success("Actualizado.")
                            rerun()
                        except Exception as e:
                            st.error(str(e))

                col7, col8 = st.columns([1, 6])
                with col7:
                    if st.button("Eliminar", key=f"del_{row['id']}"):
                        try:
                            db.delete_item(row["id"])
                            st.success("Eliminado.")
                            rerun()
                        except Exception as e:
                            st.error(str(e))

# -------------------------
# Placeholder pages (next step)
# -------------------------
elif page == "Repartija":
    st.subheader("Repartija (equidad por promedio)")

    df = load_items_df()

    if df.empty:
        st.info("Primero cargá instrumentos en la sección 'Instrumentos'.")
        st.stop()

    # Totals by assignment
    df_assigned_a = df[df["assigned_to"] == "Redo"].copy()
    df_assigned_b = df[df["assigned_to"] == "Emi"].copy()
    total_a = float(df_assigned_a["avg_value"].sum()) if not df_assigned_a.empty else 0.0
    total_b = float(df_assigned_b["avg_value"].sum()) if not df_assigned_b.empty else 0.0
    diff = total_a - total_b  # positive means Redo has more
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    c1.metric("Total Redo (promedio)", f"${total_a:,.2f}")
    c2.metric("Total Emi (promedio)", f"${total_b:,.2f}")
    c3.metric("Diferencia Redo-Emi", f"${diff:,.2f}")

    def auto_assign_all(df_all: pd.DataFrame) -> None:
        # Work with unassigned only
        unassigned = df_all[df_all["assigned_to"].isna()].copy()
        if unassigned.empty:
            st.info("No hay instrumentos sin asignar.")
            return

        # Current totals
        assigned_a = df_all[df_all["assigned_to"] == "Redo"].copy()
        assigned_b = df_all[df_all["assigned_to"] == "Emi"].copy()
        running_a = float(assigned_a["avg_value"].sum()) if not assigned_a.empty else 0.0
        running_b = float(assigned_b["avg_value"].sum()) if not assigned_b.empty else 0.0

        # Greedy: assign most expensive first to the side that is behind
        unassigned = unassigned.sort_values("avg_value", ascending=False)

        updates = []
        for _, r in unassigned.iterrows():
            if running_a <= running_b:
                updates.append((r["id"], "Redo"))
                running_a += float(r["avg_value"] or 0)
            else:
                updates.append((r["id"], "Emi"))
                running_b += float(r["avg_value"] or 0)

        # Apply updates
        for item_id, who in updates:
            db.set_assignment(item_id, who)


    with st.expander("🤖 Asignación automática", expanded=False):
        st.write("Asigna automáticamente todos los instrumentos sin asignar para balancear usando el promedio.")
        if st.button("Sugerir reparto (asignar todo)", type="primary"):
            try:
                auto_assign_all(df)
                st.success("Asignación automática completada.")
                rerun()
            except Exception as e:
                st.error(str(e))
    
    # Simple balance indicator
    # If diff > 0 => Redo is ahead, so Emi should receive next.
    if diff > 0:
        st.info("Balance actual: Redo lleva más (según promedio). Para equilibrar, asignar el próximo ítem a Emi.")
    elif diff < 0:
        st.info("Balance actual: Emi lleva más (según promedio). Para equilibrar, asignar el próximo ítem a Redo.")
    else:
        st.success("Balance actual: perfecto (según promedio).")

    st.divider()

    # Filters
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        query = st.text_input("Buscar instrumento", placeholder="Nombre o descripción...")
    with f2:
        show = st.selectbox("Mostrar", ["Todos", "Solo sin asignar", "Asignados a Redo", "Asignados a Emi"])
    with f3:
        sort = st.selectbox("Orden", ["Nombre (A-Z)", "Promedio (desc)", "Promedio (asc)"])

    view = df.copy()
    if query:
        q = query.lower().strip()
        view = view[
            view["name"].str.lower().str.contains(q)
            | view["description"].fillna("").str.lower().str.contains(q)
        ]

    if show == "Solo sin asignar":
        view = view[view["assigned_to"].isna()]
    elif show == "Asignados a Redo":
        view = view[view["assigned_to"] == "Redo"]
    elif show == "Asignados a Emi":
        view = view[view["assigned_to"] == "Emi"]

    if sort == "Nombre (A-Z)":
        view = view.sort_values("name", ascending=True)
    elif sort == "Promedio (desc)":
        view = view.sort_values("avg_value", ascending=False)
    elif sort == "Promedio (asc)":
        view = view.sort_values("avg_value", ascending=True)

    st.markdown("### Asignación por instrumento")
    st.caption("Asigná cada instrumento a Redo o Emi. El balance se calcula usando el promedio de las valuaciones Redo y Emi.")

    # Optional: reset assignments
    with st.expander("⚙️ Opciones", expanded=False):
        if st.button("Resetear todas las asignaciones"):
            try:
                db.clear_assignments()
                st.success("Asignaciones reseteadas.")
                rerun()
            except Exception as e:
                st.error(str(e))

    # Cards
    for _, row in view.iterrows():
        avg_value = float(row["avg_value"] or 0)
        assigned = row["assigned_to"] or "—"

        with st.container(border=True):
            left, right = st.columns([3, 2])

            with left:
                st.markdown(f"**{row['name']}**")
                if row.get("description"):
                    st.write(row["description"])

                cc1, cc2, cc3 = st.columns([1, 1, 1])
                cc1.write(f"**A:** ${float(row.get('price_a') or 0):,.2f}")
                cc2.write(f"**B:** ${float(row.get('price_b') or 0):,.2f}")
                cc3.write(f"**Promedio:** ${avg_value:,.2f}")

            with right:
                st.write(f"**Asignado a:** {assigned}")
                b1, b2, b3 = st.columns([1, 1, 1])
                with b1:
                    if st.button("Asignar a Redo", key=f"asA_{row['id']}"):
                        try:
                            db.set_assignment(row["id"], "Redo")
                            rerun()
                        except Exception as e:
                            st.error(str(e))
                with b2:
                    if st.button("Asignar a Emi", key=f"asB_{row['id']}"):
                        try:
                            db.set_assignment(row["id"], "Emi")
                            rerun()
                        except Exception as e:
                            st.error(str(e))
                with b3:
                    if st.button("Quitar", key=f"un_{row['id']}"):
                        try:
                            db.set_assignment(row["id"], None)
                            rerun()
                        except Exception as e:
                            st.error(str(e))

elif page == "Resumen":
    st.subheader("Resumen")

    df = load_items_df()
    if df.empty:
        st.info("No hay instrumentos cargados todavía.")
        st.stop()

    df_a = df[df["assigned_to"] == "Redo"].copy()
    df_b = df[df["assigned_to"] == "Emi"].copy()
    df_u = df[df["assigned_to"].isna()].copy()

    total_a = float(df_a["avg_value"].sum()) if not df_a.empty else 0.0
    total_b = float(df_b["avg_value"].sum()) if not df_b.empty else 0.0
    diff = total_a - total_b

    c1, c2, c3 = st.columns([1, 1, 1])
    c1.metric("Total Redo (promedio)", f"${total_a:,.2f}")
    c2.metric("Total Emi (promedio)", f"${total_b:,.2f}")
    c3.metric("Diferencia Redo-Emi", f"${diff:,.2f}")

    st.divider()

    def prep_export(dfx: pd.DataFrame) -> pd.DataFrame:
        out = dfx.copy()
        out["avg_value"] = out["avg_value"].astype(float)
        out = out.rename(columns={
            "name": "item",
            "description": "description",
            "price_a": "price_a_usd",
            "price_b": "price_b_usd",
            "avg_value": "avg_value_usd",
            "assigned_to": "assigned_to",
        })
        cols = ["item", "description", "price_a_usd", "price_b_usd", "avg_value_usd", "assigned_to"]
        return out[cols]

    left, right = st.columns(2)

    with left:
        st.markdown("### Asignados a Redo")
        if df_a.empty:
            st.write("—")
        else:
            view_a = df_a.rename(columns={
                "name": "Instrumento", "description": "Descripción",
                "price_a": "Precio Redo", "price_b": "Precio Emi", "avg_value": "Promedio"
            })
            st.dataframe(view_a[["Instrumento", "Descripción", "Precio Redo", "Precio Emi", "Promedio"]], width="stretch")

            csv_a = prep_export(df_a).to_csv(index=False).encode("utf-8")
            st.download_button("Descargar CSV (Redo)", data=csv_a, file_name="asignados_Redo.csv", mime="text/csv")

    with right:
        st.markdown("### Asignados a Emi")
        if df_b.empty:
            st.write("—")
        else:
            view_b = df_b.rename(columns={
                "name": "Instrumento", "description": "Descripción",
                "price_a": "Precio Redo", "price_b": "Precio Emi", "avg_value": "Promedio"
            })
            st.dataframe(view_b[["Instrumento", "Descripción", "Precio Redo", "Precio Emi", "Promedio"]], width="stretch")

            csv_b = prep_export(df_b).to_csv(index=False).encode("utf-8")
            st.download_button("Descargar CSV (Emi)", data=csv_b, file_name="asignados_Emi.csv", mime="text/csv")

    st.divider()
    st.markdown("### Sin asignar")
    if df_u.empty:
        st.success("No hay instrumentos sin asignar.")
    else:
        view_u = df_u.rename(columns={
            "name": "Instrumento", "description": "Descripción",
            "price_a": "Precio Redo", "price_b": "Precio Emi", "avg_value": "Promedio"
        })
        st.dataframe(view_u[["Instrumento", "Descripción", "Precio Redo", "Precio Emi", "Promedio"]], width="stretch")

        csv_u = prep_export(df_u).to_csv(index=False).encode("utf-8")
        st.download_button("Descargar CSV (sin asignar)", data=csv_u, file_name="sin_asignar.csv", mime="text/csv")
