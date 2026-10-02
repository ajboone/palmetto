from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.risk import EvidenceStatus, RiskLevel
from app.models.roads import RoadImpact
from app.models.tide import TideObservation, TidePrediction
from app.models.weather import PrecipitationForecast, WeatherAlert, WeatherPeriod
from app.services.risk import calculate_risk_assessment


CHARLESTON = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 2, 12, tzinfo=CHARLESTON)


def observation(value: float = 1.0) -> TideObservation:
    return TideObservation(
        station_id="8665530",
        station_name="Charleston, South Carolina",
        value=value,
        unit="feet",
        timestamp=NOW,
        datum="MLLW",
        source="NOAA CO-OPS test source",
    )


def prediction(
    height: float = 1.0, *, hours: float = 8, kind: str = "H"
) -> TidePrediction:
    return TidePrediction(
        station_id="8665530",
        station_name="Charleston, South Carolina",
        timestamp=NOW + timedelta(hours=hours),
        height=height,
        unit="feet",
        datum="MLLW",
        type=kind,
        source="NOAA CO-OPS prediction test source",
    )


def precipitation(amount: float = 0.0, unit: str = "mm") -> list[PrecipitationForecast]:
    return [
        PrecipitationForecast(
            start_time=NOW,
            end_time=NOW + timedelta(hours=6),
            amount=amount,
            unit=unit,
            source="NWS quantitative precipitation test source",
        )
    ]


def hourly(probability: float | None = None) -> list[WeatherPeriod]:
    return [
        WeatherPeriod(
            start_time=NOW,
            end_time=NOW + timedelta(hours=1),
            temperature=75,
            temperature_unit="F",
            precipitation_probability=probability,
            short_forecast="Test forecast",
            wind_speed=None,
            wind_direction=None,
            source="NWS hourly test source",
        )
    ]


def alert(
    event: str = "Flood Watch",
    *,
    severity: str | None = None,
    urgency: str | None = None,
    certainty: str | None = None,
) -> WeatherAlert:
    return WeatherAlert(
        id="test-alert",
        event=event,
        severity=severity,
        urgency=urgency,
        certainty=certainty,
        headline=None,
        description=None,
        instruction=None,
        effective=NOW,
        onset=NOW,
        expires=NOW + timedelta(hours=6),
        source="NWS alert test source",
    )


def road(
    object_id: int,
    *,
    reason: str | None = "CONSTRUCTION",
    description: str | None = "One lane closed",
) -> RoadImpact:
    return RoadImpact(
        id=str(object_id),
        road_name="King St",
        description=description,
        status="ACTIVE",
        impact_type="CLOSED",
        reason=reason,
        start_time=NOW,
        end_time=None,
        latitude=None,
        longitude=None,
        source="Charleston GIS test source",
        source_layer="ROAD CLOSURE (1)",
    )


def assess(
    *,
    water: TideObservation | None = None,
    tides: list[TidePrediction] | None = None,
    qpf: list[PrecipitationForecast] | None = None,
    hourly_periods: list[WeatherPeriod] | None = None,
    alerts: list[WeatherAlert] | None = None,
    roads: list[RoadImpact] | None = None,
):
    return calculate_risk_assessment(
        observation=observation() if water is None else water,
        predictions=[prediction()] if tides is None else tides,
        hourly=hourly() if hourly_periods is None else hourly_periods,
        precipitation=precipitation() if qpf is None else qpf,
        alerts=[] if alerts is None else alerts,
        road_impacts=[] if roads is None else roads,
        now=NOW,
    )


def component(assessment, name: str):
    return next(item for item in assessment.components if item.name == name)


def test_all_low_evidence_produces_low() -> None:
    result = assess()

    assert result.score == 1
    assert result.risk_level == RiskLevel.LOW
    assert result.evidence_status == EvidenceStatus.AVAILABLE


def test_moderate_evidence_has_deterministic_weighted_score() -> None:
    result = assess(
        water=observation(4.5),
        tides=[prediction(4.5, hours=4)],
        qpf=precipitation(12),
    )

    assert result.score == 23
    assert result.risk_level == RiskLevel.MODERATE
    assert [item.score for item in result.components] == [10, 8, 5, 0, 0]


def test_strong_evidence_produces_high() -> None:
    result = assess(
        water=observation(5.5),
        tides=[prediction(4.5, hours=1)],
        qpf=precipitation(25),
        alerts=[alert("Flood Warning")],
        roads=[road(1), road(2)],
    )

    assert result.score == 54
    assert result.risk_level == RiskLevel.HIGH


