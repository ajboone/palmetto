import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import (
    NWS_API_BASE,
    NWS_LATITUDE,
    NWS_LONGITUDE,
    NWS_TIMEOUT_SECONDS,
    NWS_USER_AGENT,
)
from app.models.weather import PrecipitationForecast, WeatherAlert, WeatherPeriod


class NWSServiceError(Exception):
    pass


async def get_weather_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=NWS_TIMEOUT_SECONDS,
        headers={"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"},
    ) as client:
        yield client


def _point_url() -> str:
    return f"{NWS_API_BASE}/points/{NWS_LATITUDE},{NWS_LONGITUDE}"


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise NWSServiceError("NWS request failed") from exc

    if not isinstance(payload, dict) or "error" in payload:
        raise NWSServiceError("NWS returned an invalid response")
    return payload


async def _discover(client: httpx.AsyncClient) -> dict[str, Any]:
    payload = await _get_json(client, _point_url())
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        raise NWSServiceError("NWS point discovery response is malformed")
    return properties


def _datetime(value: object, *, required: bool = False) -> datetime | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise NWSServiceError("NWS returned malformed forecast data")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NWSServiceError("NWS returned malformed forecast data") from exc


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NWSServiceError("NWS returned malformed forecast data")
    return float(value)


def _hourly_period(record: object, source: str) -> WeatherPeriod:
    if not isinstance(record, dict):
        raise NWSServiceError("NWS returned malformed hourly forecast data")
    probability = record.get("probabilityOfPrecipitation")
    if probability is not None and not isinstance(probability, dict):
        raise NWSServiceError("NWS returned malformed hourly forecast data")
    temperature_unit = record.get("temperatureUnit")
    short_forecast = record.get("shortForecast")
    wind_speed = record.get("windSpeed")
    wind_direction = record.get("windDirection")
    for value in (temperature_unit, short_forecast, wind_speed, wind_direction):
        if value is not None and not isinstance(value, str):
            raise NWSServiceError("NWS returned malformed hourly forecast data")

    return WeatherPeriod(
        start_time=_datetime(record.get("startTime"), required=True),
        end_time=_datetime(record.get("endTime")),
        temperature=_number(record.get("temperature")),
        temperature_unit=temperature_unit,
        precipitation_probability=(
            _number(probability.get("value")) if probability is not None else None
        ),
        short_forecast=short_forecast,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        source=source,
    )


async def get_hourly_forecast(
    client: httpx.AsyncClient, limit: int = 24
) -> list[WeatherPeriod]:
    point_properties = await _discover(client)
    forecast_url = point_properties.get("forecastHourly")
    if not isinstance(forecast_url, str):
        raise NWSServiceError("NWS point response has no hourly forecast link")
    payload = await _get_json(client, forecast_url)
    properties = payload.get("properties")
    periods = properties.get("periods") if isinstance(properties, dict) else None
    if not isinstance(periods, list):
        raise NWSServiceError("NWS hourly forecast response is malformed")
    return [_hourly_period(period, forecast_url) for period in periods[:limit]]


def _grid_interval(value: object) -> tuple[datetime, datetime | None]:
    if not isinstance(value, str) or "/" not in value:
        raise NWSServiceError("NWS returned malformed precipitation interval")
    start_value, duration = value.split("/", 1)
    start = _datetime(start_value, required=True)
    match = re.fullmatch(
        r"P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?"
        r"(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?",
        duration,
    )
    if not match:
        raise NWSServiceError("NWS returned malformed precipitation interval")
    days, hours, minutes, seconds = (float(part or 0) for part in match.groups())
    end = start + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    return start, end


async def get_precipitation_forecast(
    client: httpx.AsyncClient,
) -> list[PrecipitationForecast]:
    point_properties = await _discover(client)
    grid_url = point_properties.get("forecastGridData")
    if not isinstance(grid_url, str):
        raise NWSServiceError("NWS point response has no forecast grid link")
    payload = await _get_json(
        client, grid_url, params={"parameters": "quantitativePrecipitation"}
    )
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        raise NWSServiceError("NWS grid forecast response is malformed")
    quantitative_precipitation = properties.get("quantitativePrecipitation")
    if quantitative_precipitation is None:
        return []
    if not isinstance(quantitative_precipitation, dict):
        raise NWSServiceError("NWS precipitation data is malformed")
    values = quantitative_precipitation.get("values")
    if not isinstance(values, list):
        raise NWSServiceError("NWS precipitation data is malformed")
    unit_code = quantitative_precipitation.get("uom")
    units = {"wmoUnit:mm": "mm", "wmoUnit:in": "in"}
    if values and unit_code not in units:
        raise NWSServiceError("NWS precipitation unit is unsupported")

    forecasts = []
    for item in values:
        if not isinstance(item, dict):
            raise NWSServiceError("NWS precipitation data is malformed")
        amount = _number(item.get("value"))
        if amount is None:
            continue
        start_time, end_time = _grid_interval(item.get("validTime"))
        forecasts.append(
            PrecipitationForecast(
                start_time=start_time,
                end_time=end_time,
                amount=amount,
                unit=units[unit_code],
                source=grid_url,
            )
        )
    return forecasts


def _alert_datetime(properties: dict[str, Any], key: str) -> datetime | None:
    return _datetime(properties.get(key))


async def get_active_alerts(client: httpx.AsyncClient) -> list[WeatherAlert]:
    await _discover(client)
    point = f"{NWS_LATITUDE},{NWS_LONGITUDE}"
    alerts_url = f"{NWS_API_BASE}/alerts/active"
    payload = await _get_json(client, alerts_url, params={"point": point})
    features = payload.get("features")
    if not isinstance(features, list):
        raise NWSServiceError("NWS alerts response is malformed")

    normalized = []
    for feature in features:
        properties = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(properties, dict):
            raise NWSServiceError("NWS alert record is malformed")
        alert_id = properties.get("id") or feature.get("id")
        event = properties.get("event")
        if not isinstance(alert_id, str) or not isinstance(event, str):
            raise NWSServiceError("NWS alert record is missing required fields")
        optional_text_fields = (
            "severity",
            "urgency",
            "certainty",
            "headline",
            "description",
            "instruction",
        )
        if any(
            properties.get(key) is not None and not isinstance(properties[key], str)
            for key in optional_text_fields
        ):
            raise NWSServiceError("NWS alert record is malformed")
        normalized.append(
            WeatherAlert(
                id=alert_id,
                event=event,
                severity=properties.get("severity"),
                urgency=properties.get("urgency"),
                certainty=properties.get("certainty"),
                headline=properties.get("headline"),
                description=properties.get("description"),
                instruction=properties.get("instruction"),
                effective=_alert_datetime(properties, "effective"),
                onset=_alert_datetime(properties, "onset"),
                expires=_alert_datetime(properties, "expires"),
                source=f"{alerts_url}?point={point}",
            )
        )
    return normalized