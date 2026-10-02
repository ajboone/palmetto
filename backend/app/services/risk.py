"""Deterministic PALMETTO prototype flood-risk rules, not official classifications."""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import (
    CHARLESTON_TIME_ZONE,
    PALMETTO_PRECIPITATION_POP_THRESHOLDS,
    PALMETTO_PRECIPITATION_THRESHOLDS_MM,
    PALMETTO_RISK_TIME_HORIZON_HOURS,
    PALMETTO_TIDE_ELEVATED_FT,
    PALMETTO_TIDE_HIGH_FT,
    PALMETTO_TIDE_SEVERE_FT,
    PALMETTO_WATER_LEVEL_ELEVATED_FT,
    PALMETTO_WATER_LEVEL_HIGH_FT,
    PALMETTO_WATER_LEVEL_MAX_AGE_HOURS,
    PALMETTO_WATER_LEVEL_SEVERE_FT,
    RISK_CATEGORY_BOUNDS,
    RISK_COMPONENT_WEIGHTS,
)
from app.models.risk import EvidenceStatus, RiskAssessment, RiskComponent, RiskLevel
from app.models.roads import RoadImpact
from app.models.tide import TideObservation, TidePrediction
from app.models.weather import PrecipitationForecast, WeatherAlert, WeatherPeriod
from app.services.charleston_gis import (
    CharlestonGISServiceError,
    get_road_impacts,
)
from app.services.noaa import (
    NOAAServiceError,
    get_current_observation,
    get_today_predictions,
)
from app.services.weather import (
    NWSServiceError,
    get_active_alerts,
    get_hourly_forecast,
    get_precipitation_forecast,
)


METHODLOGY = (
    "A deterministic PALMETTO prototype score sums weighted water-level, tide, "
    "precipitation, active-weather-alert, and road-impact component scores. "
    "It uses PALMETTO prototype rules, not official government flood thresholds "
    "or classifications."
)
DISCLAIMER = (
    "LOW, MODERATE, HIGH, and SEVERE are PALMETTO prototype decision-support "
    "categories, not official NOAA, NWS, FEMA, or City of Charleston classifications. "
    "This is not an emergency warning system."
)
LOCATION_NAME = "Charleston, South Carolina"

SOURCE_WATER = "NOAA CO-OPS current water-level observations"
SOURCE_TIDES = "NOAA CO-OPS tide predictions"
SOURCE_HOURLY = "NWS hourly forecast"
SOURCE_PRECIPITATION = "NWS quantitative precipitation"
SOURCE_ALERTS = "NWS active weather alerts"
SOURCE_ROADS = "City of Charleston GIS road impacts"


def _localize(value: datetime, local_zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=local_zone)
    return value.astimezone(local_zone)


def _bounded(score: int, max_score: int) -> int:
    return max(0, min(score, max_score))


def _unavailable(
    name: str, max_score: int, explanation: str, source: str
) -> RiskComponent:
    return RiskComponent(
        name=name,
        score=None,
        max_score=max_score,
        explanation=explanation,
        evidence_status=EvidenceStatus.UNAVAILABLE,
        source=source,
        observed_values={},
        unit=None,
    )


