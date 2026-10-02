import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.models.tide import TideObservation, TidePrediction
from app.services.noaa import (
    NOAAServiceError,
    get_current_observation,
    get_noaa_client,
    get_today_predictions,
)


router = APIRouter(prefix="/api/tides", tags=["tides"])


@router.get("/current", response_model=TideObservation)
async def current_tide(
    client: httpx.AsyncClient = Depends(get_noaa_client),
) -> TideObservation:
    try:
        return await get_current_observation(client)
    except NOAAServiceError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to retrieve tide data from NOAA."
        ) from exc


@router.get("/today", response_model=list[TidePrediction])
async def today_tides(
    client: httpx.AsyncClient = Depends(get_noaa_client),
) -> list[TidePrediction]:
    try:
        return await get_today_predictions(client)
    except NOAAServiceError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to retrieve tide data from NOAA."
        ) from exc