import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.models.roads import RoadImpact
from app.services.charleston_gis import (
    CharlestonGISServiceError,
    get_gis_client,
    get_road_impacts,
)


router = APIRouter(prefix="/api/roads", tags=["roads"])


@router.get("/impacts", response_model=list[RoadImpact])
async def road_impacts(
    client: httpx.AsyncClient = Depends(get_gis_client),
) -> list[RoadImpact]:
    try:
        return await get_road_impacts(client)
    except CharlestonGISServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve road-impact data from Charleston GIS.",
        ) from exc