def test_extreme_combined_evidence_produces_severe_and_is_bounded() -> None:
    result = assess(
        water=observation(8),
        tides=[prediction(8, hours=1)],
        qpf=precipitation(100),
        alerts=[
            alert(
                "Flash Flood Warning",
                severity="Severe",
                urgency="Immediate",
                certainty="Observed",
            )
            for _ in range(4)
        ],
        roads=[road(index, reason="FLOOD", description="Water over roadway") for index in range(10)],
    )

    assert result.score == 100
    assert result.risk_level == RiskLevel.SEVERE
    assert result.score <= result.max_score
    assert all(item.score is None or item.score <= item.max_score for item in result.components)


def test_imminent_high_tide_scores_more_than_distant_high_tide() -> None:
    imminent = assess(tides=[prediction(4.5, hours=1)])
    distant = assess(tides=[prediction(4.5, hours=8)])

    assert component(imminent, "tide").score == 10
    assert component(distant, "tide").score == 6


def test_stale_water_level_is_visible_but_not_scored_as_current() -> None:
    stale_observation = observation()
    stale_observation.timestamp = NOW - timedelta(hours=4)

    result = assess(water=stale_observation)
    water = component(result, "water_level")

    assert water.score is None
    assert water.evidence_status == EvidenceStatus.PARTIAL
    assert water.observed_values["age_hours"] == 4
    assert SOURCE_WATER in result.unavailable_sources
    assert result.risk_level is None


def test_quantitative_precipitation_amount_is_scored_and_converted_by_unit() -> None:
    result_mm = assess(qpf=precipitation(25, "mm"))
    result_inches = assess(qpf=precipitation(25 / 25.4, "in"))

    assert component(result_mm, "precipitation").score == 10
    assert component(result_inches, "precipitation").score == 10
    assert "25 mm" in component(result_mm, "precipitation").explanation


def test_probability_is_not_converted_into_rainfall_amount() -> None:
    result = assess(qpf=[], hourly_periods=hourly(90))
    precipitation_component = component(result, "precipitation")

    assert precipitation_component.score == 5
    assert precipitation_component.evidence_status == EvidenceStatus.PARTIAL
    assert precipitation_component.observed_values == {
        "maximum_precipitation_probability": 90
    }
    assert "not treated as rainfall amount" in precipitation_component.explanation
    assert "NWS quantitative precipitation" in result.unavailable_sources


def test_flood_alert_contributes_but_unrelated_alert_does_not() -> None:
    flood = assess(alerts=[alert("Coastal Flood Advisory", severity="Minor")])
    unrelated = assess(
        alerts=[alert("Severe Thunderstorm Warning", severity="Severe", urgency="Immediate")]
    )

    assert component(flood, "weather_alerts").score == 6
    assert component(unrelated, "weather_alerts").score == 0


def test_road_impacts_are_counted_and_flood_causation_is_not_assumed() -> None:
    generic = assess(roads=[road(1), road(2)])
    flood_marked = assess(roads=[road(3, reason="FLOOD", description="Water over roadway")])

    assert component(generic, "road_impacts").score == 4
    assert component(generic, "road_impacts").observed_values["explicit_flood_related_count"] == 0
    assert component(flood_marked, "road_impacts").score == 5
    assert component(flood_marked, "road_impacts").observed_values["explicit_flood_related_count"] == 1


def test_missing_noaa_data_is_explicit_and_withholds_category() -> None:
    result = calculate_risk_assessment(
        observation=None,
        predictions=None,
        hourly=hourly(),
        precipitation=precipitation(),
        alerts=[],
        road_impacts=[],
        now=NOW,
    )

    assert component(result, "water_level").evidence_status == EvidenceStatus.UNAVAILABLE
    assert component(result, "tide").evidence_status == EvidenceStatus.UNAVAILABLE
    assert SOURCE_WATER in result.unavailable_sources
    assert SOURCE_TIDES in result.unavailable_sources
    assert result.risk_level is None
    assert result.evidence_status == EvidenceStatus.PARTIAL


