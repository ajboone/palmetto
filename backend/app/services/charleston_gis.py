from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import CHARLESTON_GIS_MAPSERVER, CHARLESTON_GIS_TIMEOUT_SECONDS
from app.models.roads import RoadImpact


class CharlestonGISServiceError(Exception):
    pass


ROAD_LAYERS = (
    {
        "id": 1,
        "name": "ROAD CLOSURE",
        "out_fields": "OBJECTID,STREET,LOCATION,TYPE,REASON,STATUS,START,END_,COMMENT",
        "road_field": "STREET",
        "description_field": "LOCATION",
        "type_field": "TYPE",
        "reason_field": "REASON",
        "start_field": "START",
        "end_field": "END_",
    },
    {
        "id": 5,
        "name": "ROAD CLOSURE EM",
        "out_fields": "OBJECTID,STREET,LOCATION,TYPE,REASON,STATUS,START,END_,COMMENT",
        "road_field": "STREET",
        "description_field": "LOCATION",
        "type_field": "TYPE",
        "reason_field": "REASON",
        "start_field": "START",
        "end_field": "END_",
    },
    {
        "id": 2,
        "name": "DETOURS",
        "out_fields": "OBJECTID,BLOCKNM,COMMENT,STATUS,STARTDATE,ENDDATE",
        "road_field": "BLOCKNM",
        "description_field": "COMMENT",
        "type_field": None,
        "reason_field": None,
        "start_field": "STARTDATE",
        "end_field": "ENDDATE",
    },
)


async def get_gis_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=CHARLESTON_GIS_TIMEOUT_SECONDS) as client:
        yield client


async def _query_layer(
    client: httpx.AsyncClient, layer: dict[str, Any]
) -> list[dict[str, Any]]:
    url = f"{CHARLESTON_GIS_MAPSERVER}/{layer['id']}/query"
    params = {
        "where": "STATUS = 'ACTIVE'",
        "outFields": layer["out_fields"],
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": "1000",
    }
    features = []
    offset = 0
    while True:
        params["resultOffset"] = str(offset)
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CharlestonGISServiceError("Charleston GIS request failed") from exc

        if not isinstance(payload, dict) or "error" in payload:
            raise CharlestonGISServiceError("Charleston GIS returned an invalid response")
        page = payload.get("features")
        if not isinstance(page, list):
            raise CharlestonGISServiceError("Charleston GIS response is malformed")
        features.extend(page)
        if payload.get("exceededTransferLimit") is not True:
            return features
        if not page:
            raise CharlestonGISServiceError("Charleston GIS pagination did not advance")
        offset += len(page)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else None


def _arcgis_datetime(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _normalize_feature(
    feature: object, layer: dict[str, Any]
) -> RoadImpact:
    if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
        raise CharlestonGISServiceError("Charleston GIS feature is malformed")
    attributes = feature["attributes"]
    object_id = attributes.get("OBJECTID")
    if not isinstance(object_id, (str, int)) or isinstance(object_id, bool):
        raise CharlestonGISServiceError("Charleston GIS feature has no object ID")
    source_layer = f"{layer['name']} ({layer['id']})"
    return RoadImpact(
        id=f"{layer['id']}:{object_id}",
        road_name=_optional_text(attributes.get(layer["road_field"])),
        description=_optional_text(attributes.get(layer["description_field"])),
        status=_optional_text(attributes.get("STATUS")),
        impact_type=(
            _optional_text(attributes.get(layer["type_field"]))
            if layer["type_field"]
            else None
        ),
        reason=(
            _optional_text(attributes.get(layer["reason_field"]))
            if layer["reason_field"]
            else None
        ),
        start_time=_arcgis_datetime(attributes.get(layer["start_field"])),
        end_time=_arcgis_datetime(attributes.get(layer["end_field"])),
        latitude=None,
        longitude=None,
        source=CHARLESTON_GIS_MAPSERVER,
        source_layer=source_layer,
    )


async def get_road_impacts(client: httpx.AsyncClient) -> list[RoadImpact]:
    impacts = []
    for layer in ROAD_LAYERS:
        features = await _query_layer(client, layer)
        impacts.extend(_normalize_feature(feature, layer) for feature in features)
    return impacts