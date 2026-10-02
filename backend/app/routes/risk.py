import httpx
from fastapi import APIRouter, Depends

from app.models.risk import RiskAssessment
from app.services.charleston_gis import get_gis_client
from app.services.noaa import get_noaa_client
from app.services.risk import get_current_risk_assessment
from app.services.weather import get_weather_client


router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/current", response_model=RiskAssessment)
async def current_risk(
    noaa_client: httpx.AsyncClient = Depends(get_noaa_client),
    weather_client: httpx.AsyncClient = Depends(get_weather_client),
    gis_client: httpx.AsyncClient = Depends(get_gis_client),
) -> RiskAssessment:
    return await get_current_risk_assessment(
        noaa_client=noaa_client,
        weather_client=weather_client,
        gis_client=gis_client,
    )