import math
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import (
    CHARLESTON_TIME_ZONE,
    NOAA_API_URL,
    NOAA_DATUM,
    NOAA_SOURCE,
    NOAA_STATION_ID,
    NOAA_STATION_NAME,
    NOAA_TIMEOUT_SECONDS,
)
from app.models.tide import TideObservation, TidePrediction


class NOAAServiceError(Exception):
    pass


async def get_noaa_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=NOAA_TIMEOUT_SECONDS) as client:
        yield client


def _local_today() -> datetime.date:
    return datetime.now(ZoneInfo(CHARLESTON_TIME_ZONE)).date()


async def _fetch_json(
    client: httpx.AsyncClient, params: dict[str, str]
) -> dict:
    try:
        response = await client.get(NOAA_API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise NOAAServiceError("NOAA request failed") from exc

    if not isinstance(payload, dict) or "error" in payload:
        raise NOAAServiceError("NOAA returned an invalid response")
    return payload


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Invalid NOAA timestamp")
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def _parse_number(value: object) -> float:
    if not isinstance(value, (str, int, float)):
        raise ValueError("Invalid NOAA measurement")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Invalid NOAA measurement")
    return number


async def get_current_observation(client: httpx.AsyncClient) -> TideObservation:
    today = _local_today()
    params = {
        "product": "water_level",
        "begin_date": (today - timedelta(days=3)).strftime("%Y%m%d"),
        "end_date": today.strftime("%Y%m%d"),
        "station": NOAA_STATION_ID,
        "time_zone": "lst_ldt",
        "units": "english",
        "datum": NOAA_DATUM,
        "format": "json",
    }
    payload = await _fetch_json(client, params)
    records = payload.get("data")
    if not isinstance(records, list):
        raise NOAAServiceError("NOAA returned an invalid response")

    usable_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            timestamp = _parse_timestamp(record.get("t"))
            value = _parse_number(record.get("v"))
        except (TypeError, ValueError):
            continue
        usable_records.append((timestamp, value))

    if not usable_records:
        raise NOAAServiceError("NOAA returned no usable observations")

    timestamp, value = max(usable_records, key=lambda item: item[0])
    return TideObservation(
        station_id=NOAA_STATION_ID,
        station_name=NOAA_STATION_NAME,
        value=value,
        unit="feet",
        timestamp=timestamp,
        datum=NOAA_DATUM,
        source=f"{NOAA_SOURCE} (water_level)",
    )


async def get_today_predictions(client: httpx.AsyncClient) -> list[TidePrediction]:
    params = {
        "product": "predictions",
        "begin_date": _local_today().strftime("%Y%m%d"),
        "end_date": _local_today().strftime("%Y%m%d"),
        "interval": "hilo",
        "station": NOAA_STATION_ID,
        "time_zone": "lst_ldt",
        "units": "english",
        "datum": NOAA_DATUM,
        "format": "json",
    }
    payload = await _fetch_json(client, params)
    records = payload.get("predictions")
    if not isinstance(records, list):
        raise NOAAServiceError("NOAA returned an invalid response")

    predictions = []
    for record in records:
        if not isinstance(record, dict):
            raise NOAAServiceError("NOAA returned malformed tide predictions")
        try:
            timestamp = _parse_timestamp(record.get("t"))
            height = _parse_number(record.get("v"))
            prediction_type = record.get("type")
            if prediction_type is not None and not isinstance(prediction_type, str):
                raise ValueError("Invalid prediction type")
        except (TypeError, ValueError) as exc:
            raise NOAAServiceError("NOAA returned malformed tide predictions") from exc

        predictions.append(
            TidePrediction(
                station_id=NOAA_STATION_ID,
                station_name=NOAA_STATION_NAME,
                timestamp=timestamp,
                height=height,
                unit="feet",
                datum=NOAA_DATUM,
                type=prediction_type,
                source=f"{NOAA_SOURCE} (predictions)",
            )
        )

    return sorted(predictions, key=lambda prediction: prediction.timestamp)