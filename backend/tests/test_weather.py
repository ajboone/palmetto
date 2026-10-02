import httpx


POINT_PROPERTIES = {
    "forecastHourly": "https://api.weather.gov/gridpoints/CHS/87,77/forecast/hourly",
    "forecastGridData": "https://api.weather.gov/gridpoints/CHS/87,77",
}


def test_hourly_discovery_normalization_and_probability(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/points/"):
            assert "32.7765,-79.9311" in request.url.path
            assert request.headers["user-agent"] == (
                "PALMETTO flood decision intelligence prototype"
            )
            return httpx.Response(200, json={"properties": POINT_PROPERTIES})
        assert request.url == httpx.URL(POINT_PROPERTIES["forecastHourly"])
        return httpx.Response(
            200,
            json={
                "properties": {
                    "periods": [
                        {
                            "startTime": "2026-10-02T11:00:00-04:00",
                            "endTime": "2026-10-02T12:00:00-04:00",
                            "temperature": 83,
                            "temperatureUnit": "F",
                            "probabilityOfPrecipitation": {
                                "unitCode": "wmoUnit:percent",
                                "value": 25,
                            },
                            "shortForecast": "Rain showers",
                            "windSpeed": "8 mph",
                            "windDirection": "SE",
                        },
                        {
                            "startTime": "2026-10-02T12:00:00-04:00",
                            "endTime": "2026-10-02T13:00:00-04:00",
                            "temperature": 82,
                            "temperatureUnit": "F",
                            "probabilityOfPrecipitation": {
                                "unitCode": "wmoUnit:percent",
                                "value": None,
                            },
                            "shortForecast": "Cloudy",
                            "windSpeed": "7 mph",
                            "windDirection": "S",
                        },
                    ]
                }
            },
        )

    response = client_factory(handler).get("/api/weather/hourly")

    assert response.status_code == 200
    periods = response.json()
    assert len(periods) == 2
    assert periods[0]["temperature"] == 83
    assert periods[0]["temperature_unit"] == "F"
    assert periods[0]["precipitation_probability"] == 25
    assert periods[0]["wind_direction"] == "SE"
    assert periods[0]["source"] == POINT_PROPERTIES["forecastHourly"]
    assert periods[1]["precipitation_probability"] is None


def test_quantitative_precipitation_is_normalized(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/points/"):
            return httpx.Response(200, json={"properties": POINT_PROPERTIES})
        assert dict(request.url.params) == {"parameters": "quantitativePrecipitation"}
        return httpx.Response(
            200,
            json={
                "properties": {
                    "quantitativePrecipitation": {
                        "uom": "wmoUnit:mm",
                        "values": [
                            {
                                "validTime": "2026-10-02T06:00:00+00:00/PT6H",
                                "value": 7.62,
                            },
                            {
                                "validTime": "2026-10-02T12:00:00+00:00/PT6H",
                                "value": None,
                            },
                        ],
                    }
                }
            },
        )

    response = client_factory(handler).get("/api/weather/precipitation")

    assert response.status_code == 200
    forecasts = response.json()
    assert len(forecasts) == 1
    assert forecasts[0]["amount"] == 7.62
    assert forecasts[0]["unit"] == "mm"
    assert forecasts[0]["start_time"] == "2026-10-02T06:00:00Z"
    assert forecasts[0]["end_time"] == "2026-10-02T12:00:00Z"
    assert forecasts[0]["source"] == POINT_PROPERTIES["forecastGridData"]


def test_missing_quantitative_precipitation_returns_empty_list(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/points/"):
            return httpx.Response(200, json={"properties": POINT_PROPERTIES})
        return httpx.Response(200, json={"properties": {}})

    response = client_factory(handler).get("/api/weather/precipitation")

    assert response.status_code == 200
    assert response.json() == []


def test_active_alerts_are_normalized(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/points/"):
            return httpx.Response(200, json={"properties": POINT_PROPERTIES})
        assert request.url.path == "/alerts/active"
        assert dict(request.url.params) == {"point": "32.7765,-79.9311"}
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "id": "https://api.weather.gov/alerts/urn:test:1",
                        "properties": {
                            "id": "urn:test:1",
                            "event": "Flood Advisory",
                            "severity": "Minor",
                            "urgency": "Expected",
                            "certainty": "Likely",
                            "headline": "Flood Advisory issued",
                            "description": "Flooding is possible.",
                            "instruction": "Turn around, don't drown.",
                            "effective": "2026-10-02T12:00:00-04:00",
                            "onset": "2026-10-02T13:00:00-04:00",
                            "expires": "2026-10-02T18:00:00-04:00",
                        },
                    }
                ]
            },
        )

    response = client_factory(handler).get("/api/weather/alerts")

    assert response.status_code == 200
    alert = response.json()[0]
    assert alert["id"] == "urn:test:1"
    assert alert["event"] == "Flood Advisory"
    assert alert["severity"] == "Minor"
    assert alert["effective"] == "2026-10-02T12:00:00-04:00"
    assert alert["source"].endswith("?point=32.7765,-79.9311")


def test_no_active_alerts_returns_empty_list(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/points/"):
            return httpx.Response(200, json={"properties": POINT_PROPERTIES})
        return httpx.Response(200, json={"features": []})

    response = client_factory(handler).get("/api/weather/alerts")

    assert response.status_code == 200
    assert response.json() == []


def test_nws_upstream_failure_is_sanitized(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="private upstream details")

    response = client_factory(handler).get("/api/weather/hourly")

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to retrieve weather data from NWS."}
    assert "private upstream details" not in response.text