def _water_component(
    observation: TideObservation | None,
    now: datetime,
    local_zone: ZoneInfo,
) -> RiskComponent:
    name = "water_level"
    maximum = RISK_COMPONENT_WEIGHTS[name]
    if observation is None:
        return _unavailable(
            name, maximum, "Current water-level evidence is unavailable.", SOURCE_WATER
        )
    if observation.unit.casefold() not in {"foot", "feet", "ft"} or observation.datum.upper() != "MLLW":
        return RiskComponent(
            name=name,
            score=None,
            max_score=maximum,
            explanation=(
                "Water-level evidence is present but is not in feet relative to MLLW, "
                "so PALMETTO prototype thresholds cannot be applied."
            ),
            evidence_status=EvidenceStatus.PARTIAL,
            source=observation.source,
            observed_values={"value": observation.value, "datum": observation.datum},
            unit=observation.unit,
        )

    age_hours = (
        _localize(now, local_zone)
        - _localize(observation.timestamp, local_zone)
    ).total_seconds() / 3600
    if age_hours < 0 or age_hours > PALMETTO_WATER_LEVEL_MAX_AGE_HOURS:
        return RiskComponent(
            name=name,
            score=None,
            max_score=maximum,
            explanation=(
                f"The latest NOAA water-level observation is {age_hours:.1f} hours old; "
                f"PALMETTO's configurable prototype freshness limit is "
                f"{PALMETTO_WATER_LEVEL_MAX_AGE_HOURS:g} hours, so it is not scored as current."
            ),
            evidence_status=EvidenceStatus.PARTIAL,
            source=observation.source,
            observed_values={
                "value": observation.value,
                "timestamp": observation.timestamp.isoformat(),
                "age_hours": round(age_hours, 2),
                "datum": observation.datum,
            },
            unit=f"ft {observation.datum}",
        )

    value = observation.value
    if value >= PALMETTO_WATER_LEVEL_SEVERE_FT:
        score, threshold_name, threshold = maximum, "severe", PALMETTO_WATER_LEVEL_SEVERE_FT
    elif value >= PALMETTO_WATER_LEVEL_HIGH_FT:
        score, threshold_name, threshold = 20, "high", PALMETTO_WATER_LEVEL_HIGH_FT
    elif value >= PALMETTO_WATER_LEVEL_ELEVATED_FT:
        score, threshold_name, threshold = 10, "elevated", PALMETTO_WATER_LEVEL_ELEVATED_FT
    else:
        score, threshold_name, threshold = 0, "below elevated", PALMETTO_WATER_LEVEL_ELEVATED_FT
    explanation = (
        f"Current Charleston Harbor water level is {value:g} ft {observation.datum}; "
        f"it is {threshold_name} relative to PALMETTO's non-official "
        f"{threshold:g} ft prototype threshold."
    )
    return RiskComponent(
        name=name,
        score=_bounded(score, maximum),
        max_score=maximum,
        explanation=explanation,
        evidence_status=EvidenceStatus.AVAILABLE,
        source=observation.source,
        observed_values={
            "value": value,
            "timestamp": observation.timestamp.isoformat(),
            "datum": observation.datum,
        },
        unit=f"ft {observation.datum}",
    )


def _tide_component(
    predictions: list[TidePrediction] | None,
    now: datetime,
    local_zone: ZoneInfo,
) -> RiskComponent:
    name = "tide"
    maximum = RISK_COMPONENT_WEIGHTS[name]
    if predictions is None:
        return _unavailable(
            name, maximum, "Tide-prediction evidence is unavailable.", SOURCE_TIDES
        )

    now_local = _localize(now, local_zone)
    future_highs = [
        prediction
        for prediction in predictions
        if prediction.type is not None
        and prediction.type.upper() == "H"
        and _localize(prediction.timestamp, local_zone) > now_local
    ]
    if not future_highs:
        return RiskComponent(
            name=name,
            score=None,
            max_score=maximum,
            explanation=(
                "No future high tide appears in today's returned predictions; "
                "the next high tide cannot be assessed from this window."
            ),
            evidence_status=EvidenceStatus.PARTIAL,
            source=predictions[0].source if predictions else "NOAA CO-OPS predictions",
            observed_values={"predictions_returned": len(predictions)},
            unit="ft MLLW",
        )

    prediction = min(
        future_highs, key=lambda item: _localize(item.timestamp, local_zone)
    )
    high_time = _localize(prediction.timestamp, local_zone)
    hours_until = (high_time - now_local).total_seconds() / 3600
    if prediction.unit.casefold() not in {"foot", "feet", "ft"} or prediction.datum.upper() != "MLLW":
        return RiskComponent(
            name=name,
            score=None,
            max_score=maximum,
            explanation="The next high tide has incompatible units or datum for prototype scoring.",
            evidence_status=EvidenceStatus.PARTIAL,
            source=prediction.source,
            observed_values={
                "height": prediction.height,
                "timestamp": prediction.timestamp.isoformat(),
            },
            unit=prediction.unit,
        )

    if prediction.height >= PALMETTO_TIDE_SEVERE_FT:
        height_score = 15
        height_band = "severe prototype height band"
    elif prediction.height >= PALMETTO_TIDE_HIGH_FT:
        height_score = 10
        height_band = "high prototype height band"
    elif prediction.height >= PALMETTO_TIDE_ELEVATED_FT:
        height_score = 5
        height_band = "elevated prototype height band"
    else:
        height_score = 0
        height_band = "below the elevated prototype height band"

    if hours_until <= 2:
        imminence_score = 5
        imminence = "within the next 2 hours"
    elif hours_until <= 6:
        imminence_score = 3
        imminence = "within the next 6 hours"
    elif hours_until <= 12:
        imminence_score = 1
        imminence = "within the next 12 hours"
    else:
        imminence_score = 0
        imminence = "more than 12 hours away"
    score = _bounded(height_score + imminence_score, maximum)
    return RiskComponent(
        name=name,
        score=score,
        max_score=maximum,
        explanation=(
            f"The next predicted high tide is {prediction.height:g} ft MLLW "
            f"{imminence} ({height_band}); the prototype score considers both height and timing."
        ),
        evidence_status=EvidenceStatus.AVAILABLE,
        source=prediction.source,
        observed_values={
            "next_high_tide_height": prediction.height,
            "next_high_tide_at": prediction.timestamp.isoformat(),
            "hours_until_high_tide": round(hours_until, 2),
        },
        unit="ft MLLW",
    )


