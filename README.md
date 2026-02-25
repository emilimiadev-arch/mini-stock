# 🎸 Inventario

App para repartir equitativamente instrumentos y efectivo entre dos socios (Redo y Emi).

Hecha con [Streamlit](https://streamlit.io/) y [Supabase](https://supabase.com/).

## Setup local

### 1. Clonar y crear entorno virtual

```bash
git clone <repo-url>
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los valores reales:

| Variable | Descripción |
|---|---|
| `SUPABASE_URL` | URL del proyecto en Supabase |
| `SUPABASE_ANON_KEY` | Anon/public key del proyecto |
| `APP_PASSWORD` | Contraseña opcional para proteger la app |

### 3. Correr la app

```bash
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

1. Hacer push del código a un repositorio de GitHub (el `.env` **nunca** debe subirse al repo)
2. Ir a [share.streamlit.io](https://share.streamlit.io) y conectar el repo
3. En *Advanced settings → Secrets*, agregar las variables de entorno en formato TOML:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "eyXXXX..."
APP_PASSWORD = "tu-contraseña"
```

4. Hacer deploy — Streamlit Community Cloud es gratuito para repos públicos y privados.

## Estructura

```
app.py          # UI (Streamlit)
db.py           # Capa de datos (Supabase)
requirements.txt
.env.example
tests/
  test_db.py    # Tests unitarios (db.py)
  test_app.py   # Tests de lógica de negocio (app.py)
```

## Tests

```bash
pip install pytest pytest-mock
pytest tests/
```