def test_missing_nws_data_is_explicit() -> None:
    result = calculate_risk_assessment(
        observation=observation(),
        predictions=[prediction()],
        hourly=None,
        precipitation=None,
        alerts=None,
        road_impacts=[],
        now=NOW,
    )

    assert component(result, "precipitation").evidence_status == EvidenceStatus.UNAVAILABLE
    assert component(result, "weather_alerts").evidence_status == EvidenceStatus.UNAVAILABLE
    assert SOURCE_HOURLY in result.unavailable_sources
    assert SOURCE_PRECIPITATION in result.unavailable_sources
    assert SOURCE_ALERTS in result.unavailable_sources
    assert result.risk_level is None


def test_missing_gis_data_is_explicit() -> None:
    result = calculate_risk_assessment(
        observation=observation(),
        predictions=[prediction()],
        hourly=hourly(),
        precipitation=precipitation(),
        alerts=[],
        road_impacts=None,
        now=NOW,
    )

    assert component(result, "road_impacts").evidence_status == EvidenceStatus.UNAVAILABLE
    assert SOURCE_ROADS in result.unavailable_sources
    assert result.risk_level is None


def test_degraded_assessment_does_not_label_missing_evidence_low() -> None:
    result = calculate_risk_assessment(
        observation=None,
        predictions=[prediction()],
        hourly=hourly(90),
        precipitation=[],
        alerts=[],
        road_impacts=[],
        now=NOW,
    )

    assert result.score == 6
    assert result.max_score == 100
    assert result.evidence_status == EvidenceStatus.PARTIAL
    assert result.risk_level is None
    assert any("subtotal" in item for item in result.limitations)


def test_risk_endpoint_returns_normalized_assessment(client_factory) -> None:
    local_now = datetime.now(CHARLESTON)
    tide_at = local_now + timedelta(hours=8)
    qpf_start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=1)
    forecast_start = local_now + timedelta(minutes=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.tidesandcurrents.noaa.gov":
            product = request.url.params["product"]
            if product == "water_level":
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {"t": local_now.strftime("%Y-%m-%d %H:%M"), "v": "1.0"}
                        ]
                    },
                )
            return httpx.Response(
                200,
                json={
                    "predictions": [
                        {"t": tide_at.strftime("%Y-%m-%d %H:%M"), "v": "1.0", "type": "H"}
                    ]
                },
            )
        if request.url.host == "api.weather.gov":
            if request.url.path.startswith("/points/"):
                return httpx.Response(
                    200,
                    json={
                        "properties": {
                            "forecastHourly": "https://api.weather.gov/hourly",
                            "forecastGridData": "https://api.weather.gov/grid",
                        }
                    },
                )
            if request.url.path == "/hourly":
                return httpx.Response(
                    200,
                    json={
                        "properties": {
                            "periods": [
                                {
                                    "startTime": forecast_start.isoformat(),
                                    "endTime": (forecast_start + timedelta(hours=1)).isoformat(),
                                    "temperature": 75,
                                    "temperatureUnit": "F",
                                    "probabilityOfPrecipitation": {"value": 0},
                                    "shortForecast": "Clear",
                                }
                            ]
                        }
                    },
                )
            if request.url.path == "/grid":
                return httpx.Response(
                    200,
                    json={
                        "properties": {
                            "quantitativePrecipitation": {
                                "uom": "wmoUnit:mm",
                                "values": [
                                    {
                                        "validTime": f"{qpf_start.isoformat()}/PT6H",
                                        "value": 0,
                                    }
                                ],
                            }
                        }
                    },
                )
            if request.url.path == "/alerts/active":
                return httpx.Response(200, json={"features": []})
        if request.url.host == "gis.charleston-sc.gov":
            return httpx.Response(200, json={"features": []})
        raise AssertionError(f"Unexpected external URL: {request.url}")

    response = client_factory(handler).get("/api/risk/current")

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "LOW"
    assert body["score"] == 1
    assert body["evidence_status"] == "AVAILABLE"
    assert len(body["components"]) == 5
    assert body["components"][0]["source"] == "NOAA CO-OPS Data API (water_level)"
    assert "not official" in body["methodology"].lower()


SOURCE_WATER = "NOAA CO-OPS current water-level observations"
SOURCE_TIDES = "NOAA CO-OPS tide predictions"
SOURCE_HOURLY = "NWS hourly forecast"
SOURCE_PRECIPITATION = "NWS quantitative precipitation"
SOURCE_ALERTS = "NWS active weather alerts"
SOURCE_ROADS = "City of Charleston GIS road impacts"