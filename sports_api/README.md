# Kyre Sports API

Private sports-data and analytics backend for the Streamlit app.

## Current foundation

- FastAPI application
- Root status endpoint: `/`
- Health endpoint: `/health`
- Automatic API docs: `/docs`
- Modular packages for collectors, database, models, simulation, and validation

## Run locally

From the repository root:

```bash
pip install -r sports_api/requirements.txt
uvicorn sports_api.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Architecture

```text
sports_api/
├── api/
├── collectors/
├── database/
├── models/
├── simulation/
├── validation/
├── main.py
└── requirements.txt
```

This foundation is intentionally isolated from the existing Streamlit application so API work can be developed and tested without changing the production app.
