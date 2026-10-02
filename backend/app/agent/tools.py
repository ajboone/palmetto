import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from app.models.risk import RiskAssessment
from app.services.charleston_gis import (
    CharlestonGISServiceError,
    get_road_impacts,
)
from app.services.noaa import (
    NOAAServiceError,
    get_current_observation,
    get_today_predictions,
)
from app.services.risk import get_current_risk_assessment
from app.services.weather import (
    NWSServiceError,
    get_active_alerts,
    get_hourly_forecast,
    get_precipitation_forecast,
)


logger = logging.getLogger(__name__)

EMPTY_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}


def _tool(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": EMPTY_OBJECT_SCHEMA,
        "strict": True,
    }


PALMETTO_TOOLS = [
    _tool(
        "get_current_water_level",
        "Get the normalized recent/current NOAA CO-OPS Charleston Harbor water-level observation.",
    ),
    _tool(
        "get_tide_predictions",
        "Get today's normalized NOAA CO-OPS Charleston tide predictions.",
    ),
    _tool(
        "get_hourly_weather",
        "Get the near-term normalized NWS hourly forecast for configured Charleston coordinates.",
    ),
    _tool(
        "get_precipitation_forecast",
        "Get NWS quantitative precipitation intervals when available; amounts are not inferred from probability.",
    ),
    _tool(
        "get_weather_alerts",
        "Get active NWS alerts relevant to the configured Charleston point.",
    ),
    _tool(
        "get_road_impacts",
        "Get normalized active road closures and detours from City of Charleston GIS.",
    ),
    _tool(
        "get_flood_risk",
        "Get the authoritative deterministic PALMETTO prototype flood-risk assessment. Do not recalculate its score or category.",
    ),
]


@dataclass
class ToolContext:
    noaa_client: Any
    weather_client: Any
    gis_client: Any


async def _current_water_level(context: ToolContext) -> Any:
    return await get_current_observation(context.noaa_client)


async def _tide_predictions(context: ToolContext) -> Any:
    return await get_today_predictions(context.noaa_client)


async def _hourly_weather(context: ToolContext) -> Any:
    return await get_hourly_forecast(context.weather_client)


async def _precipitation_forecast(context: ToolContext) -> Any:
    return await get_precipitation_forecast(context.weather_client)


async def _weather_alerts(context: ToolContext) -> Any:
    return await get_active_alerts(context.weather_client)


async def _road_impacts(context: ToolContext) -> Any:
    return await get_road_impacts(context.gis_client)


async def _flood_risk(context: ToolContext) -> RiskAssessment:
    return await get_current_risk_assessment(
        noaa_client=context.noaa_client,
        weather_client=context.weather_client,
        gis_client=context.gis_client,
    )


# Model-controlled names are resolved only through this explicit registry.
TOOL_HANDLERS: dict[str, Callable[[ToolContext], Awaitable[Any]]] = {
    "get_current_water_level": _current_water_level,
    "get_tide_predictions": _tide_predictions,
    "get_hourly_weather": _hourly_weather,
    "get_precipitation_forecast": _precipitation_forecast,
    "get_weather_alerts": _weather_alerts,
    "get_road_impacts": _road_impacts,
    "get_flood_risk": _flood_risk,
}


def serialize_tool_result(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    if isinstance(value, list):
        return "[" + ",".join(serialize_tool_result(item) for item in value) + "]"
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _service_error(tool_name: str, error: Exception) -> dict[str, Any]:
    if isinstance(error, NOAAServiceError):
        detail = "NOAA data unavailable"
    elif isinstance(error, NWSServiceError):
        detail = "NWS data unavailable"
    elif isinstance(error, CharlestonGISServiceError):
        detail = "Charleston GIS data unavailable"
    else:
        detail = "PALMETTO data service failed"
        logger.error("PALMETTO tool %s failed", tool_name, exc_info=error)
    return {"ok": False, "tool": tool_name, "error": detail}


async def dispatch_tool_call(
    *,
    tool_name: str,
    arguments: str,
    context: ToolContext,
    handlers: dict[str, Callable[[ToolContext], Awaitable[Any]]] | None = None,
) -> str:
    handler_registry = TOOL_HANDLERS if handlers is None else handlers
    handler = handler_registry.get(tool_name)
    if handler is None:
        return serialize_tool_result(
            {"ok": False, "tool": tool_name, "error": "Unknown PALMETTO tool."}
        )
    try:
        parsed_arguments = json.loads(arguments)
    except (TypeError, json.JSONDecodeError):
        return serialize_tool_result(
            {"ok": False, "tool": tool_name, "error": "Tool arguments must be valid JSON."}
        )
    if not isinstance(parsed_arguments, dict) or parsed_arguments:
        return serialize_tool_result(
            {
                "ok": False,
                "tool": tool_name,
                "error": "This PALMETTO tool accepts no arguments.",
            }
        )

    try:
        result = await handler(context)
        return serialize_tool_result(result)
    except (NOAAServiceError, NWSServiceError, CharlestonGISServiceError) as exc:
        return serialize_tool_result(_service_error(tool_name, exc))
    except Exception as exc:
        return serialize_tool_result(_service_error(tool_name, exc))