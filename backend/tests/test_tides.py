from datetime import datetime

import httpx


def test_current_tide_normalizes_latest_usable_observation(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        assert params["product"] == "water_level"
        assert params["station"] == "8665530"
        assert params["time_zone"] == "lst_ldt"
        assert params["units"] == "english"
        assert params["datum"] == "MLLW"
        return httpx.Response(
            200,
            json={
                "metadata": {"id": "8665530", "name": "Charleston"},
                "data": [
                    {"t": "2026-10-01 23:48", "v": "5.12"},
                    {"t": "2026-10-02 00:00", "v": "not-a-number"},
                    {"t": "2026-10-01 23:54", "v": "5.20"},
                ],
            },
        )

    response = client_factory(handler).get("/api/tides/current")

    assert response.status_code == 200
    assert response.json() == {
        "station_id": "8665530",
        "station_name": "Charleston, South Carolina",
        "value": 5.2,
        "unit": "feet",
        "timestamp": "2026-10-01T23:54:00",
        "datum": "MLLW",
        "source": "NOAA CO-OPS Data API (water_level)",
    }


def test_today_tides_are_normalized_and_chronological(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        assert params["product"] == "predictions"
        assert params["interval"] == "hilo"
        assert params["time_zone"] == "lst_ldt"
        assert params["units"] == "english"
        assert params["datum"] == "MLLW"
        assert params["begin_date"] == params["end_date"]
        return httpx.Response(
            200,
            json={
                "predictions": [
                    {"t": "2026-10-02 18:12", "v": "5.8", "type": "H"},
                    {"t": "2026-10-02 11:40", "v": "0.4", "type": "L"},
                ]
            },
        )

    response = client_factory(handler).get("/api/tides/today")

    assert response.status_code == 200
    predictions = response.json()
    assert [item["type"] for item in predictions] == ["L", "H"]
    assert [datetime.fromisoformat(item["timestamp"]) for item in predictions] == sorted(
        datetime.fromisoformat(item["timestamp"]) for item in predictions
    )
    assert all(item["station_id"] == "8665530" for item in predictions)
    assert all(item["unit"] == "feet" and item["datum"] == "MLLW" for item in predictions)
    assert all(item["source"] == "NOAA CO-OPS Data API (predictions)" for item in predictions)


def test_noaa_failure_returns_sanitized_gateway_error(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream secret detail")

    response = client_factory(handler).get("/api/tides/current")

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to retrieve tide data from NOAA."}
    assert "upstream secret detail" not in response.text


def test_malformed_noaa_response_returns_gateway_error(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    response = client_factory(handler).get("/api/tides/today")

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to retrieve tide data from NOAA."}