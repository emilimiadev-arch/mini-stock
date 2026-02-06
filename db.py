import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import create_client


def client():
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not supabase_anon_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment.")
    return create_client(supabase_url, supabase_anon_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ping() -> int:
    sb = client()
    res = sb.table("items").select("id").limit(1).execute()
    return len(res.data or [])


# -------------------------
# Items CRUD
# -------------------------
def list_items() -> List[Dict[str, Any]]:
    sb = client()
    res = sb.table("items").select("*").order("created_at", desc=False).execute()
    data = res.data or []
    # Map stored assignment codes ('A'/'B') to UI labels ('Redo'/'Emi')
    for row in data:
        at = row.get("assigned_to")
        if at == "A":
            row["assigned_to"] = "Redo"
        elif at == "B":
            row["assigned_to"] = "Emi"
        else:
            row["assigned_to"] = None
    return data


def add_item(name: str, description: str, price_a: float, price_b: float) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required.")

    sb = client()
    payload = {
        "name": name,
        "description": (description or "").strip() or None,
        "price_a": float(price_a or 0),
        "price_b": float(price_b or 0),
        "assigned_to": None,
        "updated_at": _now_iso(),
    }
    sb.table("items").insert(payload).execute()


def update_item(item_id: str, name: str, description: str, price_a: float, price_b: float) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required.")

    sb = client()
    payload = {
        "name": name,
        "description": (description or "").strip() or None,
        "price_a": float(price_a or 0),
        "price_b": float(price_b or 0),
        "updated_at": _now_iso(),
    }
    sb.table("items").update(payload).eq("id", item_id).execute()


def delete_item(item_id: str) -> None:
    sb = client()
    sb.table("items").delete().eq("id", item_id).execute()


def set_assignment(item_id: str, assigned_to: Optional[str]) -> None:
    """
    assigned_to: 'Redo', 'Emi', or None (unassign)
    """
    if assigned_to not in ("Redo", "Emi", None):
        raise ValueError("assigned_to must be 'Redo', 'Emi', or None.")

    # Map UI labels to stored codes expected by the DB constraint
    if assigned_to == "Redo":
        db_value = "A"
    elif assigned_to == "Emi":
        db_value = "B"
    else:
        db_value = None

    sb = client()
    payload = {"assigned_to": db_value, "updated_at": _now_iso()}
    sb.table("items").update(payload).eq("id", item_id).execute()

def clear_assignments() -> None:
    sb = client()
    payload = {"assigned_to": None, "updated_at": _now_iso()}
    sb.table("items").update(payload).neq("assigned_to", None).execute()
