# PALMETTO

PALMETTO is an AI-assisted flood decision-intelligence platform for Charleston, South Carolina. It is being developed to combine authoritative environmental and infrastructure data with deterministic risk analysis, with an AI agent planned for a later stage. This initial checkpoint retrieves and normalizes NOAA CO-OPS water-level observations and tide predictions.

## Current architecture

- `backend/app/routes/` exposes the API endpoints.
- `backend/app/services/noaa.py` retrieves NOAA CO-OPS data and normalizes its responses.
- `backend/app/models/tide.py` defines PALMETTO-owned response models with source and station provenance.
- `backend/tests/` tests API behavior with mocked NOAA responses; tests do not require NOAA to be online.

## Local backend setup

From the `palmetto` project root, create and activate a virtual environment, then install the backend requirements:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the development server from `backend` with:

```powershell
uvicorn app.main:app --reload
```

The NOAA station defaults to `8665530` (Charleston, South Carolina). Override it with the `PALMETTO_NOAA_STATION_ID` environment variable. The service requests English units, Charleston local time (`lst_ldt`), and the `MLLW` datum by default.

## Implemented endpoints

- `GET /api/health` reports API health.
- `GET /api/tides/current` returns the latest usable water-level observation in the requested recent date window.
- `GET /api/tides/today` returns today's high/low tide predictions in chronological order.

PALMETTO currently provides decision-support research and prototype functionality. It is not an emergency warning system and must not be relied upon for emergency response or evacuation decisions.