def _precipitation_component(
    precipitation: list[PrecipitationForecast] | None,
    hourly: list[WeatherPeriod] | None,
    now: datetime,
    local_zone: ZoneInfo,
) -> tuple[RiskComponent, bool]:
    name = "precipitation"
    maximum = RISK_COMPONENT_WEIGHTS[name]
    horizon_end = now + timedelta(hours=PALMETTO_RISK_TIME_HORIZON_HOURS)
    if precipitation:
        selected = [
            item
            for item in precipitation
            if _localize(item.start_time, local_zone) >= now
            and _localize(item.start_time, local_zone) < horizon_end
        ]
        total_mm = 0.0
        for item in selected:
            unit = item.unit.casefold()
            if unit in {"mm", "millimeter", "millimeters"}:
                total_mm += item.amount
            elif unit in {"in", "inch", "inches"}:
                total_mm += item.amount * 25.4
            else:
                return (
                    RiskComponent(
                        name=name,
                        score=None,
                        max_score=maximum,
                        explanation=f"Quantitative precipitation unit {item.unit!r} is unsupported.",
                        evidence_status=EvidenceStatus.PARTIAL,
                        source=item.source,
                        observed_values={},
                        unit=item.unit,
                    ),
                    True,
                )
        if selected:
            thresholds = PALMETTO_PRECIPITATION_THRESHOLDS_MM
            if total_mm >= thresholds[3]:
                score = 20
            elif total_mm >= thresholds[2]:
                score = 15
            elif total_mm >= thresholds[1]:
                score = 10
            elif total_mm >= thresholds[0]:
                score = 5
            else:
                score = 0
            return (
                RiskComponent(
                    name=name,
                    score=_bounded(score, maximum),
                    max_score=maximum,
                    explanation=(
                        f"NWS quantitative precipitation totals {total_mm:g} mm in "
                        "the selected upcoming forecast intervals; this uses amount, "
                        "not probability of precipitation."
                    ),
                    evidence_status=EvidenceStatus.AVAILABLE,
                    source="; ".join(sorted({item.source for item in selected})),
                    observed_values={
                        "quantitative_precipitation_total": round(total_mm, 2),
                        "forecast_intervals": len(selected),
                    },
                    unit="mm over selected intervals",
                ),
                False,
            )

    probabilities = []
    if hourly is not None:
        for period in hourly:
            period_start = _localize(period.start_time, local_zone)
            probability = period.precipitation_probability
            if period_start >= _localize(now, local_zone) and period_start < _localize(
                horizon_end, local_zone
            ) and probability is not None:
                probabilities.append(probability)
    if probabilities:
        thresholds = PALMETTO_PRECIPITATION_POP_THRESHOLDS
        highest = max(probabilities)
        score = 5 if highest >= thresholds[2] else 3 if highest >= thresholds[1] else 1 if highest >= thresholds[0] else 0
        return (
            RiskComponent(
                name=name,
                score=_bounded(score, maximum),
                max_score=maximum,
                explanation=(
                    "NWS quantitative rainfall amount is unavailable; the limited "
                    f"secondary context signal is a maximum {highest:g}% precipitation "
                    "probability. Probability is not treated as rainfall amount."
                ),
                evidence_status=EvidenceStatus.PARTIAL,
                source="; ".join(sorted({period.source for period in hourly or []})),
                observed_values={"maximum_precipitation_probability": highest},
                unit="% probability; rainfall amount unavailable",
            ),
            True,
        )

    return (
        _unavailable(
            name,
            maximum,
            "Quantitative precipitation and usable precipitation-probability evidence are unavailable.",
            SOURCE_PRECIPITATION,
        ),
        True,
    )


