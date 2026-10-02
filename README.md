# PALMETTO

PALMETTO is an AI-assisted flood decision-intelligence platform for Charleston, South Carolina. It collects and normalizes authoritative environmental and infrastructure evidence, then combines that evidence in a transparent deterministic prototype assessment. PALMETTO currently retrieves NOAA CO-OPS water levels and tides, National Weather Service forecasts and alerts, and City of Charleston GIS road impacts. It does not use an LLM to calculate risk.

## Current architecture

- `backend/app/routes/` exposes the API endpoints.
- `backend/app/services/` retrieves NOAA, NWS, and Charleston GIS data and normalizes provider responses.
- `backend/app/services/risk.py` scores normalized evidence using deterministic PALMETTO prototype rules. Retrieval and scoring remain separate.
- `backend/app/models/` defines PALMETTO-owned response models with source provenance.
- `backend/tests/` tests API behavior with mocked external responses; tests do not require provider APIs to be online.

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

NOAA uses station `8665530` by default; override it with `PALMETTO_NOAA_STATION_ID`. NWS point discovery defaults to downtown Charleston (`32.7765, -79.9311`); override it with `PALMETTO_NWS_LATITUDE` and `PALMETTO_NWS_LONGITUDE`. Tide requests use English units, Charleston local time (`lst_ldt`), and `MLLW` by default.

## Implemented endpoints

- `GET /api/health` reports API health.
- `GET /api/tides/current` returns the latest usable water-level observation in the requested recent date window.
- `GET /api/tides/today` returns today's high/low tide predictions in chronological order.
- `GET /api/weather/hourly` returns up to 24 NWS hourly forecast periods, including precipitation probability when supplied.
- `GET /api/weather/precipitation` returns NWS quantitative precipitation intervals when available; it does not derive amounts from precipitation probability.
- `GET /api/weather/alerts` returns active NWS alerts for the configured point.
- `GET /api/roads/impacts` returns active road closures, emergency closures, and detours from City of Charleston GIS layers 1, 5, and 2.
- `GET /api/risk/current` returns the current structured PALMETTO Charleston flood-risk assessment and component explanations.

## PALMETTO Flood Risk Engine

The risk engine sums five deterministic weighted components: water level (30), tide (20), precipitation (20), weather alerts (15), and road impacts (15), for a maximum score of 100. Prototype score bands are 0-19 LOW, 20-39 MODERATE, 40-69 HIGH, and 70-100 SEVERE. Component scores, explanations, provenance, contributing factors, and evidence limitations are returned in the assessment.

Water-level and tide thresholds default to 4, 5, and 6 feet relative to MLLW; upcoming quantitative precipitation thresholds default to 10, 25, 50, and 75 mm over selected intervals. A NOAA reading older than the configurable three-hour prototype freshness limit is not scored as current. These are centralized, configurable PALMETTO prototype thresholds and freshness rules, not authoritative NOAA thresholds or validated rainfall/flood thresholds. If quantitative precipitation is unavailable, precipitation probability may add a small context score but is never converted into rainfall amount.

Unavailable evidence is represented on each component and listed in `unavailable_sources`. The numeric score is the subtotal of available component evidence. If any component is incomplete or unavailable, the overall evidence status is PARTIAL or UNAVAILABLE and the categorical `risk_level` is withheld rather than treating missing inputs as safe. Road-impact scoring counts active records; it identifies flood-related impacts only when the source text explicitly indicates flooding or high water.

LOW, MODERATE, HIGH, and SEVERE are PALMETTO prototype decision-support categories. They are NOT official NOAA, NWS, FEMA, or City of Charleston flood classifications. PALMETTO is not an official emergency warning system and must not be relied upon for emergency response or evacuation decisions.