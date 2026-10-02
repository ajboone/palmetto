import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.models.weather import PrecipitationForecast, WeatherAlert, WeatherPeriod
from app.services.weather import (
    NWSServiceError,
    get_active_alerts,
    get_hourly_forecast,
    get_precipitation_forecast,
    get_weather_client,
)


router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/hourly", response_model=list[WeatherPeriod])
async def hourly_weather(
    client: httpx.AsyncClient = Depends(get_weather_client),
) -> list[WeatherPeriod]:
    try:
        return await get_hourly_forecast(client)
    except NWSServiceError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to retrieve weather data from NWS."
        ) from exc


@router.get("/precipitation", response_model=list[PrecipitationForecast])
async def precipitation(
    client: httpx.AsyncClient = Depends(get_weather_client),
) -> list[PrecipitationForecast]:
    try:
        return await get_precipitation_forecast(client)
    except NWSServiceError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to retrieve weather data from NWS."
        ) from exc


@router.get("/alerts", response_model=list[WeatherAlert])
async def weather_alerts(
    client: httpx.AsyncClient = Depends(get_weather_client),
) -> list[WeatherAlert]:
    try:
        return await get_active_alerts(client)
    except NWSServiceError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to retrieve weather data from NWS."
        ) from exc