def _alert_component(alerts: list[WeatherAlert] | None) -> RiskComponent:
    name = "weather_alerts"
    maximum = RISK_COMPONENT_WEIGHTS[name]
    if alerts is None:
        return _unavailable(
            name, maximum, "Active NWS alert evidence is unavailable.", SOURCE_ALERTS
        )

    relevant = []
    total = 0
    for alert in alerts:
        event = alert.event.casefold()
        if "flood" not in event:
            continue
        if "flash flood warning" in event:
            score = 12
        elif "flood warning" in event:
            score = 10
        elif "flood watch" in event:
            score = 8
        elif "flood advisory" in event:
            score = 6
        else:
            score = 4
        score += {"extreme": 2, "severe": 1}.get(
            (alert.severity or "").casefold(), 0
        )
        score += 1 if (alert.urgency or "").casefold() == "immediate" else 0
        score += 1 if (alert.certainty or "").casefold() == "observed" else 0
        total += score
        relevant.append(alert)

    score = _bounded(total, maximum)
    explanation = (
        f"{len(relevant)} flood-related NWS alert(s) contribute to this component."
        if relevant
        else "No flood-related active NWS alerts were returned; unrelated alerts do not add flood-alert points."
    )
    return RiskComponent(
        name=name,
        score=score,
        max_score=maximum,
        explanation=explanation,
        evidence_status=EvidenceStatus.AVAILABLE,
        source=(
            "; ".join(sorted({alert.source for alert in relevant}))
            if relevant
            else "NWS active alerts for configured Charleston point"
        ),
        observed_values={
            "active_alert_count": len(alerts),
            "flood_related_alert_count": len(relevant),
            "contributing_events": "; ".join(alert.event for alert in relevant) or None,
        },
        unit="points",
    )


def _flood_related_road(impact: RoadImpact) -> bool:
    evidence = " ".join(
        value or "" for value in (impact.reason, impact.description, impact.impact_type)
    ).casefold()
    return any(term in evidence for term in ("flood", "high water", "standing water", "water over roadway"))


def _road_component(impacts: list[RoadImpact] | None) -> RiskComponent:
    name = "road_impacts"
    maximum = RISK_COMPONENT_WEIGHTS[name]
    if impacts is None:
        return _unavailable(
            name, maximum, "Charleston GIS road-impact evidence is unavailable.", SOURCE_ROADS
        )

    active = [impact for impact in impacts if (impact.status or "").casefold() == "active"]
    status_missing = any(impact.status is None for impact in impacts)
    flood_related = [impact for impact in active if _flood_related_road(impact)]
    score = _bounded(len(active) * 2 + len(flood_related) * 3, maximum)
    evidence_status = EvidenceStatus.PARTIAL if status_missing else EvidenceStatus.AVAILABLE
    explanation = (
        f"Charleston GIS reports {len(active)} current road impact(s), including "
        f"{len(flood_related)} record(s) with explicit flood/high-water wording. "
        "Generic impacts are not assumed to be flood-caused."
    )
    if status_missing:
        explanation += " Some records lack status and were not counted as current."
    return RiskComponent(
        name=name,
        score=score,
        max_score=maximum,
        explanation=explanation,
        evidence_status=evidence_status,
        source=(
            "; ".join(sorted({impact.source for impact in impacts}))
            if impacts
            else "City of Charleston GIS RoadClosuresViewer"
        ),
        observed_values={
            "active_road_impact_count": len(active),
            "explicit_flood_related_count": len(flood_related),
        },
        unit="reported impacts",
    )


def calculate_risk_assessment(
    *,
    observation: TideObservation | None,
    predictions: list[TidePrediction] | None,
    hourly: list[WeatherPeriod] | None,
    precipitation: list[PrecipitationForecast] | None,
    alerts: list[WeatherAlert] | None,
    road_impacts: list[RoadImpact] | None,
    now: datetime | None = None,
) -> RiskAssessment:
    local_zone = ZoneInfo(CHARLESTON_TIME_ZONE)
    assessed_at = now or datetime.now(timezone.utc)
    if assessed_at.tzinfo is None:
        assessed_at = assessed_at.replace(tzinfo=local_zone)
    assessed_at = assessed_at.astimezone(timezone.utc)
    component_now = assessed_at.astimezone(local_zone)

    water = _water_component(observation, component_now, local_zone)
    tide = _tide_component(predictions, component_now, local_zone)
    precipitation_component, precipitation_amount_missing = _precipitation_component(
        precipitation, hourly, component_now, local_zone
    )
    alerts_component = _alert_component(alerts)
    roads_component = _road_component(road_impacts)
    components = [water, tide, precipitation_component, alerts_component, roads_component]

    unavailable_sources = []
    if water.evidence_status in {EvidenceStatus.UNAVAILABLE, EvidenceStatus.PARTIAL}:
        unavailable_sources.append(SOURCE_WATER)
    if tide.evidence_status in {EvidenceStatus.UNAVAILABLE, EvidenceStatus.PARTIAL}:
        unavailable_sources.append(SOURCE_TIDES)
    if precipitation_amount_missing:
        unavailable_sources.append(SOURCE_PRECIPITATION)
    if hourly is None:
        unavailable_sources.append(SOURCE_HOURLY)
    if alerts_component.evidence_status == EvidenceStatus.UNAVAILABLE:
        unavailable_sources.append(SOURCE_ALERTS)
    if roads_component.evidence_status == EvidenceStatus.UNAVAILABLE:
        unavailable_sources.append(SOURCE_ROADS)

    unavailable_sources = list(dict.fromkeys(unavailable_sources))
    statuses = {component.evidence_status for component in components}
    if statuses == {EvidenceStatus.UNAVAILABLE}:
        evidence_status = EvidenceStatus.UNAVAILABLE
    elif statuses == {EvidenceStatus.AVAILABLE} and not unavailable_sources:
        evidence_status = EvidenceStatus.AVAILABLE
    else:
        evidence_status = EvidenceStatus.PARTIAL

    score = sum(component.score or 0 for component in components)
    score = _bounded(score, 100)
    risk_level = None
    if evidence_status == EvidenceStatus.AVAILABLE:
        for upper_bound, level in RISK_CATEGORY_BOUNDS:
            if score <= upper_bound:
                risk_level = RiskLevel(level)
                break

    contributing_factors = []
    if water.score:
        contributing_factors.append(water.explanation)
    if tide.score:
        hours = tide.observed_values.get("hours_until_high_tide")
        if isinstance(hours, (int, float)) and hours <= 2:
            contributing_factors.append(
                f"High tide is approaching within 2 hours; predicted height is "
                f"{tide.observed_values['next_high_tide_height']} ft MLLW."
            )
        else:
            contributing_factors.append(tide.explanation)
    if precipitation_component.score:
        contributing_factors.append(precipitation_component.explanation)
    if alerts_component.score:
        contributing_factors.append(alerts_component.explanation)
    if roads_component.score:
        contributing_factors.append(roads_component.explanation)

    limitations = []
    if evidence_status != EvidenceStatus.AVAILABLE:
        limitations.append(
            "Evidence is incomplete. The score is only the subtotal of scored "
            "components; risk_level is withheld rather than treating missing inputs as safe."
        )
    if precipitation_amount_missing:
        limitations.append(
            "NWS quantitative precipitation amount was unavailable. Any precipitation "
            "probability is only a separate context signal and was not converted to rainfall."
        )
    if tide.evidence_status == EvidenceStatus.PARTIAL:
        limitations.append(tide.explanation)
    if not limitations:
        limitations.append(
            "Prototype thresholds and weights are not scientifically validated or official flood criteria."
        )

    return RiskAssessment(
        risk_level=risk_level,
        score=score,
        max_score=100,
        assessed_at=assessed_at,
        location_name=LOCATION_NAME,
        evidence_status=evidence_status,
        components=components,
        contributing_factors=contributing_factors,
        unavailable_sources=unavailable_sources,
        limitations=limitations,
        methodology=METHODLOGY,
        disclaimer=DISCLAIMER,
    )


async def _attempt(awaitable, expected_error: type[Exception]):
    try:
        return await awaitable
    except expected_error:
        return None


async def get_current_risk_assessment(
    noaa_client,
    weather_client,
    gis_client,
    now: datetime | None = None,
) -> RiskAssessment:
    observation, predictions, hourly, precipitation, alerts, road_impacts = await asyncio.gather(
        _attempt(get_current_observation(noaa_client), NOAAServiceError),
        _attempt(get_today_predictions(noaa_client), NOAAServiceError),
        _attempt(get_hourly_forecast(weather_client), NWSServiceError),
        _attempt(get_precipitation_forecast(weather_client), NWSServiceError),
        _attempt(get_active_alerts(weather_client), NWSServiceError),
        _attempt(get_road_impacts(gis_client), CharlestonGISServiceError),
    )
    return calculate_risk_assessment(
        observation=observation,
        predictions=predictions,
        hourly=hourly,
        precipitation=precipitation,
        alerts=alerts,
        road_impacts=road_impacts,
        now=now,
    )